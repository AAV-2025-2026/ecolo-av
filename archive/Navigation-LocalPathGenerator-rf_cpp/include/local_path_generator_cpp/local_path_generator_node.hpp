#pragma once

#include <optional>
#include <string>

#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
#include "nav_msgs/msg/path.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp"

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

  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr global_route_sub_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr current_path_sub_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr current_dspeed_sub_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr current_turn_sub_;

  rclcpp::Publisher<nav_msgs::msg::Path>::SharedPtr current_path_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr current_dspeed_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr current_turn_pub_;
};

}  // namespace local_path_generator_cpp