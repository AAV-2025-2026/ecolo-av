cmake_minimum_required(VERSION 3.8)
project(imu_bridge_qnx)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)

# Build executable
add_executable(imu_bridge_qnx_functionality
  src/imu_bridge_qnx_functionality.cpp
)

ament_target_dependencies(imu_bridge_qnx_functionality
  rclcpp
  sensor_msgs
)

# Install
install(TARGETS
  imu_bridge_qnx_functionality
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()