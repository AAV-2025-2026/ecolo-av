#!/usr/bin/env python3
from __future__ import annotations

import math
import time
from typing import Optional

import rclpy
from rclpy.node import Node

from ackermann_msgs.msg import AckermannDriveStamped, AckermannDrive

import serial  # pyserial

from .protocol import CmdFrame, pack_frame


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


class AckermannUartBridge(Node):
    """
    Subscribes to AckermannDrive(Stamped), converts + clamps, and sends fixed-length frames to ESP32 via UART.

    You can run it in two modes:
      - "standard" mode: steering_angle is radians; acceleration is m/s^2 (optional)
      - "raw" mode: treat steering_angle and acceleration as already in ESP32-friendly units

    Default behavior:
      - steering_angle assumed radians (steer_in_is_rad=True)
      - acceleration treated as "raw" (accel_in_is_mps2=False)
      - acceleration >= 0 => forward throttle
      - acceleration <  0 => brake (magnitude = -acceleration)
    """

    def __init__(self) -> None:
        super().__init__("ackermann_uart_bridge")

        # --- parameters ---
        self.declare_parameter("input_topic", "/ackermann_cmd")
        self.declare_parameter("input_is_stamped", True)

        self.declare_parameter("uart_port", "/dev/serial0")
        self.declare_parameter("uart_baud", 115200)

        self.declare_parameter("tx_rate_hz", 50.0)
        self.declare_parameter("timeout_ms", 250)

        # Steering conversion
        self.declare_parameter("steer_in_is_rad", True)
        self.declare_parameter("steer_max_rad", 0.45)       # tune to your rack
        self.declare_parameter("steer_cmd_max", 2000.0)     # ESP32 expects about [-2000..2000]
        self.declare_parameter("steer_deadzone_rad", 0.0)

        # Accel conversion
        self.declare_parameter("accel_in_is_mps2", False)
        self.declare_parameter("accel_to_throttle", 1.0)    # if accel is already 0..1023-ish, keep 1.0
        self.declare_parameter("accel_to_brake", 1.0)
        self.declare_parameter("throttle_max", 250)         # safety cap (0..1023)
        self.declare_parameter("brake_max", 4095)            # safety cap (0..4095)

        # Direction semantics
        self.declare_parameter("dir_fwd_when_accel_positive", True)

        # Arming
        self.declare_parameter("start_armed", False)         # safer default
        self.declare_parameter("start_estop", True)          # safer default

        self.input_topic = str(self.get_parameter("input_topic").value)
        self.input_is_stamped = bool(self.get_parameter("input_is_stamped").value)

        self.port = str(self.get_parameter("uart_port").value)
        self.baud = int(self.get_parameter("uart_baud").value)

        self.tx_rate_hz = float(self.get_parameter("tx_rate_hz").value)
        self.timeout_ms = int(self.get_parameter("timeout_ms").value)

        self.armed = bool(self.get_parameter("start_armed").value)
        self.estop = bool(self.get_parameter("start_estop").value)

        # --- state ---
        self.last_rx_time = self.get_clock().now()
        self.last_drive: AckermannDrive = AckermannDrive()
        self.seq = 0

        # --- serial ---
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baud,
            timeout=0.0,          # non-blocking
            write_timeout=0.02
        )

        # --- ROS subscriptions ---
        if self.input_is_stamped:
            self.sub = self.create_subscription(
                AckermannDriveStamped, self.input_topic, self.on_drive_stamped, 10
            )
        else:
            self.sub = self.create_subscription(
                AckermannDrive, self.input_topic, self.on_drive, 10
            )

        # --- timers ---
        period = 1.0 / max(1.0, self.tx_rate_hz)
        self.timer = self.create_timer(period, self.on_timer)

        self.get_logger().info(
            f"UART bridge ready. Sub: {self.input_topic} "
            f"({'Stamped' if self.input_is_stamped else 'Unstamped'}) -> UART {self.port}@{self.baud}"
        )
        self.get_logger().info(
            "Safety defaults: start_estop=True, start_armed=False. "
            "Set start_estop:=false and start_armed:=true once wiring is verified."
        )

    # -------- ROS callbacks --------
    def on_drive_stamped(self, msg: AckermannDriveStamped) -> None:
        self.last_rx_time = self.get_clock().now()
        self.last_drive = msg.drive

    def on_drive(self, msg: AckermannDrive) -> None:
        self.last_rx_time = self.get_clock().now()
        self.last_drive = msg

    # -------- conversion + send --------
    def build_cmd(self) -> CmdFrame:
        # Deadman: if stale, send stop + disarm
        age_ms = (self.get_clock().now() - self.last_rx_time).nanoseconds / 1e6
        if age_ms > self.timeout_ms:
            return CmdFrame(
                seq=self.seq,
                armed=False,
                estop=True,   # force safe on link loss
                dir_fwd=True,
                steer=0,
                throttle=0,
                brake=0,
            )

        d = self.last_drive

        # Steering
        steer = float(d.steering_angle)
        steer_in_is_rad = bool(self.get_parameter("steer_in_is_rad").value)
        steer_deadzone = float(self.get_parameter("steer_deadzone_rad").value)
        steer_cmd_max = float(self.get_parameter("steer_cmd_max").value)

        if steer_in_is_rad:
            if abs(steer) < steer_deadzone:
                steer = 0.0
            steer_max_rad = float(self.get_parameter("steer_max_rad").value)
            steer = clamp(steer, -steer_max_rad, steer_max_rad)
            steer_cmd = int(round((steer / steer_max_rad) * steer_cmd_max)) if steer_max_rad > 1e-6 else 0
        else:
            steer_cmd = int(round(clamp(steer, -steer_cmd_max, steer_cmd_max)))

        # Throttle / brake from acceleration sign
        a = float(d.acceleration)
        dir_pos_fwd = bool(self.get_parameter("dir_fwd_when_accel_positive").value)

        accel_in_is_mps2 = bool(self.get_parameter("accel_in_is_mps2").value)
        thr_scale = float(self.get_parameter("accel_to_throttle").value)
        brk_scale = float(self.get_parameter("accel_to_brake").value)

        throttle_max = int(self.get_parameter("throttle_max").value)
        brake_max = int(self.get_parameter("brake_max").value)

        throttle = 0
        brake = 0
        dir_fwd = True

        if a >= 0.0:
            # forward throttle
            dir_fwd = dir_pos_fwd
            val = a * thr_scale
            throttle = int(round(clamp(val, 0.0, float(throttle_max))))
            brake = 0
        else:
            # braking
            dir_fwd = dir_pos_fwd  # still "forward" direction while braking
            val = (-a) * brk_scale
            brake = int(round(clamp(val, 0.0, float(brake_max))))
            throttle = 0

        # Note: accel_in_is_mps2 is here in case you later want to treat acceleration as m/s^2.
        # For now, scaling parameters already control mapping; keep accel_in_is_mps2=False unless you implement a specific mapping.

        return CmdFrame(
            seq=self.seq,
            armed=self.armed,
            estop=self.estop,
            dir_fwd=dir_fwd,
            steer=steer_cmd,
            throttle=throttle,
            brake=brake,
        )

    def send_cmd(self, cmd: CmdFrame) -> None:
        frame = pack_frame(cmd)
        try:
            self.ser.write(frame)
        except serial.SerialTimeoutException:
            self.get_logger().warn("UART write timeout")
        except Exception as e:
            self.get_logger().error(f"UART write error: {e}")

    def on_timer(self) -> None:
        cmd = self.build_cmd()
        cmd.seq = self.seq
        self.send_cmd(cmd)
        self.seq = (self.seq + 1) & 0xFF


def main() -> None:
    rclpy.init()
    node = AckermannUartBridge()
    try:
        rclpy.spin(node)
    finally:
        try:
            node.ser.close()
        except Exception:
            pass
        node.destroy_node()
        rclpy.shutdown()
