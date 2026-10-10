"""
stop_sign_watcher: stop the car at stop signs, through a lock on twist_mux.

Subscribes  /perception/detections  vision_msgs/Detection2DArray (from the detector)
Publishes   /perception/stop        std_msgs/Bool, 10 Hz: true while the car must stay stopped

twist_mux's stop_sign lock (aav_mux, priority 30) holds every driver below it: Nav2 (20)
and the AI slot (10). A person (joystick 100, remote 90) and test scripts (50, 40) still
drive. The lock never expires on silence, so if this node dies while it's on, the car stays
stopped. It only ever stops the car; it can't make it move.

Needs no PyTorch: it runs in the default environment.
"""

import signal

from aav_yolo.stop_sign import StopRule, StopSignWatcher
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Bool
from vision_msgs.msg import Detection2DArray


class Watcher(Node):

    def __init__(self):
        super().__init__('stop_sign_watcher')
        rule = StopRule(
            min_height_px=self.declare_parameter('min_height_px', StopRule.min_height_px).value,
            min_score=self.declare_parameter('min_score', StopRule.min_score).value,
            hold_s=self.declare_parameter('hold_s', StopRule.hold_s).value,
            ignore_s=self.declare_parameter('ignore_s', StopRule.ignore_s).value,
        )
        self.watcher = StopSignWatcher(rule)
        self.pub = self.create_publisher(Bool, '/perception/stop', 10)
        self.create_subscription(Detection2DArray, '/perception/detections', self.on_boxes, 10)
        self.create_timer(0.1, self.tick)
        self.state = self.watcher.state

    def now(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def on_boxes(self, msg: Detection2DArray):
        boxes = [(d.results[0].hypothesis.class_id, d.results[0].hypothesis.score, d.bbox.size_y)
                 for d in msg.detections if d.results]
        self.publish(self.watcher.update(boxes, self.now()))

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
