#!/usr/bin/env python3
"""
AAV Lane Detection — Standalone Pipeline (Fixed)
═══════════════════════════════════════════════════════════════════
Uses the actual Dt-Pham pipeline correctly:
  1. Undistort (if calibration available)
  2. Perspective warp to bird's eye view (BEV)
  3. Threshold in BEV space
  4. Fit polynomials in BEV space
  5. Warp lane overlay BACK to original perspective
  6. Blend onto original frame

This is what the original code does — and why it works.
The previous version was fitting polynomials on the raw perspective
image which caused the "flying lanes" issue.

Usage:
  python3 lane_pipeline.py --video /path/to/dashcam.mp4
  python3 lane_pipeline.py --video /path/to/dashcam.mp4 --crop_top 0.35
  python3 lane_pipeline.py --video /path/to/dashcam.mp4 --src_points auto

Requirements:
  pip install opencv-python numpy
  (No moviepy, no docopt needed)
"""

import cv2
import numpy as np
import argparse
import os
import csv
import sys
import time
from datetime import datetime
from collections import deque


# ═══════════════════════════════════════════════════════════════════
# PERSPECTIVE TRANSFORMATION
# ═══════════════════════════════════════════════════════════════════

class PerspectiveTransform:
    """
    Warps front-view image to bird's eye view and back.
    src points define the road trapezoid in the original image.
    dst points define where that trapezoid maps to in BEV.
    """
    def __init__(self, w, h, crop_top_pct=0.0):
        """
        Auto-compute src/dst based on image size and crop.
        These proportions work well for most forward-facing dashcams.
        Adjust src if lanes still don't warp correctly for your footage.
        """
        # How far down from top the vanishing point sits
        # (after crop_top is already applied to the frame)
        vp_y = int(h * 0.62)   # vanishing point y
        bot_y = h - 1

        # Trapezoid narrower at top, wider at bottom
        top_l_x = int(w * 0.43)
        top_r_x = int(w * 0.57)
        bot_l_x = int(w * 0.12)
        bot_r_x = int(w * 0.88)

        self.src = np.float32([
            [top_l_x, vp_y],   # top-left
            [bot_l_x, bot_y],  # bottom-left
            [bot_r_x, bot_y],  # bottom-right
            [top_r_x, vp_y],   # top-right
        ])

        # BEV destination — straight parallel lanes
        margin = int(w * 0.20)
        self.dst = np.float32([
            [margin,     0],
            [margin,     h],
            [w - margin, h],
            [w - margin, 0],
        ])

        self.M     = cv2.getPerspectiveTransform(self.src, self.dst)
        self.M_inv = cv2.getPerspectiveTransform(self.dst, self.src)
        self.size  = (w, h)

    def warp(self, img):
        return cv2.warpPerspective(img, self.M, self.size,
                                   flags=cv2.INTER_LINEAR)

    def unwarp(self, img):
        return cv2.warpPerspective(img, self.M_inv, self.size,
                                   flags=cv2.INTER_LINEAR)

    def draw_src(self, img):
        """Draw the source trapezoid on the image for debugging."""
        pts = self.src.astype(np.int32).reshape((-1, 1, 2))
        return cv2.polylines(img.copy(), [pts], True, (0, 0, 255), 2)


# ═══════════════════════════════════════════════════════════════════
# THRESHOLDING
# ═══════════════════════════════════════════════════════════════════

def threshold_frame(img):
    """
    Multi-channel thresholding on the WARPED (BEV) image.
    Combines HLS S-channel + L-channel + HSV V-channel.
    Based on Dt-Pham's approach with our improvements added.
    """
    # Convert colour spaces
    hls = cv2.cvtColor(img, cv2.COLOR_BGR2HLS)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    h_ch = hls[:, :, 0]
    l_ch = hls[:, :, 1]
    s_ch = hls[:, :, 2]
    v_ch = hsv[:, :, 2]

    # White lane lines — high L + high V
    def rel(ch, lo, hi):
        vmin, vmax = float(ch.min()), float(ch.max())
        vlo = vmin + (vmax - vmin) * lo
        vhi = vmin + (vmax - vmin) * hi
        return np.uint8((ch >= vlo) & (ch <= vhi)) * 255

    def abso(ch, lo, hi):
        return np.uint8((ch >= lo) & (ch <= hi)) * 255

    white = rel(l_ch, 0.8, 1.0)

    # Yellow lane lines — H in yellow range + high V
    yellow = abso(h_ch, 20, 30)
    yellow = yellow & rel(v_ch, 0.7, 1.0)

    # HLS S-channel for shadows (our FIX 1)
    s_binary = abso(s_ch, 80, 255)

    # Sobel X on L channel (edge detection)
    l_eq = cv2.equalizeHist(l_ch)
    sobelx = cv2.Sobel(l_eq, cv2.CV_64F, 1, 0, ksize=3)
    abs_sx = np.absolute(sobelx)
    max_sx = abs_sx.max()
    if max_sx > 0:
        scaled_sx = np.uint8(255 * abs_sx / max_sx)
    else:
        scaled_sx = np.zeros_like(l_ch)
    sx_binary = abso(scaled_sx, 25, 150)

    # Combine: (white OR yellow) OR (s_channel AND sobel)
    combined = np.zeros_like(l_ch)
    combined[(white == 255) | (yellow == 255) |
             ((s_binary == 255) & (sx_binary == 255))] = 255

    return combined


# ═══════════════════════════════════════════════════════════════════
# LANE FITTING
# ═══════════════════════════════════════════════════════════════════

SMOOTH_ALPHA = 0.85
NWINDOWS     = 9
MARGIN       = 80
MINPIX       = 40

class LaneFitter:
    def __init__(self):
        self.left_fit  = None
        self.right_fit = None
        self.tracking  = False
        self.no_detect_count = 0

    def _smooth(self, old, new):
        if old is None:
            return new
        return SMOOTH_ALPHA * old + (1.0 - SMOOTH_ALPHA) * new

    def fit(self, binary):
        """Fit polynomials to lane pixels in BEV binary image."""
        h, w = binary.shape

        nonzero  = binary.nonzero()
        nonzeroy = np.array(nonzero[0])
        nonzerox = np.array(nonzero[1])

        if self.tracking and self.left_fit is not None and self.right_fit is not None:
            # Search around previous polynomial (FIX 3)
            lf, rf = self.left_fit, self.right_fit
            ploty = nonzeroy
            l_pred = lf[0]*ploty**2 + lf[1]*ploty + lf[2]
            r_pred = rf[0]*ploty**2 + rf[1]*ploty + rf[2]
            l_idx = (nonzerox >= l_pred - MARGIN) & (nonzerox <= l_pred + MARGIN)
            r_idx = (nonzerox >= r_pred - MARGIN) & (nonzerox <= r_pred + MARGIN)
            leftx  = nonzerox[l_idx]; lefty  = nonzeroy[l_idx]
            rightx = nonzerox[r_idx]; righty = nonzeroy[r_idx]
        else:
            # Sliding window from scratch
            histogram = np.sum(binary[h//2:, :], axis=0)
            mid = w // 2
            leftx_cur  = np.argmax(histogram[:mid])
            rightx_cur = np.argmax(histogram[mid:]) + mid

            win_h = h // NWINDOWS
            l_inds, r_inds = [], []

            for win in range(NWINDOWS):
                y_lo = h - (win + 1) * win_h
                y_hi = h - win * win_h
                xl_lo, xl_hi = leftx_cur  - MARGIN, leftx_cur  + MARGIN
                xr_lo, xr_hi = rightx_cur - MARGIN, rightx_cur + MARGIN

                gl = ((nonzeroy >= y_lo) & (nonzeroy < y_hi) &
                      (nonzerox >= xl_lo) & (nonzerox < xl_hi)).nonzero()[0]
                gr = ((nonzeroy >= y_lo) & (nonzeroy < y_hi) &
                      (nonzerox >= xr_lo) & (nonzerox < xr_hi)).nonzero()[0]
                l_inds.append(gl); r_inds.append(gr)

                if len(gl) > MINPIX: leftx_cur  = int(np.mean(nonzerox[gl]))
                if len(gr) > MINPIX: rightx_cur = int(np.mean(nonzerox[gr]))

            l_idx = np.concatenate(l_inds)
            r_idx = np.concatenate(r_inds)
            leftx  = nonzerox[l_idx]; lefty  = nonzeroy[l_idx]
            rightx = nonzerox[r_idx]; righty = nonzeroy[r_idx]

        # Minimum pixel threshold (Dt-Pham uses 1500, we use lower for dashcam)
        left_ok  = len(lefty)  > 800
        right_ok = len(righty) > 800

        if left_ok:
            new_l = np.polyfit(lefty, leftx, 2)
            self.left_fit = self._smooth(self.left_fit, new_l)
        if right_ok:
            new_r = np.polyfit(righty, rightx, 2)
            self.right_fit = self._smooth(self.right_fit, new_r)

        if left_ok or right_ok:
            self.tracking = True
            self.no_detect_count = 0
        else:
            self.no_detect_count += 1
            if self.no_detect_count > 20:
                self.tracking = False

        return left_ok, right_ok

    def get_lane_overlay(self, h, w):
        """
        Draw the filled lane polygon on a blank BEV image.
        This gets warped BACK to the original perspective.
        """
        overlay = np.zeros((h, w, 3), dtype=np.uint8)
        if self.left_fit is None or self.right_fit is None:
            return overlay

        ploty = np.linspace(0, h - 1, h)
        left_x  = self.left_fit[0]*ploty**2  + self.left_fit[1]*ploty  + self.left_fit[2]
        right_x = self.right_fit[0]*ploty**2 + self.right_fit[1]*ploty + self.right_fit[2]

        # Filled green polygon
        pts_l = np.array([np.transpose(np.vstack([left_x,  ploty]))])
        pts_r = np.array([np.flipud(np.transpose(np.vstack([right_x, ploty])))])
        pts   = np.hstack((pts_l, pts_r))
        cv2.fillPoly(overlay, np.int32([pts]), (0, 180, 0))

        # Lane lines
        for fitx, color in [(left_x, (255, 255, 0)), (right_x, (0, 220, 255))]:
            pts_line = np.array([np.transpose(np.vstack([fitx, ploty]))], dtype=np.int32)
            cv2.polylines(overlay, pts_line, False, color, 12)

        return overlay

    def measure_curvature(self, h):
        """Compute radius of curvature and vehicle offset in metres."""
        ym = 30.0 / 720   # metres per pixel y (Dt-Pham calibration)
        xm = 3.7 / 700    # metres per pixel x

        if self.left_fit is None or self.right_fit is None:
            return None, None, None

        y_eval = h - 1

        # Radius of curvature
        def curv(fit):
            a = fit[0] * xm / (ym**2)
            b = fit[1] * xm / ym
            y = y_eval * ym
            return ((1 + (2*a*y + b)**2)**1.5) / (abs(2*a) + 1e-6)

        lR = curv(self.left_fit)
        rR = curv(self.right_fit)
        mean_curv = (lR + rR) / 2.0

        # Vehicle offset from centre
        lx  = self.left_fit[0]*y_eval**2  + self.left_fit[1]*y_eval  + self.left_fit[2]
        rx  = self.right_fit[0]*y_eval**2 + self.right_fit[1]*y_eval + self.right_fit[2]
        w   = 1280  # assumed frame width
        pos = (w/2 - (lx + rx)/2) * xm
        lw  = (rx - lx) * xm

        return mean_curv, pos, lw


# ═══════════════════════════════════════════════════════════════════
# STATE MACHINE
# ═══════════════════════════════════════════════════════════════════

STATE_LANE_KEEP     = "LANE_KEEP"
STATE_LANE_CHANGE   = "LANE_CHANGING"
STATE_NO_LANE_STOP  = "NO_LANE_STOPPING"
STATE_RESUMING      = "RESUMING"

STATE_COLORS = {
    STATE_LANE_KEEP:    (80, 200, 80),
    STATE_LANE_CHANGE:  (40, 180, 220),
    STATE_NO_LANE_STOP: (60,  60, 220),
    STATE_RESUMING:     (180, 100, 220),
}

class StateMachine:
    def __init__(self, fps):
        self.state = STATE_LANE_KEEP
        self.no_lane_frames  = 0
        self.lc_frames       = 0
        self.watchdog_limit  = int(fps * 2)   # 2s
        self.lc_limit        = int(fps * 8)   # 8s
        self.offset_buf      = deque(maxlen=8)

    def update(self, left_ok, right_ok, offset):
        detected = left_ok or right_ok
        self.offset_buf.append(offset if offset else 0.0)

        if not detected:
            self.no_lane_frames += 1
        else:
            self.no_lane_frames = 0

        # Watchdog
        if self.no_lane_frames >= self.watchdog_limit:
            self.state = STATE_NO_LANE_STOP
            return self.state

        if self.state == STATE_LANE_KEEP:
            if not detected:
                self.state = STATE_NO_LANE_STOP
            elif offset and abs(offset) > 0.40:
                buf = list(self.offset_buf)
                if len(buf) >= 2 and abs(buf[-1] - buf[-2]) > 0.04:
                    self.state = STATE_LANE_CHANGE
                    self.lc_frames = 0

        elif self.state == STATE_LANE_CHANGE:
            self.lc_frames += 1
            if self.lc_frames >= self.lc_limit:
                self.state = STATE_NO_LANE_STOP
            elif detected and offset and abs(offset) < 0.15:
                self.state = STATE_LANE_KEEP

        elif self.state == STATE_NO_LANE_STOP:
            if detected:
                self.state = STATE_RESUMING

        elif self.state == STATE_RESUMING:
            if detected:
                self.state = STATE_LANE_KEEP

        return self.state


# ═══════════════════════════════════════════════════════════════════
# HUD OVERLAY
# ═══════════════════════════════════════════════════════════════════

def draw_hud(frame, curvature, offset, lane_width, state, frame_n):
    h, w = frame.shape[:2]
    out  = frame.copy()
    col  = STATE_COLORS.get(state, (200, 200, 200))

    # Semi-transparent bottom panel
    panel = out.copy()
    cv2.rectangle(panel, (0, h - 110), (400, h), (10, 10, 10), -1)
    cv2.addWeighted(panel, 0.65, out, 0.35, 0, out)

    # State badge
    cv2.rectangle(out, (w - 310, 12), (w - 10, 55), (20, 20, 20), -1)
    cv2.rectangle(out, (w - 310, 12), (w - 10, 55), col, 2)
    cv2.putText(out, state, (w - 300, 41),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)

    # Metrics
    curv_s = f"{curvature:.0f} m" if curvature else "---"
    off_s  = (f"{abs(offset)*100:.1f} cm {'R' if offset < 0 else 'L'}"
              if offset is not None else "---")
    lw_s   = f"{lane_width:.2f} m" if lane_width else "---"

    rows = [
        ("Curvature",  curv_s),
        ("Offset",     off_s),
        ("Lane width", lw_s),
    ]
    y0 = h - 100
    for label, val in rows:
        cv2.putText(out, f"{label}:", (12, y0),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (160, 160, 160), 1)
        cv2.putText(out, val, (155, y0),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (230, 230, 230), 1)
        y0 += 28

    cv2.putText(out, f"Frame {frame_n}", (12, h - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (100, 100, 100), 1)
    return out


# ═══════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════

def run(video_path, output_dir, crop_top, crop_bot, start_sec, show_warp):
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"ERROR: Cannot open: {video_path}")
        sys.exit(1)

    src_w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total   = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    crop_top_px = int(src_h * crop_top)
    crop_bot_px = int(src_h * crop_bot)
    out_h = src_h - crop_top_px - crop_bot_px
    out_w = src_w

    print(f"\n{'='*60}")
    print(f"  AAV Lane Detection — Standalone Pipeline")
    print(f"{'='*60}")
    print(f"  Input    : {os.path.basename(video_path)}")
    print(f"  Size     : {src_w}x{src_h}  crop→{out_w}x{out_h}")
    print(f"  FPS      : {src_fps:.0f}   Frames: {total}")
    print(f"  Output   : {output_dir}")
    print(f"{'='*60}\n")

    if start_sec > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(start_sec * src_fps))

    # Init components
    transform = PerspectiveTransform(out_w, out_h, crop_top)
    fitter    = LaneFitter()
    sm        = StateMachine(src_fps)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    w_anno = cv2.VideoWriter(
        os.path.join(output_dir, f"lane_annotated_{ts}.mp4"),
        fourcc, src_fps, (out_w, out_h))
    w_hud  = cv2.VideoWriter(
        os.path.join(output_dir, f"lane_hud_{ts}.mp4"),
        fourcc, src_fps, (out_w, out_h))

    csv_path = os.path.join(output_dir, f"lane_geometry_{ts}.csv")
    csv_f    = open(csv_path, "w", newline="")
    csv_w    = csv.writer(csv_f)
    csv_w.writerow(["frame","time_s","curvature_m","offset_m",
                    "lane_width_m","left_det","right_det","state"])

    frame_n = 0
    t0      = time.time()

    while True:
        ret, raw = cap.read()
        if not ret:
            break
        frame_n += 1
        ts_ms = cap.get(cv2.CAP_PROP_POS_MSEC)

        # 1. Crop sky and bonnet
        frame = raw[crop_top_px: src_h - crop_bot_px, :]

        # 2. Warp to BEV  ← THIS is the key fix
        warped = transform.warp(frame)

        # 3. Threshold in BEV space
        binary = threshold_frame(warped)

        # 4. Fit polynomials in BEV space
        left_ok, right_ok = fitter.fit(binary)

        # 5. Get geometry
        curvature, offset, lane_width = fitter.measure_curvature(out_h)

        # 6. State machine
        state = sm.update(left_ok, right_ok, offset)

        # 7. Draw lane overlay on BLANK BEV image
        bev_overlay = fitter.get_lane_overlay(out_h, out_w)

        # 8. Warp overlay BACK to original perspective  ← KEY fix
        overlay_unwarped = transform.unwarp(bev_overlay)

        # 9. Blend onto original frame
        annotated = cv2.addWeighted(frame, 1.0, overlay_unwarped, 0.45, 0)

        # 10. HUD
        hud_frame = draw_hud(annotated.copy(), curvature, offset,
                              lane_width, state, frame_n)

        # 11. Optional: show warp trapezoid for debugging
        if show_warp:
            annotated = transform.draw_src(annotated)

        w_anno.write(annotated)
        w_hud.write(hud_frame)

        csv_w.writerow([
            frame_n,
            f"{ts_ms/1000:.3f}",
            f"{curvature:.2f}" if curvature   else "",
            f"{offset:.4f}"    if offset is not None else "",
            f"{lane_width:.3f}" if lane_width else "",
            int(left_ok), int(right_ok), state
        ])

        if frame_n % 150 == 0 or frame_n == 1:
            elapsed = time.time() - t0
            fps_avg = frame_n / max(elapsed, 0.001)
            pct     = frame_n / max(total, 1) * 100
            eta     = (total - frame_n) / max(fps_avg, 1)
            print(f"  [{frame_n:5d}/{total}] {pct:5.1f}%  "
                  f"{fps_avg:5.1f}fps  ETA {eta:.0f}s  {state}")

    cap.release()
    w_anno.release()
    w_hud.release()
    csv_f.close()

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  DONE  {frame_n} frames  {elapsed:.1f}s  "
          f"({frame_n/max(elapsed,0.001):.1f}fps avg)")
    print(f"  lane_annotated_{ts}.mp4")
    print(f"  lane_hud_{ts}.mp4")
    print(f"  lane_geometry_{ts}.csv")
    print(f"{'='*60}\n")


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="AAV Lane Detection Pipeline")
    p.add_argument("--video",      required=True,  help="Input video path")
    p.add_argument("--output_dir", default=os.path.expanduser("~/lane_output"),
                   help="Output folder (default: ~/lane_output)")
    p.add_argument("--crop_top",   type=float, default=0.35,
                   help="Top crop fraction — remove sky (default: 0.35)")
    p.add_argument("--crop_bot",   type=float, default=0.04,
                   help="Bottom crop fraction — remove bonnet (default: 0.04)")
    p.add_argument("--start_sec",  type=float, default=0.0,
                   help="Skip ahead N seconds (default: 0)")
    p.add_argument("--show_warp",  action="store_true",
                   help="Draw warp trapezoid on output (debug)")
    args = p.parse_args()

    if not os.path.exists(args.video):
        print(f"ERROR: File not found: {args.video}")
        sys.exit(1)

    run(args.video, args.output_dir, args.crop_top,
        args.crop_bot, args.start_sec, args.show_warp)
