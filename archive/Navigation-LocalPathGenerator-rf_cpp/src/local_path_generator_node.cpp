#include "local_path_generator_cpp/local_path_generator_node.hpp"

#include <algorithm>
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

LocalPathGeneratorNode::LocalPathGeneratorNode()
: Node("local_path_generator")
{
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
    RCLCPP_ERROR(
      this->get_logger(),
      "[/current_turn_request] invalid message");
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