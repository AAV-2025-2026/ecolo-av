# GNSS Starting code to read to ROS2.
#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
import serial
import pynmea2
from sensor_msgs.msg import NavSatFix
import time

class GNSSPublisher(Node):
    def __init__(self):
        super().__init__('gnss_node')
        # Publisher for NavSatFix messages
        self.pub = self.create_publisher(NavSatFix, '/gps/fix', 10)
        
        # Initialize the serial connection to the GNSS sensor
        try:
            self.ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1)  # Will Need to Update this port multiple times, for now this only reads from Linux port 0.
            self.get_logger().info("Connected to GNSS sensor.")
        except serial.SerialException as e:
            self.get_logger().error(f"Unable to connect to GNSS sensor: {e}")
            self.ser = None

        # Start publishing GNSS data
        if self.ser:
            self.timer = self.create_timer(0.1, self.publish_gnss_data)  # 10 Hz timer, will probably need to update this in the future.

    def publish_gnss_data(self):
        try:
            line = self.ser.readline().decode('ascii', errors='replace').strip()
            # Check if it's a GGA sentence, which contains GPS data
            if line.startswith('$GNGGA'):
                msg = pynmea2.parse(line)
                # Create the NavSatFix message
                gps_msg = NavSatFix()
                gps_msg.header.stamp = self.get_clock().now().to_msg()
                gps_msg.header.frame_id = "gps"
                gps_msg.latitude = msg.latitude
                gps_msg.longitude = msg.longitude
                gps_msg.altitude = msg.altitude
                # Publish the GNSS data
                self.pub.publish(gps_msg)
                self.get_logger().info(f"Published GNSS Data: Lat {msg.latitude}, Long {msg.longitude}, Alt {msg.altitude}")
        except pynmea2.ParseError as e:
            self.get_logger().warn(f"Failed to parse NMEA sentence: {e}")
        except Exception as e:
            self.get_logger().error(f"Error reading from GNSS sensor: {e}")

    def cleanup(self):
        if self.ser:
            self.ser.close()
            self.get_logger().info("Closed serial connection.")

def main(args=None):
    rclpy.init(args=args)
    node = GNSSPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.cleanup()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
