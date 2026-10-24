from aav_detector.stop_sign import CLEAR, PASSING, STOPPING, StopRule, StopSignWatcher

RULE = StopRule(min_height_px=72.0, min_score=0.5, hold_s=4.0, ignore_s=10.0)
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
