"""
The fits against what the real car will have.

Play, coarse wheel speed, noise, no brake level, a dead time (docs/designs/
concepts_brief.md, S1).

Each test makes pretend measurements with known numbers (synthetic.py) and checks the
fit gives them back within the tolerance stated, or refuses with a reason.
"""

from aav_actuator_tests import analysis as an
import pytest
import synthetic as sy


# --- a dead time, then a lag, read off a level (throttle or brake) ------------------------

def level_run():
    t = sy.times(6)
    cmd = sy.steps(t, [(0, 0.0), (1.0, 0.6), (3.0, 0.2), (4.5, 0.8)])
    return t, cmd


@pytest.mark.parametrize('dead,tau,noise', [(0.08, 0.15, 0.0), (0.08, 0.15, 0.02),
                                            (0.3, 0.4, 0.05), (0.0, 0.1, 0.0)])
def test_dead_time_and_lag_from_a_level(dead, tau, noise):
    # Tolerance: 10 ms each, 40 ms with noise of 5% of full scale.
    t, cmd = level_run()
    measured = sy.noisy(an.fopdt_response(t, cmd, tau, dead), noise) if noise else \
        an.fopdt_response(t, cmd, tau, dead)
    fit = an.fit_fopdt(t, cmd, measured)
    tol = 0.04 if noise > 0.03 else 0.01
    assert fit.best_dead == pytest.approx(dead, abs=tol)
    assert fit.best_tau == pytest.approx(tau, abs=tol)
    assert not fit.problems('throttle', 'the level')
    assert fit.rms == pytest.approx(noise, abs=0.005)


def test_the_old_fit_stays_beside_it_and_is_worse_with_a_dead_time():
    t, cmd = level_run()
    fit = an.fit_fopdt(t, cmd, an.fopdt_response(t, cmd, 0.15, 0.08))
    assert fit.lag_only > 0.2                       # a lag alone soaks up the dead time
    assert fit.rms_lag_only > 10 * max(fit.rms, 1e-4)


def test_a_dead_time_between_log_ticks_is_found_with_true_stamps():
    # The command's messages at their own times (40 ms apart, offset from the 50 Hz log),
    # the dead time 30 ms: not a whole number of ticks.
    t = sy.times(6)
    cmd_t = [0.013 + 0.04 * i for i in range(150)]
    cmd = sy.steps(cmd_t, [(0, 0.0), (1.0, 0.6), (3.0, 0.2), (4.5, 0.8)])
    measured = an.fopdt_response(t, cmd, 0.12, 0.03, cmd_t)
    fit = an.fit_fopdt(t, cmd, measured, cmd_t=cmd_t)
    assert fit.dead_time == pytest.approx(0.03, abs=0.005)
    assert fit.tau == pytest.approx(0.12, abs=0.005)


def test_a_slow_sensor_cannot_resolve_a_short_dead_time():
    # A level read at 5 Hz: a 30 ms dead time is far under its 0.4 s resolution, so the
    # lag alone is used.
    t, cmd = level_run()
    slow_t = [round(0.2 * i, 9) for i in range(31)]
    slow = sy.resample(t, an.fopdt_response(t, cmd, 0.5, 0.03), slow_t)
    fit = an.fit_fopdt(slow_t, cmd, slow, cmd_t=t)
    assert fit.resolution >= 0.4
    assert fit.best_dead == 0.0
    assert fit.best_tau == pytest.approx(0.53, abs=0.05)


# --- steering: play (backlash) and a dead time -------------------------------------------

def steer_run():
    t = sy.times(10)
    cmd = sy.steps(t, [(0, 0.0), (1.0, 0.5), (3.5, 0.0), (6.0, -0.5), (8.5, 0.0)])
    return t, cmd


def cut(t, values, start, end):
    return [v for ti, v in zip(t, values) if start <= ti < end]


@pytest.mark.parametrize('play,dead', [(0.0, 0.0), (0.02, 0.0), (0.04, 0.06)])
def test_steering_with_play(play, dead):
    # Motor 0.8 rad/s, linkage lag 0.1 s, offset 0.01 rad, noise 2 mrad.
    # Tolerance: rate 3%, play 3 mrad, offset 2 mrad, lag 10 ms, dead time 25 ms.
    t, cmd = steer_run()
    measured = sy.noisy(sy.steer(t, cmd, 0.8, 0.1, dead, play, 0.01), 0.002)
    swings = [an.swing(cut(t, t, s - 1, s + 2.4), cut(t, cmd, s - 1, s + 2.4),
                       cut(t, measured, s - 1, s + 2.4), s) for s in (1.0, 6.0)]
    rate = an.mean([s.rate for s in swings])
    assert rate == pytest.approx(0.8, rel=0.03)
    p = an.steer_play(t, cmd, measured)
    assert p.width == pytest.approx(play, abs=0.003)
    assert p.offset == pytest.approx(0.01, abs=0.002)
    fit = an.fit_steer(t, cmd, measured, rate, play=max(0.0, p.width), offset=p.offset)
    assert fit.best_tau == pytest.approx(0.1, abs=0.01)
    assert fit.best_dead == pytest.approx(dead, abs=0.025)


def test_play_left_out_shows_as_a_longer_lag():
    t, cmd = steer_run()
    measured = sy.steer(t, cmd, 0.8, 0.1, 0.0, 0.04)
    fit = an.fit_steer(t, cmd, measured, 0.8)
    assert fit.lag_only > 0.13                 # why fit_steer takes the play first


# --- coarse wheel speed: Hall pulses ------------------------------------------------------

def throttle_run(fast):
    t = sy.times(10)
    if fast:     # up to 3 m/s: a pulse every 0.04-0.1 s
        changes = [(0, 0.0), (1.0, 0.4), (4.0, 0.2), (6.0, 0.6), (8.0, 0.1)]
    else:        # the car's 1 m/s cap: a pulse every 0.15-0.5 s
        changes = [(0, 0.0), (1.0, 0.15), (3.0, 0.05), (5.0, 0.12), (7.5, 0.03)]
    return t, sy.steps(t, changes)


@pytest.mark.parametrize('tau,dead', [(0.15, 0.05), (0.3, 0.0), (0.6, 0.3)])
def test_throttle_through_hall_pulses_up_to_3_m_s(tau, dead):
    # 8 holes on a 0.30 m wheel, sent at 100 Hz. Tolerance: max_accel 2%; the total delay
    # (dead time + lag) 40 ms or 10%; the dead time split out only when it shows (0.3 s).
    t, thr = throttle_run(fast=True)
    tf, v, _ = sy.drive(t, thr, 1.5, tau, dead, 0.1)
    ht, hv = sy.hall(tf, v)
    fit = an.fit_speed_response(t, thr, ht, hv, 0.1)
    assert fit.gain == pytest.approx(1.5, rel=0.02)
    assert fit.best_tau + fit.best_dead == pytest.approx(tau + dead,
                                                         abs=max(0.04, 0.1 * (tau + dead)))
    assert fit.lag_problem('throttle', 'the wheel speed') is None
    if dead >= 0.3:
        assert fit.dead_resolved
        assert fit.best_dead == pytest.approx(dead, abs=0.04)
        assert fit.best_tau == pytest.approx(tau, abs=0.08)


def test_a_lag_shorter_than_the_pulses_is_refused():
    # At walking pace the pulses come every 0.15-0.5 s: a 0.15 s delay can't be seen.
    t, thr = throttle_run(fast=False)
    tf, v, _ = sy.drive(t, thr, 1.5, 0.1, 0.05, 0.1)
    ht, hv = sy.hall(tf, v)
    fit = an.fit_speed_response(t, thr, ht, hv, 0.1)
    assert fit.gain == pytest.approx(1.5, rel=0.05)       # the gain is still good
    why = fit.lag_problem('throttle', 'the wheel speed')
    assert why and 'the wheel speed' in why and 'not measured' in why
    assert fit.resolution > 2 * an.pulse_interval(1.0, sy.WHEEL, sy.HOLES)


def test_comparing_with_the_mean_between_pulses_matters():
    # A Hall speed is the mean since the last pulse: half an interval late. Read as a
    # point it adds that to the delay.
    t, thr = throttle_run(fast=True)
    tf, v, _ = sy.drive(t, thr, 1.5, 0.3, 0.0, 0.1)
    ht, hv = sy.hall(tf, v)
    mean_fit = an.fit_speed_response(t, thr, ht, hv, 0.1)
    point_fit = an.fit_speed_response(t, thr, ht, hv, 0.1, average=False)
    true = 0.3
    assert abs(mean_fit.best_tau + mean_fit.best_dead - true) < \
        abs(point_fit.best_tau + point_fit.best_dead - true)


# --- the brake with no level: the IMU's deceleration only ---------------------------------

def brake_run(tau, dead, noise=0.05):
    t = sy.times(4)
    cmd = sy.steps(t, [(0, 0.0), (0.5, 0.5), (1.5, 0.3), (2.3, 0.6)])
    tf, v, a = sy.drive(t, cmd, 3.0, tau, dead, 0.1, sign=-1.0, v0=4.0)
    ax = sy.noisy(sy.resample(tf, a, t), noise, seed=3)
    vs = sy.resample(tf, v, t)
    use = [i for i in range(len(t)) if vs[i] > 0.2]
    return ([t[i] for i in use], [-ax[i] - 0.1 * vs[i] for i in use], t, cmd)


@pytest.mark.parametrize('tau,dead', [(0.2, 0.1), (0.2, 0.0)])
def test_brake_from_the_imu_alone(tau, dead):
    # max_brake 3 m/s^2, IMU noise 0.05 m/s^2 at 50 Hz. Tolerance: max_brake 2%, lag and
    # dead time 20 ms.
    t, decel, cmd_t, cmd = brake_run(tau, dead)
    fit = an.fit_fopdt(t, cmd, decel, cmd_t=cmd_t, free_gain=True)
    assert fit.gain == pytest.approx(3.0, rel=0.02)
    assert fit.best_tau == pytest.approx(tau, abs=0.02)
    assert fit.best_dead == pytest.approx(dead, abs=0.02)
    assert abs(fit.offset) < 0.05


def test_the_stop_as_a_whole_without_a_brake_demand():
    # No brake level, no demand: only when the stop was asked for. A brake that bites
    # 0.25 s later with a 0.2 s lag: the whole stop's dead time and lag come back.
    t = sy.times(4)
    asked = sy.steps(t, [(0, 0.0), (0.5, 1.0)])
    tf, v, a = sy.drive(t, [0.4 * x for x in asked], 3.0, 0.2, 0.25, 0.1, sign=-1.0, v0=4.0)
    ax = sy.noisy(sy.resample(tf, a, t), 0.05, seed=4)
    vs = sy.resample(tf, v, t)
    use = [i for i in range(len(t)) if vs[i] > 0.2]
    fit = an.fit_fopdt([t[i] for i in use], asked, [-ax[i] - 0.1 * vs[i] for i in use],
                       cmd_t=t, free_gain=True)
    assert fit.gain == pytest.approx(1.2, rel=0.03)      # 0.4 of 3 m/s^2
    assert fit.best_dead == pytest.approx(0.25, abs=0.02)
    assert fit.best_tau == pytest.approx(0.2, abs=0.02)
