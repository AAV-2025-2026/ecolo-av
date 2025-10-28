#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

class CameraReceiver(Node):
    def __init__(self):
        super().__init__('camera_receiver')
        
        self.bridge = CvBridge()
        self.frame_count = 0
        
        self.get_logger().info('Creating subscription to /camera/image_raw')
        
        # Create QoS profile compatible with image publishers
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        self.subscription = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            qos_profile)
        
        self.get_logger().info('Camera Receiver Node Started - Subscribed with BEST_EFFORT QoS!')
        
    def image_callback(self, msg):
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            
            self.frame_count += 1
            if self.frame_count % 30 == 0:
                self.get_logger().info(f'Received {self.frame_count} frames - Size: {cv_image.shape}')
            
            cv2.imshow('Received Camera Feed', cv_image)
            cv2.waitKey(1)
        except Exception as e:
            self.get_logger().error(f'Error processing frame: {e}')

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
