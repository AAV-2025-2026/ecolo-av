import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

class CameraBridge(Node):

    def __init__(self):

        super().__init__('camera_bridge')

        self.sub = self.create_subscription(
            Image,
            '/camera/cam1/image_raw',
            self.callback,
            10)

        self.pub = self.create_publisher(
            Image,
            '/carla/hero/rgb_front/image',
            10)

    def callback(self, msg):

        self.pub.publish(msg)

        self.get_logger().info("Forwarding camera scan to CARLA")

def main():

    rclpy.init()
    node = CameraBridge()
    rclpy.spin(node)

if __name__ == '__main__':
    main()
