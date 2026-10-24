cmake_minimum_required(VERSION 3.0)
project(brake_test)

find_package(gazebo REQUIRED)

include_directories(${GAZEBO_INCLUDE_DIRS})
link_directories(${GAZEBO_LIBRARY_DIRS})
add_definitions(${GAZEBO_CXX_FLAGS})

add_library(brake_controller SHARED brake_controller.cc)
target_link_libraries(brake_controller ${GAZEBO_LIBRARIES})

add_library(joint_state_plugin SHARED joint_state_plugin.cc)
target_link_libraries(joint_state_plugin ${GAZEBO_LIBRARIES})

