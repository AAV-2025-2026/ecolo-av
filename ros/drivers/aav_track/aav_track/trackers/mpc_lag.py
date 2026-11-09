"""
The lag-aware MPC: plan the steering and the set speed through the car's own lags.

No ROS here; numpy, and the QP of aav_track.qp. The other MPCs see the steering as one
lag and the speed as whatever was asked. This one predicts with the whole chain the
command passes through (aav_track.lag_model, vehicle.yaml's `actuators:`):

    set speed ──> the spine's PI ──> throttle, brake (lags) ──> speed (drag)
    steering  ──> dead time ──> motor (rate, deadband) ──> linkage (lag) ──> wheels
                                                     └──> the bicycle, in the path's frame

so it steers early by as much as the steering is late, and lifts off before a bend by as
much as the speed loop is slow. It sets its own speed (`Command.speed`), as mpc_full.

Every tick (real-time iteration, at the node's 20 Hz):
1. Its state: the pose and speed measured; the throttle, brake, steering motor, wheels
   and the speed loop's integral estimated, from the commands it sent (no sensor on the
   car reports them yet); the commands still inside a dead time, in a buffer.
2. A nominal plan: the last plan shifted by a tick, run through the model for `horizon`
   ticks. Each tick's model is linearised about it, by finite differences in one call
   (lag_model.step works on arrays), and the plan is condensed: X = X_bar + M dU.
3. One QP (aav_track.qp, OSQP's ADMM), in dU = [steering (N), set speed (N), slack (N)]:

    cost   sum q.(e_y, e_theta, wheels - r)^2 + q_speed (v - v_lim)^2
             + r (u - r)^2 + r_rate (du)^2 + r_speed (dc)^2 + w_slack slack^2
    within |u| <= full lock, |du| <= rate dt         (the tighter of ego and the motor:
                                                       so the motor keeps up, and the
                                                       model's rate limit stays linear)
           0 <= c <= cruise, -decel dt <= dc <= accel dt   (the smoother's and ego's)
           v - slack <= v_lim, slack >= 0            (v_lim: cruise, the bends' sideways
                                                       limit, the stop at the end, each
                                                       eased back at the planned braking)

   r = atan(L kappa), the bend's own steering; v_lim at where the plan puts the car.
4. It sends u[0] and c[0] (within the limits exactly).

The deadbands are left out of the plan (they'd flatten its gradients; the steering's
5 mrad is under one tick of its rate), but kept in the estimate. The dead times are
whole ticks of the commands already sent: the throttle's and the brake's longer one
for the set speed (an approximation: on the car they act after the speed loop).
`latency` adds the ROS chain's own delay (s) to both. The LQI speed loop isn't modelled.

It tells ego so: a lag-aware tracker (`lag_aware = True`), ego's lead turns off.
"""

from __future__ import annotations

from collections import deque
from dataclasses import replace
import math
import time
from typing import Sequence

from aav_description import car_model
from aav_drive_to_point.approach import planned_deceleration
from aav_track import lag_model as lm
from aav_track import qp
from aav_track.path import wrap
from aav_track.trackers import Command, Limits, State, Tracker
import numpy as np

# The states the cost sees.
COSTED = (lm.E_Y, lm.E_TH, lm.WHEELS, lm.V)


def T_ticks(n: int, period: float) -> np.ndarray:
    """Return the times of a plan's n ticks: period, 2 period, ... n period."""
    return period * np.arange(1, n + 1)


class MPCLag(Tracker):
    name = 'mpc_lag'
    plans_speed = True            # Command.speed
    lag_aware = True              # it models the lags: ego's lead stays off

    def __init__(self, limits: Limits, model: lm.CarParams, cruise: float = 1.0,
                 accel: float = 1.0, decel: float = 2.0, max_brake: float = 3.0,
                 lateral_accel: float = 1.0, period: float = 0.05, horizon: int = 30,
                 q: Sequence[float] = (1.0, 2.0, 0.05), r: float = 0.2, r_rate: float = 1.0,
                 q_speed: float = 0.5, r_speed: float = 0.5, w_slack: float = 50.0,
                 terminal: float = 5.0, latency: float = 0.1, speed_loop: str = 'default',
                 substeps: int = 2, max_iter: int = 400, rho: float = 1.0, sqp: int = 1):
        super().__init__(limits)
        if cruise <= 0 or accel <= 0 or decel <= 0 or max_brake <= 0 or lateral_accel <= 0 \
                or period <= 0 or horizon < 2 or r <= 0 or r_rate < 0 or q_speed < 0 or \
                r_speed < 0 or w_slack <= 0 or terminal < 1 or latency < 0 or substeps < 1 or \
                sqp < 1:
            raise ValueError('need cruise, accel, decel, max_brake, lateral_accel, period, '
                             'r, w_slack above 0; horizon >= 2; terminal >= 1; r_rate, '
                             'q_speed, r_speed, latency >= 0; substeps >= 1')
        model = replace(model, wheelbase=limits.wheelbase, max_steering=limits.max_steer)
        self.model = model
        # The estimate: the shared car model, with the speed loop's own state (its
        # integral); the dead times are this tracker's queues, a tick at a time.
        self.car = lm.without_dead_times(model)
        self.plan_car = lm.without_deadbands(self.car)      # for the plan
        self.loop = lm.speed_loop(speed_loop)
        self.model_dt = period / substeps
        self.cruise, self.accel, self.decel = cruise, accel, decel
        self.brake = planned_deceleration(max_brake)
        self.lateral_accel = lateral_accel
        self.period, self.n, self.substeps = period, horizon, substeps
        self.max_iter, self.rho, self.sqp = max_iter, rho, sqp
        self.q = np.array([*q, q_speed], float)            # on COSTED
        self.r_u, self.r_rate, self.r_speed, self.w_slack = r, r_rate, r_speed, w_slack
        self.terminal = terminal
        # Whole ticks of dead time (the commands already sent, waiting).
        self.d_steer = lm.dead_ticks(model.steer_dead_time + latency, period)
        self.d_speed = lm.dead_ticks(max(model.throttle_dead_time, model.brake_dead_time) +
                                     latency, period)
        self.car_state = None         # the estimate: car_model.CarState, at the last tick
        self.speed_loop = None        # its car_model.SpeedLoop (the integral)
        self.sent = None              # (steer, set speed) of the last tick
        self.acting = None            # (steer, set speed) acting over this tick
        self.steer_queue = deque()    # the steering commands still in the dead time
        self.speed_queue = deque()
        self.plan_u = None            # (N, 2): the last plan, for the next nominal
        self.warm_y = None
        n = horizon
        self.diff = np.eye(n) - np.eye(n, k=-1)

    def reset(self, path):
        super().reset(path)
        # Keep the estimate and the plan: the new path starts where the car is.

    # --- the estimate ---------------------------------------------------------------------

    def estimate(self, state: State, dt: float) -> np.ndarray:
        """
        Return the state now: the pose and speed measured, the rest from what was sent.

        The actuators and the speed loop's integral come from the shared car model
        (car_model.step, with its SpeedLoop), run over the last tick from the speed then
        measured, with the commands that acted over it.
        """
        foot = self.foot(state.x, state.y)
        v = max(state.v, 0.0)
        if self.car_state is None:
            self.car_state = car_model.CarState(steer=state.steer, steer_motor=state.steer,
                                                steer_setpoint=state.steer,
                                                steer_linkage=state.steer)
            self.speed_loop = car_model.SpeedLoop(self.loop)
            self.steer_queue = deque([state.steer] * self.d_steer)
            self.speed_queue = deque([v] * self.d_speed)
            self.sent = (state.steer, v)
        else:
            # The commands that acted over the last tick (sent a dead time before it).
            command = car_model.Command(steer=self.acting[0], speed=self.acting[1])
            car = self.car_state
            for _ in range(max(1, int(round(dt / self.model_dt)))):
                car = car_model.step(self.car, car, command, self.model_dt, self.speed_loop)
            self.car_state = car
        c = self.car_state
        x = np.zeros(lm.NX)
        x[lm.E_Y], x[lm.E_TH], x[lm.S] = foot.cross, wrap(state.yaw - foot.heading), foot.s
        x[lm.V] = v
        x[lm.THROTTLE], x[lm.BRAKE] = c.throttle_level, c.brake_level
        x[lm.SETPOINT], x[lm.MOTOR] = c.steer_setpoint, c.steer_motor
        x[lm.WHEELS] = c.steer_linkage
        x[lm.INTEGRAL] = self.speed_loop.integral
        # The next tick starts from the speed measured now.
        self.car_state = replace(c, v=v)
        return x

    @staticmethod
    def passed(queue: deque, newest: float) -> float:
        """Queue `newest`; return the command that acts over the next tick."""
        queue.append(newest)
        return queue.popleft()

    # --- the speed limit ahead ------------------------------------------------------------

    def limits_ahead(self, s0: float, length: float, ds: float = 0.25):
        """Return (s, v_lim) on a grid from s0: cruise, bends, the stop; eased back."""
        path = self.path
        reach = self.cruise ** 2 / (2.0 * self.brake)
        s = s0 + ds * np.arange(int(math.ceil((length + reach) / ds)) + 2)
        bend = np.abs([path.curvature_at(float(a)) for a in s])
        w = np.full(len(s), self.cruise ** 2)
        w = np.minimum(w, np.where(bend > 1e-9, self.lateral_accel / np.maximum(bend, 1e-9),
                                   np.inf))
        w = np.minimum(w, 2.0 * self.brake * np.maximum(path.length - s, 0.0))
        for k in range(len(s) - 2, -1, -1):
            w[k] = min(w[k], w[k + 1] + 2.0 * self.brake * ds)
        return s, np.sqrt(np.maximum(w, 0.0))

    # --- the plan -------------------------------------------------------------------------

    def nominal_inputs(self, x0: np.ndarray, steer_now: float) -> np.ndarray:
        """Return (N, 2): the last plan shifted by a tick, or holding what was sent."""
        n = self.n
        if self.plan_u is None:
            u = np.tile([steer_now, x0[lm.V]], (n, 1))
        else:
            u = np.vstack([self.plan_u[1:], self.plan_u[-1:]])
        if np.max(u[:, 1]) < self.loop.stopped_speed:
            # A plan that stands still is linearised where the brake holds the car: no
            # gradient to start from. Start from speeding up to cruise; the QP slows it.
            u[:, 1] = np.minimum(self.cruise, self.accel * T_ticks(n, self.period))
        return u

    def effective(self, u: np.ndarray, k: int, steer_buf, speed_buf) -> np.ndarray:
        """Return the input acting at tick k of the plan: the buffer's, or the plan's."""
        ds_, dv = self.d_steer, self.d_speed
        steer = steer_buf[k] if k < ds_ else u[k - ds_, 0]
        speed = speed_buf[k] if k < dv else u[k - dv, 1]
        return np.array([steer, speed])

    def linearise(self, x0, u_bar, steer_buf, speed_buf):
        """Return (X_bar (N, NX), A (N, NX, NX), B (N, NX, NU), kappa (N,))."""
        n, eps = self.n, 1e-4
        xs = np.empty((n, lm.NX))
        a = np.empty((n, lm.NX, lm.NX))
        b = np.empty((n, lm.NX, lm.NU))
        kappas = np.empty(n)
        x = x0
        # One column for the nominal, one for each state and input nudged.
        nudge = np.hstack([np.zeros((lm.NX + lm.NU, 1)), eps * np.eye(lm.NX + lm.NU)])
        for k in range(n):
            u = self.effective(u_bar, k, steer_buf, speed_buf)
            kappa = self.path.curvature_at(float(x[lm.S]))
            cols = np.concatenate([x, u])[:, None] + nudge
            out = lm.step(self.plan_car, self.loop, cols[:lm.NX], cols[lm.NX:], kappa,
                          self.period, self.substeps)
            nominal = out[:, 0]
            jac = (out[:, 1:] - nominal[:, None]) / eps
            a[k], b[k] = jac[:, :lm.NX], jac[:, lm.NX:]
            kappas[k] = kappa
            xs[k] = x = nominal
        return xs, a, b, kappas

    def condense(self, a, b):
        """Return M (N, |COSTED|, 2N): how each planned input moves the costed states."""
        n = self.n
        m = np.zeros((n, lm.NX, 2 * n))
        acc = np.zeros((lm.NX, 2 * n))
        for k in range(n):
            acc = a[k] @ acc
            j = k - self.d_steer                      # which planned steering acts at k
            if j >= 0:
                acc[:, j] += b[k][:, lm.STEER]
            j = k - self.d_speed
            if j >= 0:
                acc[:, n + j] += b[k][:, lm.SPEED]
            m[k] = acc
        return m[:, COSTED, :]

    def step(self, state: State, dt: float) -> Command:
        t0 = time.perf_counter()
        T = self.period
        x0 = self.estimate(state, dt)
        bufs = (list(self.steer_queue), list(self.speed_queue))
        plan = self.nominal_inputs(x0, state.steer)
        iterations, solved = 0, True
        for _ in range(self.sqp):
            plan, res, r0, v0 = self.solve(x0, plan, state.steer, bufs)
            iterations += res.iterations
            solved = solved and res.solved
        self.plan_u = plan

        # Exactly within the limits: the steering's lock and rate, the speed's.
        tick = max(dt, T)
        steer = self.limited(float(plan[0, 0]), state.steer, tick)
        speed = float(np.clip(plan[0, 1], self.sent[1] - self.decel * tick,
                              self.sent[1] + self.accel * tick))
        speed = float(np.clip(speed, 0.0, self.cruise))
        self.sent = (steer, speed)
        self.acting = (self.passed(self.steer_queue, steer),
                       self.passed(self.speed_queue, speed))
        self.plan_u[0] = (steer, speed)
        return Command(steer, speed=speed, debug={
            'solve_ms': 1000.0 * (time.perf_counter() - t0),
            'iterations': float(iterations), 'solved': float(solved),
            'wheels_est_rad': float(x0[lm.WHEELS]),
            'speed_limit_mps': float(v0),
            'feed_forward_rad': float(r0)})

    def solve(self, x0, u_bar, steer_now, bufs):
        """Return (the plan (N, 2), the QP's result, the bend's steering and v_lim now)."""
        lim, n, T = self.limits, self.n, self.period
        xs, a, b, kappa = self.linearise(x0, u_bar, *bufs)
        m = self.condense(a, b)                                    # (N, 4, 2N)

        # The targets along the nominal plan.
        r = np.clip(np.arctan(lim.wheelbase * kappa), -lim.max_steer, lim.max_steer)
        grid, v_grid = self.limits_ahead(float(x0[lm.S]),
                                         float(xs[-1, lm.S] - x0[lm.S]) + 1.0)
        v_lim = np.interp(xs[:, lm.S], grid, v_grid)
        target = np.stack([np.zeros(n), np.zeros(n), r, v_lim], axis=1)
        weights = np.tile(self.q, (n, 1))
        weights[-1] *= self.terminal
        err = (xs[:, COSTED] - target).reshape(-1)                  # at dU = 0
        mf = m.reshape(4 * n, 2 * n)
        wd = weights.reshape(-1)

        # The cost in z = [dU_steer (N), dU_speed (N), slack (N)].
        nz = 3 * n
        p = np.zeros((nz, nz))
        qv = np.zeros(nz)
        p[:2 * n, :2 * n] = mf.T @ (wd[:, None] * mf)
        qv[:2 * n] = mf.T @ (wd * err)
        # The steering near the bend's own (where it will act), and smooth.
        r_cmd = r[np.minimum(np.arange(n) + self.d_steer, n - 1)]
        us, cs = u_bar[:, 0], u_bar[:, 1]
        e_s = np.zeros(n)
        e_s[0] = steer_now
        e_c = np.zeros(n)
        e_c[0] = self.sent[1]
        dtd = self.diff.T @ self.diff
        ss, sc = slice(0, n), slice(n, 2 * n)
        p[ss, ss] += self.r_u * np.eye(n) + self.r_rate * dtd
        qv[ss] += self.r_u * (us - r_cmd) + self.r_rate * self.diff.T @ (self.diff @ us - e_s)
        p[sc, sc] += self.r_speed * dtd
        qv[sc] += self.r_speed * self.diff.T @ (self.diff @ cs - e_c)
        p[2 * n:, 2 * n:] = self.w_slack * np.eye(n)

        # The constraints: lo <= A z <= hi.
        eye, zero = np.eye(n), np.zeros((n, n))
        step_s = lim.max_steer_rate * T
        rows = [np.hstack([eye, zero, zero]),                         # full lock
                np.hstack([self.diff, zero, zero]),                   # the steering rate
                np.hstack([zero, eye, zero]),                         # 0 <= c <= cruise
                np.hstack([zero, self.diff, zero]),                   # accel, decel
                np.hstack([zero, zero, eye])]                         # slack >= 0
        lo = [-lim.max_steer - us, -step_s - (self.diff @ us - e_s), -cs,
              -self.decel * T - (self.diff @ cs - e_c), np.zeros(n)]
        hi = [lim.max_steer - us, step_s - (self.diff @ us - e_s), self.cruise - cs,
              self.accel * T - (self.diff @ cs - e_c), np.full(n, np.inf)]
        # v - slack <= v_lim, v = v_bar + M_v dU.
        mv = m[:, 3, :]
        rows.append(np.hstack([mv, -eye]))
        lo.append(np.full(n, -np.inf))
        hi.append(v_lim - xs[:, lm.V])
        a_mat = np.vstack(rows)
        lo_v, hi_v = np.concatenate(lo), np.concatenate(hi)
        hi_v = np.maximum(hi_v, lo_v)

        y0 = self.warm_y if self.warm_y is not None and len(self.warm_y) == len(lo_v) else None
        res = qp.solve(p, qv, a_mat, lo_v, hi_v, z0=np.zeros(nz), y0=y0, eps=1e-4,
                       max_iter=self.max_iter, rho=self.rho)
        self.warm_y = res.y
        plan = u_bar + np.stack([res.z[:n], res.z[n:2 * n]], axis=1)
        # What the plan expects (e_y, e_theta, wheels, v per tick), for checking the model.
        self.predicted = xs[:, COSTED] + m @ res.z[:2 * n]
        return plan, res, float(r[0]), float(v_lim[0])
