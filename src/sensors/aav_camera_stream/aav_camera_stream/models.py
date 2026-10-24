"""
models: the detector hook. Any model with detect(bgr, confidence, labels) -> boxes.

The models themselves are aav_yolo's (aav_yolo.detectors.load_detector), imported, not
copied: RF-DETR Nano by default (Ben, 23 Oct), as PyTorch (.pth), Core ML (.mlpackage, a
Mac) or TensorRT (.engine, the Orin), by the model file's ending; YOLO with
detector:=yolo. `none` runs no model: the stream, undistortion and preview only, for a
computer without PyTorch. Boxes are aav_yolo.boxes.Box, in the picture's pixels.
"""

DETECTORS = ('rfdetr', 'yolo', 'none')


class NoModel:
    """No detector: every picture has no boxes."""

    detector, model, device = 'none', '', ''

    def detect(self, bgr, confidence=0.5, labels=None):
        return []


def make(detector: str, model: str, device: str, image_size: int, log, root: str):
    """
    Load the detector once, or raise as load_detector does.

    ValueError for a bad choice, FileNotFoundError without the model file, ImportError
    when this Python lacks the model's library (PyTorch: pixi run -e ml).
    """
    kind = detector.strip().lower()
    if kind not in DETECTORS:
        raise ValueError(f'detector:={detector}: use one of {", ".join(DETECTORS)}')
    if kind == 'none':
        return NoModel()
    from aav_yolo.detectors import load_detector
    return load_detector(detector=kind, model=model, device=device, image_size=image_size,
                         root=root, log=log)
