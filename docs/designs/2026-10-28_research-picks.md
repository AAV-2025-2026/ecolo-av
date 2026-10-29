# Four things worth researching

* **Author:** Ben
* **Date:** 2026-10-28
* **Status:** research list, nothing decided. No RTK on this car (Ben, 28 Oct)

Ben's picture of localization, which is how cars do it:

| Layer | Gives | Ours |
|---|---|---|
| Dead reckoning (wheels + IMU) | smooth and fast, but drifts | `ekf_local` |
| GPS | absolute, about 1-3 m | `ekf_global` |
| Camera or lidar against things you can see | centimetres, near those things | **not yet**: picks 2 and 4 |

## 1. Autoware: the open-source reference stack

The largest open-source self-driving stack on ROS 2 (Apache-2.0). Borrow its designs,
not the whole stack: it targets ROS 2 Humble, it's large, and it's C++ (stock packages are
fine for us; "no C++ of our own").

| Read | Why |
|---|---|
| Its architecture: sensing → localization → perception → planning → control | check ours against it |
| `pid_longitudinal_controller` | PID + feed-forward for speed, with slope compensation and a "smooth stop": the same as our control plan's step 1 |
| `mpc_lateral_controller` (and its pure pursuit) | MPC steering, for the plan's step 5 |
| `ndt_scan_matcher` + `ekf_localizer` | lidar-map localization (pick 2) |

## 2. Lidar localization: map the lot with KISS-ICP, then locate in it

No RTK, so the centimetres have to come from what the lidar sees. Our VLP-16 is a 3D
lidar (16 rings, 360°).

| Step | How |
|---|---|
| 1. Record | drive the test lot slowly, record the VLP-16 and the IMU (`tools/record.sh`) |
| 2. Map | run **KISS-ICP** on the bag (`pip install kiss-icp`): lidar odometry with almost no tuning, and a point-cloud map |
| 3. Locate | match each new scan against that map: **NDT** (Normal Distributions Transform: the map in small cubes, each a blob; find the pose where the scan fits the blobs) or ICP |
| 4. Fuse | its pose into `ekf_global` beside the GPS |

**Also:** KISS-ICP's odometry alone, fused into `ekf_local`, is a better dead reckoning
than wheels at low speed. **Catch:** a bare lot gives the lidar little to match: curbs,
posts and walls help. Alternatives: FAST-LIO2, LIO-SAM (lidar + IMU), `slam_toolbox`
(2D), AMCL (a particle filter: "Ideas to keep").

## 3. A safety argument: Simplex, plus RSS

**Simplex:** a clever controller, a simple trusted one, and a monitor that switches to the
simple one before a rule is broken. We already have most of it:

| Part | Ours |
|---|---|
| Clever controllers | MPPI (Nav2), drive-to-point, the AI slot |
| Simple trusted controller | the spine: brake, latch |
| Monitors | twist_mux locks (e-stop, stop sign, sensor watchdog, the no-timeout lock), collision_monitor, the spine's 100 ms watchdog |
| Missing | a speed and area envelope independent of Nav2 (F6, the geofence) |

**RSS** (Responsibility-Sensitive Safety, Mobileye): a safe stopping distance,
`d = v·ρ + v²/(2·b)` (ρ: reaction time, b: the braking we can count on). Use it to size
collision_monitor's stop zone from measured braking, not a guess. Together these make
the final report's safety case.

## 4. Seeing from above: BEV, and camera-to-lidar calibration

| Step | What | Training? |
|---|---|---|
| **Inverse perspective mapping** | a homography warps the camera image to a top-down view (flat ground): lane lines, and a painted mark or an **AprilTag** at B for the last metre | no |
| **Camera-to-lidar calibration** | where the camera sits relative to the lidar; then each RF-DETR box gets a real distance from the lidar points inside it. Tool: `direct_visual_lidar_calibration` (Koide, open source, ROS 2) | no |
| Learned BEV (BEVFusion, BEVFormer) | all cameras and the lidar into one top-down view | yes: next year |

## Related

`docs/designs/2026-10-27_control-plan.md` (the control plan), `TODO.md` ("Ideas to keep",
"For the 2027-28 team").
