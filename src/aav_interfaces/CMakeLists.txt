cmake_minimum_required(VERSION 3.10)
project(aav_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/VehicleStatus.msg"
  "msg/SensorSource.msg"
  "msg/DataSource.msg"
  "msg/ActuatorState.msg"
  "msg/WheelSpeeds.msg"
  "action/ScriptedDrive.action"
  DEPENDENCIES std_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
