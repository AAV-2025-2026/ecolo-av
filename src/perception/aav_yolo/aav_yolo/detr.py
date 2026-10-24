"""
RF-DETR's maths for an exported model (Core ML, TensorRT, ONNX): the picture in, the boxes out.

The rfdetr library does this itself for its PyTorch model (predict()). An exported model
gives only two raw arrays, so this module does the same steps, with NumPy alone:

  in    the picture, resized to the model's square (384 px for Nano), as RGB, scaled to 0-1
        and normalised with ImageNet's mean and spread: shape (1, 3, H, W)
  out   boxes   (1, Q, 4): each query's box, centre x, centre y, width, height, as 0-1 of
                the picture (ONNX and TensorRT name it "dets")
        logits  (1, Q, C): each query's score for each class, before the sigmoid ("labels").
                C is 91 for the stock COCO models: the column is COCO's own class number

  decode: a sigmoid on every score; the best Q (query, class) pairs of all, as
  PostProcess does (one query can be two classes, a car and a truck); those over the
  threshold; their boxes in pixels of the original picture. No NMS: DETR needs none.

This mirrors rfdetr 1.11's export/_runtime (decode.py, preprocess.py), which is private,
so we keep our own. No ROS, PyTorch or rfdetr imports, so the tests run anywhere.
"""

from __future__ import annotations

from typing import Mapping, Tuple

import numpy as np

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
# The ONNX and TensorRT names of the two outputs; Core ML renames them, so shape decides there.
BOXES, LOGITS = 'dets', 'labels'


def preprocess(rgb: np.ndarray, height: int, width: int) -> np.ndarray:
    """
    Return an RGB picture (H x W x 3, uint8) as the model's input: (1, 3, height, width).

    Bilinear, without anti-aliasing, on the 0-1 values, as rfdetr's predict() resizes
    (torchvision, antialias=False): OpenCV's INTER_LINEAR is the same filter.
    """
    import cv2   # here: only the exported models need it, and they run where OpenCV is
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError(f'expected an RGB picture, H x W x 3; got shape {rgb.shape}')
    scaled = rgb.astype(np.float32) / 255.0
    if scaled.shape[:2] != (height, width):
        scaled = cv2.resize(scaled, (width, height), interpolation=cv2.INTER_LINEAR)
    normal = (scaled - IMAGENET_MEAN) / IMAGENET_STD
    return np.ascontiguousarray(normal.transpose(2, 0, 1)[None], dtype=np.float32)


def split_outputs(outputs: Mapping[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return (boxes, logits) from a model's outputs, by name, or else by shape.

    ONNX and TensorRT keep the names dets and labels. Core ML calls them what its graph
    did (concat_2, linear_102...): there the boxes are the output whose last size is 4.
    """
    if BOXES in outputs and LOGITS in outputs:
        return np.asarray(outputs[BOXES]), np.asarray(outputs[LOGITS])
    arrays = [np.asarray(a) for a in outputs.values()]
    boxes = [a for a in arrays if a.shape[-1] == 4]
    logits = [a for a in arrays if a.shape[-1] != 4]
    if len(arrays) != 2 or len(boxes) != 1 or len(logits) != 1:
        shapes = {k: np.shape(v) for k, v in outputs.items()}
        raise ValueError(f"not an RF-DETR model's outputs (boxes and logits): {shapes}")
    return boxes[0], logits[0]


def decode(boxes: np.ndarray, logits: np.ndarray, width: int, height: int,
           threshold: float = 0.5,
           num_select: int = 300) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Return one picture's detections: (corners, scores, class numbers), best first.

    boxes (Q, 4) are centre x, centre y, width and height as 0-1 of the picture; logits
    (Q, C) the raw scores; width and height the original picture's, in pixels. A batch of
    one, (1, Q, 4) and (1, Q, C), is taken too. corners are (N, 4): x1, y1, x2, y2 in
    pixels, inside the picture. Only scores over `threshold` are kept, of the best
    `num_select` (query, class) pairs.
    """
    boxes, logits = np.asarray(boxes), np.asarray(logits, dtype=np.float32)
    if boxes.ndim == 3:
        boxes, logits = boxes[0], logits[0]
    if boxes.ndim != 2 or boxes.shape[1] != 4 or logits.ndim != 2 \
            or logits.shape[0] != boxes.shape[0]:
        raise ValueError(f'boxes must be (Q, 4) and logits (Q, C): got {boxes.shape} '
                         f'and {logits.shape}')
    scores = 1.0 / (1.0 + np.exp(-np.clip(logits, -88.0, 88.0)))
    flat = scores.reshape(-1)
    count = min(num_select, flat.size)
    # The best `count`, highest first; a stable sort keeps equal scores in query order.
    best = np.argsort(-flat, kind='stable')[:count]
    best = best[flat[best] > threshold]
    query, cls = np.divmod(best, logits.shape[1])
    cx, cy, w, h = boxes[query].astype(np.float32).T
    scale = np.array([width, height, width, height], dtype=np.float32)
    corners = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1) * scale
    corners = np.clip(corners, 0.0, scale)
    return corners.reshape(-1, 4), flat[best], cls.astype(np.int64)


def input_size(shape) -> Tuple[int, int]:
    """Return (height, width) from a model's input shape, (1, 3, H, W)."""
    dims = [int(d) for d in shape]
    if len(dims) != 4 or dims[1] != 3 or min(dims[2:]) <= 0:
        raise ValueError(f'expected an input of (1, 3, H, W), fixed; got {tuple(shape)}')
    return dims[2], dims[3]
