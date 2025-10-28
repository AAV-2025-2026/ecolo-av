#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

class CameraReceiver(Node):
    def __init__(self):
        super().__init__('camera_receiver')
        
        self.bridge = CvBridge()
        self.frame_count = 0
        
        self.get_logger().info('Creating subscription to /camera/image_raw')
        
        # Use default QoS (same as ros2 topic echo)
        self.subscription = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10)  # Just queue depth, no custom QoS
        
        self.get_logger().info('Camera Receiver Node Started - Subscribed with default QoS!')
        
    def image_callback(self, msg):
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            
            self.frame_count += 1
            
            # Log first 10 frames to verify callback
            if self.frame_count <= 10:
                self.get_logger().info(f'*** FRAME RECEIVED! #{self.frame_count} Size: {cv_image.shape} ***')
            
            if self.frame_count % 30 == 0:
                self.get_logger().info(f'Received {self.frame_count} frames')
            
            # Display the image
            cv2.imshow('Camera Feed from Pi', cv_image)
            cv2.waitKey(1)
            
        except Exception as e:
            self.get_logger().error(f'Error in callback: {e}')
            import traceback
            self.get_logger().error(traceback.format_exc())

def main(args=None):
    rclpy.init(args=args)
    receiver = CameraReceiver()
    
    try:
        rclpy.spin(receiver)
    except KeyboardInterrupt:
        pass
    finally:
        receiver.destroy_node()
        cv2.destroyAllWindows()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
