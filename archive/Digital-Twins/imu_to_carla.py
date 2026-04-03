import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu

class IMUBridge(Node):

    def __init__(self):

        super().__init__('imu_bridge')

        self.sub = self.create_subscription(
            Imu,
            '/imu/data_raw',
            self.callback,
            10)

        self.pub = self.create_publisher(
            Imu,
            '/carla/hero/imu',
            10)

    def callback(self, msg):

        self.pub.publish(msg)

        self.get_logger().info("Forwarding IMU data to CARLA")

def main():

    rclpy.init()
    node = IMUBridge()
    rclpy.spin(node)

if __name__ == '__main__':
    main()
