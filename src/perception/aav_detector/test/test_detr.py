import importlib.util

from aav_detector.detr import decode, input_size, preprocess, split_outputs
import numpy as np
import pytest

needs_cv2 = pytest.mark.skipif(importlib.util.find_spec('cv2') is None, reason='no OpenCV')


def logit(p):
    """Return the raw score a model gives for probability p."""
    return float(np.log(p / (1.0 - p)))


def grid(queries, classes, scores):
    """Return logits (Q, C), all near 0 except the given {(query, class): probability}."""
    out = np.full((queries, classes), -20.0, dtype=np.float32)
    for (q, c), p in scores.items():
        out[q, c] = logit(p)
    return out


def test_one_box_in_pixels():
    boxes = np.array([[0.5, 0.5, 0.25, 0.5], [0.1, 0.1, 0.1, 0.1]], dtype=np.float32)
    corners, scores, classes = decode(boxes, grid(2, 91, {(0, 13): 0.9}), 640, 360)
    assert corners.tolist() == [[240.0, 90.0, 400.0, 270.0]]   # centre (320, 180), 160 x 180
    assert scores == pytest.approx([0.9])
    assert classes.tolist() == [13]                            # COCO's stop sign


def test_a_batch_of_one_is_taken_too():
    boxes = np.array([[[0.5, 0.5, 0.2, 0.2]]], dtype=np.float32)
    corners, _, classes = decode(boxes, grid(1, 91, {(0, 1): 0.8})[None], 100, 100)
    assert corners[0] == pytest.approx([40, 40, 60, 60]) and classes.tolist() == [1]


def test_the_threshold_keeps_only_higher_scores():
    logits = grid(3, 91, {(0, 13): 0.9, (1, 1): 0.5, (2, 3): 0.49})
    boxes = np.full((3, 4), 0.5, dtype=np.float32)
    _, scores, classes = decode(boxes, logits, 10, 10, threshold=0.5)
    assert classes.tolist() == [13]               # over 0.5, as rfdetr: 0.5 itself is out
    _, scores, classes = decode(boxes, logits, 10, 10, threshold=0.3)
    assert classes.tolist() == [13, 1, 3]         # best first
    assert scores == pytest.approx([0.9, 0.5, 0.49])


def test_one_query_can_be_two_classes():
    # Sigmoids, not a softmax: a query can be a car and a truck at once, as in PostProcess.
    _, _, classes = decode(np.full((1, 4), 0.5), grid(1, 91, {(0, 3): 0.8, (0, 8): 0.7}),
                           10, 10)
    assert classes.tolist() == [3, 8]


def test_only_the_best_num_select_pairs():
    logits = grid(4, 5, {(0, 0): 0.9, (1, 1): 0.8, (2, 2): 0.7, (3, 3): 0.6})
    _, scores, _ = decode(np.full((4, 4), 0.5), logits, 10, 10, num_select=2)
    assert scores == pytest.approx([0.9, 0.8])


def test_boxes_stay_inside_the_picture():
    corners, _, _ = decode(np.array([[0.95, 0.05, 0.3, 0.3]]), grid(1, 2, {(0, 1): 0.9}),
                           200, 100)
    assert corners[0] == pytest.approx([160.0, 0.0, 200.0, 20.0])


def test_nothing_found():
    corners, scores, classes = decode(np.zeros((300, 4)), grid(300, 91, {}), 640, 360)
    assert corners.shape == (0, 4) and scores.size == 0 and classes.size == 0


def test_wrong_shapes_are_an_error():
    with pytest.raises(ValueError, match=r'\(Q, 4\)'):
        decode(np.zeros((3, 5)), np.zeros((3, 91)), 10, 10)
    with pytest.raises(ValueError, match=r'\(Q, C\)'):
        decode(np.zeros((3, 4)), np.zeros((2, 91)), 10, 10)


def test_outputs_by_name_or_by_shape():
    boxes, logits = np.zeros((1, 300, 4)), np.zeros((1, 300, 91))
    # ONNX and TensorRT: by name.
    b, k = split_outputs({'labels': logits, 'dets': boxes})
    assert b is not None and b.shape == (1, 300, 4) and k.shape == (1, 300, 91)
    # Core ML renames them: by shape.
    b, k = split_outputs({'linear_102': logits, 'concat_2': boxes})
    assert b.shape == (1, 300, 4) and k.shape == (1, 300, 91)
    with pytest.raises(ValueError, match="not an RF-DETR model's outputs"):
        split_outputs({'a': boxes, 'b': boxes})
    with pytest.raises(ValueError, match="not an RF-DETR model's outputs"):
        split_outputs({'a': logits})


def test_input_size():
    assert input_size([1, 3, 384, 384]) == (384, 384)
    assert input_size((1, 3, 384, 512)) == (384, 512)
    with pytest.raises(ValueError, match='fixed'):
        input_size((1, 3, -1, -1))
    with pytest.raises(ValueError, match='fixed'):
        input_size((1, 384, 384, 3))      # channels last isn't RF-DETR's


@needs_cv2
def test_preprocess_resizes_scales_and_normalises():
    rgb = np.zeros((360, 640, 3), dtype=np.uint8)
    rgb[:, :, 0] = 255                                 # all red
    x = preprocess(rgb, 384, 384)
    assert x.shape == (1, 3, 384, 384) and x.dtype == np.float32
    assert x[0, 0].mean() == pytest.approx((1.0 - 0.485) / 0.229, abs=1e-5)
    assert x[0, 1].mean() == pytest.approx((0.0 - 0.456) / 0.224, abs=1e-5)
    assert x[0, 2].mean() == pytest.approx((0.0 - 0.406) / 0.225, abs=1e-5)


@needs_cv2
def test_preprocess_keeps_left_and_top():
    rgb = np.zeros((100, 200, 3), dtype=np.uint8)
    rgb[:50, :100] = 255                               # the top left quarter, white
    x = preprocess(rgb, 10, 10)
    assert x[0, 0, 2, 2] > 1.5 and x[0, 0, 7, 7] < -1.5


@needs_cv2
def test_preprocess_wants_rgb():
    with pytest.raises(ValueError, match='RGB'):
        preprocess(np.zeros((10, 10), dtype=np.uint8), 4, 4)
