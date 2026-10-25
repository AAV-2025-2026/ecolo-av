#!/usr/bin/env python3
"""
topic_bridge.py  —  lane_stitcher package
═══════════════════════════════════════════════════════════════════
Bridges your existing camera system topics to the lane pipeline.

Your camera system publishes:
  /aav/cam1/image_raw   (from camera_decoder_node via NVDEC)
  /aav/cam2/image_raw   (from camera_decoder_node via NVDEC)

The lane pipeline expects:
  /cam_left/image_raw
  /cam_right/image_raw

This node subscribes to the /aav/ topics and republishes them
with the names the pipeline expects. Zero copy — just header update.

Run once at startup. Works for BOTH live cameras AND bag playback.

Launch:
  ros2 run lane_stitcher topic_bridge

Or add to stitch_and_detect.launch.py (already done in updated launch).
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image


class TopicBridge(Node):

    def __init__(self):
        super().__init__('topic_bridge')

        # ── Parameters: source and destination topic names ────────────
        # Change these if your topic names differ
        self.declare_parameter('cam1_src', '/aav/cam1/image_raw')
        self.declare_parameter('cam2_src', '/aav/cam2/image_raw')
        self.declare_parameter('cam_left_dst',  '/cam_left/image_raw')
        self.declare_parameter('cam_right_dst', '/cam_right/image_raw')

        src1 = self.get_parameter('cam1_src').value
        src2 = self.get_parameter('cam2_src').value
        dst1 = self.get_parameter('cam_left_dst').value
        dst2 = self.get_parameter('cam_right_dst').value

        # Publishers
        self.pub_left  = self.create_publisher(Image, dst1, 10)
        self.pub_right = self.create_publisher(Image, dst2, 10)

        # Subscribers
        self.sub1 = self.create_subscription(
            Image, src1,
            lambda msg: self.bridge_cb(msg, self.pub_left, 'left'),
            10)
        self.sub2 = self.create_subscription(
            Image, src2,
            lambda msg: self.bridge_cb(msg, self.pub_right, 'right'),
            10)

        self.count_left  = 0
        self.count_right = 0

        self.get_logger().info(
            f"Topic Bridge ready\n"
            f"  {src1}  →  {dst1}\n"
            f"  {src2}  →  {dst2}\n"
            f"  Works for live cameras AND bag playback."
        )

        # Status log every 5 seconds
        self.create_timer(5.0, self.status_cb)

    def bridge_cb(self, msg: Image, pub, side: str):
        # Update frame_id to match pipeline expectation
        msg.header.frame_id = f'cam_{side}'
        pub.publish(msg)
        if side == 'left':
            self.count_left += 1
        else:
            self.count_right += 1

    def status_cb(self):
        self.get_logger().info(
            f"Bridge forwarded — left: {self.count_left} frames  "
            f"right: {self.count_right} frames",
            throttle_duration_sec=5.0
        )


def main(args=None):
    rclpy.init(args=args)
    node = TopicBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
