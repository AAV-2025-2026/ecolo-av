#!/usr/bin/env python3
"""
image_stitcher.py  —  lane_stitcher package  [IMPROVED v2]
═══════════════════════════════════════════════════════════════════
Improvement over v1:
  ✅ FIX 5 — Wide-angle camera distortion:
       Explicitly verifies and uses your stereo_calib.npz file.
       Logs clearly whether calibration loaded or fell back to defaults.
       Applies cv2.fisheye undistortion correctly for IMX219 160° lens.
       Added balance parameter tuning: balance=0.0 removes all black
       borders; balance=1.0 keeps full FOV. Default 0.5 is a good
       trade-off for lane detection.
       Validation: logs estimated FOV after undistortion as a
       sanity check that the calibration was applied correctly.

All other stitching logic unchanged from v1.
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import numpy as np
import yaml, os
from message_filters import ApproximateTimeSynchronizer, Subscriber
from ament_index_python.packages import get_package_share_directory


def load_config() -> dict:
    pkg  = get_package_share_directory('lane_stitcher')
    path = os.path.join(pkg, 'config', 'homography.yaml')
    with open(path) as f:
        return yaml.safe_load(f)


def build_blend_maps(canvas_w, canvas_h, left_x, bev_w, right_x, blend_px):
    wl = np.zeros((canvas_h, canvas_w), np.float32)
    wr = np.zeros((canvas_h, canvas_w), np.float32)
    left_end = left_x + bev_w
    ov_s, ov_e = right_x, left_end
    for x in range(canvas_w):
        in_l = left_x  <= x < left_end
        in_r = right_x <= x < right_x + bev_w
        if ov_s <= x < ov_e:
            t = (x - ov_s) / max(ov_e - ov_s, 1)
            wl[:, x] = 1.0 - t
            wr[:, x] = t
        else:
            if in_l: wl[:, x] = 1.0
            if in_r: wr[:, x] = 1.0
    return wl[:, :, np.newaxis], wr[:, :, np.newaxis]


class ImageStitcher(Node):

    def __init__(self):
        super().__init__('image_stitcher')
        cfg = load_config()

        self.canvas_w = cfg['canvas_width']
        self.canvas_h = cfg['canvas_height']
        self.bev_w    = cfg['bev_width']
        self.bev_h    = cfg['bev_height']
        self.left_x   = cfg['left_x_offset']
        self.right_x  = cfg['right_x_offset']
        self.blend_px = cfg['blend_zone_px']
        self.bev_size = (self.bev_w, self.bev_h)
        self.H_left   = np.array(cfg['left_H'],  dtype=np.float64)
        self.H_right  = np.array(cfg['right_H'], dtype=np.float64)

        # ── FIX 5: Load calibration with validation ────────────────────
        img_w = cfg['image_width']
        img_h = cfg['image_height']
        stereo_path = cfg.get('stereo_calib_path', '')

        K, D, calib_source = self.load_calibration(
            stereo_path, cfg, img_w, img_h)

        # Build fisheye undistortion maps
        self.do_undistort = cfg.get('undistort', True)
        if self.do_undistort:
            # balance=0.5: balanced trade-off between FOV and black borders
            # increase to 1.0 to keep max FOV, decrease to 0.0 for no borders
            balance = cfg.get('undistort_balance', 0.5)
            K_new = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
                K, D, (img_w, img_h), np.eye(3), balance=balance)
            self.map1, self.map2 = cv2.fisheye.initUndistortRectifyMap(
                K, D, np.eye(3), K_new, (img_w, img_h), cv2.CV_16SC2)

            # Validate: log estimated FOV as sanity check
            fov_x = 2.0 * np.degrees(np.arctan(img_w / (2.0 * K_new[0,0])))
            fov_y = 2.0 * np.degrees(np.arctan(img_h / (2.0 * K_new[1,1])))
            self.get_logger().info(
                f"✅ Fisheye undistortion ready\n"
                f"   Source: {calib_source}\n"
                f"   Estimated undistorted FOV: {fov_x:.0f}° x {fov_y:.0f}°\n"
                f"   (Original lens: 160°FOV. After undistortion ~80-100° expected)\n"
                f"   balance={balance}"
            )
        else:
            self.get_logger().warn("Undistortion DISABLED — lane lines may appear curved")

        # Pre-compute blend weights
        self.wl3, self.wr3 = build_blend_maps(
            self.canvas_w, self.canvas_h,
            self.left_x, self.bev_w,
            self.right_x, self.blend_px)

        self.bridge = CvBridge()

        self.sub_l = Subscriber(self, Image, cfg['left_camera_topic'])
        self.sub_r = Subscriber(self, Image, cfg['right_camera_topic'])
        self.sync  = ApproximateTimeSynchronizer(
            [self.sub_l, self.sub_r], queue_size=10, slop=0.05)
        self.sync.registerCallback(self.stitch_cb)

        self.pub_unified = self.create_publisher(Image, '/bev_unified',     10)
        self.pub_viz     = self.create_publisher(Image, '/bev_unified_viz', 10)

        self.get_logger().info(
            f"Image Stitcher v2 ready | "
            f"canvas={self.canvas_w}x{self.canvas_h} | "
            f"blend={self.blend_px}px"
        )

    def load_calibration(self, stereo_path, cfg, img_w, img_h):
        """
        FIX 5: Load calibration with fallback and clear logging.
        Returns: K (3x3), D (4,), source_description (str)
        """
        # ── Try stereo_calib.npz first ───────────────────────────────
        if stereo_path and os.path.exists(stereo_path):
            try:
                calib = np.load(stereo_path)
                keys  = list(calib.keys())
                self.get_logger().info(
                    f"stereo_calib.npz found. Keys: {keys}")

                # Try standard key names first, then alternatives
                K = calib.get('K_left',
                    calib.get('camera_matrix_left',
                    calib.get('mtx', None)))
                D = calib.get('dist_left',
                    calib.get('dist_coeffs_left',
                    calib.get('dist', None)))

                if K is None or D is None:
                    raise KeyError(
                        f"Could not find K/D in keys: {keys}. "
                        "Update key names in image_stitcher.py load_calibration()")

                K = K.astype(np.float64)
                D = D.flatten()[:4].astype(np.float64)

                self.get_logger().info(
                    f"✅ Calibration loaded from stereo_calib.npz\n"
                    f"   K[0,0]={K[0,0]:.1f}  K[1,1]={K[1,1]:.1f}  "
                    f"cx={K[0,2]:.1f}  cy={K[1,2]:.1f}\n"
                    f"   D={D}"
                )
                return K, D, "stereo_calib.npz ✅"

            except Exception as e:
                self.get_logger().warn(
                    f"Failed to load stereo_calib.npz: {e}\n"
                    "  Falling back to YAML defaults"
                )

        # ── Fallback: YAML approximate values ───────────────────────
        self.get_logger().warn(
            "⚠️  Using APPROXIMATE calibration from homography.yaml\n"
            "   For accurate lane detection, run camera calibration\n"
            "   and set stereo_calib_path in homography.yaml"
        )
        cm = cfg['camera_matrix']
        K  = np.array([[cm['fx'], 0, cm['cx']],
                       [0, cm['fy'], cm['cy']],
                       [0, 0, 1]], dtype=np.float64)
        D  = np.array(cfg['distortion_coefficients'],
                      dtype=np.float64).flatten()[:4]
        return K, D, "homography.yaml defaults ⚠️"

    def preprocess(self, msg: Image) -> np.ndarray:
        frame = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        if self.do_undistort:
            frame = cv2.remap(frame, self.map1, self.map2,
                              cv2.INTER_LINEAR, cv2.BORDER_CONSTANT)
        return frame

    def to_bev(self, frame, H):
        return cv2.warpPerspective(frame, H, self.bev_size,
                                   flags=cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_CONSTANT)

    def stitch_cb(self, msg_l: Image, msg_r: Image):
        bev_l = self.to_bev(self.preprocess(msg_l), self.H_left)
        bev_r = self.to_bev(self.preprocess(msg_r), self.H_right)

        canvas_l = np.zeros((self.canvas_h, self.canvas_w, 3), np.float32)
        canvas_r = np.zeros((self.canvas_h, self.canvas_w, 3), np.float32)

        lx0 = self.left_x
        lx1 = min(self.left_x  + self.bev_w, self.canvas_w)
        rx0 = self.right_x
        rx1 = min(self.right_x + self.bev_w, self.canvas_w)

        canvas_l[:, lx0:lx1] = bev_l[:, :lx1-lx0].astype(np.float32)
        canvas_r[:, rx0:rx1] = bev_r[:, :rx1-rx0].astype(np.float32)

        unified = np.clip(
            canvas_l * self.wl3 + canvas_r * self.wr3, 0, 255
        ).astype(np.uint8)

        stamp = msg_l.header.stamp

        out = self.bridge.cv2_to_imgmsg(unified, 'bgr8')
        out.header.stamp    = stamp
        out.header.frame_id = 'bev_unified'
        self.pub_unified.publish(out)

        viz = self.draw_viz(unified, lx0, lx1, rx0, rx1)
        v   = self.bridge.cv2_to_imgmsg(viz, 'bgr8')
        v.header.stamp    = stamp
        v.header.frame_id = 'bev_unified'
        self.pub_viz.publish(v)

    def draw_viz(self, img, lx0, lx1, rx0, rx1):
        viz = img.copy()
        h   = viz.shape[0]
        cv2.line(viz, (lx1, 0), (lx1, h), (255,255,255), 1)
        cv2.line(viz, (rx0, 0), (rx0, h), (255,255,255), 1)
        cv2.putText(viz, "LEFT",  (lx0+10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100,255,100), 2)
        cv2.putText(viz, "BLEND", ((lx1+rx0)//2-40, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255),   2)
        cv2.putText(viz, "RIGHT", (rx0+10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100,100,255), 2)
        cv2.putText(viz, "FIX5: fisheye undistort applied | /bev_unified",
                    (10, h-12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180,180,180), 1)
        return viz


def main(args=None):
    rclpy.init(args=args)
    node = ImageStitcher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
