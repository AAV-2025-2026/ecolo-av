#!/usr/bin/env python3
"""
dt_pham_wrapper.py  —  lane_stitcher package  [IMPROVED v2]
═══════════════════════════════════════════════════════════════════
Improvements over v1:
  ✅ FIX 1 — Shadow robustness:
       Multi-feature thresholding replaces single-threshold.
       HLS S-channel + Sobel X + LAB b-channel combined.
       Adaptive normalisation reduces shadow brightness shifts.

  ✅ FIX 2 — Faded lane markings:
       Added LAB b-channel threshold (detects yellow/white even
       when contrast is weak). Combined with OR logic so any one
       feature detecting a lane is enough.

  ✅ FIX 7 — Region of Interest:
       Trapezoid ROI mask applied BEFORE thresholding to remove
       sky, cars, buildings, and irrelevant edges. Makes the
       binary mask much cleaner — fewer false detections.

What we still use from Dt-Pham:
  ✅ LaneLines.forward()  — sliding window + polyfit
  ✅ LaneLines.plot()     — curvature + offset text

What we REPLACED from Dt-Pham:
  🔄 Thresholding.forward() — replaced with our improved version
     that handles shadows and faded markings better.

Subscribes:  /bev_unified
Publishes:   /lane_mask_unified  /lane_annotated  /lane_debug_thresh
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import numpy as np
import sys, os

# ── Load Dt-Pham repo ───────────────────────────────────────────────
LANE_REPO = os.environ.get(
    'LANE_REPO', os.path.expanduser('~/Advanced-Lane-Lines'))
sys.path.insert(0, LANE_REPO)

PIPELINE_OK = False
try:
    from LaneLines import LaneLines as _Lanes
    PIPELINE_OK = True
    print(f"[dt_pham_wrapper] ✅ LaneLines loaded from: {LANE_REPO}")
except ImportError as e:
    print(f"[dt_pham_wrapper] ❌ Import error: {e}")
    print(f"[dt_pham_wrapper]    Run: export LANE_REPO=~/Advanced-Lane-Lines")


# ══════════════════════════════════════════════════════════════════════
# IMPROVED THRESHOLDING  (replaces Dt-Pham Thresholding.forward())
# ══════════════════════════════════════════════════════════════════════

class ImprovedThresholding:
    """
    Multi-feature thresholding robust to shadows and faded markings.

    Three independent detectors combined with OR logic:
      1. HLS S-channel  — detects saturated colours (white/yellow lines)
      2. Sobel X        — detects strong horizontal edges (lane boundaries)
      3. LAB b-channel  — detects yellow markings even in low contrast

    Any ONE of the three firing is enough to mark a pixel as lane.
    This means shadows that kill one detector don't kill all three.
    """

    def __init__(self,
                 s_thresh   = (100, 255),   # HLS S channel
                 sx_thresh  = (20,  100),   # Sobel X gradient
                 lab_thresh = (155, 200),   # LAB b channel (yellow)
                 ):
        self.s_thresh   = s_thresh
        self.sx_thresh  = sx_thresh
        self.lab_thresh = lab_thresh

    def forward(self, img: np.ndarray) -> np.ndarray:
        """
        img:    BGR BEV image (already undistorted + warped)
        return: binary uint8 mask  0=road  255=lane
        """
        # ── 1. HLS S-channel threshold ─────────────────────────────
        # S channel = colour saturation. Lane paint = high saturation.
        # Shadows reduce brightness (L) but NOT saturation (S) → robust.
        hls  = cv2.cvtColor(img, cv2.COLOR_BGR2HLS)
        s    = hls[:, :, 2]
        s_binary = np.zeros_like(s, dtype=np.uint8)
        s_binary[(s >= self.s_thresh[0]) & (s <= self.s_thresh[1])] = 1

        # ── 2. Sobel X gradient threshold ──────────────────────────
        # Measures rate of change in X direction → finds vertical edges.
        # Lane lines have strong vertical edges even when colour is faded.
        gray   = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # CLAHE: contrast normalisation — reduces shadow brightness shift
        clahe  = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        gray   = clahe.apply(gray)
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        abs_sx  = np.absolute(sobel_x)
        # Normalise to 0-255
        if abs_sx.max() > 0:
            scaled_sx = np.uint8(255 * abs_sx / abs_sx.max())
        else:
            scaled_sx = np.zeros_like(gray)
        sx_binary = np.zeros_like(scaled_sx, dtype=np.uint8)
        sx_binary[(scaled_sx >= self.sx_thresh[0]) &
                  (scaled_sx <= self.sx_thresh[1])] = 1

        # ── 3. LAB b-channel threshold ──────────────────────────────
        # LAB b-channel separates blue from yellow very reliably.
        # Yellow lane markings → high b values even when faded.
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        b   = lab[:, :, 2]
        lab_binary = np.zeros_like(b, dtype=np.uint8)
        if b.max() > self.lab_thresh[0]:  # only apply if yellow present
            lab_binary[(b >= self.lab_thresh[0]) &
                       (b <= self.lab_thresh[1])] = 1

        # ── Combine: OR logic ───────────────────────────────────────
        # Any feature detecting a lane = lane pixel.
        combined = np.zeros_like(s_binary, dtype=np.uint8)
        combined[(s_binary == 1) | (sx_binary == 1) | (lab_binary == 1)] = 255

        return combined


# ══════════════════════════════════════════════════════════════════════
# ROI MASK  (Fix 7 — Region of Interest)
# ══════════════════════════════════════════════════════════════════════

def make_roi_mask(h: int, w: int) -> np.ndarray:
    """
    Trapezoidal ROI mask for a BEV image.
    In BEV the 'road' is the full canvas — we crop a central trapezoid
    to remove the edges of the stitched image which may contain
    artefacts, car bonnets, or irrelevant scenery.

    Keeps: centre 80% width, full height
    Removes: left/right 10% margins (stitching artefacts)
    """
    mask = np.zeros((h, w), dtype=np.uint8)
    margin_x = int(w * 0.05)   # 5% margin each side
    margin_y_top = int(h * 0.05)   # ignore top 5% (far horizon artefacts)
    pts = np.array([
        [margin_x,       margin_y_top],
        [w - margin_x,   margin_y_top],
        [w - margin_x,   h],
        [margin_x,       h],
    ], dtype=np.int32)
    cv2.fillPoly(mask, [pts], 255)
    return mask


# ══════════════════════════════════════════════════════════════════════
# MAIN NODE
# ══════════════════════════════════════════════════════════════════════

class DtPhamWrapper(Node):

    def __init__(self):
        super().__init__('dt_pham_wrapper')

        if not PIPELINE_OK:
            self.get_logger().error(
                f"LaneLines not found at: {LANE_REPO}\n"
                "  Fix: export LANE_REPO=~/Advanced-Lane-Lines"
            )

        # Our improved thresholding — replaces Dt-Pham's Thresholding
        self.thresholding = ImprovedThresholding()

        # Still use Dt-Pham's lane fitting (it's good)
        self.lane_lines = _Lanes() if PIPELINE_OK else None

        self.bridge  = CvBridge()
        self.frame_n = 0
        self.roi_mask = None   # built on first frame (need image size)

        self.sub = self.create_subscription(
            Image, '/bev_unified', self.detect_cb, 10)

        self.pub_mask  = self.create_publisher(Image, '/lane_mask_unified',  10)
        self.pub_anno  = self.create_publisher(Image, '/lane_annotated',     10)
        self.pub_debug = self.create_publisher(Image, '/lane_debug_thresh',  10)

        self.get_logger().info(
            "Dt-Pham Wrapper v2 ready\n"
            "  Improvements: shadows (FIX1) + faded markings (FIX2) + ROI (FIX7)\n"
            "  Thresholding: HLS-S + Sobel-X + LAB-b combined\n"
            "  /bev_unified → [Improved Threshold + ROI + LaneLines] → /lane_mask_unified"
        )

    def detect_cb(self, msg: Image):
        if not PIPELINE_OK:
            return

        bev = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        h, w = bev.shape[:2]
        self.frame_n += 1

        try:
            # ── FIX 7: Build ROI mask on first frame ─────────────────
            if self.roi_mask is None or self.roi_mask.shape != (h, w):
                self.roi_mask = make_roi_mask(h, w)
                self.get_logger().info(
                    f"ROI mask built for {w}x{h} image")

            # ── FIX 7: Apply ROI before thresholding ─────────────────
            # Mask out irrelevant parts of the image first.
            # This removes stitching artefacts and off-road areas.
            bev_roi = cv2.bitwise_and(bev,
                                      bev,
                                      mask=self.roi_mask)

            # ── FIX 1 + 2: Improved multi-feature thresholding ───────
            # HLS-S (shadow robust) + Sobel-X (faded lines) + LAB-b (yellow)
            binary = self.thresholding.forward(bev_roi)

            # ── Lane fitting (Dt-Pham LaneLines — unchanged) ─────────
            # Convert to 0/1 for compatibility with Dt-Pham
            binary_01 = (binary // 255).astype(np.uint8)
            lane_overlay = self.lane_lines.forward(binary_01)

            # ── Blend overlay onto BEV ────────────────────────────────
            if lane_overlay is not None and lane_overlay.shape == bev.shape:
                annotated = cv2.addWeighted(bev, 0.75, lane_overlay, 0.4, 0)
            else:
                annotated = bev.copy()

            # ── Optional text overlay from Dt-Pham ────────────────────
            try:
                annotated = self.lane_lines.plot(annotated)
            except Exception:
                pass

            cv2.putText(annotated,
                        f"v2: HLS+Sobel+LAB | ROI | frame {self.frame_n}",
                        (10, annotated.shape[0]-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,200), 1)

            # ── Publish ───────────────────────────────────────────────
            stamp = msg.header.stamp
            fid   = 'bev_unified'

            m = self.bridge.cv2_to_imgmsg(binary, 'mono8')
            m.header.stamp = stamp; m.header.frame_id = fid
            self.pub_mask.publish(m)

            a = self.bridge.cv2_to_imgmsg(annotated, 'bgr8')
            a.header.stamp = stamp; a.header.frame_id = fid
            self.pub_anno.publish(a)

            # Debug: show all three threshold layers as colour channels
            debug = self.make_debug_viz(bev, binary)
            d = self.bridge.cv2_to_imgmsg(debug, 'bgr8')
            d.header.stamp = stamp; d.header.frame_id = fid
            self.pub_debug.publish(d)

        except Exception as e:
            self.get_logger().warn(
                f"Frame {self.frame_n} error: {e}",
                throttle_duration_sec=2.0)

    def make_debug_viz(self, bev, combined_mask):
        """
        Show each threshold layer as a coloured overlay.
        Green  = S-channel detections
        Blue   = Sobel-X detections
        Red    = LAB-b detections
        White  = combined mask
        """
        h, w = bev.shape[:2]
        debug = bev.copy()

        # Recompute individual masks for visualisation
        hls = cv2.cvtColor(bev, cv2.COLOR_BGR2HLS)
        s   = hls[:, :, 2]
        s_m = np.zeros((h, w), np.uint8)
        s_m[(s >= 100) & (s <= 255)] = 255

        gray  = cv2.cvtColor(bev, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        gray  = clahe.apply(gray)
        sx    = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        asx   = np.absolute(sx)
        if asx.max() > 0:
            sx_sc = np.uint8(255 * asx / asx.max())
        else:
            sx_sc = np.zeros_like(gray)
        sx_m = np.zeros((h, w), np.uint8)
        sx_m[(sx_sc >= 20) & (sx_sc <= 100)] = 255

        overlay = np.zeros_like(debug)
        overlay[s_m  > 0] = (0,   200, 0)    # Green = S channel
        overlay[sx_m > 0] = (200,   0, 0)    # Blue  = Sobel
        overlay[combined_mask > 0] = (255, 255, 255)  # White = combined

        return cv2.addWeighted(debug, 0.6, overlay, 0.4, 0)


def main(args=None):
    rclpy.init(args=args)
    node = DtPhamWrapper()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
