#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import serial

class RadarSerialPublisher(Node):
    def __init__(self):
        super().__init__("radar_serial_publisher")
        self.declare_parameter('serial_port', '/dev/ttyACM0')
        self.declare_parameter('baud_rate', 115200)
        port = self.get_parameter('serial_port').value
        baud = self.get_parameter('baud_rate').value
        self.ser = serial.Serial(port, baud, timeout=0.05)
        self.pub = self.create_publisher(String, "radar/raw_can", 50)
        self.create_timer(0.01, self.read_and_publish)
        self.get_logger().info(f"Connected to {port} @ {baud}")

    def read_and_publish(self):
        line = self.ser.readline().decode(errors="ignore").strip()
        if "#" not in line:
            return
        msg = String()
        msg.data = line
        self.pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = RadarSerialPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()

