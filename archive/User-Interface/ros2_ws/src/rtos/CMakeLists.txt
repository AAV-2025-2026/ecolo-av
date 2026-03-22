cmake_minimum_required(VERSION 3.8)
project(rtos)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)

# Susbcriber executable
add_executable(ui_rtos_sub
  src/ui_rtos_sub.cpp
)
ament_target_dependencies(ui_rtos_sub
  rclcpp
  sensor_msgs
)

# Publisher executable
add_executable(ui_rtos_pub
  src/ui_rtos_pub.cpp
)
ament_target_dependencies(ui_rtos_pub
  rclcpp
  sensor_msgs
)

install(TARGETS
  ui_rtos_sub
  ui_rtos_pub
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
