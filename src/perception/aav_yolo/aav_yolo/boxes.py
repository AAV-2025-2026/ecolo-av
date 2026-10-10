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


# Each of these means "the GPU this computer has", so one setting works everywhere.
GPU_WORDS = ('auto', 'gpu', 'cuda', 'metal', 'mps')


def pick_device(requested: str, model: str, cuda: bool, mps: bool) -> Optional[str]:
    """
    Choose where a model runs.

    'auto' (the default), 'gpu', 'cuda', 'metal' and 'mps' all mean the GPU this computer
    has, for a PyTorch model (.pt): CUDA on an NVIDIA card or the Orin, Metal on a Mac,
    and the CPU if there's neither. So 'cuda' on a Mac means Metal. 'cuda:1' picks a
    second NVIDIA card. Other formats decide for themselves (Core ML picks the Mac's parts,
    TensorRT uses the GPU), so they get None. Anything else, such as 'cpu', is obeyed.
    """
    name = requested.strip().lower()
    if name not in GPU_WORDS and not name.startswith('cuda:'):
        return requested
    if not model.endswith('.pt'):
        return None
    if cuda:
        return name if name.startswith('cuda:') else 'cuda:0'
    if mps:
        return 'mps'
    return 'cpu'
