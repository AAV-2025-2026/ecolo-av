"""
detector: a YOLO model finds objects, such as stop signs, in camera images.

Subscribes  image              sensor_msgs/Image (the launch file maps it to
                               /sensors/camera/front_left/image_raw)
            image/compressed   sensor_msgs/CompressedImage instead, with compressed:=true
                               (image_transport's JPEG topic: for a laptop on WiFi)
Publishes   detections         vision_msgs/Detection2DArray (/perception/detections), with
                               the image's header: its stamp, and its camera's frame
            detections/image   sensor_msgs/Image: the picture with the boxes drawn on

The model file is a parameter, so the same node runs everywhere:
  .pt         PyTorch, on any machine. device: auto (the GPU this computer has), or
              PyTorch's own names: cuda, cuda:N, mps (a Mac's GPU, through Metal), cpu.
  .mlpackage  Core ML, on Macs: the GPU or the Neural Engine.
  .engine     TensorRT, on the Orin. Build it on the Orin itself.

It needs PyTorch and Ultralytics, from the ml environment. Try it:
  pixi run get-models                                                # once
  pixi run detect picture:=src/perception/aav_yolo/test/stop_sign.jpg
"""

import signal
import time

from aav_yolo.boxes import boxes_from_result, parse_labels, pick_device
from cv_bridge import CvBridge
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage, Image
from vision_msgs.msg import Detection2D, Detection2DArray, ObjectHypothesisWithPose

# Only the newest frame: if the model is slower than the camera, old frames are dropped
# instead of queueing up. Reliable, not best effort: a camera image is too big for one UDP
# packet, and best effort drops the whole image when one piece is lost. On a Mac that's
# nearly every image (measured: 0 of 50 arrived, against 50 of 50 reliable).
LATEST = QoSProfile(depth=1, history=HistoryPolicy.KEEP_LAST,
                    reliability=ReliabilityPolicy.RELIABLE)
# The picture with boxes keeps a few frames: a big frame arrives in many pieces, and with
# room for only one, a busy subscriber may never finish a frame before the next replaces it.
PICTURES = QoSProfile(depth=3, history=HistoryPolicy.KEEP_LAST,
                      reliability=ReliabilityPolicy.RELIABLE)


class Detector(Node):

    def __init__(self):
        super().__init__('yolo_detector')
        model = self.declare_parameter('model', '').value
        device = self.declare_parameter('device', 'auto').value
        self.confidence = self.declare_parameter('confidence', 0.5).value
        self.image_size = self.declare_parameter('image_size', 640).value
        self.labels = parse_labels(self.declare_parameter('labels', '').value)
        publish_image = self.declare_parameter('publish_image', True).value
        self.compressed = self.declare_parameter('compressed', False).value
        if not model:
            raise SystemExit('Set the model file: model:=models/yolo11n.pt '
                             '(pixi run get-models downloads it)')
        try:
            import torch
            from ultralytics import YOLO
        except ImportError as e:
            raise SystemExit(f'{e}: run the detector in the ml environment (pixi run detect)')
        try:
            self.device = pick_device(device, model, torch.cuda.device_count(),
                                      torch.backends.mps.is_available())
        except ValueError as e:
            raise SystemExit(str(e))
        self.model = YOLO(model, task='detect')
        self.bridge = CvBridge()
        self.pub = self.create_publisher(Detection2DArray, 'detections', 10)
        self.image_pub = (self.create_publisher(Image, 'detections/image', PICTURES)
                          if publish_image else None)
        # image_transport's naming: the JPEG pictures are <image topic>/compressed. Resolve
        # 'image' first, so a remapping of it (image:=/sensors/camera/front_left/image_raw)
        # carries over.
        topic = self.resolve_topic_name('image')
        if self.compressed:
            topic += '/compressed'
            self.create_subscription(CompressedImage, topic, self.on_image, LATEST)
        else:
            self.create_subscription(Image, topic, self.on_image, LATEST)
        self.frames, self.busy_s, self.since = 0, 0.0, time.monotonic()
        keep = ', '.join(self.labels) if self.labels else 'every label'
        self.get_logger().info(f'{model} on {self.device or "its own choice of hardware"}, '
                               f'reading {topic}; keeping {keep}, at confidence '
                               f'{self.confidence} or more')

    def on_image(self, msg):
        t0 = time.monotonic()
        try:
            if self.compressed:
                frame = self.bridge.compressed_imgmsg_to_cv2(msg, 'bgr8')
            else:
                frame = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
            kwargs = {'device': self.device} if self.device else {}
            result = self.model.predict(frame, imgsz=self.image_size, conf=self.confidence,
                                        verbose=False, **kwargs)[0]
        except Exception as e:  # noqa: B902 - a bad frame must not stop the node
            self.get_logger().error(f'detection failed: {e}', throttle_duration_sec=5.0)
            return
        out = Detection2DArray(header=msg.header)
        for box in boxes_from_result(result, self.labels):
            d = Detection2D(header=msg.header)
            d.bbox.center.position.x = box.cx
            d.bbox.center.position.y = box.cy
            d.bbox.size_x = box.width
            d.bbox.size_y = box.height
            h = ObjectHypothesisWithPose()
            h.hypothesis.class_id = box.label
            h.hypothesis.score = box.score
            d.results.append(h)
            out.detections.append(d)
        self.pub.publish(out)
        if self.image_pub is not None:
            picture = self.bridge.cv2_to_imgmsg(result.plot(), 'bgr8')
            picture.header = msg.header
            self.image_pub.publish(picture)
        self.frames += 1
        self.busy_s += time.monotonic() - t0
        if time.monotonic() - self.since >= 10.0:
            self.get_logger().info(f'{self.frames} frames in 10 s, '
                                   f'{1000.0 * self.busy_s / self.frames:.1f} ms each')
            self.frames, self.busy_s, self.since = 0, 0.0, time.monotonic()


def main():
    rclpy.init()
    node = None
    try:
        node = Detector()
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


if __name__ == '__main__':
    main()
