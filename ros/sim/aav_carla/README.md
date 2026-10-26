# aav_carla

CARLA as the car, behind the same topics as the real one. `carla_adapter` talks to a
CARLA server (0.10 on Unreal Engine 5, or 0.9.16) through CARLA's own Python client,
over TCP. It does not use carla-ros-bridge or CARLA's built-in ROS 2 (which stalls on
Jazzy).

Status: never run against a real CARLA server yet. See `docs/carla.md`.

## Overview

- The CARLA server runs anywhere this computer reaches on TCP 2000-2001. ROS stays on
  this computer.
- The client only exists for Linux x86_64 and Windows. On a Mac, `carla_adapter`
  stops with a one-line explanation.
- `launch/carla.launch.py` starts `carla_adapter` and the car's model (TF) on CARLA's
  clock. `pixi run carla-car host:=<the CARLA computer>` runs it through `aav_bringup`.
- The map frame: map (0, 0) is the datum in `aav_localization`'s `navsat.yaml`, x east.
  A CARLA town is moved so its spawn point sits there, facing east. A Carleton map built
  round the datum (`osm:=`) needs no move.

## Interface

### Node: `carla_adapter`

| Direction | Topic | Type |
|---|---|---|
| Subscribes | `/control/carla/actuator_cmd` | `ackermann_msgs/AckermannDriveStamped` (from `aav_io_mux`, target carla) |
| Subscribes | `/safety/estop` | `std_msgs/Bool`: true brakes at once, until false |
| Publishes | `/clock` | `rosgraph_msgs/Clock`: CARLA's time, each step |
| Publishes | `/vehicle/odom` | `nav_msgs/Odometry`, twist only |
| Publishes | `/vehicle/status` | `aav_interfaces/VehicleStatus` (mode COMPUTER) |
| Publishes | `/vehicle/steering`, `/vehicle/throttle`, `/vehicle/brake` | `aav_interfaces/ActuatorState` |
| Publishes | `/vehicle/wheels` | `aav_interfaces/WheelSpeeds` |
| Publishes | `/vehicle/carla/truth` | `nav_msgs/Odometry`: where the car really is |
| Publishes | `/sensors/imu/data_raw` | `sensor_msgs/Imu`, `imu_link`, no orientation |
| Publishes | `/sensors/gps/fix` | `sensor_msgs/NavSatFix`: the antenna round our datum, plus noise |
| Publishes | `/sensors/camera/{front_left,front_right,rear}/image_raw`, `.../camera_info` | with `cameras:=true` |
| Publishes | `/sensors/radar/points` | `PointCloud2`, best effort, the TI driver's fields; `radar:=true` |
| Publishes | `/sensors/lidar/points` | `PointCloud2`; `lidar:=true` |
| Publishes | `/system/source` | `aav_interfaces/DataSource`, latched: all SIM |

### Parameters

| Parameter | Default | Means |
|---|---|---|
| `host`, `port`, `timeout` | 127.0.0.1, 2000, 20.0 s | the CARLA server |
| `town`, `osm`, `xodr` | '' | a map to load ('' keeps the server's) |
| `sync`, `fixed_delta`, `realtime` | true, 0.05 s, true | synchronous stepping, kept in step with the wall clock |
| `vehicle`, `role_name`, `spawn` | '', ego_vehicle, '' | which car, and where (N, or x,y,yaw in our map frame) |
| `frame` | auto | auto, world or spawn |
| `control` | ackermann | ackermann (CARLA's speed loop) or pedals (ours) |
| `cameras`, `radar`, `lidar` | true | which sensors to attach |
| `cmd_timeout` | 0.2 s | a command older than this means speed 0 |
| `datum_lat`, `datum_lon` | 45.3860, -75.6960 | from `navsat.yaml`, via the launch file |
| `gps_stddev`, `gyro_stddev`, `accel_stddev`, `speed_variance` | 0.5 m, 0.02 rad/s, 0.2 m/s², 0.01 | noise |

### Modules (no ROS imports, except `carla_adapter.py`)

| Module | Holds |
|---|---|
| `frames.py` | CARLA's left-handed degrees to REP-103: `location_to_ros`, `rotation_to_ros`, `SpawnFrame`, `map_frame`, `enu_to_geodetic`, `mount` |
| `control.py` | ego's command to CARLA's: `Geometry`, `match_curvature`, `ackermann`, `pedals`, `SpeedLoop`, `Watchdog` |
| `sensors.py` | CARLA blueprints placed where `vehicle.yaml` puts ours: `Sensor`, `chosen`, `camera_matrix`, `lidar_points`, `radar_points`, `wheel_speeds` |
| `state.py` | the car actor to our topics: `CarState`, `car_state`, `antenna`, `Pacer` |
| `georef.py` | a Carleton map round the datum: `proj_string`, `bbox`, `osm_settings`, `parse_spawn`, `datum_from_navsat` |
| `link.py` | every call to the CARLA server: `CarlaLink`, `load_carla` |

## Invariants

- Only `link.load_carla()` imports `carla`. Everything else loads, and is tested, on a
  computer without CARLA (a Mac, CI).
- CARLA's y points right and its angles are degrees; ours are REP-103 (y left, radians,
  + steering = left). `frames.py` and `control.py` flip them.
- The CARLA car turns on the circle ours would (`match_curvature`), not at our angle.
- A command older than `cmd_timeout` gives speed 0. An e-stop stops the car until it
  clears.
- On exit or a failed start, `CarlaLink.close()` removes our car and sensors and gives
  the server back its settings. Synchronous mode left on would freeze it.
- Car measurements come from `vehicle.yaml`, never from here.

## Side Effects

- TCP to the CARLA server: loads a map, sets synchronous mode, spawns a car and its
  sensors, then removes them.
- Publishes `/clock` and the topics above. A background thread steps CARLA.
- `georef.py` can be run to print the map recipe; `tools/get_carla_osm.sh` downloads
  the `.osm`.

## Verification

```sh
pixi run build && colcon test --packages-select aav_carla && colcon test-result --verbose
```

The tests use a pretend `carla` (`test/fake_carla.py`). `pixi run test` runs everything.
Against a real server: untested.
