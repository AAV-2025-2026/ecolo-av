# Interfaces

Generated from `docs/interfaces.yaml` by `tools/gen_interfaces_md.py`; edit the YAML.
Check a running system against it with `tools/check_graph.py --profile <turtle|sim|car>`.

## Topics

| Topic | Type | Publishers | Subscribers | Must be live in | Notes |
|---|---|---|---|---|---|
| `/joy` | `sensor_msgs/msg/Joy` | `joy_node` | `teleop_twist_joy_node`, `joy_teleop` | - | Joystick axes and buttons, 20 Hz while held. |
| `/cmd_vel/joy` | `geometry_msgs/msg/TwistStamped` | `teleop_twist_joy_node` | `twist_mux` | - | Priority 100. Only while the deadman (trigger) is held. |
| `/cmd_vel/remote` | `geometry_msgs/msg/TwistStamped` | `teleop_twist_keyboard` | `twist_mux` | - | Priority 90. A person driving from a laptop - teleop_twist_keyboard (stamped:=true), the Foxglove teleop panel, or the HUD once ported. |
| `/cmd_vel/scripted` | `geometry_msgs/msg/TwistStamped` | `scripted_driver` | `twist_mux` | - | Priority 50. Only while a /scripted_drive goal runs. |
| `/cmd_vel/replay` | `geometry_msgs/msg/TwistStamped` | - | `twist_mux` | - | Priority 40. ros2 bag play of a recorded /cmd_vel (tools/replay_commands.sh). |
| `/cmd_vel/nav` | `geometry_msgs/msg/TwistStamped` | `velocity_smoother` | `twist_mux` | - | Priority 20. Nav2; from collision_monitor instead when it is enabled. |
| `/cmd_vel/ai` | `geometry_msgs/msg/TwistStamped` | - | `twist_mux` | - | Priority 10. Reserved for a learned driver. |
| `/estop` | `std_msgs/msg/Bool` | `joy_teleop` | `twist_mux`, `spine_bridge`, `legacy_uart_bridge` | - | true = stop. Lock on twist_mux (priority 255) and the backends brake at once. Cleared only by publishing false. |
| `/cmd_vel` | `geometry_msgs/msg/TwistStamped` | `twist_mux` | `ego` | turtle, sim, car | The one command ego obeys. v (m/s) and w (rad/s) in base_link. |
| `/ego/actuator_cmd` | `ackermann_msgs/msg/AckermannDriveStamped` | `ego` | `spine_bridge`, `legacy_uart_bridge`, `turtlesim_adapter`, `gazebo_adapter`, `carla_adapter` | turtle, sim, car | 50 Hz, always. speed (m/s), steering_angle (rad, + left), acceleration, steering_angle_velocity. Exactly one backend runs. |
| `/vehicle/odom` | `nav_msgs/msg/Odometry` | `spine_bridge`, `encoder_udp`, `turtlesim_adapter`, `gazebo_adapter`, `carla_adapter` | `ekf_local`, `ekf_global` | turtle, sim, car, replay | Twist only (vx, vy = 0, vyaw) in base_link, with covariances; pose covariance 1e3 (not measured). |
| `/vehicle/status` | `aav_interfaces/msg/VehicleStatus` | `spine_bridge`, `gazebo_adapter` | - | sim | Mode, armed, e-stop, measured speed and steering, actuator levels, fault bits. For the HUD and Foxglove. |
| `/vehicle/joint_states` | `sensor_msgs/msg/JointState` | `spine_bridge` | `joint_state_publisher` | - | Measured front steering joint angles, merged into /joint_states. |
| `/joint_states` | `sensor_msgs/msg/JointState` | `joint_state_publisher`, `gz_bridge` | `robot_state_publisher` | turtle, sim, car, replay |  |
| `/to_can_bus` | `can_msgs/msg/Frame` | `spine_bridge` | `socket_can_sender` | - | DRIVE_CMD 0x100 at 50 Hz, ESTOP_CMD 0x010 at 10 Hz (firmware/can/aav.dbc). |
| `/from_can_bus` | `can_msgs/msg/Frame` | `socket_can_receiver` | `spine_bridge` | - | VEHICLE_FEEDBACK 0x180, VEHICLE_STATUS 0x181. |
| `/imu/data_raw` | `sensor_msgs/msg/Imu` | `imu_node`, `gazebo_adapter` | `imu_filter_madgwick` | sim, car, replay | Gyro and accelerometer in imu_link, with covariances; no orientation. |
| `/imu/mag` | `sensor_msgs/msg/MagneticField` | `imu_node` | - | - | Raw counts, not tesla yet; unused. |
| `/imu/data` | `sensor_msgs/msg/Imu` | `imu_filter_madgwick` | `ekf_local`, `ekf_global` | sim, car, replay | Adds a relative orientation (no magnetometer). The EKFs fuse the yaw rate only. |
| `/gps/fix` | `sensor_msgs/msg/NavSatFix` | `ublox_nav_sat_fix_hp`, `gazebo_adapter` | `navsat_transform` | sim, car, replay | Lat/lon of the antenna (gps_link). ublox publishes it best-effort (SensorDataQoS). |
| `/radar/points` | `sensor_msgs/msg/PointCloud2` | `radar` | - | - | Perception phase. Will feed the local costmap's obstacle layer and collision_monitor. |
| `/battery_status` | `sensor_msgs/msg/BatteryState` | `battery_monitor` | - | - |  |
| `/odometry/local` | `nav_msgs/msg/Odometry` | `ekf_local` | `controller_server`, `bt_navigator`, `scripted_driver` | turtle, sim, car, replay | odom frame. Smooth; drifts. |
| `/odometry/global` | `nav_msgs/msg/Odometry` | `ekf_global` | `navsat_transform` | sim, car, replay | map frame. Includes GPS; can jump. |
| `/odometry/gps` | `nav_msgs/msg/Odometry` | `navsat_transform` | `ekf_global` | sim, car, replay | Each GPS fix as a map-frame position of base_link (antenna offset removed). |
| `/gps/filtered` | `sensor_msgs/msg/NavSatFix` | `navsat_transform` | - | sim, car, replay | The global EKF's position as lat/lon, for maps in the HUD or Foxglove. |
| `/map` | `nav_msgs/msg/OccupancyGrid` | `map_server` | `global_costmap`, `local_costmap` | sim | Transient local (latched). From aav_navigation/maps. |
| `/goal_pose` | `geometry_msgs/msg/PoseStamped` | `rviz2` | `bt_navigator` | - | RViz "2D Goal Pose" starts a navigate_to_pose. |
| `/plan` | `nav_msgs/msg/Path` | `planner_server` | - | - | The planned path, for RViz/Foxglove. |
| `/tf` | `tf2_msgs/msg/TFMessage` | `ekf_local`, `ekf_global`, `robot_state_publisher` | - | turtle, sim, car, replay | map -> odom (ekf_global), odom -> base_link (ekf_local), moving joints (robot_state_publisher). |
| `/tf_static` | `tf2_msgs/msg/TFMessage` | `robot_state_publisher` | - | turtle, sim, car, replay | base_link -> chassis and every sensor frame, from vehicle.yaml through the URDF. |
| `/robot_description` | `std_msgs/msg/String` | `robot_state_publisher` | - | turtle, sim, car, replay |  |
| `/clock` | `rosgraph_msgs/msg/Clock` | `gz_bridge` | - | sim, replay | Simulation time; every node runs with use_sim_time:=true in sim and replay. |

## Services

| Name | Type | Server | Notes |
|---|---|---|---|
| `/spine/arm` | `std_srvs/srv/SetBool` | `spine_bridge` | The spine ignores drive commands until armed; refused while /estop is true. |
| `/fromLL` | `robot_localization/srv/FromLL` | `navsat_transform` | Lat/lon -> map x, y. Nav2's follow_gps_waypoints calls it. |
| `/toLL` | `robot_localization/srv/ToLL` | `navsat_transform` |  |
| `/datum` | `robot_localization/srv/SetDatum` | `navsat_transform` | Move the map origin (normally set once from navsat.yaml). |
| `/ekf_local/set_pose` | `robot_localization/srv/SetPose` | `ekf_local` |  |
| `/ekf_global/set_pose` | `robot_localization/srv/SetPose` | `ekf_global` | Re-seed the start pose by hand (heading!). |

## Actions

| Name | Type | Server | Notes |
|---|---|---|---|
| `/scripted_drive` | `aav_interfaces/action/ScriptedDrive` | `scripted_driver` | Drive a speed profile (accelerate, hold for a time or distance, stop). Phase 1. |
| `/navigate_to_pose` | `nav2_msgs/action/NavigateToPose` | `bt_navigator` | Drive to one map-frame pose. |
| `/navigate_through_poses` | `nav2_msgs/action/NavigateThroughPoses` | `bt_navigator` |  |
| `/follow_waypoints` | `nav2_msgs/action/FollowWaypoints` | `waypoint_follower` |  |
| `/follow_gps_waypoints` | `nav2_msgs/action/FollowGPSWaypoints` | `waypoint_follower` | Lat/lon waypoints (the HUD's destination or OSRM route). Phase 2. |

## Frames

| Frame | Parent | Published by | Notes |
|---|---|---|---|
| `map` | - | ekf_global (map -> odom) | x east, y north; origin = the navsat datum |
| `odom` | map | ekf_local (odom -> base_link) | continuous; starts where the car starts |
| `base_link` | odom | - | on the ground under the rear axle centre; x forward, y left, z up |
| `chassis` | base_link | robot_state_publisher |  |
| `imu_link` | base_link | robot_state_publisher | vehicle.yaml sensors.imu_link |
| `gps_link` | base_link | robot_state_publisher | the antenna |
| `radar_link` | base_link | robot_state_publisher |  |
| `camera_left_link` | base_link | robot_state_publisher |  |
| `camera_right_link` | base_link | robot_state_publisher |  |
