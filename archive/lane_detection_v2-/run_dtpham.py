#!/usr/bin/env python3
"""
run_dtpham.py — Run original Dt-Pham lane detection on any video
═══════════════════════════════════════════════════════════════════
Wraps the original FindLaneLines pipeline from Dt-Pham's
Advanced-Lane-Lines repo. Works on MP4, MOV, AVI, MKV.

IMPORTANT: Must be run from the Advanced-Lane-Lines directory
  cd ~/Advanced-Lane-Lines
  python3 run_dtpham.py --video ~/videos/MOV00001.AVI

Or set LANE_REPO env variable:
  LANE_REPO=~/Advanced-Lane-Lines python3 run_dtpham.py --video ...

Arguments:
  --video       Path to input video (required)
  --output      Output video path (default: ~/lane_output/out_TIMESTAMP.mp4)
  --crop_top    Fraction to crop from top — removes sky (default: 0.35)
  --crop_bot    Fraction to crop from bottom — removes bonnet (default: 0.04)
  --resize_w    Resize width before processing (default: 1280)
  --resize_h    Resize height before processing (default: 720)
"""

import cv2
import numpy as np
import argparse
import os
import sys
import time
from datetime import datetime

# ── Locate Dt-Pham repo ───────────────────────────────────────────
LANE_REPO = os.environ.get(
    "LANE_REPO",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".")
)

# Check common locations
for candidate in [
    LANE_REPO,
    os.path.expanduser("~/Advanced-Lane-Lines"),
    os.path.expanduser("~/Desktop/aav/Advanced-Lane-Lines"),
    os.path.dirname(os.path.abspath(__file__)),
]:
    if os.path.exists(os.path.join(candidate, "LaneLines.py")):
        LANE_REPO = candidate
        break
else:
    print("ERROR: Cannot find Advanced-Lane-Lines repo.")
    print("  Run from that directory, or set:")
    print("  export LANE_REPO=/path/to/Advanced-Lane-Lines")
    sys.exit(1)

sys.path.insert(0, LANE_REPO)
os.chdir(LANE_REPO)  # needed so LaneLines can find left_turn.png etc.

from CameraCalibration import CameraCalibration
from Thresholding import Thresholding
from PerspectiveTransformation import PerspectiveTransformation
from LaneLines import LaneLines


# ═══════════════════════════════════════════════════════════════════
# PIPELINE CLASS (from Dt-Pham main.py, adapted for any video)
# ═══════════════════════════════════════════════════════════════════

class FindLaneLines:
    def __init__(self):
        self.calibration = CameraCalibration('camera_cal', 9, 6)
        self.thresholding = Thresholding()
        self.transform    = PerspectiveTransformation()
        self.lanelines    = LaneLines()

    def forward(self, img):
        """Process one frame — img is RGB (moviepy convention)."""
        out_img = np.copy(img)
        img = self.calibration.undistort(img)
        img = self.transform.forward(img)
        img = self.thresholding.forward(img)
        img = self.lanelines.forward(img)
        img = self.transform.backward(img)
        out_img = cv2.addWeighted(out_img, 1, img, 0.6, 0)
        out_img = self.lanelines.plot(out_img)
        return out_img


# ═══════════════════════════════════════════════════════════════════
# VIDEO PROCESSING (OpenCV — no moviepy needed for I/O)
# ═══════════════════════════════════════════════════════════════════

def run(video_path, output_path, crop_top, crop_bot, resize_w, resize_h):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"ERROR: Cannot open video: {video_path}")
        sys.exit(1)

    src_w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total   = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"\n{'='*60}")
    print(f"  Dt-Pham Lane Detection — Video Wrapper")
    print(f"{'='*60}")
    print(f"  Repo     : {LANE_REPO}")
    print(f"  Input    : {os.path.basename(video_path)}")
    print(f"  Source   : {src_w}x{src_h} @ {src_fps:.0f}fps  ({total} frames)")
    print(f"  Process  : {resize_w}x{resize_h}  crop top={crop_top:.0%} bot={crop_bot:.0%}")
    print(f"  Output   : {output_path}")
    print(f"{'='*60}\n")

    pipeline = FindLaneLines()

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, src_fps, (resize_w, resize_h))

    frame_n = 0
    t0      = time.time()
    errors  = 0

    while True:
        ret, raw = cap.read()
        if not ret:
            break
        frame_n += 1

        # Crop top and bottom
        h = raw.shape[0]
        top_px = int(h * crop_top)
        bot_px = int(h * crop_bot)
        cropped = raw[top_px: h - bot_px, :]

        # Resize to expected dimensions (Dt-Pham tuned for 1280x720)
        resized = cv2.resize(cropped, (resize_w, resize_h))

        # Convert BGR→RGB for Dt-Pham (it uses RGB internally)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        # Run Dt-Pham pipeline
        try:
            out_rgb = pipeline.forward(rgb)
            out_bgr = cv2.cvtColor(out_rgb, cv2.COLOR_RGB2BGR)
        except Exception as e:
            # If a frame fails just write the original
            out_bgr = resized
            errors += 1

        writer.write(out_bgr)

        if frame_n % 150 == 0 or frame_n == 1:
            elapsed = time.time() - t0
            fps_avg = frame_n / max(elapsed, 0.001)
            eta     = (total - frame_n) / max(fps_avg, 1)
            pct     = frame_n / max(total, 1) * 100
            print(f"  [{frame_n:5d}/{total}]  {pct:5.1f}%  "
                  f"{fps_avg:5.1f}fps  ETA {eta:.0f}s")

    cap.release()
    writer.release()

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  DONE  {frame_n} frames  {elapsed:.1f}s  "
          f"({frame_n/max(elapsed,0.001):.1f}fps avg)")
    if errors:
        print(f"  Skipped frames (errors): {errors}")
    print(f"  Output: {output_path}")
    print(f"{'='*60}\n")


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Run Dt-Pham lane detection on any video")
    p.add_argument("--video",     required=True,
                   help="Input video path (MP4, MOV, AVI, MKV)")
    p.add_argument("--output",    default=None,
                   help="Output MP4 path (default: ~/lane_output/out_TIMESTAMP.mp4)")
    p.add_argument("--crop_top",  type=float, default=0.35,
                   help="Top crop fraction to remove sky (default: 0.35)")
    p.add_argument("--crop_bot",  type=float, default=0.04,
                   help="Bottom crop fraction for bonnet (default: 0.04)")
    p.add_argument("--resize_w",  type=int,   default=1280,
                   help="Processing width (default: 1280)")
    p.add_argument("--resize_h",  type=int,   default=720,
                   help="Processing height (default: 720)")
    args = p.parse_args()

    if not os.path.exists(args.video):
        print(f"ERROR: Video not found: {args.video}")
        sys.exit(1)

    if args.output is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = os.path.expanduser("~/lane_output")
        os.makedirs(out_dir, exist_ok=True)
        args.output = os.path.join(out_dir, f"dtpham_{ts}.mp4")

    run(args.video, args.output,
        args.crop_top, args.crop_bot,
        args.resize_w, args.resize_h)
