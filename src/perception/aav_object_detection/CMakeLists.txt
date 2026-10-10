cmake_minimum_required(VERSION 3.10)
project(aav_object_detection)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)  # PCL 1.15 and rclcpp need C++17
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

cmake_policy(SET CMP0074 NEW)

# find dependencies
find_package(ament_cmake REQUIRED)
# uncomment the following section in order to fill in
# further dependencies manually.
find_package(rclcpp REQUIRED)
find_package(pcl_ros REQUIRED)
find_package(pcl_conversions REQUIRED)
find_package(PCL 1.12 REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(octomap REQUIRED)
find_package(backward_ros REQUIRED)

include_directories(${PCL_INCLUDE_DIRS} include)
link_directories(${PCL_LIBRARY_DIRS})
add_definitions(${PCL_DEFINITIONS})

# No style tests: inherited code, left as it came (tools/lint.sh says the same).

add_executable(filter_single_frame example/filter_single_frame.cpp)
add_executable(filter_multi_frames example/filter_multi_frames.cpp)
add_executable(dbscan example/dbscan.cpp)
add_executable(test_icp example/test_icp.cpp)

target_link_libraries(filter_single_frame
  ${Boost_SYSTEM_LIBRARY}
  ${PCL_LIBRARIES}
)
target_link_libraries(filter_multi_frames
  ${Boost_SYSTEM_LIBRARY}
  ${PCL_LIBRARIES}
)
target_link_libraries(dbscan
  ${Boost_SYSTEM_LIBRARY}
  ${PCL_LIBRARIES}
)
target_link_libraries(test_icp
  ${Boost_SYSTEM_LIBRARY}
  ${PCL_LIBRARIES}
)

ament_target_dependencies(filter_single_frame
rclcpp PCL pcl_conversions pcl_ros)
ament_target_dependencies(filter_multi_frames
rclcpp PCL pcl_conversions pcl_ros octomap visualization_msgs)
ament_target_dependencies(dbscan
rclcpp PCL pcl_conversions pcl_ros visualization_msgs)
ament_target_dependencies(test_icp
rclcpp PCL pcl_conversions pcl_ros octomap visualization_msgs)

install(TARGETS
  filter_single_frame
  filter_multi_frames
  dbscan
  test_icp
  DESTINATION lib/${PROJECT_NAME})

install(DIRECTORY
  launch rviz map include
  DESTINATION share/${PROJECT_NAME}/
)

ament_package()

