# AAV Longitudinal Closed-Loop Simulation (ROS 2)

This package implements a **closed-loop longitudinal speed & brake simulation** for an autonomous vehicle using ROS 2.  

The simulation focuses on the **inner loop** of control:

- **Input**: a preset sequence of desired speeds (standing in for GPS/navigation + obstacle decisions).
- **Controller**: uses simulated speed and IMU feedback to generate throttle & brake commands.
- **Plant**: a simple longitudinal vehicle dynamics model publishing simulated speed and IMU data.

---

## 1. Requirements

- Ubuntu 20.04 (recommended for ROS 2 Foxy)
- ROS 2 **Foxy** desktop installed

Core dependencies are standard ROS 2 messages:

- `rclpy`
- `std_msgs`
- `geometry_msgs`
- `sensor_msgs`

---

## 2. Workspace setup

If you don’t already have a ROS 2 workspace:

```bash
mkdir -p ~/aav_ws/src
cd ~/aav_ws/src


---

## 3. Build the project
In every new terminal before building or running:

source /opt/ros/foxy/setup.bash
cd ~/aav_ws
source install/setup.bash  # only exists after the first build
From the workspace root:
source /opt/ros/foxy/setup.bash
cd ~/aav_ws
colcon build
After a successful build:
source install/setup.bash

Speed profile set:
Default expected path:
~/aav_ws/src/aav_longitudinal_sim/config/speed_profile.txt
Create the folder and file if they don’t exist:
mkdir -p ~/aav_ws/src/aav_longitudinal_sim/config
nano ~/aav_ws/src/aav_longitudinal_sim/config/speed_profile.txt
Example contents:
0.0
0.3
0.6
1.0
1.0
0.6
0.3
0.0
0.0

Replace the src file with the github one

Running the closed-loop simulation:
Terminal 1 – Plant:
source /opt/ros/foxy/setup.bash
cd ~/aav_ws
source install/setup.bash

ros2 run aav_longitudinal_sim plant_node

Terminal 2 – Controller:
IMU&Speed Controller
source /opt/ros/foxy/setup.bash
cd ~/aav_ws
source install/setup.bash
ros2 run aav_longitudinal_sim imu_speed_controller

Terminal 3 – Speed profile
source /opt/ros/foxy/setup.bash
cd ~/aav_ws
source install/setup.bash

ros2 run aav_longitudinal_sim speed_profile_node

Monitoring the simulation
Optional extra terminal:
source /opt/ros/foxy/setup.bash
cd ~/aav_ws
source install/setup.bash

Check topics:
ros2 topic list

monitor command
ros2 topic echo /v_ref
ros2 topic echo /speed_sim
ros2 topic echo /imu_sim
ros2 topic echo /motor_cmd
