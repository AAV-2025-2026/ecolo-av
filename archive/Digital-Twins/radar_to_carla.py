import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2

class RadarBridge(Node):

    def __init__(self):

        super().__init__('radar_bridge')

        self.sub = self.create_subscription(
            PointCloud2,
            '/iwr6843_pcl',
            self.callback,
            10)

        self.pub = self.create_publisher(
            PointCloud2,
            '/carla/hero/radar_front',
            10)

    def callback(self, msg):

        self.pub.publish(msg)

        self.get_logger().info("Forwarding radar scan to CARLA")

def main():

    rclpy.init()
    node = RadarBridge()
    rclpy.spin(node)

if __name__ == '__main__':
    main()
