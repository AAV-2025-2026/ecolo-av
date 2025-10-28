#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import subprocess

class NetworkCameraReceiver(Node):
    def __init__(self):
        super().__init__('network_camera_receiver')
        
        self.bridge = CvBridge()
        
        # Publisher for received images
        self.publisher = self.create_publisher(Image, '/jetson/camera/image_raw', 10)
        
        # GStreamer pipeline to receive UDP stream
        gst_pipeline = (
            'udpsrc port=5000 ! '
            'application/x-rtp,encoding-name=H264,payload=96 ! '
            'rtph264depay ! '
            'h264parse ! '
            'avdec_h264 ! '
            'videoconvert ! '
            'appsink'
        )
        
        # Open video capture with GStreamer
        self.cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
        
        if not self.cap.isOpened():
            self.get_logger().error('Failed to open network stream')
            return
            
        self.get_logger().info('Network receiver started, waiting for stream...')
        
        # Timer to read frames
        self.timer = self.create_timer(0.033, self.timer_callback)  # ~30 FPS
        
    def timer_callback(self):
        ret, frame = self.cap.read()
        
        if ret:
            # Convert OpenCV image to ROS message
            msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = 'jetson_camera'
            
            # Publish
            self.publisher.publish(msg)
        
    def destroy_node(self):
        if self.cap:
            self.cap.release()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    receiver = NetworkCameraReceiver()
    
    try:
        rclpy.spin(receiver)
    except KeyboardInterrupt:
        pass
    finally:
        receiver.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
