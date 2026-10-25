#pragma once

#include <optional>
#include <string>

#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
#include "nav_msgs/msg/path.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp"
#include "sensor_msgs/msg/nav_sat_fix.hpp"
#include "ackermann_msgs/msg/ackermann_drive_stamped.hpp"
#include "nav_msgs/msg/occupancy_grid.hpp"
#include "std_msgs/msg/bool.hpp"

#include "local_path_generator_cpp/osrm_models.hpp"

namespace local_path_generator_cpp
{

class LocalPathGeneratorNode : public rclcpp::Node
{
public:
  LocalPathGeneratorNode();

private:
  void on_global_route_request(const std_msgs::msg::String::SharedPtr msg);
  void on_current_path_request(const std_msgs::msg::String::SharedPtr msg);
  void on_current_dspeed_request(const std_msgs::msg::String::SharedPtr msg);
  void on_current_turn_request(const std_msgs::msg::String::SharedPtr msg);
  void on_gps_update(const sensor_msgs::msg::NavSatFix::SharedPtr msg);
  void on_emergency_stop(const std_msgs::msg::Bool::SharedPtr msg);
  void on_local_costmap(const nav_msgs::msg::OccupancyGrid::SharedPtr msg);

  double estimate_front_obstacle_distance(
    const nav_msgs::msg::OccupancyGrid & grid) const;

  double compute_speed_scale(double front_distance) const;

  void publish_ackermann(double turning_angle_rad, double dspeed_mps);

  bool parse_request(const std::string & raw, PointLL & coordinate, int & leg_index) const;
  

  nav_msgs::msg::Path build_remaining_path(
    const PointLL & current_coordinate,
    int leg_index,
    const StepMatchResult & match) const;

  SpeedEvalResult evaluate_speed(
    const PointLL & current_coordinate,
    int leg_index,
    const StepMatchResult & match) const;

  std::optional<OSRMGlobalRoute> global_route_;
  int current_leg_index_ = -1;
  std::optional<int> current_step_index_;

  std::optional<PointLL> prev_gps_coordinate_;
  std::optional<double> prev_heading_deg_;

  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr global_route_sub_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr current_path_sub_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr current_dspeed_sub_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr current_turn_sub_;
  rclcpp::Subscription<sensor_msgs::msg::NavSatFix>::SharedPtr gps_sub_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr emergency_stop_sub_;
  rclcpp::Subscription<nav_msgs::msg::OccupancyGrid>::SharedPtr local_costmap_sub_;

  bool emergency_stop_active_ = false;
  nav_msgs::msg::OccupancyGrid::SharedPtr latest_costmap_;

  double safety_vehicle_width_ = 1.4;
  double safety_corridor_padding_ = 0.4;
  double safety_min_safe_distance_ = 0.55;
  int safety_cost_threshold_ = 50;
  double safety_max_forward_distance_ = 8.0;

  rclcpp::Publisher<ackermann_msgs::msg::AckermannDriveStamped>::SharedPtr ackermann_pub_;
  rclcpp::Publisher<nav_msgs::msg::Path>::SharedPtr current_path_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr current_dspeed_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr current_turn_pub_;
  
};

}  // namespace local_path_generator_cpp