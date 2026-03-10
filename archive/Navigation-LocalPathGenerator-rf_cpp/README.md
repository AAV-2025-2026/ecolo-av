# local_path_generator_cpp

Complete C++ port of the original Python ROS2 local_path_generator package.

## Topics

Subscriptions:
- `/global_route_request` (`std_msgs/msg/String`) : full OSRM JSON
- `/current_path_request` (`std_msgs/msg/String`) : `"lon,lat,leg_index"`
- `/current_dspeed_request` (`std_msgs/msg/String`) : `"lon,lat,leg_index"`

Publications:
- `/current_path` (`nav_msgs/msg/Path`)
- `/current_dspeed` (`std_msgs/msg/String`) : `"mps,kmph,leg,step,segment,t,distance"`

## Build

```bash
source /opt/ros/jazzy/setup.bash
sudo apt install nlohmann-json3-dev
cd ~/ros2_ws
colcon build --packages-select local_path_generator_cpp
source install/setup.bash
ros2 run local_path_generator_cpp local_path_generator_node
```
