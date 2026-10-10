cmake_minimum_required(VERSION 3.8)
project(aav_description)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

install(DIRECTORY config launch rviz urdf
  DESTINATION share/${PROJECT_NAME})

# aav_description.vehicle: lets launch files read config/vehicle.yaml.
ament_python_install_package(${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_vehicle test/test_vehicle.py)
endif()

ament_package()
