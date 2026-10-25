from aav_detector.stop_sign import (CLEAR, GAZEBO_FOCAL_PX, PASSING, sign_distance_m,
                                    STOPPING, StopRule, StopSignWatcher)
import pytest

# 3.5 m: 73.5 px with Gazebo's lens.
RULE = StopRule(stop_distance_m=3.5, min_score=0.5, hold_s=4.0, ignore_s=10.0)
NEAR = [('stop sign', 0.9, 100.0)]
FAR = [('stop sign', 0.9, 30.0)]


def test_a_far_sign_does_nothing_a_near_one_locks():
    w = StopSignWatcher(RULE)
    assert not w.update(FAR, 0.0)
    assert w.state == CLEAR
    assert w.update(NEAR, 1.0)
    assert w.state == STOPPING


def test_it_holds_then_lets_go_and_ignores_the_same_sign():
    w = StopSignWatcher(RULE)
    w.update(NEAR, 0.0)
    assert w.update(NEAR, 3.9)            # still holding
    assert not w.update(NEAR, 4.0)        # let go...
    assert w.state == PASSING
    assert not w.update(NEAR, 13.9)       # ...and drive past it
    assert not w.update([], 14.0)
    assert w.state == CLEAR
    assert w.update(NEAR, 15.0), 'the next sign counts again'


def test_timers_run_without_new_boxes():
    w = StopSignWatcher(RULE)
    w.update(NEAR, 0.0)
    assert not w.tick(5.0)
    assert w.state == PASSING


def test_low_scores_and_other_labels_never_lock():
    w = StopSignWatcher(RULE)
    assert not w.update([('stop sign', 0.3, 200.0), ('person', 0.99, 300.0)], 0.0)


def test_the_2024_25_models_label_counts_too():
    assert StopSignWatcher(RULE).update([('Stop_Sign', 0.9, 100.0)], 0.0)


def test_the_default_is_55_px_with_gazebos_lens():
    rule = StopRule()
    assert rule.focal_px == GAZEBO_FOCAL_PX == 343.0
    assert rule.min_height_px() == pytest.approx(55.0, abs=0.5)     # the rule until 24 Oct
    assert sign_distance_m(55.0, 343.0) == pytest.approx(4.68, abs=0.01)
    assert sign_distance_m(0.0, 343.0) == float('inf')


def box_at(distance_m, focal_px):
    """Return a 0.75 m stop sign's box, distance_m ahead of a camera with this lens."""
    return [('stop sign', 0.9, focal_px * 0.75 / distance_m)]


@pytest.mark.parametrize('focal_px', [343.0, 950.0, 1400.0])     # Gazebo; 1280x720 lenses
def test_the_distance_carries_over_to_any_lens(focal_px):
    for distance, stops in ((8.0, False), (4.9, False), (4.6, True), (2.0, True)):
        w = StopSignWatcher(StopRule())
        assert w.update(box_at(distance, focal_px), 0.0, focal_px) == stops, distance


def test_a_bigger_lens_needs_a_bigger_box():
    # 100 px is 2.6 m with Gazebo's lens, but 7.1 m with a 950 px one: too far yet.
    assert StopSignWatcher(StopRule()).update([('stop sign', 0.9, 100.0)], 0.0)
    assert not StopSignWatcher(StopRule()).update([('stop sign', 0.9, 100.0)], 0.0, 950.0)
    assert StopRule().min_height_px(950.0) == pytest.approx(151.6, abs=0.1)
    # No lens given: the rule's own (Gazebo's, or focal_px from the parameters).
    assert StopSignWatcher(StopRule(focal_px=950.0)).update(box_at(4.0, 950.0), 0.0)
