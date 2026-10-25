"""
camera_calibration_cv5: run ROS's camera_calibration with OpenCV 5's checkerboard corners.

  python3 tools/camera_calibration_cv5.py cameracalibrator --size 9x6 --square 0.025 ...
  python3 tools/camera_calibration_cv5.py tarfile_calibration --mono -s 9x6 -q 0.025 FILE

Run by tools/calibrate_camera.py in the calib environment (pixi.toml). camera_calibration
5.0.13 (Jazzy) expects cv2.findChessboardCorners to give an N x 1 x 2 array, as OpenCV 4
did; OpenCV 5.0, which RoboStack builds Jazzy against, gives N x 2, and the calibrator
stops at the first board it sees (IndexError in _get_corners, found 24 Oct). This puts
the old shape back, then runs the calibrator's own main(), unchanged.
"""

import functools
import sys

import cv2


def _old_shape(find):
    @functools.wraps(find)
    def wrapper(*args, **kwargs):
        ok, corners = find(*args, **kwargs)
        if corners is not None and corners.ndim == 2:
            corners = corners.reshape(-1, 1, 2)
        return ok, corners
    return wrapper


cv2.findChessboardCorners = _old_shape(cv2.findChessboardCorners)


def main():
    name, sys.argv = sys.argv[1], sys.argv[1:]
    if name == 'cameracalibrator':
        from camera_calibration.nodes.cameracalibrator import main as run
    elif name == 'tarfile_calibration':
        from camera_calibration.nodes.tarfile_calibration import main as run
    else:
        raise SystemExit(f'{name}: cameracalibrator or tarfile_calibration')
    return run()


if __name__ == '__main__':
    sys.exit(main())
