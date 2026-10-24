import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2

class LidarBridge(Node):

    def __init__(self):
        super().__init__('lidar_bridge')

        self.sub = self.create_subscription(
            PointCloud2,
            '/velodyne_points',
            self.callback,
            10
        )

        self.pub = self.create_publisher(
            PointCloud2,
            '/carla/hero/lidar',
            10
        )

    def callback(self, msg):
        msg.header.frame_id = "carla/hero/lidar"
        self.pub.publish(msg)
        self.get_logger().info("Forwarding Velodyne scan to CARLA")

def main():
    rclpy.init()
    node = LidarBridge()
    rclpy.spin(node)

if __name__ == '__main__':
    main()
