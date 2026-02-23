cmake_minimum_required(VERSION 3.8)
project(yahboom_imu_cpp)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)

include_directories(include)

# Fix typo: scr -> src
add_library(serial_port src/serial_port.cpp)

# Add the executable (was missing entirely)
add_executable(imu_node src/imu_node.cpp)
target_link_libraries(imu_node serial_port)
ament_target_dependencies(imu_node rclcpp sensor_msgs geometry_msgs)

# Install so ros2 run can find it
install(TARGETS imu_node
  DESTINATION lib/${PROJECT_NAME}
)

install (DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
