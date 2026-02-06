cmake_minimum_required(VERSION 3.8)
project(qnx)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)

# Build executable
add_executable(qnx
  src/test_Sub.cpp
)

ament_target_dependencies(qnx
  rclcpp
  sensor_msgs
)

# Install
install(TARGETS
  qnx
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()

