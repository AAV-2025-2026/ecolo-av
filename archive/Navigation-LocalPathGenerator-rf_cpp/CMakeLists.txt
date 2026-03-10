cmake_minimum_required(VERSION 3.8)
project(local_path_generator_cpp)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic -O2)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nlohmann_json REQUIRED)

add_executable(local_path_generator_node
  src/main.cpp
  src/local_path_generator_node.cpp
  src/path_service.cpp
  src/speed_planner.cpp
  src/osrm_reader_service.cpp
  src/turn_planner.cpp
)

target_include_directories(local_path_generator_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

target_compile_features(local_path_generator_node PUBLIC cxx_std_17)

ament_target_dependencies(local_path_generator_node
  rclcpp
  std_msgs
  nav_msgs
  geometry_msgs
)

target_link_libraries(local_path_generator_node
  nlohmann_json::nlohmann_json
)

install(TARGETS
  local_path_generator_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

ament_package()
