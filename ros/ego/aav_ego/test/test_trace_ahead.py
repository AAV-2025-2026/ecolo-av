"""ego's trace: where the car goes, from its twin and a copy of ego."""

import math

from aav_description.car_model import ActuatorConfig, speed_loop_profile
from aav_ego.ackermann import EgoModel, Limits
from aav_ego.lag_lead import LagLead, LeadTimes
from aav_ego.trace_ahead import trace, Twin
import pytest

CFG = ActuatorConfig()
DT = 0.02


def twin():
    return Twin(CFG, speed_loop_profile('default'))


def test_parked_with_no_command_the_trace_stays_put():
    poses = trace(twin(), EgoModel(Limits()), None, None, 2.0, DT, 5)
    assert len(poses) == 21
    assert poses[-1].t == pytest.approx(2.0)
    assert all(p.x == 0.0 and p.y == 0.0 for p in poses)


def test_a_left_turn_request_bends_the_trace_left_and_late():
    model = EgoModel(Limits(max_speed=1.0))
    poses = trace(twin(), model, (1.0, 0.3), None, 2.0, DT, 5)
    assert poses[-1].x > 0.3 and poses[-1].y > 0.0 and poses[-1].yaw > 0.0
    # Lag: the car is far slower than asked after the first 0.2 s.
    assert poses[2].v < 0.2
    # Nothing passed in moved.
    assert model.speed == 0.0 and model.steering == 0.0


def test_the_twin_takes_the_measured_speed():
    t = twin()
    t.measured(1.0)
    poses = trace(t, EgoModel(Limits()), None, None, 2.0, DT, 5)   # stopping
    assert poses[0].v == 1.0
    assert poses[-1].x > 0.0 and poses[-1].v < 0.5


def test_the_twin_answers_what_ego_sent():
    t = twin()
    for _ in range(100):
        t.sent(1.0, 0.2, DT)
    assert t.state.v > 0.3 and t.state.steer > 0.1
    assert math.isfinite(t.state.x)


def test_the_lead_in_the_trace_is_a_copy():
    lead = LagLead(LeadTimes.from_config(CFG))
    lead.step(0.0, 0.0, DT)
    before = (lead.speed, lead.angle)
    trace(twin(), EgoModel(Limits()), (1.0, 0.0), lead, 2.0, DT, 5)
    assert (lead.speed, lead.angle) == before
