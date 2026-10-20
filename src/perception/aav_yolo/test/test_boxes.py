import re
from types import SimpleNamespace

from aav_yolo.boxes import (Box, boxes_from_corners, boxes_from_result, check_detector, corners,
                            normal_label, parse_labels, pick_device, rfdetr_size)
import numpy as np
import pytest


def result(rows, names):
    """Make a stand-in for an Ultralytics result: rows of (cx, cy, w, h, score, class)."""
    a = np.array(rows, dtype=float).reshape(-1, 6)
    return SimpleNamespace(boxes=SimpleNamespace(xywh=a[:, :4], conf=a[:, 4], cls=a[:, 5]),
                           names=names)


COCO = {0: 'person', 5: 'bus', 11: 'stop sign'}


def test_every_box_becomes_a_box():
    boxes = boxes_from_result(result([(320, 240, 100, 120, 0.97, 11),
                                      (50, 60, 20, 80, 0.8, 0)], COCO))
    assert [b.label for b in boxes] == ['stop sign', 'person']
    first = boxes[0]
    assert (first.cx, first.cy, first.width, first.height) == (320, 240, 100, 120)
    assert first.score == pytest.approx(0.97)


def test_labels_keep_only_those():
    r = result([(1, 1, 1, 1, 0.9, 11), (1, 1, 1, 1, 0.9, 0), (1, 1, 1, 1, 0.9, 5)], COCO)
    assert [b.label for b in boxes_from_result(r, ['stop sign'])] == ['stop sign']
    assert len(boxes_from_result(r, None)) == 3


def test_the_old_model_and_the_stock_model_name_stop_signs_alike():
    old = result([(1, 1, 1, 1, 0.9, 0)], {0: 'Stop_Sign'})
    assert [b.label for b in boxes_from_result(old, ['stop sign'])] == ['Stop_Sign']
    assert normal_label('Stop_Sign') == normal_label('stop sign') == normal_label(' STOP-sign')


def test_no_boxes():
    assert boxes_from_result(result([], COCO)) == []


def test_parse_labels():
    assert parse_labels('') is None
    assert parse_labels(' , ') is None
    assert parse_labels('stop sign, Person') == ['stop sign', 'person']


PT, ENGINE, MLPACKAGE = 'models/yolo11n.pt', 'models/yolo11n.engine', 'models/yolo11n.mlpackage'
PTH = 'models/rf-detr-nano.pth'
ORIN, MAC, PC = (1, False), (0, True), (0, False)   # (NVIDIA GPUs, Metal)


@pytest.mark.parametrize('requested, model, machine, expect', [
    ('auto', PT, ORIN, 'cuda:0'),            # auto: the GPU this computer has
    ('auto', PT, MAC, 'mps'),
    ('auto', PT, PC, 'cpu'),
    ('auto', PTH, ORIN, 'cuda:0'),           # RF-DETR's .pth is PyTorch too
    ('auto', PTH, MAC, 'mps'),
    ('cuda', PT, ORIN, 'cuda'),              # PyTorch's own names, passed on as they are
    ('cuda:1', PT, (2, False), 'cuda:1'),
    ('mps', PT, MAC, 'mps'),
    ('cpu', PT, ORIN, 'cpu'),
    ('cpu', PT, MAC, 'cpu'),
    ('auto', MLPACKAGE, MAC, None),          # Core ML picks its own hardware
    ('auto', ENGINE, ORIN, None),            # and so does TensorRT
    ('cuda', MLPACKAGE, MAC, None),          # whatever was asked
])
def test_pick_device(requested, model, machine, expect):
    assert pick_device(requested, model, *machine) == expect


@pytest.mark.parametrize('requested, machine, says', [
    ('cuda', MAC, 'use auto or mps'),        # cuda on a Mac: say what works there
    ('cuda:0', MAC, 'use auto or mps'),
    ('cuda', PC, 'use auto or cpu'),
    ('cuda:1', ORIN, 'cuda:0 to cuda:0'),    # only one NVIDIA card here
    ('mps', ORIN, 'use auto, or cuda'),
    ('mps', PC, 'use auto, or cpu'),
    ('gpu', ORIN, 'use auto, cuda, cuda:N, mps or cpu'),    # the old aliases are gone
    ('metal', MAC, 'use auto, cuda, cuda:N, mps or cpu'),
    ('CUDA', ORIN, 'use auto, cuda, cuda:N, mps or cpu'),   # PyTorch's names are lower case
])
def test_pick_device_says_what_to_use_instead(requested, machine, says):
    with pytest.raises(ValueError, match=re.escape(says)):
        pick_device(requested, PT, *machine)


def test_a_misspelt_device_is_an_error_even_for_tensorrt():
    with pytest.raises(ValueError, match='isn.t a device name'):
        pick_device('gpu', ENGINE, *ORIN)


@pytest.mark.parametrize('detector, model, expect', [
    ('rfdetr', '', 'models/rf-detr-nano.pth'),       # empty: the detector's own model
    ('yolo', '', 'models/yolo11n.pt'),
    (' RFDETR ', '', 'models/rf-detr-nano.pth'),
    ('rfdetr', 'models/rf-detr-small.pth', 'models/rf-detr-small.pth'),
    ('yolo', ENGINE, ENGINE),
    ('yolo', MLPACKAGE, MLPACKAGE),
])
def test_check_detector(detector, model, expect):
    assert check_detector(detector, model) == expect


@pytest.mark.parametrize('detector, model, says', [
    ('detr', '', 'use rfdetr or yolo'),
    ('rfdetr', PT, 'it is a yolo model, so use detector:=yolo'),
    ('yolo', PTH, 'it is a rfdetr model, so use detector:=rfdetr'),
    ('rfdetr', 'models/weights.onnx', 'it takes .pth'),
])
def test_check_detector_says_what_to_use_instead(detector, model, says):
    with pytest.raises(ValueError, match=re.escape(says)):
        check_detector(detector, model)


@pytest.mark.parametrize('model, expect', [
    ('models/rf-detr-nano.pth', 'RFDETRNano'),
    ('/x/rf-detr-small.pth', 'RFDETRSmall'),
    ('Large_RFDETR.pth', 'RFDETRLarge'),
])
def test_rfdetr_size(model, expect):
    assert rfdetr_size(model) == expect


@pytest.mark.parametrize('model', ['models/checkpoint_best_regular.pth', 'small-or-nano.pth'])
def test_rfdetr_size_needs_one_size_in_the_name(model):
    with pytest.raises(ValueError, match='name the file after its size'):
        rfdetr_size(model)


RFDETR_COCO = {1: 'person', 13: 'stop sign'}    # rfdetr's COCO numbers, not Ultralytics'


def test_boxes_from_corners():
    boxes = boxes_from_corners([[10, 20, 50, 100], [0, 0, 4, 4]], [0.9, 0.6], [13, 1],
                               RFDETR_COCO)
    assert boxes == [Box('stop sign', 0.9, 30.0, 60.0, 40.0, 80.0),
                     Box('person', 0.6, 2.0, 2.0, 4.0, 4.0)]
    assert [b.label for b in boxes_from_corners([[0, 0, 1, 1]] * 2, [0.9, 0.9], [13, 1],
                                                RFDETR_COCO, ['Stop_Sign'])] == ['stop sign']
    assert boxes_from_corners([[0, 0, 1, 1]], [0.9], [99], RFDETR_COCO)[0].label == '99'


def test_corners_are_whole_pixels():
    assert corners(Box('x', 1.0, 30.4, 60.0, 40.0, 80.0)) == {'x1': 10, 'y1': 20,
                                                              'x2': 50, 'y2': 100}
