#!/usr/bin/env python3
"""
homography_calibrator.py  —  lane_stitcher package
═══════════════════════════════════════════════════════════════════
Interactive tool: click 4 road points to compute the BEV homography.
Run ONCE per camera on the real road. Paste output into homography.yaml.

CLICK ORDER — looking at the raw camera image:
  Point 1 → Top-Left    (far ahead, left edge of lane)
  Point 2 → Top-Right   (far ahead, right edge of lane)
  Point 3 → Bottom-Right (close to car, right edge)
  Point 4 → Bottom-Left  (close to car, left edge)

Keys:
  r     → reset clicks
  ENTER → compute homography + show BEV preview
  q     → quit

Run:
  ros2 run lane_stitcher homography_calibrator.py --ros-args -p camera:=left
  ros2 run lane_stitcher homography_calibrator.py --ros-args -p camera:=right
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import numpy as np

BEV_W = 800
BEV_H = 600

# Destination corners in the BEV output image
DST_PTS = np.float32([
    [100,   0],   # TL
    [700,   0],   # TR
    [700, 600],   # BR
    [100, 600],   # BL
])

POINT_LABELS  = ["1: Top-Left", "2: Top-Right", "3: Bot-Right", "4: Bot-Left"]
POINT_COLOURS = [(0,255,0), (0,255,255), (0,128,255), (255,0,0)]


class HomographyCalibrator(Node):

    def __init__(self):
        super().__init__('homography_calibrator')
        self.declare_parameter('camera', 'left')
        self.side   = self.get_parameter('camera').value
        self.bridge = CvBridge()
        self.frame  = None
        self.pts    = []

        topic = f'/cam_{self.side}/image_raw'
        self.sub   = self.create_subscription(Image, topic, self.img_cb, 1)
        self.timer = self.create_timer(0.033, self.show)

        win = f'Homography Calibrator — {self.side.upper()} camera'
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win, 1000, 700)
        cv2.setMouseCallback(win, self.mouse_cb)
        self.win = win

        self.get_logger().info(
            f"\n  Calibrating {self.side.upper()} camera from: {topic}"
            "\n  Click 4 road points in order:"
            "\n    1 → Top-Left   2 → Top-Right"
            "\n    3 → Bot-Right  4 → Bot-Left"
            "\n  Then press ENTER"
        )

    def img_cb(self, msg):
        self.frame = self.bridge.imgmsg_to_cv2(msg, 'bgr8')

    def mouse_cb(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(self.pts) < 4:
            self.pts.append((x, y))

    def show(self):
        if self.frame is None:
            return

        disp = self.frame.copy()
        h, w = disp.shape[:2]

        # Instructions
        cv2.rectangle(disp, (0, 0), (w, 50), (20, 20, 20), -1)
        cv2.putText(disp,
            f"Click 4 road points: TL → TR → BR → BL  |  r=reset  ENTER=compute  q=quit",
            (10, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        # Draw clicked points
        for i, (px, py) in enumerate(self.pts):
            cv2.circle(disp, (px, py), 10, POINT_COLOURS[i], -1)
            cv2.circle(disp, (px, py), 10, (255,255,255), 2)
            cv2.putText(disp, POINT_LABELS[i], (px+12, py-8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, POINT_COLOURS[i], 2)

        # Draw polygon when all 4 clicked
        if len(self.pts) == 4:
            poly = np.array(self.pts, np.int32).reshape((-1, 1, 2))
            cv2.polylines(disp, [poly], True, (255, 255, 255), 2)
            cv2.putText(disp, "Press ENTER to compute homography",
                        (10, h-15), cv2.FONT_HERSHEY_SIMPLEX,
                        0.75, (0, 255, 255), 2)

        cv2.putText(disp, f"Points: {len(self.pts)}/4",
                    (w-180, h-15), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (180, 180, 180), 1)

        cv2.imshow(self.win, disp)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('r'):
            self.pts = []
        elif key == 13 and len(self.pts) == 4:  # ENTER
            self.compute()
        elif key == ord('q'):
            cv2.destroyAllWindows()
            rclpy.shutdown()

    def compute(self):
        src = np.float32(self.pts)
        H, status = cv2.findHomography(src, DST_PTS)

        if H is None:
            self.get_logger().error("Homography failed — try clicking more spread-out points")
            self.pts = []
            return

        # Show BEV preview
        bev = cv2.warpPerspective(self.frame, H, (BEV_W, BEV_H))
        cv2.putText(bev, "BEV Preview — lane lines should be parallel and vertical",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 1)
        cv2.putText(bev, "Press any key to continue",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 1)
        cv2.imshow(f"BEV Preview — {self.side}", bev)
        cv2.waitKey(0)

        # Print result
        print("\n" + "="*58)
        print(f"  ✅  {self.side.upper()} homography — paste into homography.yaml")
        print("="*58)
        print(f"\n{self.side}_H:")
        for row in H:
            print(f"  - [{row[0]:.8f}, {row[1]:.8f}, {row[2]:.8f}]")
        print("\n" + "="*58)
        print("  Then rebuild:  colcon build --packages-select lane_stitcher")
        print("="*58 + "\n")

        self.get_logger().info(
            f"{self.side.upper()} H matrix printed above. "
            "Paste into homography.yaml and rebuild."
        )
        self.pts = []


def main(args=None):
    rclpy.init(args=args)
    node = HomographyCalibrator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
