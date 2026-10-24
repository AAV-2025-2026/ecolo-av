"""
camera_stream: one camera's H.264 stream (RTSP, from MediaMTX) to detections, in one process.

  camera Pi: MediaMTX ──RTSP H.264──> decoder ──> undistort ──> detector ──> detections
                                     (child)     (OpenCV)     (aav_yolo)

Pulls rtsp://<pi>:8554/<camera>, decodes it (decoders.py: ffmpeg, or GStreamer with
NVIDIA's hardware on the Orin), undistorts each picture (lens.py) and runs the detector
on it here, so raw pictures never cross the network or DDS. Only the newest picture is
worked on: a slow detector drops frames instead of falling behind.

Subscribes  nothing
Publishes   /perception/detections               vision_msgs/Detection2DArray: the boxes,
                                                 in the undistorted picture's pixels;
                                                 header.frame_id the camera's frame
            /sensors/camera/<camera>/camera_info sensor_msgs/CameraInfo: the undistorted
                                                 picture's lens, with each detection
                                                 (publish_camera_info)
            /perception/camera/<camera>/preview/compressed  sensor_msgs/CompressedImage:
                                                 a small JPEG with the boxes, every
                                                 preview_period s (0: none)
            /sensors/camera/<camera>/image_raw   sensor_msgs/Image: every undistorted
                                                 picture, only with publish_image (for
                                                 another node on this computer)
            /diagnostics                         diagnostic_msgs/DiagnosticArray, 1 Hz: the
                                                 rates, drops, times and, with time_code,
                                                 the measured delays
            /system/source                       aav_interfaces/DataSource, latched: this
                                                 camera, and its source (real, sim...)

Stamp: a picture's header.stamp is its arrival minus `delay` (s), the stream's measured
delay from the camera to here (docs/camera-pipeline.md). Set it from a measurement.

Parameters: camera (front_left), url, frame_id, decoder (ffmpeg, gst-nvidia, gst-soft,
gst-mac, opencv), pipeline (a GStreamer pipeline instead of the preset), program (the
decoder program's path), hwaccel (ffmpeg's -hwaccel), transport (tcp or udp), width and
height (1280x720), fps (15: the stream's, for the report), calibration (an INI or YAML
file; empty: no undistortion), alpha, delay, detector (rfdetr, yolo or none), model,
device, confidence, labels, image_size, preview_period, preview_width, publish_image,
publish_camera_info, time_code (read the test's time code: tools/stream_check.py),
source (real, sim, bench, replay).
"""

import os
import signal
import threading
import time

from aav_camera_stream import decoders, lens as lenses, models, timecode
from aav_camera_stream.latest import Delays, Latest, Rate, stamp_ns
from aav_camera_stream.reader import Reader
from aav_interfaces.msg import DataSource, SensorSource
from builtin_interfaces.msg import Time
import cv2
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CameraInfo, CompressedImage, Image
from std_msgs.msg import Header
from vision_msgs.msg import Detection2D, Detection2DArray, ObjectHypothesisWithPose

FRAMES = {'front_left': 'camera_left_link', 'front_right': 'camera_right_link',
          'rear': 'camera_rear_link'}
SOURCES = {'real': SensorSource.REAL, 'sim': SensorSource.SIM, 'bench': SensorSource.BENCH,
           'replay': SensorSource.REPLAY}
LATCHED = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL)


def to_time(ns):
    return Time(sec=ns // 1_000_000_000, nanosec=ns % 1_000_000_000)


def detections_msg(header, boxes):
    out = Detection2DArray(header=header)
    for box in boxes:
        d = Detection2D(header=header)
        d.bbox.center.position.x = float(box.cx)
        d.bbox.center.position.y = float(box.cy)
        d.bbox.size_x = float(box.width)
        d.bbox.size_y = float(box.height)
        h = ObjectHypothesisWithPose()
        h.hypothesis.class_id = box.label
        h.hypothesis.score = float(box.score)
        d.results.append(h)
        out.detections.append(d)
    return out


def camera_info_msg(header, lens):
    msg = CameraInfo(header=header, width=lens.width, height=lens.height,
                     distortion_model='plumb_bob')
    msg.k = [float(x) for x in lens.k]
    msg.d = [0.0] * 5
    msg.r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    msg.p = [float(x) for x in lenses.projection(lens)]
    return msg


class CameraStream(Node):

    def __init__(self):
        super().__init__('camera_stream')
        p = self.declare_parameter
        self.camera = p('camera', 'front_left').value
        url = p('url', f'rtsp://127.0.0.1:8554/{self.camera}').value
        self.frame_id = p('frame_id', FRAMES.get(self.camera,
                                                 f'camera_{self.camera}_link')).value
        decoder = p('decoder', 'ffmpeg').value
        pipeline = p('pipeline', '').value
        program = p('program', '').value
        hwaccel = p('hwaccel', '').value
        transport = p('transport', 'tcp').value
        width, height = p('width', 1280).value, p('height', 720).value
        self.expected_hz = p('fps', 15.0).value
        calibration = p('calibration', '').value
        alpha = p('alpha', 0.0).value
        self.delay = p('delay', 0.06).value
        detector = p('detector', 'rfdetr').value
        model = p('model', '').value
        device = p('device', 'auto').value
        self.confidence = p('confidence', 0.5).value
        labels = p('labels', '').value
        image_size = p('image_size', 640).value
        self.preview_period = p('preview_period', 1.0).value
        self.preview_width = p('preview_width', 320).value
        publish_image = p('publish_image', False).value
        publish_info = p('publish_camera_info', True).value
        self.time_code = p('time_code', False).value
        source = p('source', 'real').value
        if source not in SOURCES:
            raise SystemExit(f'source:={source}: use one of {", ".join(SOURCES)}')
        try:
            decoders.check(decoder, transport)
            from aav_yolo.boxes import parse_labels
            self.labels = parse_labels(labels)
            self.undistort = None
            if calibration:
                lens = lenses.scaled(lenses.load(calibration), width, height)
                self.undistort = lenses.Undistorter(lens, alpha)
            root = os.environ.get('PIXI_PROJECT_ROOT', os.getcwd())
            self.model = models.make(detector, model, device, image_size,
                                     self.get_logger().info, root)
        except (ValueError, OSError) as e:
            raise SystemExit(f'camera_stream {self.camera}: {e}')
        except ImportError as e:
            raise SystemExit(f'{e}: the detector needs PyTorch (pixi run -e ml ...), '
                             'or detector:=none')
        self.lens = self.undistort.lens() if self.undistort else None

        if decoder == 'opencv':
            def make_source():
                return decoders.OpenCvSource(url, width, height, transport, pipeline)
        else:
            argv = decoders.command(decoder, url, width, height, transport, program,
                                    pipeline, hwaccel)
            env = decoders.child_env(os.environ, argv[0], os.environ.get('CONDA_PREFIX', ''))

            def make_source():
                return decoders.PipeSource(argv, width, height, env)
            self.get_logger().info('decoder: ' + ' '.join(argv))

        base = f'/sensors/camera/{self.camera}'
        self.det_pub = self.create_publisher(Detection2DArray, '/perception/detections', 10)
        self.info_pub = (self.create_publisher(CameraInfo, f'{base}/camera_info', 10)
                         if publish_info and self.lens else None)
        self.preview_pub = (self.create_publisher(
            CompressedImage, f'/perception/camera/{self.camera}/preview/compressed', 2)
            if self.preview_period > 0 else None)
        self.image_pub = (self.create_publisher(Image, f'{base}/image_raw', 2)
                          if publish_image else None)
        self.diag_pub = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        announce = self.create_publisher(DataSource, '/system/source', LATCHED)
        msg = DataSource(announcer=self.get_name())
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.sensors = [SensorSource(name=f'camera_{self.camera}',
                                    topic=f'{base}/image_raw' if publish_image else '',
                                    source=SOURCES[source])]
        announce.publish(msg)
        self.announce = announce

        self.url = url
        self.latest = Latest()
        self.reader = Reader(make_source, self.latest,
                             log=lambda text: self.get_logger().info(f'{self.camera} {text}'))
        self.in_rate, self.out_rate = Rate(), Rate()
        self.work_ms = Delays(keep=300)
        self.detect_ms = Delays(keep=300)
        # The last minute of measured delays (time_code): time code -> picture out of the
        # decoder, and -> detections published.
        minute = max(10, int(60 * self.expected_hz))
        self.arrival = Delays(keep=minute)
        self.done = Delays(keep=minute)
        self.codes = 0
        self.last_preview = 0.0
        self.stopping = threading.Event()
        self.worker = threading.Thread(target=self.work, name='stream-worker', daemon=True)
        self.create_timer(1.0, self.report)
        self.reader.start()
        self.worker.start()
        self.get_logger().info(
            f'{self.camera}: {url} by {decoder}, {width}x{height}, '
            f'{"undistorted by " + calibration if calibration else "not undistorted"}; '
            f'detector {self.model.detector}'
            f'{" " + self.model.model if self.model.model else ""}'
            f'{" on " + str(self.model.device) if self.model.device else ""}; '
            f'stamps = arrival - '
            f'{self.delay:.3f} s; frame {self.frame_id}')

    def work(self):
        while not self.stopping.is_set():
            item = self.latest.take(0.5)
            if item is None:
                continue
            frame, arrived_ns = item
            self.in_rate.tick()
            try:
                self.process(frame, arrived_ns)
            except Exception as e:  # noqa: B902 - a bad frame must not stop the node
                self.get_logger().error(f'{self.camera}: {e}', throttle_duration_sec=5.0)

    def process(self, frame, arrived_ns):
        t0 = time.monotonic()
        sent = timecode.read(frame) if self.time_code else None
        if sent is not None:
            self.codes += 1
            self.arrival.add(timecode.age_s(sent, arrived_ns / 1e9))
        if self.undistort is not None:
            frame = self.undistort.apply(frame)
        t1 = time.monotonic()
        boxes = self.model.detect(frame, self.confidence, self.labels)
        self.detect_ms.add(1000.0 * (time.monotonic() - t1))
        header = Header(frame_id=self.frame_id)
        header.stamp = to_time(stamp_ns(arrived_ns, self.get_clock().now().nanoseconds,
                                        time.time_ns(), self.delay))
        self.det_pub.publish(detections_msg(header, boxes))
        if sent is not None:
            self.done.add(timecode.age_s(sent, time.time()))
        if self.info_pub is not None:
            self.info_pub.publish(camera_info_msg(header, self.lens))
        if self.image_pub is not None:
            from cv_bridge import CvBridge
            image = CvBridge().cv2_to_imgmsg(frame, 'bgr8')
            image.header = header
            self.image_pub.publish(image)
        if self.preview_pub is not None and t0 - self.last_preview >= self.preview_period:
            self.last_preview = t0
            self.preview_pub.publish(self.preview(header, frame, boxes))
        self.out_rate.tick()
        self.work_ms.add(1000.0 * (time.monotonic() - t0))

    def preview(self, header, frame, boxes):
        from aav_yolo.detector import draw
        picture = draw(frame, boxes) if boxes else frame
        scale = self.preview_width / picture.shape[1]
        small = cv2.resize(picture, (self.preview_width, int(round(picture.shape[0] * scale))),
                           interpolation=cv2.INTER_AREA)
        ok, jpeg = cv2.imencode('.jpg', small, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return CompressedImage(header=header, format='jpeg', data=jpeg.tobytes())

    def report(self):
        values = {
            'connected': str(self.reader.connected).lower(),
            'decoder_starts': str(self.reader.starts),
            'frames_in': str(self.reader.frames),
            'fps_in': f'{self.in_rate.hz():.1f}',
            'fps_out': f'{self.out_rate.hz():.1f}',
            'dropped': str(self.latest.dropped),
            'delay_s': f'{self.delay:.3f}',
        }
        for name, stats in (('work_ms', self.work_ms), ('detect_ms', self.detect_ms)):
            s = stats.summary()
            if s:
                values[name] = f'{s["median"]:.1f}'
        if self.time_code:
            values['time_codes'] = str(self.codes)
            for name, stats in (('arrival', self.arrival), ('detection', self.done)):
                s = stats.summary()
                if s:
                    for key in ('median', 'p95', 'max'):
                        values[f'{name}_{key}_ms'] = f'{1000.0 * s[key]:.1f}'
        fps = self.out_rate.hz()
        status = DiagnosticStatus(name=f'camera_stream: {self.camera}', hardware_id=self.url)
        if not self.reader.connected:
            status.level, status.message = DiagnosticStatus.ERROR, 'no pictures'
        elif fps < 0.5 * self.expected_hz:
            status.level, status.message = DiagnosticStatus.WARN, f'slow: {fps:.1f} fps'
        else:
            status.level, status.message = DiagnosticStatus.OK, f'{fps:.1f} fps'
        status.values = [KeyValue(key=k, value=v) for k, v in values.items()]
        out = DiagnosticArray(status=[status])
        out.header.stamp = self.get_clock().now().to_msg()
        self.diag_pub.publish(out)

    def shutdown(self):
        self.stopping.set()
        self.reader.stop()
        self.worker.join(5.0)


def main():
    rclpy.init()
    node = None
    try:
        node = CameraStream()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        # Ctrl-C reaches a launched node twice (the terminal, then launch): ignore the
        # second, so it can't interrupt the clean-up with a traceback.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if node is not None:
            node.shutdown()
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
