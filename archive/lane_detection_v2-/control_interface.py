#!/usr/bin/env python3
"""
control_interface.py  —  lane_geometry package  [IMPROVED v3]
═══════════════════════════════════════════════════════════════════
Added in v3:
  ✅ LANE CHANGE HANDLER
  ✅ INTERSECTION / NO-LANE HANDLER

Both use the same simple, safe logic:
  "Stop when unsure. Wait. Continue when lanes are seen again."

═══════════════════════════════════════════════════════════════════
LANE CHANGE BEHAVIOUR
═══════════════════════════════════════════════════════════════════
Problem:
  The vehicle begins moving sideways (intentional lane change).
  The PID controller sees a large offset and fights it —
  trying to steer back to the original lane centre.

Fix — 3-state machine:

  LANE_KEEP (normal)
    │
    │  offset grows fast  (rate > LANE_CHANGE_RATE_THRESHOLD)
    │  AND offset > LANE_CHANGE_OFFSET_THRESHOLD
    ▼
  LANE_CHANGING
    │  Vehicle slows to LANE_CHANGE_SPEED
    │  PID is SUPPRESSED — do not fight the lateral movement
    │  Steering holds the current gentle angle
    │
    │  offset starts SHRINKING  (vehicle centring on new lane)
    ▼
  LANE_COMMITTED
    │  New lane centre found
    │  Reset PID
    │  Resume normal LANE_KEEP speed
    ▼
  LANE_KEEP  (on new lane)

If the manoeuvre takes too long (> LANE_CHANGE_TIMEOUT):
  → STOP → wait for lanes → resume

═══════════════════════════════════════════════════════════════════
INTERSECTION / NO-LANE BEHAVIOUR
═══════════════════════════════════════════════════════════════════
Problem:
  Lane markings disappear at intersections.
  Current code: stops after 1 second and stays stopped forever.

Fix — 3-state machine:

  NORMAL (lanes visible)
    │
    │  both lanes lost
    ▼
  NO_LANE_STOPPING
    │  Vehicle decelerates smoothly to a stop
    │  Steering holds last known heading
    │  Waits...
    │
    │  one or both lanes reappear
    ▼
  RESUMING
    │  Gentle acceleration back to base speed
    │  PID resumes on new lane readings
    ▼
  NORMAL

This handles:
  - Intersections           (lanes disappear, then reappear on exit)
  - Occlusion by vehicles   (temporary loss then recovery)
  - Lane change gap         (brief loss during lane transition)
  - Shadow / detection fail (short loss then recovery)

═══════════════════════════════════════════════════════════════════
Topics subscribed:
  /lane_geometry          lane_geometry/LaneGeometry

Topics published:
  /control_cmd            geometry_msgs/Twist
  /lane_geometry_status   std_msgs/String
  /vehicle_state          std_msgs/String   (current state machine state)
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String
from lane_geometry.msg import LaneGeometry
import numpy as np
import time


# ══════════════════════════════════════════════════════════════════════
# State definitions
# ══════════════════════════════════════════════════════════════════════

class VehicleState:
    # Normal lane keeping
    LANE_KEEP    = "LANE_KEEP"
    # Lane change states
    LANE_CHANGING   = "LANE_CHANGING"
    LANE_COMMITTED  = "LANE_COMMITTED"
    # No-lane / intersection states
    NO_LANE_STOPPING = "NO_LANE_STOPPING"
    RESUMING         = "RESUMING"


# ══════════════════════════════════════════════════════════════════════
# PID Controller
# ══════════════════════════════════════════════════════════════════════

class PID:
    def __init__(self, kp=0.8, ki=0.01, kd=0.3):
        self.kp, self.ki, self.kd = kp, ki, kd
        self._integral  = 0.0
        self._prev_err  = 0.0
        self._prev_time = time.time()

    def compute(self, error: float) -> float:
        now = time.time()
        dt  = max(now - self._prev_time, 1e-4)
        self._integral  += error * dt
        derivative       = (error - self._prev_err) / dt
        out = (self.kp * error +
               self.ki * self._integral +
               self.kd * derivative)
        self._prev_err  = error
        self._prev_time = now
        return out

    def reset(self):
        self._integral = 0.0
        self._prev_err = 0.0


# ══════════════════════════════════════════════════════════════════════
# Main control node
# ══════════════════════════════════════════════════════════════════════

class ControlInterface(Node):

    def __init__(self):
        super().__init__('control_interface')

        # ── Base driving parameters ───────────────────────────────────
        self.declare_parameter('base_speed_mps',       2.0)
        self.declare_parameter('max_angular_z',        0.5)
        self.declare_parameter('min_speed_mps',        0.3)
        self.declare_parameter('min_curvature_m',     20.0)

        # ── Lane change parameters ────────────────────────────────────
        # Offset rate threshold: if offset changes faster than this
        # m/s it is treated as an intentional lane change
        self.declare_parameter('lane_change_rate_threshold',   0.05)
        # Offset magnitude that triggers lane change detection
        self.declare_parameter('lane_change_offset_threshold', 0.40)
        # Speed to drive during lane change manoeuvre
        self.declare_parameter('lane_change_speed',            1.0)
        # Max time allowed for a lane change before giving up
        self.declare_parameter('lane_change_timeout_s',        8.0)

        # ── No-lane / intersection parameters ────────────────────────
        # How long to wait stopped before checking for lanes again
        self.declare_parameter('stop_wait_s',                  2.0)
        # Deceleration rate when stopping (m/s per second)
        self.declare_parameter('decel_rate',                   0.5)
        # Acceleration rate when resuming (m/s per second)
        self.declare_parameter('accel_rate',                   0.3)

        # ── PID parameters ────────────────────────────────────────────
        self.declare_parameter('pid_kp', 0.8)
        self.declare_parameter('pid_ki', 0.01)
        self.declare_parameter('pid_kd', 0.3)

        # Load all parameters
        self.base_speed   = self.get_parameter('base_speed_mps').value
        self.max_ang      = self.get_parameter('max_angular_z').value
        self.min_speed    = self.get_parameter('min_speed_mps').value
        self.min_curv     = self.get_parameter('min_curvature_m').value

        self.lc_rate_thr  = self.get_parameter('lane_change_rate_threshold').value
        self.lc_off_thr   = self.get_parameter('lane_change_offset_threshold').value
        self.lc_speed     = self.get_parameter('lane_change_speed').value
        self.lc_timeout   = self.get_parameter('lane_change_timeout_s').value

        self.stop_wait    = self.get_parameter('stop_wait_s').value
        self.decel_rate   = self.get_parameter('decel_rate').value
        self.accel_rate   = self.get_parameter('accel_rate').value

        self.pid = PID(
            kp=self.get_parameter('pid_kp').value,
            ki=self.get_parameter('pid_ki').value,
            kd=self.get_parameter('pid_kd').value,
        )

        # ── State machine ─────────────────────────────────────────────
        self.state           = VehicleState.LANE_KEEP
        self.current_speed   = 0.0
        self.last_steer      = 0.0
        self.last_offset     = 0.0
        self.offset_rate     = 0.0
        self.state_entry_t   = time.time()
        self.last_msg_t      = time.time()

        # Lane change tracking
        self.lc_peak_offset  = 0.0   # largest offset seen during lane change

        # ── ROS2 ──────────────────────────────────────────────────────
        self.sub = self.create_subscription(
            LaneGeometry, '/lane_geometry', self.geometry_cb, 10)

        self.pub_cmd    = self.create_publisher(Twist,  '/control_cmd',          10)
        self.pub_stat   = self.create_publisher(String, '/lane_geometry_status', 10)
        self.pub_vstate = self.create_publisher(String, '/vehicle_state',        10)

        # Watchdog at 10 Hz
        self.create_timer(0.1, self.watchdog_cb)

        self.get_logger().info(
            "\n╔══ Control Interface v3 ══════════════════════════╗"
            "\n║  Lane change:   stop + wait + resume on new lane ║"
            "\n║  Intersection:  stop + wait + resume on re-detect║"
            "\n╚══════════════════════════════════════════════════╝"
        )

    # ══════════════════════════════════════════════════════════════════
    # Main geometry callback
    # ══════════════════════════════════════════════════════════════════

    def geometry_cb(self, msg: LaneGeometry):
        self.last_msg_t = time.time()
        now = time.time()

        # Compute offset rate of change (m/s)
        dt = max(now - getattr(self, '_last_t', now), 1e-4)
        self._last_t     = now
        self.offset_rate = (msg.vehicle_offset_m - self.last_offset) / dt
        self.last_offset = msg.vehicle_offset_m

        lanes_ok = msg.left_lane_detected or msg.right_lane_detected

        # ── Route to correct state handler ────────────────────────────
        if self.state == VehicleState.LANE_KEEP:
            self.handle_lane_keep(msg, lanes_ok)

        elif self.state == VehicleState.LANE_CHANGING:
            self.handle_lane_changing(msg, lanes_ok)

        elif self.state == VehicleState.LANE_COMMITTED:
            self.handle_lane_committed(msg, lanes_ok)

        elif self.state == VehicleState.NO_LANE_STOPPING:
            self.handle_no_lane_stopping(msg, lanes_ok)

        elif self.state == VehicleState.RESUMING:
            self.handle_resuming(msg, lanes_ok)

        # Publish vehicle state for monitoring
        vs = String(); vs.data = self.state
        self.pub_vstate.publish(vs)

    # ══════════════════════════════════════════════════════════════════
    # State handlers
    # ══════════════════════════════════════════════════════════════════

    def handle_lane_keep(self, msg: LaneGeometry, lanes_ok: bool):
        """
        Normal lane keeping.
        Checks for lane change intent or lane loss.
        """
        # ── Check for lane loss → intersection ────────────────────────
        if not lanes_ok:
            self.get_logger().info(
                "Lanes lost → entering NO_LANE_STOPPING")
            self.transition(VehicleState.NO_LANE_STOPPING)
            return

        # ── Check for lane change intent ──────────────────────────────
        # Trigger if offset is large AND growing fast
        offset_large = abs(msg.vehicle_offset_m) > self.lc_off_thr
        offset_fast  = abs(self.offset_rate)     > self.lc_rate_thr

        if offset_large and offset_fast:
            self.get_logger().info(
                f"Lane change detected: "
                f"offset={msg.vehicle_offset_m:+.2f}m "
                f"rate={self.offset_rate:+.3f}m/s "
                f"→ LANE_CHANGING"
            )
            self.lc_peak_offset = abs(msg.vehicle_offset_m)
            self.transition(VehicleState.LANE_CHANGING)
            return

        # ── Normal lane keeping ───────────────────────────────────────
        cmd = self.build_cmd_lane_keep(msg)
        self.pub_cmd.publish(cmd)
        self.publish_status(msg, "LANE_KEEP")

    def handle_lane_changing(self, msg: LaneGeometry, lanes_ok: bool):
        """
        Lane change in progress.
        Suppress PID — do NOT fight the lateral movement.
        Slow down. Wait for offset to reduce (vehicle centring on new lane).
        """
        elapsed = time.time() - self.state_entry_t

        # ── Timeout safety ────────────────────────────────────────────
        if elapsed > self.lc_timeout:
            self.get_logger().warn(
                f"Lane change timed out after {elapsed:.1f}s → stopping")
            self.transition(VehicleState.NO_LANE_STOPPING)
            return

        # ── Check if lanes completely lost ────────────────────────────
        if not lanes_ok:
            self.get_logger().info(
                "Lanes lost during lane change → NO_LANE_STOPPING")
            self.transition(VehicleState.NO_LANE_STOPPING)
            return

        # ── Track peak offset ─────────────────────────────────────────
        curr_abs = abs(msg.vehicle_offset_m)
        self.lc_peak_offset = max(self.lc_peak_offset, curr_abs)

        # ── Detect offset REDUCING — vehicle is centring on new lane ──
        # When offset has reduced by >50% from peak → commit to new lane
        offset_reducing = (curr_abs < self.lc_peak_offset * 0.5)

        if offset_reducing and curr_abs < self.lc_off_thr * 0.5:
            self.get_logger().info(
                f"Lane change complete: offset now {curr_abs:.2f}m "
                f"→ LANE_COMMITTED"
            )
            self.transition(VehicleState.LANE_COMMITTED)
            return

        # ── Drive slowly, hold steering, suppress PID ─────────────────
        cmd = Twist()
        cmd.linear.x  = self.lc_speed
        cmd.angular.z = self.last_steer  # hold last steering angle
        self.pub_cmd.publish(cmd)
        self.current_speed = self.lc_speed

        self.publish_status(msg,
            f"LANE_CHANGING | offset={msg.vehicle_offset_m:+.2f}m "
            f"peak={self.lc_peak_offset:.2f}m t={elapsed:.1f}s")

    def handle_lane_committed(self, msg: LaneGeometry, lanes_ok: bool):
        """
        Just completed a lane change.
        Reset PID, resume speed, transition back to LANE_KEEP.
        """
        self.pid.reset()
        self.get_logger().info("Lane committed → resuming LANE_KEEP on new lane")
        self.transition(VehicleState.LANE_KEEP)
        # Immediately process this frame as LANE_KEEP
        self.handle_lane_keep(msg, lanes_ok)

    def handle_no_lane_stopping(self, msg: LaneGeometry, lanes_ok: bool):
        """
        No lanes visible (intersection, occlusion, detection failure).

        Phase 1 — Decelerate smoothly to a stop.
        Phase 2 — Wait stopped. Keep checking for lanes.
        Phase 3 — As soon as lanes reappear → RESUMING.
        """
        elapsed = time.time() - self.state_entry_t

        # ── Lanes reappeared → resume immediately ─────────────────────
        if lanes_ok:
            self.get_logger().info(
                f"Lanes reappeared after {elapsed:.1f}s → RESUMING")
            self.transition(VehicleState.RESUMING)
            return

        # ── Phase 1: Decelerate to stop ───────────────────────────────
        if self.current_speed > 0.0:
            self.current_speed = max(
                0.0,
                self.current_speed - self.decel_rate * 0.1  # 10Hz timer
            )
            cmd = Twist()
            cmd.linear.x  = self.current_speed
            cmd.angular.z = self.last_steer  # hold heading
            self.pub_cmd.publish(cmd)

            self.publish_status(msg,
                f"NO_LANE: decelerating {self.current_speed:.2f}m/s | "
                f"t={elapsed:.1f}s")

        # ── Phase 2: Stopped — wait for lanes ────────────────────────
        else:
            self.pub_cmd.publish(Twist())  # full stop
            self.publish_status(msg,
                f"STOPPED: waiting for lanes | {elapsed:.1f}s elapsed | "
                f"watching /lane_mask_unified...")

            # Log every 2 seconds so operator knows vehicle is waiting
            if int(elapsed) % 2 == 0:
                self.get_logger().info(
                    f"Stopped at lane loss. Waiting for lanes. "
                    f"Elapsed: {elapsed:.0f}s",
                    throttle_duration_sec=2.0)

    def handle_resuming(self, msg: LaneGeometry, lanes_ok: bool):
        """
        Lanes reappeared. Accelerate gently back to base speed.
        Transition to LANE_KEEP once up to speed.
        """
        # ── Lane lost again before we got up to speed ─────────────────
        if not lanes_ok:
            self.get_logger().warn("Lane lost again during resume → stopping")
            self.transition(VehicleState.NO_LANE_STOPPING)
            return

        # ── Accelerate gently ─────────────────────────────────────────
        self.current_speed = min(
            self.base_speed,
            self.current_speed + self.accel_rate * 0.1  # 10Hz timer
        )

        cmd = self.build_cmd_lane_keep(msg)
        cmd.linear.x = self.current_speed  # override with ramp speed
        self.pub_cmd.publish(cmd)

        self.publish_status(msg,
            f"RESUMING: {self.current_speed:.2f}/{self.base_speed:.1f} m/s")

        # Fully up to speed → back to normal
        if self.current_speed >= self.base_speed * 0.95:
            self.get_logger().info("Up to speed → LANE_KEEP")
            self.transition(VehicleState.LANE_KEEP)

    # ══════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════

    def build_cmd_lane_keep(self, msg: LaneGeometry) -> Twist:
        """Build a Twist command for normal lane keeping."""
        cmd = Twist()

        speed = self.base_speed
        if not msg.both_lanes_detected:
            speed *= 0.7
        if 0 < msg.mean_curvature_m < self.min_curv:
            speed *= max(0.4, msg.mean_curvature_m / self.min_curv)

        cmd.linear.x = float(max(self.min_speed, speed))
        self.current_speed = cmd.linear.x

        steer = self.pid.compute(-msg.vehicle_offset_m)
        cmd.angular.z = float(np.clip(steer, -self.max_ang, self.max_ang))
        self.last_steer = cmd.angular.z

        return cmd

    def transition(self, new_state: str):
        """Change state and record entry time."""
        old = self.state
        self.state        = new_state
        self.state_entry_t = time.time()
        self.get_logger().info(f"State: {old} → {new_state}")
        if new_state in (VehicleState.LANE_KEEP,
                         VehicleState.LANE_COMMITTED):
            self.pid.reset()

    def publish_status(self, msg: LaneGeometry, extra: str = ""):
        s = String()
        s.data = (
            f"[{self.state}] "
            f"offset={msg.vehicle_offset_m:+.3f}m | "
            f"curv={msg.mean_curvature_m:.0f}m | "
            f"speed={self.current_speed:.2f}m/s | "
            f"{extra}"
        )
        self.pub_stat.publish(s)

    def watchdog_cb(self):
        """
        Watchdog: if no geometry message for >2s and not already stopped,
        transition to NO_LANE_STOPPING.
        """
        elapsed = time.time() - self.last_msg_t
        if (elapsed > 2.0 and
                self.state not in (VehicleState.NO_LANE_STOPPING,)):
            self.get_logger().warn(
                f"No geometry message for {elapsed:.1f}s → stopping",
                throttle_duration_sec=2.0)
            self.pub_cmd.publish(Twist())
            if self.state != VehicleState.NO_LANE_STOPPING:
                self.transition(VehicleState.NO_LANE_STOPPING)


def main(args=None):
    rclpy.init(args=args)
    node = ControlInterface()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
