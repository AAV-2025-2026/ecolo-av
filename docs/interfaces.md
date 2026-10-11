# Interfaces

Generated from `docs/interfaces.yaml` by `tools/gen_interfaces_md.py`; edit the YAML.
Check a running system against it with `pixi run check <turtle|sim|car|replay|bench>`.

## Topics

| Topic | Type | Publishers | Subscribers | Must be live in | Notes |
|---|---|---|---|---|---|
| `/joy` | `sensor_msgs/msg/Joy` | `joy_node` | `teleop_twist_joy_node`, `joy_teleop` | - | Joystick axes and buttons, 20 Hz while held. |
| `/cmd_vel/joy` | `geometry_msgs/msg/TwistStamped` | `teleop_twist_joy_node` | `twist_mux` | - | Priority 100. Only while the deadman (trigger) is held. |
| `/cmd_vel/remote` | `geometry_msgs/msg/TwistStamped` | `teleop_twist_keyboard` | `twist_mux` | - | Priority 90. A person driving from a laptop - teleop_twist_keyboard (stamped:=true), the Foxglove teleop panel, or the HUD once ported. |
| `/cmd_vel/scripted` | `geometry_msgs/msg/TwistStamped` | `scripted_driver` | `twist_mux` | - | Priority 50. Only while a /scripted_drive goal runs. |
| `/cmd_vel/replay` | `geometry_msgs/msg/TwistStamped` | - | `twist_mux` | - | Priority 40. ros2 bag play of a recorded /cmd_vel (tools/replay_commands.sh). |
| `/cmd_vel/nav` | `geometry_msgs/msg/TwistStamped` | `velocity_smoother` | `twist_mux` | - | Priority 20. Nav2; from collision_monitor instead when it is enabled. |
| `/cmd_vel/ai` | `geometry_msgs/msg/TwistStamped` | `control_interface` | `twist_mux` | - | Priority 10, the slot for a learned driver. Today the 2025-26 lane keeping (aav_lane_geometry) uses it. |
| `/estop` | `std_msgs/msg/Bool` | `joy_teleop` | `twist_mux`, `spine_bridge`, `legacy_uart_bridge` | - | true = stop. Lock on twist_mux (priority 255) and the backends brake at once. Cleared only by publishing false. |
| `/cmd_vel` | `geometry_msgs/msg/TwistStamped` | `twist_mux` | `ego` | turtle, sim, car, bench | The one command ego obeys. v (m/s) and w (rad/s) in base_link. |
| `/ego/actuator_cmd` | `ackermann_msgs/msg/AckermannDriveStamped` | `ego` | `spine_bridge`, `legacy_uart_bridge`, `turtlesim_adapter`, `gazebo_adapter`, `carla_adapter` | turtle, sim, car, bench | 50 Hz, always. speed (m/s), steering_angle (rad, + left), acceleration, steering_angle_velocity. Exactly one backend runs. |
| `/vehicle/odom` | `nav_msgs/msg/Odometry` | `spine_bridge`, `encoder_udp`, `turtlesim_adapter`, `gazebo_adapter`, `carla_adapter` | `ekf_local`, `ekf_global` | turtle, sim, car, replay, bench | Twist only (vx, vy = 0, vyaw) in base_link, with covariances; pose covariance 1e3 (not measured). |
| `/vehicle/status` | `aav_interfaces/msg/VehicleStatus` | `spine_bridge`, `gazebo_adapter` | `hud_server` | sim, bench | Mode, armed, e-stop, measured speed and steering, actuator levels, fault bits. For the HUD and Foxglove. |
| `/vehicle/joint_states` | `sensor_msgs/msg/JointState` | `spine_bridge` | `joint_state_publisher` | bench | Measured front steering joint angles, merged into /joint_states. |
| `/joint_states` | `sensor_msgs/msg/JointState` | `joint_state_publisher`, `gz_bridge` | `robot_state_publisher` | turtle, sim, car, replay, bench |  |
| `/to_can_bus` | `can_msgs/msg/Frame` | `spine_bridge` | `socket_can_sender`, `spine_sim` | bench | DRIVE_CMD 0x100 at 50 Hz, ESTOP_CMD 0x010 at 10 Hz (firmware/can/aav.dbc). |
| `/from_can_bus` | `can_msgs/msg/Frame` | `socket_can_receiver`, `spine_sim` | `spine_bridge` | bench | VEHICLE_FEEDBACK 0x180 at 50 Hz, VEHICLE_STATUS 0x181 at 10 Hz. On the bench, spine_sim sends them. |
| `/imu/data_raw` | `sensor_msgs/msg/Imu` | `imu_node`, `gazebo_adapter`, `mock_imu` | `imu_filter_madgwick` | sim, car, replay, bench | Gyro and accelerometer in imu_link, with covariances; no orientation. |
| `/imu/mag` | `sensor_msgs/msg/MagneticField` | `imu_node`, `mock_imu` | `imu_filter_madgwick` | bench | Raw counts from imu_node (not tesla yet); tesla from mock_imu. The filter ignores it (use_mag false). |
| `/imu/data` | `sensor_msgs/msg/Imu` | `imu_filter_madgwick` | `ekf_local`, `ekf_global` | sim, car, replay, bench | Adds a relative orientation (no magnetometer). The EKFs fuse the yaw rate only. |
| `/gps/fix` | `sensor_msgs/msg/NavSatFix` | `ublox_nav_sat_fix_hp`, `gazebo_adapter`, `mock_gps` | `navsat_transform` | sim, car, replay, bench | Lat/lon of the antenna (gps_link). ublox publishes it best-effort (SensorDataQoS). |
| `/radar/points` | `sensor_msgs/msg/PointCloud2` | `radar`, `mock_radar` | `radar_clusters` | bench | The TI radar's points, in radar_link. Best effort - subscribe best effort, or nothing matches. Clustered by aav_object_detection; later also the local costmap's obstacle layer and collision_monitor. |
| `/battery_status` | `sensor_msgs/msg/BatteryState` | `battery_state_publisher`, `mock_battery` | - | bench | battery_monitor's node is battery_state_publisher (the Victron VE.Direct cable). |
| `/battery_monitor_heartbeat` | `std_msgs/msg/String` | `heartbeat_publisher` | - | - | battery_monitor's sign of life. |
| `/camera/image_raw` | `sensor_msgs/msg/Image` | `usb_cam`, `mock_camera`, `test_camera` | `yolo_detector`, `hud_server` | bench | The front camera (camera_left_link). Big messages - subscribe reliably, as best effort loses them over UDP. mock_camera draws the bench world; test_camera publishes a file. |
| `/camera/image_raw/compressed` | `sensor_msgs/msg/CompressedImage` | `usb_cam` | `yolo_detector` | - | The same pictures as JPEG, from image_transport's compressed plugin (usb_cam publishes it by itself). A detector on a laptop over WiFi reads this one (detector.launch.py compressed:=true). |
| `/camera/camera_info` | `sensor_msgs/msg/CameraInfo` | `usb_cam`, `mock_camera`, `test_camera` | - | bench | The lens. usb_cam reads aav_sensors/config/cameras/left.ini (the 2024-25 calibration). |
| `/radar/clusters` | `sensor_msgs/msg/PointCloud2` | `radar_clusters` | - | bench | The radar points DBSCAN grouped into objects, coloured by cluster. |
| `/radar/cluster_boxes` | `visualization_msgs/msg/MarkerArray` | `radar_clusters` | - | bench | A box round each radar cluster, for RViz. |
| `/perception/detections` | `vision_msgs/msg/Detection2DArray` | `yolo_detector` | `stop_sign_watcher` | - | YOLO's boxes in pixels; header.frame_id names the camera, results[0].hypothesis is the label (e.g. "stop sign") and score. One detector per computer with a GPU (the Orin, a laptop), each under its own node name (detector.launch.py name:=), all on this topic. Runs in the ml environment. |
| `/perception/detections/image` | `sensor_msgs/msg/Image` | `yolo_detector` | - | - | The camera picture with the boxes drawn on, for RViz or Foxglove. |
| `/perception/stop` | `std_msgs/msg/Bool` | `stop_sign_watcher` | `twist_mux`, `hud_server` | - | true while the car stops for a stop sign. A twist_mux lock at priority 30 - it holds Nav2 and the AI slot, never a person; never expires on silence. |
| `/lane_geometry` | `aav_lane_geometry/msg/LaneGeometry` | `fake_lane_geometry_pub` | `control_interface` | - | The lane lines as polynomials, the car's offset and the curvature. The lane finder that makes them from the camera is missing; fake_lane_geometry_pub stands in. |
| `/lane_geometry_status` | `std_msgs/msg/String` | `control_interface` | - | - | Lane keeping's state and numbers, as text. |
| `/vehicle_state` | `std_msgs/msg/String` | `control_interface` | - | - | Lane keeping's state machine (LANE_KEEP, LANE_CHANGING, ...). Not the car's state - that's /vehicle/status. |
| `/bench/truth` | `nav_msgs/msg/Odometry` | `spine_sim` | `mock_imu`, `mock_gps`, `mock_camera` | bench | Where the model car really is (map frame, 50 Hz). Only the stand-ins read it; compare it with /odometry/global to check the EKFs. |
| `/bench/hw_estop` | `std_msgs/msg/Bool` | - | `spine_sim` | - | true = press the hardware e-stop, on the bench; false = release it. The spine brakes, and needs arming again. |
| `/bench/driver_faults` | `std_msgs/msg/UInt16` | - | `spine_sim` | - | Pretend a driver failed. Fault bits as in VehicleStatus (8 = steering, 16 = brake, 32 = throttle DAC, 64 = encoder). |
| `/odometry/local` | `nav_msgs/msg/Odometry` | `ekf_local` | `controller_server`, `bt_navigator`, `scripted_driver` | turtle, sim, car, replay, bench | odom frame. Smooth; drifts. |
| `/odometry/global` | `nav_msgs/msg/Odometry` | `ekf_global` | `navsat_transform` | sim, car, replay, bench | map frame. Includes GPS; can jump. |
| `/odometry/gps` | `nav_msgs/msg/Odometry` | `navsat_transform` | `ekf_global` | sim, car, replay, bench | Each GPS fix as a map-frame position of base_link (antenna offset removed). |
| `/gps/filtered` | `sensor_msgs/msg/NavSatFix` | `navsat_transform` | `hud_server` | sim, car, replay, bench | The global EKF's position as lat/lon, for maps in the HUD or Foxglove. |
| `/map` | `nav_msgs/msg/OccupancyGrid` | `map_server` | `global_costmap`, `local_costmap` | sim | Transient local (latched). From aav_navigation/maps. |
| `/goal_pose` | `geometry_msgs/msg/PoseStamped` | `rviz2` | `bt_navigator` | - | RViz "2D Goal Pose" starts a navigate_to_pose. |
| `/plan` | `nav_msgs/msg/Path` | `planner_server` | - | - | The planned path, for RViz/Foxglove. |
| `/tf` | `tf2_msgs/msg/TFMessage` | `ekf_local`, `ekf_global`, `robot_state_publisher` | - | turtle, sim, car, replay, bench | map -> odom (ekf_global), odom -> base_link (ekf_local), moving joints (robot_state_publisher). |
| `/tf_static` | `tf2_msgs/msg/TFMessage` | `robot_state_publisher`, `map_to_odom_no_gps` | - | turtle, sim, car, replay, bench | base_link -> chassis and every sensor frame, from vehicle.yaml through the URDF. With gps:=false, map_to_odom_no_gps adds a fixed map -> odom. |
| `/robot_description` | `std_msgs/msg/String` | `robot_state_publisher` | - | turtle, sim, car, replay, bench |  |
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
| `/follow_gps_waypoints` | `nav2_msgs/action/FollowGPSWaypoints` | `waypoint_follower` | Lat/lon waypoints. The HUD (hud_server) sends its locked route here. Phase 2. |

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
