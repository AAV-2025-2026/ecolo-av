#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import NavSatFix

class GNSSSubscriber(Node):
    def __init__(self):
        super().__init__('gnss_subscriber_node')
        
        # Create a subscriber to the /gps/fix topic
        self.sub = self.create_subscription(
            NavSatFix, 
            '/gps/fix',  # Topic name
            self.gnss_callback,  # Callback function
            10  # QoS history depth
        )

    def gnss_callback(self, msg):
        # Process the received GNSS data
        latitude = msg.latitude
        longitude = msg.longitude
        altitude = msg.altitude
        
        # Print or log the data
        self.get_logger().info(f"Received GNSS Data: Lat {latitude}, Long {longitude}, Alt {altitude}")

def main(args=None):
    rclpy.init(args=args)
    node = GNSSSubscriber()
    try:
        rclpy.spin(node)  # Keep the subscriber running
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
