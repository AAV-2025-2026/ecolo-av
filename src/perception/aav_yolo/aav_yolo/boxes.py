"""
YOLO's boxes as plain values, which labels to keep, and where the model runs.

No ROS or PyTorch imports, so the tests run anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
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


DEVICES = 'auto, cuda, cuda:N, mps or cpu'
CUDA_N = re.compile(r'cuda:(\d+)')


def pick_device(requested: str, model: str, cuda_devices: int, mps: bool) -> Optional[str]:
    """
    Choose where a PyTorch model (.pt) runs, from what this computer has.

    'auto' (the default) picks the GPU: CUDA (an NVIDIA card, or the Orin) first, then
    Metal on a Mac ('mps'), else the CPU. The other names are PyTorch's own, passed on as
    they are: 'cuda' (the first NVIDIA card), 'cuda:N', 'mps' and 'cpu'.

    A .engine (TensorRT) or .mlpackage (Core ML) model picks its own hardware, so it gets
    None, whatever was asked. Raises ValueError, saying what to use instead, for a name
    PyTorch doesn't know or a device this computer doesn't have.
    """
    name = requested.strip()
    if name not in ('auto', 'cuda', 'mps', 'cpu') and not CUDA_N.fullmatch(name):
        raise ValueError(f"device '{requested}' isn't a device name: use {DEVICES}")
    if not model.endswith('.pt'):
        return None
    if name == 'auto':
        return 'cuda:0' if cuda_devices else 'mps' if mps else 'cpu'
    if name == 'mps' and not mps:
        raise ValueError("device 'mps' is a Mac's GPU, and this computer isn't a Mac with "
                         f"Metal: use auto, or {'cuda' if cuda_devices else 'cpu'}")
    if name.startswith('cuda'):
        if not cuda_devices:
            instead = "mps (this Mac's GPU)" if mps else 'cpu'
            raise ValueError(f"device '{name}' needs an NVIDIA GPU, and this computer has "
                             f'none: use auto or {instead}')
        number = CUDA_N.fullmatch(name)
        if number and int(number.group(1)) >= cuda_devices:
            raise ValueError(f"device '{name}': this computer has {cuda_devices} NVIDIA "
                             f'GPU(s), cuda:0 to cuda:{cuda_devices - 1}')
    return name
