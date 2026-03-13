#!/usr/bin/env python3
from __future__ import annotations

import json
from typing import Optional

import rclpy
from rclpy.node import Node

from ackermann_msgs.msg import AckermannDrive, AckermannDriveStamped
from std_msgs.msg import String

import serial

from .protocol import CmdFrame, pack_frame


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


class AckermannUartBridge(Node):
    def __init__(self) -> None:
        super().__init__('ackermann_uart_bridge')

        self.declare_parameter('input_topic', '/ackermann_cmd')
        self.declare_parameter('input_is_stamped', True)
        self.declare_parameter('uart_port', '/dev/serial0')
        self.declare_parameter('uart_baud', 115200)
        self.declare_parameter('tx_rate_hz', 50.0)
        self.declare_parameter('timeout_ms', 250)
        self.declare_parameter('steer_in_is_rad', True)
        self.declare_parameter('steer_max_rad', 0.45)
        self.declare_parameter('steer_cmd_max', 2000.0)
        self.declare_parameter('steer_deadzone_rad', 0.0)
        self.declare_parameter('accel_to_throttle', 1.0)
        self.declare_parameter('accel_to_brake', 1.0)
        self.declare_parameter('throttle_max', 250)
        self.declare_parameter('brake_max', 4095)
        self.declare_parameter('direction_source', 'speed')  # speed or accel
        self.declare_parameter('dir_fwd_when_positive', True)
        self.declare_parameter('start_armed', False)
        self.declare_parameter('start_estop', True)

        self.input_topic = str(self.get_parameter('input_topic').value)
        self.input_is_stamped = bool(self.get_parameter('input_is_stamped').value)
        self.port = str(self.get_parameter('uart_port').value)
        self.baud = int(self.get_parameter('uart_baud').value)
        self.tx_rate_hz = float(self.get_parameter('tx_rate_hz').value)
        self.timeout_ms = int(self.get_parameter('timeout_ms').value)
        self.armed = bool(self.get_parameter('start_armed').value)
        self.estop = bool(self.get_parameter('start_estop').value)

        self.last_rx_time = self.get_clock().now()
        self.last_drive: AckermannDrive = AckermannDrive()
        self.seq = 0
        self.last_cmd: Optional[CmdFrame] = None

        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baud,
            timeout=0.0,
            write_timeout=0.02,
        )

        if self.input_is_stamped:
            self.sub = self.create_subscription(
                AckermannDriveStamped, self.input_topic, self.on_drive_stamped, 10
            )
        else:
            self.sub = self.create_subscription(
                AckermannDrive, self.input_topic, self.on_drive, 10
            )

        self.status_pub = self.create_publisher(String, '/aav_bridge_status', 10)
        period = 1.0 / max(1.0, self.tx_rate_hz)
        self.timer = self.create_timer(period, self.on_timer)

        self.get_logger().info(
            f'UART bridge ready: {self.input_topic} -> {self.port}@{self.baud}'
        )
        self.get_logger().info(
            'Default safety state is disarmed + estop asserted. Update params before live testing.'
        )

    def on_drive_stamped(self, msg: AckermannDriveStamped) -> None:
        self.last_rx_time = self.get_clock().now()
        self.last_drive = msg.drive

    def on_drive(self, msg: AckermannDrive) -> None:
        self.last_rx_time = self.get_clock().now()
        self.last_drive = msg

    def build_cmd(self) -> tuple[CmdFrame, bool]:
        age_ms = (self.get_clock().now() - self.last_rx_time).nanoseconds / 1e6
        stale = age_ms > self.timeout_ms
        if stale:
            return CmdFrame(
                seq=self.seq,
                armed=False,
                estop=True,
                dir_fwd=True,
                steer=0,
                throttle=0,
                brake=0,
            ), True

        d = self.last_drive
        steer = float(d.steering_angle)
        steer_in_is_rad = bool(self.get_parameter('steer_in_is_rad').value)
        steer_deadzone = float(self.get_parameter('steer_deadzone_rad').value)
        steer_cmd_max = float(self.get_parameter('steer_cmd_max').value)

        if steer_in_is_rad:
            steer_max_rad = float(self.get_parameter('steer_max_rad').value)
            if abs(steer) < steer_deadzone:
                steer = 0.0
            steer = clamp(steer, -steer_max_rad, steer_max_rad)
            steer_cmd = int(round((steer / steer_max_rad) * steer_cmd_max)) if steer_max_rad > 1e-6 else 0
        else:
            steer_cmd = int(round(clamp(steer, -steer_cmd_max, steer_cmd_max)))

        a = float(d.acceleration)
        throttle_max = int(self.get_parameter('throttle_max').value)
        brake_max = int(self.get_parameter('brake_max').value)
        thr_scale = float(self.get_parameter('accel_to_throttle').value)
        brk_scale = float(self.get_parameter('accel_to_brake').value)

        throttle = 0
        brake = 0
        if a >= 0.0:
            throttle = int(round(clamp(a * thr_scale, 0.0, float(throttle_max))))
        else:
            brake = int(round(clamp((-a) * brk_scale, 0.0, float(brake_max))))

        direction_source = str(self.get_parameter('direction_source').value).strip().lower()
        dir_pos_fwd = bool(self.get_parameter('dir_fwd_when_positive').value)
        if direction_source == 'accel':
            reference = a
        else:
            reference = float(d.speed)
        dir_fwd = dir_pos_fwd if reference >= 0.0 else (not dir_pos_fwd)

        cmd = CmdFrame(
            seq=self.seq,
            armed=self.armed,
            estop=self.estop,
            dir_fwd=dir_fwd,
            steer=steer_cmd,
            throttle=throttle,
            brake=brake,
        )
        return cmd, False

    def publish_status(self, cmd: CmdFrame, stale: bool) -> None:
        msg = String()
        msg.data = json.dumps({
            'seq': int(cmd.seq),
            'armed': bool(cmd.armed),
            'estop': bool(cmd.estop),
            'dir_fwd': bool(cmd.dir_fwd),
            'steer_cmd': int(cmd.steer),
            'throttle_cmd': int(cmd.throttle),
            'brake_cmd': int(cmd.brake),
            'stale_input': bool(stale),
            'uart_port': self.port,
            'uart_baud': self.baud,
        })
        self.status_pub.publish(msg)

    def send_cmd(self, cmd: CmdFrame) -> None:
        frame = pack_frame(cmd)
        self.ser.write(frame)

    def on_timer(self) -> None:
        cmd, stale = self.build_cmd()
        cmd.seq = self.seq
        try:
            self.send_cmd(cmd)
            self.last_cmd = cmd
        except serial.SerialTimeoutException:
            self.get_logger().warn('UART write timeout')
        except Exception as exc:
            self.get_logger().error(f'UART write error: {exc}')
        self.publish_status(cmd, stale)
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


if __name__ == '__main__':
    main()
