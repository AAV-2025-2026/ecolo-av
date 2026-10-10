cmake_minimum_required(VERSION 3.8)
project(aav_navigation)

find_package(ament_cmake REQUIRED)

install(DIRECTORY behavior_trees config launch maps
  DESTINATION share/${PROJECT_NAME})

ament_package()
