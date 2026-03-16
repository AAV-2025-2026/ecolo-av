#include "local_path_generator_cpp/local_path_generator_node.hpp"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <optional>
#include <sstream>
#include <string>
#include <vector>

#include "geometry_msgs/msg/pose_stamped.hpp"
#include "local_path_generator_cpp/osrm_reader_service.hpp"
#include "local_path_generator_cpp/path_service.hpp"
#include "local_path_generator_cpp/speed_planner.hpp"

namespace local_path_generator_cpp
{

struct TurnEvalResult
{
  bool found = false;
  int segment_index = -1;
  int target_geom_index = -1;
  double target_heading_deg = 0.0;
  double turn_deg = 0.0;
};

bool parse_turn_request(
  const std::string & raw,
  PointLL & coordinate,
  int & leg_index,
  double & current_heading_deg);

TurnEvalResult evaluate_turn_angle(
  const PointLL & current_coordinate,
  const OSRMStep & step,
  int segment_index,
  double current_heading_deg,
  int lookahead_points);

namespace
{

double deg2rad(double deg)
{
  return deg * M_PI / 180.0;
}

double rad2deg(double rad)
{
  return rad * 180.0 / M_PI;
}

double compute_heading_deg_between_points(const PointLL & from, const PointLL & to)
{
  const auto xy = to_xy(to.lon, to.lat, from.lon, from.lat);
  return rad2deg(std::atan2(xy.y, xy.x));
}

}  // namespace

LocalPathGeneratorNode::LocalPathGeneratorNode()
: Node("local_path_generator")
{
  emergency_stop_sub_ = this->create_subscription<std_msgs::msg::Bool>(
    "/emergency_stop", 10,
    std::bind(&LocalPathGeneratorNode::on_emergency_stop, this, std::placeholders::_1));

  local_costmap_sub_ = this->create_subscription<nav_msgs::msg::OccupancyGrid>(
    "/local_costmap", 10,
    std::bind(&LocalPathGeneratorNode::on_local_costmap, this, std::placeholders::_1));

  ackermann_pub_ =
    create_publisher<ackermann_msgs::msg::AckermannDriveStamped>(
      "/local_mapping_ackermann", 10);

  gps_sub_ =
    create_subscription<sensor_msgs::msg::NavSatFix>(
      "/gps",
      10,
      std::bind(&LocalPathGeneratorNode::on_gps_update, this, std::placeholders::_1));

  global_route_sub_ = this->create_subscription<std_msgs::msg::String>(
    "/global_route_request", 10,
    std::bind(&LocalPathGeneratorNode::on_global_route_request, this, std::placeholders::_1));

  current_path_sub_ = this->create_subscription<std_msgs::msg::String>(
    "/current_path_request", 10,
    std::bind(&LocalPathGeneratorNode::on_current_path_request, this, std::placeholders::_1));

  current_dspeed_sub_ = this->create_subscription<std_msgs::msg::String>(
    "/current_dspeed_request", 10,
    std::bind(&LocalPathGeneratorNode::on_current_dspeed_request, this, std::placeholders::_1));

  current_turn_sub_ = this->create_subscription<std_msgs::msg::String>(
    "/current_turn_request", 10,
    std::bind(&LocalPathGeneratorNode::on_current_turn_request, this, std::placeholders::_1));

  current_path_pub_ = this->create_publisher<nav_msgs::msg::Path>("/current_path", 10);
  current_dspeed_pub_ = this->create_publisher<std_msgs::msg::String>("/current_dspeed", 10);
  current_turn_pub_ = this->create_publisher<std_msgs::msg::String>("/current_turn", 10);

  RCLCPP_INFO(this->get_logger(), "LocalPathGeneratorNode initialized.");
}

double LocalPathGeneratorNode::compute_speed_scale(double front_distance) const
{
  if (!std::isfinite(front_distance)) {
    return 1.0;
  }

  if (front_distance <= 0.0) {
    return 0.0;
  }

  const double scale = front_distance / safety_min_safe_distance_;
  return std::clamp(scale, 0.0, 1.0);
}

void LocalPathGeneratorNode::on_emergency_stop(
  const std_msgs::msg::Bool::SharedPtr msg)
{
  emergency_stop_active_ = msg->data;
}

void LocalPathGeneratorNode::on_local_costmap(
  const nav_msgs::msg::OccupancyGrid::SharedPtr msg)
{
  latest_costmap_ = msg;
}

void LocalPathGeneratorNode::on_gps_update(
  const sensor_msgs::msg::NavSatFix::SharedPtr msg)
{
  if (!global_route_.has_value() || global_route_->routes.empty()) {
    return;
  }

  PointLL current;
  current.lat = msg->latitude;
  current.lon = msg->longitude;

  int leg_index = current_leg_index_;
  if (leg_index < 0) {
    leg_index = 0;
  }

  const auto & route = global_route_->routes[0];
  if (leg_index < 0 || leg_index >= static_cast<int>(route.legs.size())) {
    return;
  }

  const auto & steps = route.legs[leg_index].steps;
  if (steps.empty()) {
    return;
  }

  const auto match = get_current_step_by_coordinate(current, steps, current_step_index_);
  if (!match.found) {
    prev_gps_coordinate_ = current;
    return;
  }

  current_leg_index_ = leg_index;
  current_step_index_ = match.step_index;

  const auto speed = evaluate_speed(current, leg_index, match);

  double current_heading_deg = 0.0;
  bool heading_available = false;

  if (prev_gps_coordinate_.has_value()) {
    const auto delta_xy = to_xy(
      current.lon,
      current.lat,
      prev_gps_coordinate_->lon,
      prev_gps_coordinate_->lat);

    const double move_dist = std::hypot(delta_xy.x, delta_xy.y);
    if (move_dist > 0.3) {
      current_heading_deg =
        compute_heading_deg_between_points(*prev_gps_coordinate_, current);
      prev_heading_deg_ = current_heading_deg;
      heading_available = true;
    }
  }

  if (!heading_available && prev_heading_deg_.has_value()) {
    current_heading_deg = *prev_heading_deg_;
    heading_available = true;
  }

  if (!heading_available) {
    prev_gps_coordinate_ = current;
    return;
  }

  if (match.step_index < 0 || match.step_index >= static_cast<int>(steps.size())) {
    prev_gps_coordinate_ = current;
    return;
  }

  const auto & step = steps[match.step_index];
  const auto turn = evaluate_turn_angle(
    current,
    step,
    match.segment_index,
    current_heading_deg,
    3);

  if (!turn.found) {
    prev_gps_coordinate_ = current;
    return;
  }

  const double steering_angle_rad = deg2rad(turn.turn_deg);

  publish_ackermann(steering_angle_rad, speed.target_speed_mps);

  prev_gps_coordinate_ = current;
}

double LocalPathGeneratorNode::estimate_front_obstacle_distance(
  const nav_msgs::msg::OccupancyGrid & grid) const
{
  const auto & info = grid.info;
  if (info.width == 0 || info.height == 0 || grid.data.empty()) {
    return std::numeric_limits<double>::infinity();
  }

  const double corridor_half_width =
    (safety_vehicle_width_ + safety_corridor_padding_) * 0.5;

  double min_front_distance = std::numeric_limits<double>::infinity();

  const double origin_x = info.origin.position.x;
  const double origin_y = info.origin.position.y;
  const double resolution = info.resolution;

  for (unsigned int row = 0; row < info.height; ++row) {
    for (unsigned int col = 0; col < info.width; ++col) {
      const std::size_t idx = static_cast<std::size_t>(row) * info.width + col;
      if (idx >= grid.data.size()) {
        continue;
      }

      const int8_t cost = grid.data[idx];
      if (cost < safety_cost_threshold_) {
        continue;
      }

      const double x = origin_x + (static_cast<double>(col) + 0.5) * resolution;
      const double y = origin_y + (static_cast<double>(row) + 0.5) * resolution;

      if (x <= 0.0 || x > safety_max_forward_distance_) {
        continue;
      }

      if (std::fabs(y) > corridor_half_width) {
        continue;
      }

      if (x < min_front_distance) {
        min_front_distance = x;
      }
    }
  }

  return min_front_distance;
}

void LocalPathGeneratorNode::publish_ackermann(
  double turning_angle_rad,
  double dspeed_mps)
{
  double final_speed = dspeed_mps;

  if (emergency_stop_active_) {
    final_speed = 0.0;
  } else if (latest_costmap_) {
    const double front_distance = estimate_front_obstacle_distance(*latest_costmap_);
    const double scale = compute_speed_scale(front_distance);
    final_speed = dspeed_mps * scale;

    RCLCPP_INFO_THROTTLE(
      this->get_logger(), *this->get_clock(), 1000,
      "[/local_mapping_ackermann] dspeed=%.3f front_dist=%.3f scale=%.3f final_speed=%.3f",
      dspeed_mps, front_distance, scale, final_speed);
  }

  ackermann_msgs::msg::AckermannDriveStamped msg;
  msg.header.stamp = this->now();
  msg.header.frame_id = "map";

  msg.drive.steering_angle = turning_angle_rad;
  msg.drive.steering_angle_velocity = 0.0;
  msg.drive.speed = final_speed;
  msg.drive.acceleration = 0.0;
  msg.drive.jerk = 0.0;

  ackermann_pub_->publish(msg);
}

bool LocalPathGeneratorNode::parse_request(
  const std::string & raw, PointLL & coordinate, int & leg_index) const
{
  std::stringstream ss(raw);
  std::string item;
  std::vector<std::string> parts;
  while (std::getline(ss, item, ',')) {
    parts.push_back(item);
  }

  if (parts.size() != 3) {
    return false;
  }

  try {
    coordinate.lon = std::stod(parts[0]);
    coordinate.lat = std::stod(parts[1]);
    leg_index = std::stoi(parts[2]);
  } catch (...) {
    return false;
  }

  return true;
}

void LocalPathGeneratorNode::on_global_route_request(const std_msgs::msg::String::SharedPtr msg)
{
  RCLCPP_INFO(this->get_logger(), "[/global_route_request] received route JSON.");
  try {
    global_route_ = load_osrm_route(msg->data);
    current_leg_index_ = -1;
    current_step_index_.reset();
    prev_gps_coordinate_.reset();
    prev_heading_deg_.reset();
    RCLCPP_INFO(this->get_logger(), "[/global_route_request] success build route model.");
  } catch (const std::exception & e) {
    RCLCPP_ERROR(this->get_logger(), "[/global_route_request] failed to parse route JSON: %s", e.what());
    RCLCPP_WARN(this->get_logger(), "[/global_route_request] Keeping old route. Driving continues.");
  }
}

nav_msgs::msg::Path LocalPathGeneratorNode::build_remaining_path(
  const PointLL & current_coordinate, int leg_index, const StepMatchResult & match) const
{
  nav_msgs::msg::Path path;
  path.header.stamp = this->now();
  path.header.frame_id = "map";

  if (!global_route_.has_value() || global_route_->routes.empty()) {
    return path;
  }

  const auto & route = global_route_->routes[0];
  if (leg_index < 0 || leg_index >= static_cast<int>(route.legs.size())) {
    return path;
  }

  const auto & leg = route.legs[leg_index];
  const auto ref = current_coordinate;

  geometry_msgs::msg::PoseStamped first_pose;
  first_pose.header = path.header;
  first_pose.pose.position.x = match.closest_point.x;
  first_pose.pose.position.y = match.closest_point.y;
  first_pose.pose.position.z = 0.0;
  first_pose.pose.orientation.w = 1.0;
  path.poses.push_back(first_pose);

  for (int step_i = match.step_index; step_i < static_cast<int>(leg.steps.size()); ++step_i) {
    const auto & step = leg.steps[step_i];
    if (step.geometry.empty()) {
      continue;
    }

    int start_geom = 0;
    if (step_i == match.step_index) {
      start_geom = std::min(match.segment_index + 1, static_cast<int>(step.geometry.size()) - 1);
    }

    for (int gi = start_geom; gi < static_cast<int>(step.geometry.size()); ++gi) {
      const auto & p = step.geometry[gi];
      const auto xy = to_xy(p.lon, p.lat, ref.lon, ref.lat);

      geometry_msgs::msg::PoseStamped pose;
      pose.header = path.header;
      pose.pose.position.x = xy.x;
      pose.pose.position.y = xy.y;
      pose.pose.position.z = 0.0;
      pose.pose.orientation.w = 1.0;
      path.poses.push_back(pose);
    }
  }

  return path;
}

SpeedEvalResult LocalPathGeneratorNode::evaluate_speed(
  const PointLL & current_coordinate, int leg_index, const StepMatchResult & match) const
{
  (void)current_coordinate;
  SpeedEvalResult out;
  out.leg_index = leg_index;
  out.step_index = match.step_index;
  out.segment_index = match.segment_index;
  out.t = match.t;
  out.distance = match.distance;

  if (!global_route_.has_value() || global_route_->routes.empty()) {
    return out;
  }

  const auto & route = global_route_->routes[0];
  if (leg_index < 0 || leg_index >= static_cast<int>(route.legs.size())) {
    return out;
  }

  const auto & leg = route.legs[leg_index];
  if (match.step_index < 0 || match.step_index >= static_cast<int>(leg.steps.size())) {
    return out;
  }

  const auto & step = leg.steps[match.step_index];
  out.target_speed_mps = evaluate_target_speed(step, match.segment_index, match.t);
  out.target_speed_kmph = out.target_speed_mps * 3.6;
  return out;
}

void LocalPathGeneratorNode::on_current_path_request(const std_msgs::msg::String::SharedPtr msg)
{
  if (!global_route_.has_value() || global_route_->routes.empty()) {
    RCLCPP_WARN(this->get_logger(), "[/current_path_request] No global route yet.");
    return;
  }

  PointLL coordinate;
  int leg_index = -1;
  if (!parse_request(msg->data, coordinate, leg_index)) {
    RCLCPP_ERROR(this->get_logger(), "[/current_path_request] invalid message");
    return;
  }

  const auto & route = global_route_->routes[0];
  if (leg_index < 0 || leg_index >= static_cast<int>(route.legs.size())) {
    RCLCPP_ERROR(this->get_logger(), "[/current_path_request] invalid leg index: %d", leg_index);
    return;
  }

  if (current_leg_index_ != leg_index) {
    current_leg_index_ = leg_index;
    current_step_index_.reset();
  }

  const auto & steps = route.legs[leg_index].steps;
  const auto match = get_current_step_by_coordinate(coordinate, steps, current_step_index_);
  if (!match.found) {
    RCLCPP_WARN(this->get_logger(), "[/current_path_request] Not on route or too far.");
    return;
  }

  current_step_index_ = match.step_index;
  const auto path = build_remaining_path(coordinate, leg_index, match);
  current_path_pub_->publish(path);

  const auto speed = evaluate_speed(coordinate, leg_index, match);
  RCLCPP_INFO(
    this->get_logger(),
    "[/current_path_request] step=%d seg=%d t=%.3f dist=%.3f target=%.2f m/s",
    match.step_index, match.segment_index, match.t, match.distance, speed.target_speed_mps);
}

void LocalPathGeneratorNode::on_current_dspeed_request(const std_msgs::msg::String::SharedPtr msg)
{
  if (!global_route_.has_value() || global_route_->routes.empty()) {
    RCLCPP_WARN(this->get_logger(), "[/current_dspeed_request] No global route yet.");
    return;
  }

  PointLL coordinate;
  int leg_index = -1;
  if (!parse_request(msg->data, coordinate, leg_index)) {
    RCLCPP_ERROR(this->get_logger(), "[/current_dspeed_request] invalid message");
    return;
  }

  const auto & route = global_route_->routes[0];
  if (leg_index < 0 || leg_index >= static_cast<int>(route.legs.size())) {
    RCLCPP_ERROR(this->get_logger(), "[/current_dspeed_request] invalid leg index: %d", leg_index);
    return;
  }

  if (current_leg_index_ != leg_index) {
    current_leg_index_ = leg_index;
    current_step_index_.reset();
  }

  const auto & steps = route.legs[leg_index].steps;
  const auto match = get_current_step_by_coordinate(coordinate, steps, current_step_index_);
  if (!match.found) {
    RCLCPP_WARN(this->get_logger(), "[/current_dspeed_request] Not on route or too far.");
    return;
  }

  current_step_index_ = match.step_index;
  const auto speed = evaluate_speed(coordinate, leg_index, match);

  std_msgs::msg::String out;
  std::ostringstream oss;
  oss << std::fixed << std::setprecision(3)
      << speed.target_speed_mps << ","
      << speed.target_speed_kmph << ","
      << speed.leg_index << ","
      << speed.step_index << ","
      << speed.segment_index << ","
      << std::setprecision(4) << speed.t << ","
      << std::setprecision(3) << speed.distance;
  out.data = oss.str();
  current_dspeed_pub_->publish(out);

  RCLCPP_INFO(
    this->get_logger(),
    "[/current_dspeed_request] step=%d seg=%d t=%.3f dist=%.3f target=%.2f m/s (%.2f km/h)",
    match.step_index, match.segment_index, match.t, match.distance,
    speed.target_speed_mps, speed.target_speed_kmph);
}

void LocalPathGeneratorNode::on_current_turn_request(const std_msgs::msg::String::SharedPtr msg)
{
  if (!global_route_.has_value() || global_route_->routes.empty()) {
    RCLCPP_WARN(this->get_logger(), "[/current_turn_request] No global route yet.");
    return;
  }

  PointLL coordinate;
  int leg_index = -1;
  double current_heading_deg = 0.0;

  if (!parse_turn_request(msg->data, coordinate, leg_index, current_heading_deg)) {
    RCLCPP_ERROR(this->get_logger(), "[/current_turn_request] invalid message");
    return;
  }

  const auto & route = global_route_->routes[0];
  if (leg_index < 0 || leg_index >= static_cast<int>(route.legs.size())) {
    RCLCPP_ERROR(this->get_logger(), "[/current_turn_request] invalid leg index: %d", leg_index);
    return;
  }

  if (current_leg_index_ != leg_index) {
    current_leg_index_ = leg_index;
    current_step_index_.reset();
  }

  const auto & steps = route.legs[leg_index].steps;
  const auto match = get_current_step_by_coordinate(coordinate, steps, current_step_index_);
  if (!match.found) {
    RCLCPP_WARN(this->get_logger(), "[/current_turn_request] Not on route or too far.");
    return;
  }

  current_step_index_ = match.step_index;

  if (match.step_index < 0 || match.step_index >= static_cast<int>(steps.size())) {
    RCLCPP_ERROR(this->get_logger(), "[/current_turn_request] invalid step index: %d", match.step_index);
    return;
  }

  const auto & step = steps[match.step_index];
  const auto turn = evaluate_turn_angle(
    coordinate, step, match.segment_index, current_heading_deg, 3);

  if (!turn.found) {
    RCLCPP_WARN(this->get_logger(), "[/current_turn_request] turn evaluate failed.");
    return;
  }

  std_msgs::msg::String out;
  std::ostringstream oss;
  oss << std::fixed << std::setprecision(3)
      << turn.turn_deg << ","
      << turn.target_heading_deg << ","
      << leg_index << ","
      << match.step_index << ","
      << match.segment_index << ","
      << turn.target_geom_index;
  out.data = oss.str();
  current_turn_pub_->publish(out);

  RCLCPP_INFO(
    this->get_logger(),
    "[/current_turn_request] step=%d seg=%d target_geom=%d turn=%.2f deg target_heading=%.2f deg",
    match.step_index, match.segment_index, turn.target_geom_index,
    turn.turn_deg, turn.target_heading_deg);
}

}  // namespace local_path_generator_cpp