import numpy as np
from main import FindLaneLines

class LaneDetector:
    def __init__(self):
        self.pipe = FindLaneLines()

    def detect(self, frame_bgr):
        """
        Returns:
          overlay_bgr: frame with lane overlay drawn
          metrics: dict with fields you can use for control
        """
        overlay = self.pipe.forward(frame_bgr)

        # If LaneLines.fit_poly couldn't fit both lanes, it sets clear_visibility False
        visible = bool(self.pipe.lanelines.clear_visibility)

        metrics = {"lanes_visible": visible}

        if visible:
            h, w = frame_bgr.shape[:2]
            left_fit = self.pipe.lanelines.left_fit
            right_fit = self.pipe.lanelines.right_fit

            # lane center at bottom of image
            y = h - 1
            xl = left_fit[0]*y*y + left_fit[1]*y + left_fit[2]
            xr = right_fit[0]*y*y + right_fit[1]*y + right_fit[2]
            lane_center = (xl + xr) / 2.0
            image_center = w / 2.0

            # pixels; convert to meters only after you calibrate scale
            metrics["center_offset_px"] = float(lane_center - image_center)

        return overlay, metrics
