#!/usr/bin/env python3
"""
lane_geometry_node.py  —  lane_geometry package  [IMPROVED v2]
═══════════════════════════════════════════════════════════════════
Improvements over v1:
  ✅ FIX 3 — Occlusion / lane tracking:
       Added TRACKING MODE. When lanes are found in frame t-1,
       frame t searches AROUND the previous polynomial instead
       of rescanning the whole image from scratch.
       Falls back to full sliding window only when tracking fails.
       Prevents sudden lane disappearance when a vehicle occludes.

  ✅ FIX 4 — Curved lane detection:
       Confirmed 2nd-order polynomial  x = Ay² + By + C.
       Added sanity checks to reject fits that are physically
       impossible (lane too wide, curvature too extreme).
       If only one lane found, the other is reconstructed using
       standard lane width (3.7m) — keeps curves stable.

  ✅ FIX 6 — Jitter / temporal smoothing:
       Exponential moving average on BOTH polynomials.
         smoothed = alpha * previous + (1 - alpha) * current
         alpha = 0.85 (keeps 85% of previous, blends 15% new)
       Also added per-frame sanity check: if new fit deviates
       more than MAX_FIT_DELTA from smoothed → reject + keep previous.
       Offset smoothed over last 10 frames (was 5).
       Curvature smoothed over last 10 frames (new).

Unchanged from v1:
  - Sliding window search (used as fallback)
  - Polynomial curvature formula
  - Real-world metre conversion
  - HUD visualisation (expanded)

Subscribed topics:
  /lane_mask_unified    sensor_msgs/Image
  /bev_unified          sensor_msgs/Image

Published topics:
  /lane_geometry        lane_geometry/LaneGeometry
  /lane_geometry_viz    sensor_msgs/Image
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import numpy as np
from message_filters import ApproximateTimeSynchronizer, Subscriber
from lane_geometry.msg import LaneGeometry

# Sliding window config
N_WINDOWS        = 9
WINDOW_WIDTH     = 100
MIN_PIX_RECENTER = 50
MIN_LANE_PIXELS  = 50

# Tracking mode config (FIX 3)
TRACKING_MARGIN  = 80    # px — search ±80px around previous polynomial
MIN_TRACK_PIXELS = 30    # minimum pixels in tracking mode to accept

# Smoothing config (FIX 6)
SMOOTH_ALPHA     = 0.85  # exponential moving average weight for previous
MAX_FIT_DELTA    = 200   # max allowed change in poly C coefficient per frame
CURV_BUF_LEN     = 10   # frames to average curvature over
OFFSET_BUF_LEN   = 10   # frames to average offset over (was 5)


class LaneGeometryNode(Node):

    def __init__(self):
        super().__init__('lane_geometry_node')

        self.declare_parameter('metres_per_pixel_x', 0.020)
        self.declare_parameter('metres_per_pixel_y', 0.025)
        self.declare_parameter('canvas_width',      1200)
        self.declare_parameter('canvas_height',      500)
        self.declare_parameter('steering_gain',      0.8)
        self.declare_parameter('max_steering',       1.0)
        self.declare_parameter('smooth_alpha',       0.85)

        self.mppx      = self.get_parameter('metres_per_pixel_x').value
        self.mppy      = self.get_parameter('metres_per_pixel_y').value
        self.canvas_w  = self.get_parameter('canvas_width').value
        self.canvas_h  = self.get_parameter('canvas_height').value
        self.steer_k   = self.get_parameter('steering_gain').value
        self.max_steer = self.get_parameter('max_steering').value
        self.alpha     = self.get_parameter('smooth_alpha').value

        self.bridge = CvBridge()

        # ── FIX 3: tracking state ────────────────────────────────────
        self.left_fit_prev  = None   # previous frame polynomial
        self.right_fit_prev = None
        self.tracking_mode  = False  # True = use search-around-poly

        # ── FIX 6: smoothing buffers ─────────────────────────────────
        self.left_fit_smooth  = None  # exponential moving average fit
        self.right_fit_smooth = None
        self.offset_buf = []          # rolling average offset
        self.curv_buf   = []          # rolling average curvature

        self.sub_mask = Subscriber(self, Image, '/lane_mask_unified')
        self.sub_bev  = Subscriber(self, Image, '/bev_unified')
        self.sync = ApproximateTimeSynchronizer(
            [self.sub_mask, self.sub_bev], queue_size=10, slop=0.05)
        self.sync.registerCallback(self.geometry_cb)

        self.pub_geom = self.create_publisher(LaneGeometry, '/lane_geometry',     10)
        self.pub_viz  = self.create_publisher(Image,        '/lane_geometry_viz', 10)

        self.get_logger().info(
            f"Lane Geometry node v2 ready\n"
            f"  Improvements: tracking (FIX3) + curves (FIX4) + smoothing (FIX6)\n"
            f"  scale: {self.mppx*100:.1f}cm/px (X)  {self.mppy*100:.1f}cm/px (Y)\n"
            f"  smooth_alpha={self.alpha} | tracking_margin={TRACKING_MARGIN}px"
        )

    # ── Main callback ─────────────────────────────────────────────────

    def geometry_cb(self, mask_msg: Image, bev_msg: Image):
        mask = self.bridge.imgmsg_to_cv2(mask_msg, 'mono8')
        bev  = self.bridge.imgmsg_to_cv2(bev_msg,  'bgr8')

        # ── FIX 3: Choose detection mode ─────────────────────────────
        if (self.tracking_mode and
                self.left_fit_prev is not None and
                self.right_fit_prev is not None):
            left_px, right_px, dbg, used_tracking = \
                self.search_around_poly(mask, bev.copy())
        else:
            left_px, right_px, dbg = self.sliding_window(mask, bev.copy())
            used_tracking = False

        # ── FIX 4: Polynomial fit with sanity checks ──────────────────
        left_fit,  lok = self.fit_poly_safe(
            left_px, self.left_fit_smooth)
        right_fit, rok = self.fit_poly_safe(
            right_px, self.right_fit_smooth)

        # ── FIX 3: Update tracking state ─────────────────────────────
        if lok and rok:
            self.tracking_mode  = True
            self.left_fit_prev  = left_fit.copy()
            self.right_fit_prev = right_fit.copy()
        elif lok or rok:
            self.tracking_mode = True   # partial — keep trying
            if lok: self.left_fit_prev  = left_fit.copy()
            if rok: self.right_fit_prev = right_fit.copy()
        else:
            # Complete loss — fall back to full window next frame
            self.tracking_mode = False

        # ── FIX 6: Exponential smoothing of polynomial fits ───────────
        left_fit  = self.smooth_fit(left_fit,  'left',  lok)
        right_fit = self.smooth_fit(right_fit, 'right', rok)
        lok = left_fit  is not None
        rok = right_fit is not None

        # ── Build LaneGeometry message ────────────────────────────────
        msg = LaneGeometry()
        msg.header.stamp    = mask_msg.header.stamp
        msg.header.frame_id = 'bev_unified'

        msg.left_lane_detected  = lok
        msg.right_lane_detected = rok
        msg.both_lanes_detected = lok and rok

        msg.left_confidence  = float(
            min(1.0, len(left_px[0])  / 500.0)) if lok and len(left_px) > 0 else 0.0
        msg.right_confidence = float(
            min(1.0, len(right_px[0]) / 500.0)) if rok and len(right_px) > 0 else 0.0

        if lok:
            msg.left_curvature_m = self.curvature_m(left_fit)
            msg.left_poly_a = float(left_fit[0])
            msg.left_poly_b = float(left_fit[1])
            msg.left_poly_c = float(left_fit[2])
        if rok:
            msg.right_curvature_m = self.curvature_m(right_fit)
            msg.right_poly_a = float(right_fit[0])
            msg.right_poly_b = float(right_fit[1])
            msg.right_poly_c = float(right_fit[2])

        if lok and rok:
            raw_curv = (msg.left_curvature_m + msg.right_curvature_m) / 2.0
            msg.curve_direction = float(
                np.sign((left_fit[1] + right_fit[1]) / 2.0))
        elif lok:
            raw_curv = msg.left_curvature_m
        elif rok:
            raw_curv = msg.right_curvature_m
        else:
            raw_curv = 9999.0

        # ── FIX 6: Smooth curvature over N frames ────────────────────
        self.curv_buf.append(raw_curv)
        if len(self.curv_buf) > CURV_BUF_LEN:
            self.curv_buf.pop(0)
        msg.mean_curvature_m = float(np.mean(self.curv_buf))

        msg.vehicle_offset_m, msg.lane_width_m = self.offset_and_width(
            left_fit if lok else None,
            right_fit if rok else None)

        # ── FIX 6: Smooth offset over N frames ───────────────────────
        self.offset_buf.append(msg.vehicle_offset_m)
        if len(self.offset_buf) > OFFSET_BUF_LEN:
            self.offset_buf.pop(0)
        msg.vehicle_offset_m = float(np.mean(self.offset_buf))

        msg.steering_hint = float(np.clip(
            msg.vehicle_offset_m * self.steer_k,
            -self.max_steer, self.max_steer))

        self.pub_geom.publish(msg)

        viz = self.draw_viz(dbg, msg,
                            left_fit  if lok else None,
                            right_fit if rok else None,
                            used_tracking)
        viz_msg = self.bridge.cv2_to_imgmsg(viz, 'bgr8')
        viz_msg.header = mask_msg.header
        self.pub_viz.publish(viz_msg)

    # ══════════════════════════════════════════════════════════════════
    # FIX 3 — Tracking mode: search around previous polynomial
    # ══════════════════════════════════════════════════════════════════

    def search_around_poly(self, mask, dbg):
        """
        Instead of scanning the whole image with sliding windows,
        search only within TRACKING_MARGIN pixels of the previous poly.
        Much faster and more robust when a vehicle briefly occludes.
        Falls back to sliding window if fewer than MIN_TRACK_PIXELS found.
        """
        h, w   = mask.shape
        ploty  = np.arange(h)

        def search_near(fit, col):
            x_base = np.polyval(fit, ploty).astype(int)
            x_lo   = np.clip(x_base - TRACKING_MARGIN, 0, w-1)
            x_hi   = np.clip(x_base + TRACKING_MARGIN, 0, w-1)
            nzy, nzx = np.nonzero(mask)
            mask_ok = (nzx >= x_lo[nzy]) & (nzx <= x_hi[nzy])
            px_y = nzy[mask_ok]
            px_x = nzx[mask_ok]
            # Draw search zone outline on debug image
            for y in range(0, h, 10):
                cv2.circle(dbg, (int(x_lo[y]), y), 1, col, -1)
                cv2.circle(dbg, (int(x_hi[y]), y), 1, col, -1)
            return px_x, px_y

        l_x, l_y = search_near(self.left_fit_prev,  (0,200,0))
        r_x, r_y = search_near(self.right_fit_prev, (0,0,200))

        # Fall back to sliding window if tracking found too few pixels
        if len(l_x) < MIN_TRACK_PIXELS or len(r_x) < MIN_TRACK_PIXELS:
            self.get_logger().info(
                "Tracking lost — falling back to sliding window",
                throttle_duration_sec=1.0)
            left_px, right_px, dbg2 = self.sliding_window(mask, dbg)
            return left_px, right_px, dbg2, False

        return (l_x, l_y), (r_x, r_y), dbg, True

    # ══════════════════════════════════════════════════════════════════
    # Standard sliding window (used on first frame or after loss)
    # ══════════════════════════════════════════════════════════════════

    def sliding_window(self, mask, dbg):
        h, w  = mask.shape
        hist  = np.sum(mask[h//2:, :], axis=0).astype(np.float32)
        mid   = w // 2
        lx    = int(np.argmax(hist[:mid]))
        rx    = int(np.argmax(hist[mid:]) + mid)
        win_h = h // N_WINDOWS
        l_pts, r_pts = [], []

        for win in range(N_WINDOWS):
            y0 = h - (win+1) * win_h
            y1 = h -  win    * win_h
            for cx, pts, col in [
                (lx, l_pts, (0, 255, 0)),
                (rx, r_pts, (0, 0, 255)),
            ]:
                x0 = max(cx - WINDOW_WIDTH, 0)
                x1 = min(cx + WINDOW_WIDTH, w)
                cv2.rectangle(dbg, (x0, y0), (x1, y1), col, 2)
                roi = mask[y0:y1, x0:x1]
                nzy, nzx = np.where(roi)
                nzx_abs = nzx + x0
                nzy_abs = nzy + y0
                pts.extend(zip(nzx_abs.tolist(), nzy_abs.tolist()))
                if len(nzx) > MIN_PIX_RECENTER:
                    if pts is l_pts: lx = int(np.mean(nzx_abs))
                    else:            rx = int(np.mean(nzx_abs))

        def to_arr(pts):
            if not pts:
                return np.array([]), np.array([])
            a = np.array(pts).T
            return a[0], a[1]

        return to_arr(l_pts), to_arr(r_pts), dbg

    # ══════════════════════════════════════════════════════════════════
    # FIX 4 — Safe polynomial fit with sanity checks
    # ══════════════════════════════════════════════════════════════════

    def fit_poly_safe(self, px, prev_smooth):
        """
        Fits 2nd-order polynomial x = Ay² + By + C.
        Rejects physically impossible fits:
          - Lane too far left or right (C < 0 or C > canvas_w)
          - Curvature impossibly tight (|A| > threshold)
          - Fit deviates too far from smoothed previous
        Falls back to smoothed previous if fit fails sanity check.
        """
        if len(px) < 2 or len(px[0]) < MIN_LANE_PIXELS:
            return None, False

        try:
            fit = np.polyfit(px[1], px[0], 2)
        except Exception:
            return None, False

        # Sanity checks
        A, B, C = fit
        # C = x position at bottom of image — must be on canvas
        if not (0 <= C <= self.canvas_w):
            if prev_smooth is not None:
                return prev_smooth.copy(), True   # use smoothed fallback
            return None, False

        # A = curvature coefficient — reject impossible values
        if abs(A) > 0.005:   # ~20m radius at this scale is tightest plausible
            if prev_smooth is not None:
                return prev_smooth.copy(), True
            return None, False

        # Reject if too far from previous smoothed fit
        if (prev_smooth is not None and
                abs(C - prev_smooth[2]) > MAX_FIT_DELTA):
            self.get_logger().info(
                f"Fit rejected: C delta={abs(C-prev_smooth[2]):.0f}px > {MAX_FIT_DELTA}",
                throttle_duration_sec=1.0)
            return prev_smooth.copy(), True

        return fit, True

    # ══════════════════════════════════════════════════════════════════
    # FIX 6 — Exponential moving average smoothing of polynomial
    # ══════════════════════════════════════════════════════════════════

    def smooth_fit(self, fit, side: str, detected: bool):
        """
        smoothed = alpha * prev_smooth + (1-alpha) * current
        If no detection this frame → hold previous smoothed value.
        """
        attr = f'{side}_fit_smooth'
        prev = getattr(self, attr)

        if fit is None and not detected:
            return prev   # hold previous

        if prev is None:
            setattr(self, attr, fit.copy() if fit is not None else None)
            return fit

        if fit is not None:
            smoothed = self.alpha * prev + (1.0 - self.alpha) * fit
            setattr(self, attr, smoothed)
            return smoothed

        return prev  # detection failed — hold previous

    # ── Curvature in real metres (FIX 4 — confirmed 2nd order) ───────

    def curvature_m(self, fit) -> float:
        A = fit[0] * (self.mppx / self.mppy ** 2)
        B = fit[1] * (self.mppx / self.mppy)
        y = self.canvas_h * self.mppy
        R = ((1 + (2*A*y + B)**2) ** 1.5) / max(abs(2*A), 1e-6)
        return float(np.clip(R, 0.0, 10000.0))

    # ── Vehicle offset + lane width ───────────────────────────────────

    def offset_and_width(self, left_fit, right_fit):
        y = float(self.canvas_h)
        def ev(f): return f[0]*y**2 + f[1]*y + f[2]
        default_w_px = 3.7 / self.mppx

        if left_fit is not None and right_fit is not None:
            xl, xr = ev(left_fit), ev(right_fit)
        elif left_fit is not None:
            xl = ev(left_fit); xr = xl + default_w_px
        elif right_fit is not None:
            xr = ev(right_fit); xl = xr - default_w_px
        else:
            return 0.0, 3.7

        offset_m = (((xl + xr) / 2.0) - (self.canvas_w / 2.0)) * self.mppx
        width_m  = (xr - xl) * self.mppx
        return float(offset_m), float(width_m)

    # ── HUD visualisation (expanded for v2) ───────────────────────────

    def draw_viz(self, img, msg, left_fit, right_fit, used_tracking):
        h, w  = img.shape[:2]
        ploty = np.linspace(0, h-1, h)

        def draw_poly(fit, col):
            if fit is None: return
            pts = np.array([
                [int(np.polyval(fit, y)), int(y)]
                for y in ploty
                if 0 <= int(np.polyval(fit, y)) < w
            ], np.int32)
            if len(pts) > 1:
                cv2.polylines(img, [pts], False, col, 4)

        draw_poly(left_fit,  (0, 255, 0))
        draw_poly(right_fit, (0, 0, 255))

        # Shade lane area
        if left_fit is not None and right_fit is not None:
            lp = [[int(np.polyval(left_fit,  y)), int(y)] for y in ploty]
            rp = [[int(np.polyval(right_fit, y)), int(y)] for y in reversed(ploty)]
            lm = np.zeros_like(img)
            cv2.fillPoly(lm, [np.array(lp+rp, np.int32)], (0,60,0))
            img = cv2.addWeighted(img, 0.8, lm, 0.3, 0)

        # Tracking mode badge
        mode_txt = "TRACKING" if used_tracking else "SLIDING WIN"
        mode_col = (0,255,255) if used_tracking else (0,200,200)
        cv2.putText(img, mode_txt, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, mode_col, 2)

        # HUD panel
        panel = np.full((110, w, 3), 28, np.uint8)

        def put(txt, x, y, col=(240,240,240), s=0.65, th=1):
            cv2.putText(panel, txt, (x,y),
                        cv2.FONT_HERSHEY_SIMPLEX, s, col, th)

        # Curvature
        put("CURVATURE", 10, 26, (140,140,140), 0.5)
        curv = msg.mean_curvature_m
        put(f"{curv:.0f}m" if curv < 9000 else "Straight",
            10, 58, (0,255,255), 0.85, 2)

        # Offset
        off = msg.vehicle_offset_m
        off_col = (0,255,0) if abs(off)<0.15 else \
                  (0,165,255) if abs(off)<0.30 else (0,0,255)
        put("OFFSET", w//2-70, 26, (140,140,140), 0.5)
        put(f"{abs(off)*100:.1f}cm {'R' if off>0 else 'L'}",
            w//2-70, 58, off_col, 0.85, 2)

        # Steering hint
        put("STEERING", w-190, 26, (140,140,140), 0.5)
        sh = msg.steering_hint
        sh_col = (0,255,0) if abs(sh)<0.2 else \
                 (0,165,255) if abs(sh)<0.5 else (0,0,255)
        put(f"{sh:+.3f}", w-190, 58, sh_col, 0.9, 2)

        # Smooth mode label
        put(f"smooth α={self.alpha} | {10}fr avg",
            10, 92, (100,100,100), 0.38)

        # Confidence bars
        lc = int(msg.left_confidence  * 80)
        rc = int(msg.right_confidence * 80)
        cv2.rectangle(panel, (w//2-60, 74), (w//2-60+lc, 85), (0,200,0),  -1)
        cv2.rectangle(panel, (w//2+10, 74), (w//2+10+rc, 85), (0,0,200),  -1)
        put("L", w//2-68, 84, (100,200,100), 0.4)
        put("R", w//2+5,  84, (100,100,200), 0.4)

        return np.vstack([img, panel])


def main(args=None):
    rclpy.init(args=args)
    node = LaneGeometryNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
