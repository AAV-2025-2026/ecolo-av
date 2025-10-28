#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

class CameraReceiver(Node):
    def __init__(self):
        super().__init__('camera_receiver')
        
        # Initialize CV Bridge
        self.bridge = CvBridge()
        
        # Subscribe to camera topic
        self.subscription = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10)
        
        self.get_logger().info('Camera Receiver Node Started')
        self.frame_count = 0
        
    def image_callback(self, msg):
        # Convert ROS Image message to OpenCV format
        cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        
        # Display the image
        cv2.imshow('Received Camera Feed', cv_image)
        cv2.waitKey(1)
        
        # Log frame rate info
        self.frame_count += 1
        if self.frame_count % 30 == 0:
            self.get_logger().info(f'Received {self.frame_count} frames')

def main(args=None):
    rclpy.init(args=args)
    receiver = CameraReceiver()
    
    try:
        rclpy.spin(receiver)
    except KeyboardInterrupt:
        pass
    finally:
        receiver.destroy_node()
        rclpy.shutdown()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
