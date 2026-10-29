"""
LQR steering, its gains scheduled by speed.

No ROS here. The model is aav_ego's VehicleModel.lateral(v): the path errors about
driving straight, with the steering as one lag tau_s,

    x = [e_y, e_theta, delta - delta_ff]      e_y + left of the path, e_theta car - path
    dx/dt = A(v) x + B u'                     u' = u - delta_ff

and u = delta_ff - K(v) x, K from the continuous Riccati equation
(scipy.linalg.solve_continuous_are) for each speed in a table, linear in between. The
model is linear about straight, so on a bend it adds the feed-forward delta_ff = atan(L
kappa), the steering that holds the path's curvature kappa. Below `min_speed` the table's
first row: at v = 0 the model can't steer at all (A has no v in it), and the car isn't
steering there anyway.
"""

from __future__ import annotations

from dataclasses import replace
import math
from typing import Sequence

from aav_track.path import wrap
from aav_track.trackers import Command, Limits, State, SteerLag, Tracker
import numpy as np
from scipy.linalg import solve_continuous_are


class LQR(Tracker):
    name = 'lqr'

    def __init__(self, limits: Limits, model, q: Sequence[float] = (1.0, 2.0, 0.05),
                 r: float = 2.0, min_speed: float = 0.5, max_speed: float = 6.0,
                 speed_step: float = 0.25):
        super().__init__(limits)
        if min_speed <= 0 or max_speed <= min_speed or speed_step <= 0 or r <= 0:
            raise ValueError('need 0 < min_speed < max_speed, speed_step and r above 0')
        self.model = replace(model, wheelbase=limits.wheelbase, max_steering=limits.max_steer)
        self.lag = SteerLag(self.model.steer_tau)
        self.speeds = np.arange(min_speed, max_speed + 1e-9, speed_step)
        qm, rm = np.diag(q), np.array([[r]])
        rows = []
        for v in self.speeds:
            a, b, _, _ = self.model.lateral(float(v))
            p = solve_continuous_are(a, b, qm, rm)
            rows.append((np.linalg.solve(rm, b.T @ p))[0])
        self.table = np.array(rows)          # one row of K = [k_y, k_theta, k_delta] each

    def gains(self, v: float) -> np.ndarray:
        """Return K at speed v: the table, linear in between, its ends beyond."""
        return np.array([np.interp(v, self.speeds, self.table[:, i]) for i in range(3)])

    def step(self, state: State, dt: float) -> Command:
        L = self.limits.wheelbase
        foot = self.foot(state.x, state.y)
        delta = self.lag.update(state.steer, dt)
        ff = math.atan(L * foot.curvature)
        x = np.array([foot.cross, wrap(state.yaw - foot.heading), delta - ff])
        k = self.gains(max(state.v, 0.0))
        steer = self.limited(ff - float(k @ x), state.steer, dt)
        return Command(steer, debug={'feed_forward_rad': ff})
