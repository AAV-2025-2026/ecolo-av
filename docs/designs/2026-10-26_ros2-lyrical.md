# Should we move to ROS 2 Lyrical Luth?

**As of 26 Oct 2026.** A research note, not a decision. Every fact below comes from a
page or package index opened on this date (see [Sources](#sources)).

## The answer in one table

| Question | Answer |
|---|---|
| Should we move this school year? | **No. Stay on Jazzy until the 2026-27 team hands over (spring 2027).** |
| Is Lyrical a good distro? | Yes: LTS, supported to **May 2031** (Jazzy: May 2029) |
| Why not now? | Its official home is **Ubuntu 26.04**. Our Orins (JetPack 7.2) and laptops run **24.04**, where Lyrical is "build it yourself" (Tier 3) |
| Does anything we use break? | One thing: **velodyne_pointcloud** (our lidar's point clouds) fails to build on 26.04 apt |
| Is there anything we'd want from it? | Yes: Nav2 MPPI **delay compensation** (fits our dead-time work), and **Isaac ROS 5**, which now needs Lyrical |
| What to do cheaply | A **non-blocking Lyrical CI job** through RoboStack, once a month or nightly |

---

## 1. Lyrical: dates, support, platforms

| Fact | Lyrical | Jazzy (ours) |
|---|---|---|
| Released | 22 May 2026 | 23 May 2024 |
| Long-term support (LTS)? | Yes | Yes |
| End of life | May 2031 | May 2029 |
| Main Ubuntu | **26.04 Resolute** | 24.04 Noble |
| Python | 3.12 to 3.14 (3.14 on 26.04) | 3.12 |
| C++ minimum | C++20 | C++17 |
| Default middleware | Fast DDS 3.6 | Fast DDS |
| Gazebo | Jetty | Harmonic |

### Platforms (official "Supported Platforms" page)

| Platform | Tier | How you get it |
|---|---|---|
| Ubuntu 26.04, amd64 and arm64 | Tier 1 | apt packages, binary archive |
| Windows 11 amd64 | Tier 1 | binary archive |
| RHEL 10 amd64 | Tier 2 | RPM packages, archive |
| **Ubuntu 24.04 (any arch)** | **Tier 3** | **source only**; support ends early, 1 Jun 2029 |
| macOS | Tier 3 | source only |
| Debian 13 Trixie | Tier 3 | source only; support ends 9 Aug 2028 |

### Checked by hand (apt indexes)

| apt source | Ubuntu | `ros-lyrical-*` packages |
|---|---|---|
| packages.ros.org | 26.04 amd64 | 2,684 |
| packages.ros.org | 26.04 arm64 | 2,680 |
| packages.ros.org | **24.04 arm64** | **0** (it has 3,955 `ros-jazzy-*`) |
| NVIDIA "Isaac ROS Buildfarm" | 24.04 arm64 | 2,673 |
| NVIDIA "Isaac ROS Buildfarm" | 24.04 amd64 | 2,700 |

So on Ubuntu 24.04, Lyrical comes from **NVIDIA's own apt repo**, from **RoboStack**, or
from a source build. Not from ROS's own apt repo.

## 2. Gazebo for Lyrical

| | Jetty (for Lyrical) | Harmonic (ours, for Jazzy) |
|---|---|---|
| Released | Sep 2025 | Sep 2023 |
| LTS | Yes | Yes |
| End of life | May 2031 | May 2029 |
| With Jazzy? | **Incompatible** | Recommended |
| With Lyrical? | Recommended | "Possible, use with caution" |

- ROS ships Jetty for Lyrical as vendor packages: `ros-lyrical-gz-sim-vendor` 0.4.6 is on
  26.04 apt (amd64 and arm64). NVIDIA's 24.04 repo has it too.
- Gazebo's own Jetty page lists 24.04 binaries (recommended) and 26.04 as "coming soon".
- Moving to Lyrical means moving our worlds and `ros_gz` bridges to Jetty at the same
  time (`ros_gz` 1.0.x becomes 3.0.x).

## 3. JetPack 7.2 on the Orins

| Fact | Value |
|---|---|
| JetPack 7.2.1 / Jetson Linux | L4T r39.2.1, dated 11 Aug 2026 |
| Base | **Ubuntu 24.04**, Linux 6.8 |
| Modules | Jetson Thor and the **Jetson Orin family** |
| CUDA / TensorRT | 13.2.2 / 10.16.2 |
| Our Orin today | JetPack 6 (Ubuntu 22.04, L4T R36.4.7); reflash planned ([platforms](../platforms.md)) |

### What installs on JetPack 7.2 (Ubuntu 24.04, arm64)

| ROS | How | Who supports it |
|---|---|---|
| **Jazzy** | apt from packages.ros.org | ROS (Tier 1) |
| Jazzy | Pixi (RoboStack) | RoboStack |
| Lyrical | apt from NVIDIA's "Isaac ROS Buildfarm" (`isaac.download.nvidia.com/isaac-ros/ubuntu/main noble`) | NVIDIA, not ROS |
| Lyrical | Pixi (RoboStack `linux-aarch64`) | RoboStack |
| Lyrical | colcon source build | us (Tier 3) |
| Lyrical | apt from packages.ros.org | **not possible**: no 24.04 packages |

### NVIDIA Isaac ROS

| Isaac ROS | Date | ROS distro | Orin? |
|---|---|---|---|
| 4.6.0 | 18 Aug 2026 | **Jazzy** (last one) | Yes, first on JetPack 7.2 |
| 5.0.0 | 21 Sep 2026 | **Lyrical** | Yes (AGX Orin named in its known issues) |

Isaac ROS 5.0 dropped NITROS for Lyrical's `rosidl::Buffer` (GPU zero copy). NVIDIA says
plainly: "The public ROS 2 apt repository does not provide ROS 2 Lyrical packages for
Ubuntu 24.04 (Noble)", so it builds them itself.

## 4. RoboStack (Pixi)

**Yes, RoboStack ships Lyrical.** Channel `robostack-lyrical` on prefix.dev; repo created
17 May 2026; last upload 25 Oct 2026.

| Platform | Distinct `ros-lyrical-*` names | (Jazzy, for scale) |
|---|---|---|
| osx-arm64 (our Macs) | 2,232 | 2,360 |
| linux-64 | 2,490 | 2,647 |
| linux-aarch64 (Orin, Pi) | 2,444 | 2,603 |

Every ROS package in our `pixi.toml` exists in `robostack-lyrical` on all three platforms,
**except** `ros2-socketcan` and `usb-cam` on Macs. Those are missing for Jazzy on Macs
too, and our `pixi.toml` already installs them on Linux only. RoboStack even has
`velodyne-pointcloud` 2.5.1, which ROS's own apt doesn't.

## 5. Our packages on Lyrical

Every ROS package in our `pixi.toml`, checked on 26 Oct 2026 in: the Lyrical rosdistro
file, ROS apt for 26.04 (amd64 and arm64), NVIDIA's 24.04 arm64 repo, and RoboStack.

### Released (the ones asked about)

| Package | Lyrical | Jazzy |
|---|---|---|
| navigation2, incl. **nav2_mppi_controller** | 1.5.2 apt (1.5.3 in rosdistro) | 1.3.14 |
| robot_localization | 3.10.0 | 3.8.3 |
| twist_mux | 4.5.1 | 4.5.0 |
| ros_gz (bridge, sim) | 3.0.10 | 1.0.25 |
| foxglove_bridge | 3.6.0 apt (3.6.3 in rosdistro) | 3.6.3 |
| ublox (ublox_gps) | 3.0.0 | 2.3.0 |
| ublox_dgnss | 0.7.5 | 0.7.4 |
| teleop_twist_joy / teleop_twist_keyboard | 2.6.5 / 2.4.1 | same |
| velodyne_driver, velodyne_msgs, velodyne_laserscan | 2.5.1 | 2.5.1 |
| rosidl_generator_rs (rclrs messages) | 0.5.0 | 0.5.0 |

Also out: joy, joy_teleop, nmea_navsat_driver, imu_filter_madgwick, usb_cam,
ros2_socketcan, can_msgs, rosbridge_server, rosbag2_storage_mcap, topic_tools,
vision_msgs, ackermann_msgs, cv_bridge, camera_calibration, xacro, rmw_cyclonedds_cpp,
rmw_zenoh_cpp.

### Not out, or not a ROS package

| Package | State | Matters? |
|---|---|---|
| **velodyne_pointcloud** (so also the `velodyne` metapackage) | In rosdistro, but **no apt package** on 26.04 or in NVIDIA's repo. The build farm's 26.04 amd64 job last ran 26 Oct 2026: **FAILURE** | **Yes**: `aav_sensors` makes `/sensors/lidar/points` with it. RoboStack has it; apt doesn't |
| rclrs | Not in rosdistro: it's a crate. 0.8.0 (23 Sep 2026); its CI tests Humble, Jazzy, Kilted, **Lyrical**, Rolling | No |

## 6. What Lyrical gives a small car

Only the parts that touch our stack. "Already in Jazzy" means the feature was backported.

### Nav2 (1.3 → 1.5)

| Feature | Use to us | In Jazzy? |
|---|---|---|
| **MPPI per-axis delay compensation** (`model_delay_vx`, `model_delay_wz`): replays the commands still "in flight" | **High.** Our system identification now fits a dead time ([actuator tests](../actuator-tests.md)); a slow steering motor is exactly the case Nav2 shows (600 ms steering delay, oscillation gone) | **No** (in the `lyrical` branch, not `jazzy`) |
| MPPI open-loop mode | Helps with laggy wheel odometry | Already in Jazzy |
| MPPI asymmetric acceleration limits | Brake harder than you accelerate | Already in Jazzy (`ax_max`, `ax_min`) |
| MPPI motion models become plugins (`mppi::AckermannMotionModel`) | Config change only | No (a breaking change) |
| Route server, loopback simulator, docking | GPS routes, cheap tests | Already in Jazzy |
| Collision monitor: toggle service, exclusion zones, costmap source | Nice for the e-stop chain | No |
| Faster inflation layer (OpenMP) | Lower CPU on the Orin | No |
| Following server, pause/resume | Maybe later | No |

### Core ROS 2

| Feature | Use to us |
|---|---|
| rosbag2: **`--max-bag-files`** (ring buffer of bags) | A "black box" on the car without filling the disk |
| rosbag2: record/stop **services**, and `/events/rosbag2_messages_lost` | Start a bag from the HUD; know when a car-day bag lost data |
| rclpy **`AsyncNode`** (asyncio, "significantly less CPU") | Our Python nodes; marked experimental |
| `rosidl::Buffer` (GPU zero copy) | Camera → TensorRT on the Orin; what Isaac ROS 5 is built on |
| Typed YAML parameters (`!!float 10`) | Ends "int vs double" parameter bugs in `vehicle.yaml` loaders |
| `ros2 param get <param>` across **all** nodes | Check `use_sim_time` everywhere in one line |
| `ros2 topic bw --all`, `ros2 service info --verbose`, richer `ros2 doctor --report` | Our bandwidth and network checks |
| URDF 1.2: acceleration, deceleration, jerk limits | Could hold our actuator limits in the URDF |

None of these is needed to drive A to B.

## 7. Recommendation

### Stay on Jazzy for 2026-27

| Reason | Detail |
|---|---|
| The platforms don't line up | Lyrical's apt home is 26.04. JetPack 7.2 is 24.04. There is no ROS-supported way to put Lyrical on the Orin |
| It would change three things at once | ROS, Gazebo (Harmonic → Jetty) and Nav2 (breaking config changes), in the year we first drive the car |
| One sensor breaks | velodyne_pointcloud has no Lyrical apt package |
| Jazzy has time left | Jazzy and Harmonic are both supported to **May 2029** |
| Most Nav2 wins are already backported | Open loop, asymmetric limits, route server, docking |

**Until when:** the end of the 2026-27 year (the final demo, spring 2027). Put the
question to the 2027-28 team in summer 2027.

### What would make us move sooner

| Trigger | Why it flips the answer |
|---|---|
| We want **Isaac ROS 5+** on the Orin (cuVSLAM, nvblox, TensorRT nodes with zero copy) | 4.6 is the last Jazzy release; `decisions.md` names Isaac ROS as the Orin's upgrade path |
| The steering **dead time** we measure makes MPPI oscillate, and tuning doesn't fix it | MPPI delay compensation is Lyrical-only (the alternative: handle the delay in ego) |
| NVIDIA ships a **JetPack on Ubuntu 26.04** | Lyrical becomes Tier 1 apt on the Orin |
| velodyne_pointcloud **builds** on Lyrical | Removes the one missing package |

### Try it cheaply now

1. **A Lyrical CI job, non-blocking.** A Pixi environment with channel
   `robostack-lyrical` on `linux-64`, running `colcon build` and `colcon test` once a
   week or nightly, allowed to fail. It shows what breaks (Nav2 parameter renames,
   `ros_gz` 3, Jetty) with no risk to `main`. A new `pixi run` task needs its README row.
2. **One laptop test:** `pixi run sim-check` under that environment, to see if our Gazebo
   world loads in Jetty.
3. **Keep Lyrical code-ready:** write new Python so it runs on 3.12 to 3.14, and avoid
   Nav2 parameters that Lyrical removed (for example MPPI's `prune_distance`,
   `transform_tolerance`).
4. **Don't** reflash an Orin for Lyrical, or use NVIDIA's Lyrical repo on the car, this year.

---

## Sources

All opened 26 Oct 2026. docs.ros.org blocked automated reads (a bot check), so its pages
were read from their source in the `ros2/ros2_documentation` GitHub repo.

| Source | What it gave |
|---|---|
| [Release-Lyrical-Luth.rst](https://github.com/ros2/ros2_documentation/blob/rolling/source/Releases/Release-Lyrical-Luth.rst) (the source of [the owner's link](https://docs.ros.org/en/rolling/Releases/Release-Lyrical-Luth.html)) | LTS to May 2031, new features |
| [lyrical/supported-platforms.rst](https://github.com/ros2/ros2_documentation/blob/rolling/source/Releases/lyrical/supported-platforms.rst) | Tiers, Noble Tier 3, Jetty, Python, DDS versions |
| [lyrical/release-timeline.rst](https://github.com/ros2/ros2_documentation/blob/rolling/source/Releases/lyrical/release-timeline.rst) | GA 22 May 2026, EOL May 2031 |
| [Releases.rst](https://github.com/ros2/ros2_documentation/blob/rolling/source/Releases.rst) | Jazzy EOL May 2029 |
| [rosdistro lyrical/distribution.yaml](https://github.com/ros/rosdistro/blob/master/lyrical/distribution.yaml) and [jazzy/distribution.yaml](https://github.com/ros/rosdistro/blob/master/jazzy/distribution.yaml) | Release platforms; package versions |
| packages.ros.org apt indexes: `ros2/ubuntu/dists/{resolute,noble}/main/binary-{amd64,arm64}/Packages.gz` | Package counts, which are built |
| [build.ros2.org: velodyne_pointcloud, Lyrical 26.04 amd64](https://build.ros2.org/job/Lbin_uR64__velodyne_pointcloud__ubuntu_resolute_amd64__binary/) | Last build FAILURE, 26 Oct 2026 |
| [Gazebo releases](https://gazebosim.org/docs/latest/releases/) | Jetty and Harmonic dates, LTS |
| [Gazebo: ROS installation](https://gazebosim.org/docs/latest/ros_installation/) | ROS/Gazebo pairing table |
| [Gazebo Jetty: getting started](https://gazebosim.org/docs/jetty/getstarted/) | Jetty platforms |
| [NVIDIA JetPack](https://developer.nvidia.com/embedded/jetpack) | JetPack 7: Ubuntu 24.04, kernel 6.8, Orin and Thor |
| [JetPack 7.2.1 archive](https://developer.nvidia.com/embedded/jetpack/downloads/archive-7.2.1.md) | L4T 39.2.1, 11 Aug 2026, CUDA 13.2.2 |
| [AGX Orin: set up JetPack](https://docs.nvidia.com/jetson/agx-orin-devkit/user-guide/latest/setup_jetpack.html) | JetPack 7.2.1 on AGX Orin, apt install |
| [Isaac ROS releases](https://nvidia-isaac-ros.github.io/releases/index.html) | 4.6 (Orin, JP 7.2), 5.0 (Lyrical) |
| [Isaac ROS getting started (latest)](https://nvidia-isaac-ros.github.io/getting_started/index.html) and [release 4.6](https://nvidia-isaac-ros.github.io/v/release-4.6/getting_started/index.html) | Lyrical now; Jazzy for 4.6 |
| [Isaac ROS Buildfarm](https://nvidia-isaac-ros.github.io/getting_started/isaac_ros_buildfarm_cdn.html), and its apt index `isaac.download.nvidia.com/isaac-ros/ubuntu/main/dists/noble/` | Lyrical-on-24.04 packages |
| [RoboStack ros-lyrical](https://github.com/RoboStack/ros-lyrical), and `prefix.dev/robostack-{lyrical,jazzy}/<platform>/repodata.json` | Lyrical on all three platforms; package lists |
| [rclrs on crates.io](https://crates.io/crates/rclrs) and [ros2_rust CI workflow](https://github.com/ros2-rust/ros2_rust/blob/main/.github/workflows/rust-minimal.yml) | 0.8.0; tests Lyrical |
| [Nav2 Lyrical release post](https://discourse.openrobotics.org/t/nav2-lyrical-release-key-features/57666) (25 Aug 2026) | Nav2 Lyrical features |
| [Nav2 Kilted release post](https://discourse.openrobotics.org/t/nav2-kilted-release/44079) (2 Jun 2025) | Nav2 Kilted features |
| [Nav2 migration: Kilted to Lyrical](https://docs.nav2.org/lyrical/configuration_and_development/migration_guides/kilted/Kilted/) | Delay compensation, motion-model plugins, breaking changes |
| [navigation2 PR #6154](https://github.com/ros-navigation/navigation2/pull/6154), and `optimizer.cpp` on its `lyrical` and `jazzy` branches | Delay compensation merged 8 Jun 2026; in `lyrical`, not `jazzy` |
| `vendor/ros2-src/ecosystem/navigation2` (Jazzy 1.3.13, in this repo) | Jazzy MPPI already has open loop and `ax_max`/`ax_min` |
