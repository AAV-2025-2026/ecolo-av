from types import SimpleNamespace

from aav_yolo.boxes import boxes_from_result, normal_label, parse_labels, pick_device
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


@pytest.mark.parametrize('requested, model, cuda, mps, expect', [
    ('auto', 'models/yolo11n.pt', True, False, 'cuda:0'),    # an NVIDIA card, the Orin
    ('auto', 'models/yolo11n.pt', False, True, 'mps'),       # a Mac
    ('auto', 'models/yolo11n.pt', False, False, 'cpu'),
    ('auto', 'models/yolo11n.mlpackage', False, True, None),  # Core ML picks for itself
    ('auto', 'models/yolo11n.engine', True, False, None),     # TensorRT: the GPU anyway
    ('cpu', 'models/yolo11n.pt', True, True, 'cpu'),          # asked for: always obeyed
])
def test_pick_device(requested, model, cuda, mps, expect):
    assert pick_device(requested, model, cuda, mps) == expect
