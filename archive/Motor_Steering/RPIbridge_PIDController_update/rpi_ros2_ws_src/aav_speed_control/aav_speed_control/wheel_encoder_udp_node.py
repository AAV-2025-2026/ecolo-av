#!/usr/bin/env python3
from __future__ import annotations

import json
import socket
from typing import Optional

import rclpy
from rclpy.node import Node

from std_msgs.msg import Int32, String


class WheelEncoderUdpNode(Node):
    def __init__(self) -> None:
        super().__init__('wheel_encoder_udp')

        self.declare_parameter('bind_host', '0.0.0.0')
        self.declare_parameter('bind_port', 5000)
        self.declare_parameter('expected_period_ms', 100)
        self.declare_parameter('packet_timeout_ms', 300)
        self.declare_parameter('poll_rate_hz', 200.0)

        bind_host = str(self.get_parameter('bind_host').value)
        bind_port = int(self.get_parameter('bind_port').value)
        poll_rate_hz = float(self.get_parameter('poll_rate_hz').value)

        self.count_pub = self.create_publisher(Int32, '/wheel_encoder/count', 20)
        self.status_pub = self.create_publisher(String, '/wheel_encoder/status', 10)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((bind_host, bind_port))
        self.sock.setblocking(False)

        self.last_rx_time = self.get_clock().now()
        self.last_sender: Optional[str] = None
        self.packet_count = 0

        self.timer = self.create_timer(1.0 / max(1.0, poll_rate_hz), self.on_timer)

        self.get_logger().info(f'Listening for encoder UDP on {bind_host}:{bind_port}')

    def on_timer(self) -> None:
        got_packet = False
        while True:
            try:
                data, addr = self.sock.recvfrom(64)
            except BlockingIOError:
                break
            except Exception as exc:
                self.get_logger().error(f'UDP receive error: {exc}')
                break

            got_packet = True
            self.last_rx_time = self.get_clock().now()
            self.last_sender = f'{addr[0]}:{addr[1]}'
            self.packet_count += 1

            if len(data) != 4:
                self.get_logger().warn(f'Ignoring UDP payload with size {len(data)} from {self.last_sender}')
                continue

            count = int.from_bytes(data, byteorder='big', signed=True)
            msg = Int32()
            msg.data = count
            self.count_pub.publish(msg)

        age_ms = (self.get_clock().now() - self.last_rx_time).nanoseconds / 1e6
        status = String()
        status.data = json.dumps({
            'packet_count': self.packet_count,
            'last_sender': self.last_sender,
            'age_ms': round(age_ms, 1),
            'timed_out': age_ms > float(self.get_parameter('packet_timeout_ms').value),
            'got_packet_this_spin': got_packet,
        })
        self.status_pub.publish(status)


def main() -> None:
    rclpy.init()
    node = WheelEncoderUdpNode()
    try:
        rclpy.spin(node)
    finally:
        try:
            node.sock.close()
        except Exception:
            pass
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
