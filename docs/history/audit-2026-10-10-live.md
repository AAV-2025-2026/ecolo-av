# Audit, 10 October 2026: the sim, car and replay profiles, run live on Jazzy

A live audit by a Claude Code agent, kept as it reported. It tested its fixes in copies
under `/tmp`; the main session then applied them (see the end). Line numbers are from the
tree at the time.

I ran sim, car and replay live; these are the results. **Sim drives from `/cmd_vel/remote`, but a Nav2 goal fails in both sim and replay.** Two bugs stack up: Nav2 runs on wall-clock time, and the simulated GPS noise is in degrees instead of metres. On the car profile, Nav2 starts without a map, and the GPS driver can't be installed through pixi. I tested the fixes in copies under `/tmp`, put first on `AMENT_PREFIX_PATH`; nothing under `/home/ben/aav` was changed.

**1. Per profile**

**Sim** (`gui:=false rviz:=false`, empty world, nav on)
- **Startup:** comes up in about 3 s with 20 processes and 27 ROS nodes. All 9 Nav2 lifecycle nodes are active. `spawn_aav` exits cleanly after spawning the car.
- **check_graph:** 0 failed.
- **TF:** map→odom comes only from `ekf_global` and odom→base_link only from `ekf_local`. Gazebo's own TF (`/model/aav/tf`) isn't bridged, so there are no duplicates and no frame has two parents.
- **QoS:** no mismatches on `/cmd_vel`, `/ego/actuator_cmd`, `/odometry/local`, `/odometry/global`, `/gps/fix`, `/imu/data`, `/estop` or `/map`.
- **use_sim_time:** true everywhere except the 9 Nav2 nodes (B1 below).
- **Driving:** 100 commands of v 1.0, w 0.2 on `/cmd_vel/remote` came through as `/ego/actuator_cmd` speed 1.0, steering 0.304 (the bicycle-model value), then `/gazebo/cmd_vel`, then `/vehicle/odom` (v 1.0, w 0.199). `/odometry/local` moved +4.51 m, +1.59 m, yaw +0.80, and ego stopped after the timeout. `/odometry/global` jumped by tens of kilometres (B2).
- **Nav2 goal, as the repo stands:** goal (8.0, 5.2) was accepted, then aborted with code 203: "Start Coordinates of(26584.281841, 34198.146701) was outside bounds".
- **With only the GPS fix:** aborted with code 102 (B1).
- **With B1, B2, W1 and W2 fixed:** both goals succeeded (8 m in about 9 s, a curved 15 m in about 21 s), with `/cmd_vel/nav` up to 1.0 m/s.

**Car** (`machine:=all`; spine, radar and battery were launched separately)
- **Startup:** comes up partly. Still running: robot_state_publisher, joint_state_publisher, twist_mux, ego, joy_node, teleop_twist_joy_node, joy_teleop, scripted_driver, imu_filter_madgwick, ekf_local, ekf_global, navsat_transform, encoder_udp, and the 8 Nav2 processes.
- **Died:** imu_node and legacy_uart_bridge (no hardware) and foxglove_bridge (N1). `gps_container` is up but empty (B4).
- **Nav2:** map_server is active but has no map (B3). The rest stay inactive because bringup aborted with no TF, which is expected with no sensors.
- **check_graph:** 2 failed, `/imu/data_raw` and `/gps/fix`.
- **TF:** only the robot_state_publisher frames.
- **use_sim_time:** false everywhere.

**Replay** (`nav:=true rviz:=false`)
- **Bag:** recorded myself from sim: 83 s, MCAP, in `/tmp/aav_liveaudit2/bag_simB`.
- **Result:** comes up and waits for `/clock`. Played with the bag's own `/clock`, the replayed EKFs match the recorded `/odometry/local` and `/odometry/global` to within 0.03 m.
- **Nav2:** all active, but on wall-clock time (B1).
- **TF:** fine; rosbag2_player republishes identical static frames.
- **check_graph:** there is no `replay` profile (N4). With `--profile sim` it fails only on `/cmd_vel`, `/ego/actuator_cmd` and `/vehicle/status`, which replay doesn't run.

**2. Findings**

**BREAKS**

**B1. Nav2 ignores use_sim_time in sim and replay** — `src/drivers/aav_navigation/launch/navigation.launch.py:46` and `:69`
- **Evidence:** use_sim_time is False on map_server, planner_server, controller_server, behavior_server, bt_navigator, waypoint_follower, velocity_smoother and both costmaps. The controller log says "[tf_help]: Transform data too old when converting from map to odom … Data time: 1791617454s …, Transform time: 46s", then "Failed to transform end pose to global frame".
- **Cause:** RewrittenYaml only rewrites keys that exist, and `nav2.yaml` has no `use_sim_time` key.
- **Fix:** line 69 `parameters=[params], remappings=remaps)` -> `parameters=[params, {'use_sim_time': use_sim_time}], remappings=remaps)`, and delete line 46 `'use_sim_time': str(use_sim_time),`. Tested: all 9 nodes then read True.

**B2. Sim GPS noise is applied in degrees** — `src/aav_description/urdf/aav.gazebo.xacro:75`
- **Evidence:** with the car parked, 47 fixes had a spread of 0.495° latitude and 0.456° longitude (about 55 km). `/odometry/global` sat at (32711, 33210), and the planner logged "Robot is out of bounds of the costmap" 71 times.
- **Fix:** `<stddev>0.5</stddev>` -> `<stddev>4.5e-6</stddev>`. Tested: spread about 0.5 m, and `ekf_global` stayed within 0.15 m of Gazebo's ground truth.

**B3. Car starts Nav2 without a map** — `src/aav_bringup/launch/car.launch.py:82` and `:101`
- **Evidence:** map_server logs "yaml-filename parameter is empty, set map through 'load_map'-service", and `ros2 param get /map_server yaml_filename` returns an empty string.
- **Cause:** car's empty `map` launch argument is inherited by `navigation.launch.py` and overrides its default at line 88.
- **Fix:** line 82 -> `nav_args = {'map': arg('map') or os.path.join(FindPackageShare('aav_navigation').perform(context), 'maps', 'empty.yaml')}`

**B4. The GPS driver isn't in the pixi environment** — `src/sensors/aav_sensors/launch/sensors.launch.py:75-96`; `pixi.toml` doesn't list it
- **Evidence:** "Failed to load node 'ublox_dgnss' of type 'ublox_dgnss::UbloxDGNSSNode' in container '/gps_container': Could not find requested resource in ament index", and the same for ublox_nav_sat_fix_hp. `pixi search` finds no ublox_dgnss on robostack-jazzy, only `ros-jazzy-ublox` 2.3.0 (the ublox_gps driver).
- **Fix:** the team needs to choose one:
  - install `ros-jazzy-ublox-dgnss` from apt on the Orin (I couldn't check it from here) and only enable gps on apt machines; or
  - switch to `ros-jazzy-ublox` and add it to `pixi.toml`.

**WRONG**

**W1. Simulated steering is too slow, so Nav2 weaves** — `aav.gazebo.xacro:20-41` sets no `<steer_p_gain>`
- **Evidence:** with B1 and B2 fixed, an 8 m straight goal took over 60 s with a detour to (1.6, −9). A second goal wasn't reached in 50 s; the `/cmd_vel/nav` turn rate flipped ±0.333 and the measured yaw rate lagged steering by more than 1 s.
- **Fix:** add `<steer_p_gain>10.0</steer_p_gain>` after line 27. Tested: both goals succeeded quickly.

**W2. Global costmap inflation is smaller than the car** — `src/drivers/aav_navigation/config/nav2.yaml:182`
- **Evidence:** "[computeCircumscribedCost]: The inflation radius (1.500000) is smaller than the circumscribed radius (1.930026)".
- **Fix:** `inflation_radius: 1.5` -> `inflation_radius: 2.0`. Tested: the error is gone.

**IGNORED** (live parameter check)
- **Intentional:**
  - `nav2.yaml:97-123`, the MPPI block (25 keys): controller not loaded.
  - `nav2.yaml:145-157`, `obstacle_layer` (11 keys): not in the plugin list.
  - `nav2.yaml:278`, the whole `collision_monitor` block: the node only starts with `collision_monitor:=true`. Its keys match the Jazzy source.
- **Every other key is declared:** ekf_local 22/22, ekf_global 27/27, navsat 10/10, imu_filter 9/9, ego 10/10, scripted 3/3, joy 6/6, teleop_twist_joy 10/10, encoder_udp 7/7, spine_bridge 6/6, and all keys on every running Nav2 server and costmap. All inline launch parameters are declared too.
- **Can't be checked live:**
  - twist_mux and joy_teleop accept any parameter, so a typo would still show as declared. I read their configs against the source instead, and they look right.
  - `imu.yaml:5` and `legacy.yaml:3` only because those nodes died first. Their names match `imu_node.cpp:24-30` and `legacy_uart_bridge.py:29-35`.

**NOTE**
- **N1:** foxglove_bridge 3.6.0 dies on this AlmaLinux machine: "version `GLIBC_2.35' not found (required by …/libfoxglove.so)". The machine has glibc 2.34. Ubuntu 24.04 and Macs have newer glibc, so it shouldn't happen there.
- **N2:** twist_mux subscribes best-effort (live: `/estop` sub BEST_EFFORT). joy_teleop publishes `/estop` once per press (`estop_button.yaml:3`), so one lost packet means the mux lock never engages. The backends still brake, because their `/estop` subscriptions are reliable.
- **N3:** Nav2 bringup gives up if TF is missing. Device nodes have no `respawn` (`sensors.launch.py:57`, `legacy.launch.py:31`), so a late or crashed sensor leaves Nav2 inactive until a relaunch.
- **N4:** `tools/check_graph.py:32` has no `replay` choice, and `docs/interfaces.yaml` has no replay `live` lists.
- **N5:** the documented `--clock` replay command (`replay.launch.py:5`) only works for bags recorded on the car. With a sim bag, the EKF state blew up to −7.9e15 m ("Easting -8.97943e+12km not in UTM range").
  - **Fix:** add `/clock` to the topic list in `tools/record.sh:11-17`, and document `--topics /clock …` without `--clock` for sim bags.
- **N6:** ego warns "cmd_vel stamp is more than 0.5 s from this clock" when Nav2 stops; this one is harmless (more in section 3).
- **N7:** Nav2's turn command still alternates sign about once a second when GPS shifts the map frame. A longer lookahead might help (`min_lookahead_dist` 2.5, `lookahead_time` 2.0); I haven't tested that.

**Checked, no problems:** Nav2 plugin names; both behavior-tree XMLs (they load at activation and every node is registered); robot_localization's 15-boolean `*_config` arrays (the 15-value covariances are accepted as diagonals); Gazebo plugins; the six `bridge.yaml` bridges; RViz class names.

**3. Expected errors with no hardware (harmless)**
- **imu_node:** "terminate called after throwing … Failed to open: /dev/aav/imu" (exit −6).
- **legacy_uart_bridge:** "could not open port /dev/ttyAMA0" (exit 1).
- **radar (pcl_pub):** cannot open `/dev/aav/radar_cmd`.
- **battery_monitor:** cannot open `/dev/aav/battery`.
- **socket_can_sender and socket_can_receiver:** "Error opening CAN receiver: can0 - Failed to set CAN socket name via ioctl()", then "Failed to make transition 'TRANSITION_CONFIGURE'". spine_bridge itself runs.
- **encoder_udp:** "no encoder packets: not publishing vehicle/odom".
- **imu_filter_madgwick:** "Still waiting for data on topic imu/data_raw".
- **Nav2 on the car:** "Timed out waiting for transform from base_link to map", then "Aborting bringup".
- **check_graph on the car:** "FAIL /imu/data_raw". The `/gps/fix` failure is partly hardware and partly B4.
- **Sim startup, one-offs:**
  - three costmap transform timeouts before `/clock` starts;
  - navsat "Latitude 45.0816d more than 20d from N pole" (a fix arrives before the datum is set);
  - two Gazebo "XML Element[gz_frame_id] … not defined in SDF. Copying" warnings;
  - controller "No goal checker / progress checker was specified".
- **Ego stamp warning (N6):** after Nav2 stops, the velocity smoother re-sends old stamps for up to 1 s, so ego logs the 0.5 s warning; it is harmless once B1 is fixed.

All my process groups are stopped and nothing is left on domain 81. I didn't start a ros2 daemon or run colcon. Logs and scripts are in `/tmp/aav_liveaudit2/`.

## Applied by the main session (10 October, about 04:00)

| Finding | Change | Checked live in the repo |
|---|---|---|
| B1 | `navigation.launch.py` passes `use_sim_time` on its own | Nav2 nodes read True |
| B2 | GPS noise 4.5e-6 degrees (about 0.5 m) | parked `ekf_global` at (0.07, 0.16) m |
| B3 | `car.launch.py` always passes a map | `map_server` has `maps/empty.yaml` |
| W1 | `steer_p_gain` 10 | goals (8, 0) in 13 s and (8, 5.2) in 47 s: both SUCCEEDED |
| W2 | inflation 2.0 m in both costmaps | |
| N4 | `check_graph --profile replay`; replay `live` lists in `interfaces.yaml` | replay of the sim bag: 0 failed |
| N5 | `tools/record.sh` records `/clock`; the sim-bag command in `replay.launch.py` | |
| B4, N2, N3, N7 | not changed: the team decides (listed in `TODO.md`) | |

On this machine Gazebo also needs `GZ_IP=127.0.0.1` (its discovery is multicast, which
doesn't loop back here); otherwise `spawn_aav` waits forever for the world.
