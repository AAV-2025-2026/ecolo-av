"""
stop_sign_watcher: stop the car at stop signs, through a lock on twist_mux.

Subscribes  /perception/detections  vision_msgs/Detection2DArray (from the detector)
            camera_info_topics      sensor_msgs/CameraInfo, one topic per camera (default
                                    /sensors/camera/<front_left, front_right, rear>/
                                    camera_info): its lens, kept by the frame it names
Publishes   /perception/stop_sign        std_msgs/Bool, 10 Hz: true while the car must stay stopped

A sign counts once it is stop_distance_m (4.7) away or closer: its box's height, the
sign's (sign_height_m, 0.75) and the focal length of the camera that saw it, the fy of
the CameraInfo with the detections' frame_id (stop_sign.py). A camera with no CameraInfo
yet (not calibrated) gets focal_px (343: Gazebo's and the bench's lens, 640x360), with a
warning: set focal_px for it, or calibrate it (docs/camera-calibration.md).

twist_mux's stop_sign lock (aav_command_mux, priority 30) holds every driver below it: Nav2 (20)
and the AI slot (10). A person (joystick 100, keyboard 90) and test scripts (50, 40) still
drive. The lock never expires on silence, so if this node dies while it's on, the car stays
stopped. It only ever stops the car; it can't make it move.

Needs no PyTorch: it runs in the default environment.
"""

import signal

from aav_detector.stop_sign import StopRule, StopSignWatcher
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo
from std_msgs.msg import Bool
from vision_msgs.msg import Detection2DArray

CAMERA_INFO = [f'/sensors/camera/{c}/camera_info' for c in ('front_left', 'front_right', 'rear')]


class Watcher(Node):

    def __init__(self):
        super().__init__('stop_sign_watcher')
        p = self.declare_parameter
        rule = StopRule(
            stop_distance_m=p('stop_distance_m', StopRule.stop_distance_m).value,
            focal_px=p('focal_px', StopRule.focal_px).value,
            sign_height_m=p('sign_height_m', StopRule.sign_height_m).value,
            min_score=p('min_score', StopRule.min_score).value,
            hold_s=p('hold_s', StopRule.hold_s).value,
            ignore_s=p('ignore_s', StopRule.ignore_s).value,
        )
        self.watcher = StopSignWatcher(rule)
        self.focal = {}                 # frame_id -> fy (px), from each camera's CameraInfo
        for topic in p('camera_info_topics', CAMERA_INFO).value:
            self.create_subscription(CameraInfo, topic, self.on_camera_info, 10)
        self.get_logger().info(
            f'stops {rule.stop_distance_m:g} m before a {rule.sign_height_m:g} m stop sign: '
            f'{rule.min_height_px():.0f} px tall with focal_px {rule.focal_px:g}, the lens '
            'of a camera without CameraInfo')
        self.pub = self.create_publisher(Bool, '/perception/stop_sign', 10)
        self.create_subscription(Detection2DArray, '/perception/detections', self.on_boxes, 10)
        self.create_timer(0.1, self.tick)
        self.state = self.watcher.state

    def now(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def on_camera_info(self, msg: CameraInfo):
        fy = float(msg.k[4])
        if fy > 0 and self.focal.get(msg.header.frame_id) != fy:
            self.get_logger().info(
                f'{msg.header.frame_id}: focal length {fy:.0f} px: stops for a stop sign '
                f'{self.watcher.rule.min_height_px(fy):.0f} px tall')
            self.focal[msg.header.frame_id] = fy

    def on_boxes(self, msg: Detection2DArray):
        boxes = [(d.results[0].hypothesis.class_id, d.results[0].hypothesis.score, d.bbox.size_y)
                 for d in msg.detections if d.results]
        focal = self.focal.get(msg.header.frame_id)
        if focal is None and boxes:
            self.get_logger().warning(
                f'no CameraInfo for camera {msg.header.frame_id!r}: its stop signs are judged '
                f'with focal_px {self.watcher.rule.focal_px:g}. Calibrate it, or set focal_px',
                throttle_duration_sec=30.0)
        self.publish(self.watcher.update(boxes, self.now(), focal))

    def tick(self):
        self.publish(self.watcher.tick(self.now()))

    def publish(self, stop: bool):
        if self.watcher.state != self.state:
            self.state = self.watcher.state
            self.get_logger().info(f'stop sign: {self.state}')
        self.pub.publish(Bool(data=stop))


def main():
    rclpy.init()
    node = None
    try:
        node = Watcher()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        # Ctrl-C reaches a launched node twice (the terminal, then launch): ignore the
        # second, so it can't interrupt the clean-up with a traceback.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()
