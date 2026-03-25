#!/usr/bin/env python3
"""
camera_publisher.py  —  lane_stitcher package
═══════════════════════════════════════════════════════════════════
Opens both IMX219 cameras and publishes raw frames to ROS2.
Supports GStreamer (Jetson Orin native) and V4L2 (USB fallback).

Publishes:
  /cam_left/image_raw   sensor_msgs/Image
  /cam_right/image_raw  sensor_msgs/Image

Parameters:
  left_id        int   default 0     /dev/video0
  right_id       int   default 1     /dev/video1
  width          int   default 640
  height         int   default 480
  fps            int   default 30
  use_gstreamer  bool  default true  set false for USB cameras
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2


def gst_pipeline(sensor_id: int, w: int, h: int, fps: int) -> str:
    """GStreamer pipeline string for Jetson Orin CSI cameras."""
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM), width=3280, height=2464, "
        f"format=NV12, framerate={fps}/1 ! "
        f"nvvidconv flip-method=0 ! "
        f"video/x-raw, width={w}, height={h}, format=BGRx ! "
        f"videoconvert ! video/x-raw, format=BGR ! appsink"
    )


class CameraPublisher(Node):

    def __init__(self):
        super().__init__('camera_publisher')

        self.declare_parameter('left_id',       0)
        self.declare_parameter('right_id',      1)
        self.declare_parameter('width',         640)
        self.declare_parameter('height',        480)
        self.declare_parameter('fps',           30)
        self.declare_parameter('use_gstreamer', True)

        lid  = self.get_parameter('left_id').value
        rid  = self.get_parameter('right_id').value
        w    = self.get_parameter('width').value
        h    = self.get_parameter('height').value
        fps  = self.get_parameter('fps').value
        gst  = self.get_parameter('use_gstreamer').value

        self.bridge = CvBridge()

        if gst:
            self.get_logger().info("Opening IMX219 cameras via GStreamer (Jetson Orin)...")
            self.cap_l = cv2.VideoCapture(gst_pipeline(lid, w, h, fps), cv2.CAP_GSTREAMER)
            self.cap_r = cv2.VideoCapture(gst_pipeline(rid, w, h, fps), cv2.CAP_GSTREAMER)
        else:
            self.get_logger().info("Opening cameras via V4L2 (USB mode)...")
            self.cap_l = cv2.VideoCapture(lid)
            self.cap_r = cv2.VideoCapture(rid)
            for cap in (self.cap_l, self.cap_r):
                cap.set(cv2.CAP_PROP_FRAME_WIDTH,  w)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                cap.set(cv2.CAP_PROP_FPS, fps)

        if not self.cap_l.isOpened():
            self.get_logger().error(f"LEFT camera (id={lid}) failed to open!")
        if not self.cap_r.isOpened():
            self.get_logger().error(f"RIGHT camera (id={rid}) failed to open!")

        self.pub_l = self.create_publisher(Image, '/cam_left/image_raw',  10)
        self.pub_r = self.create_publisher(Image, '/cam_right/image_raw', 10)
        self.create_timer(1.0 / fps, self.capture)

        self.get_logger().info(
            f"Camera publisher ready | {w}x{h} @ {fps}fps | "
            f"left={lid} right={rid} | gstreamer={gst}"
        )

    def capture(self):
        now = self.get_clock().now().to_msg()
        for cap, pub, fid in [
            (self.cap_l, self.pub_l, 'cam_left'),
            (self.cap_r, self.pub_r, 'cam_right'),
        ]:
            ret, frame = cap.read()
            if ret:
                msg = self.bridge.cv2_to_imgmsg(frame, 'bgr8')
                msg.header.stamp    = now
                msg.header.frame_id = fid
                pub.publish(msg)
            else:
                self.get_logger().warn(
                    f"{fid}: frame read failed",
                    throttle_duration_sec=2.0)

    def destroy_node(self):
        self.cap_l.release()
        self.cap_r.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = CameraPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
