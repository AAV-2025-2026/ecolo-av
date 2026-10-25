cmake_minimum_required(VERSION 3.8)
project(lane_geometry)

find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(rclpy REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/LaneGeometry.msg"
  DEPENDENCIES std_msgs
)

install(PROGRAMS
  scripts/control_interface.py
  scripts/geometry_logger.py
  scripts/fake_lane_geometry_pub.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY launch msg
  DESTINATION share/${PROJECT_NAME}
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
