#include "rclcpp/rclcpp.hpp"
#include "local_path_generator_cpp/local_path_generator_node.hpp"

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<local_path_generator_cpp::LocalPathGeneratorNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
