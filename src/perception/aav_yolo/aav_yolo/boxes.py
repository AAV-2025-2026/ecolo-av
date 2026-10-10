"""
YOLO's boxes as plain values, which labels to keep, and where the model runs.

No ROS or PyTorch imports, so the tests run anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence


@dataclass
class Box:
    """One detection, in pixels of the image it was found in."""

    label: str
    score: float
    cx: float       # centre
    cy: float
    width: float
    height: float


def normal_label(label: str) -> str:
    """'Stop_Sign' (the 2024-25 model) and 'stop sign' (the stock model) are the same label."""
    return ' '.join(label.replace('_', ' ').replace('-', ' ').lower().split())


def parse_labels(text: str) -> Optional[List[str]]:
    """Read the labels parameter: 'stop sign, person' -> both; '' -> None (keep them all)."""
    labels = [normal_label(s) for s in text.split(',') if s.strip()]
    return labels or None


def boxes_from_result(result, labels: Optional[Sequence[str]] = None) -> List[Box]:
    """
    Return the boxes in one Ultralytics result, keeping only `labels` if given.

    result.boxes holds xywh (centre x, centre y, width, height), conf and cls, as tensors;
    result.names maps a class number to its label.
    """
    keep = {normal_label(s) for s in labels} if labels else None
    boxes = result.boxes
    out = []
    for (cx, cy, w, h), score, cls in zip(boxes.xywh.tolist(), boxes.conf.tolist(),
                                          boxes.cls.tolist()):
        label = result.names[int(cls)]
        if keep is None or normal_label(label) in keep:
            out.append(Box(label, float(score), float(cx), float(cy), float(w), float(h)))
    return out


def pick_device(requested: str, model: str, cuda: bool, mps: bool) -> Optional[str]:
    """
    Choose where a model runs.

    'auto' picks the GPU for a PyTorch model (.pt): CUDA (NVIDIA cards, the Orin), then
    Metal (Macs), then the CPU. Other formats decide for themselves (Core ML picks the Mac's
    parts, TensorRT uses the GPU), so they get None.
    """
    if requested != 'auto':
        return requested
    if not model.endswith('.pt'):
        return None
    if cuda:
        return 'cuda:0'
    if mps:
        return 'mps'
    return 'cpu'
