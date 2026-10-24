import math

from aav_safety import watchdog
from aav_safety.watchdog import FROZEN, JUMP, NAN, NEVER, OK, Rule, STALE, Watchdog
import pytest

ODOM = Rule('odom', '/vehicle/odom', 'odom', max_age=0.5)
IMU = Rule('imu', '/sensors/imu/data', 'imu', max_age=0.5, frozen_after=1.0)
GPS = Rule('gps', '/sensors/gps/fix', 'gps', max_age=2.0, max_jump_speed=15.0)
CAMERA = Rule('camera', '/sensors/camera/front_left/image_raw', 'image', max_age=1.0,
              frozen_after=1.0)
RADAR = Rule('radar', '/sensors/radar/points', 'cloud', max_age=1.0, stop=False)
HUD = Rule('hud', '/hud/heartbeat', 'heartbeat', max_age=1.0, frozen_after=1.0)
HERE = (45.3860, -75.6960)


def state(dog, name, now):
    return {n: s for n, s, _, _ in dog.states(now)}[name]


def test_nothing_yet_stops_the_drivers():
    dog = Watchdog([ODOM])
    assert state(dog, 'odom', 0.0) == NEVER
    assert dog.locked(0.0)


def test_fresh_is_ok_and_silence_goes_stale():
    dog = Watchdog([ODOM])
    dog.watches['odom'].arrived(10.0, (1.0, 0.0))
    assert state(dog, 'odom', 10.4) == OK and not dog.locked(10.4)
    assert state(dog, 'odom', 10.6) == STALE and dog.locked(10.6)
    dog.watches['odom'].arrived(10.7, (1.0, 0.0))     # back: drives again on its own
    assert not dog.locked(10.7)


def test_nan_stops_at_once():
    dog = Watchdog([ODOM])
    dog.watches['odom'].arrived(1.0, (math.nan, 0.0))
    assert state(dog, 'odom', 1.0) == NAN and dog.locked(1.0)


def test_a_gps_without_a_fix_counts_as_lost_after_max_age():
    dog = Watchdog([GPS])
    gps = dog.watches['gps']
    gps.arrived(0.0, fix=HERE)
    gps.arrived(1.0, fix=(math.nan, math.nan))
    assert state(dog, 'gps', 1.5) == OK              # a short gap is normal for a GPS
    gps.arrived(2.1, fix=HERE, has_fix=False)
    s, detail = gps.state(2.1)
    assert s == STALE and 'no fix' in detail


def test_a_gps_jump_latches_until_cleared():
    dog = Watchdog([GPS])
    gps = dog.watches['gps']
    gps.arrived(0.0, fix=HERE)
    gps.arrived(0.2, fix=(HERE[0] + 0.5e-5, HERE[1]))   # 0.56 m in 0.2 s: driving
    assert state(dog, 'gps', 0.2) == OK
    gps.arrived(0.4, fix=(HERE[0] + 20 / 111195.0, HERE[1]))   # 20 m in 0.2 s
    assert state(dog, 'gps', 0.4) == JUMP
    gps.arrived(0.6, fix=(HERE[0] + 20 / 111195.0, HERE[1]))
    assert state(dog, 'gps', 10.0) == JUMP            # the next fixes agree: still latched
    dog.clear()
    gps.arrived(10.0, fix=(HERE[0] + 20 / 111195.0, HERE[1]))
    assert state(dog, 'gps', 10.0) == OK


def test_gps_noise_and_fixes_that_arrive_together_are_not_jumps():
    dog = Watchdog([GPS])
    gps = dog.watches['gps']
    north = 1 / 111195.0           # a metre of latitude
    gps.arrived(0.0, fix=HERE, stamp=100.0)
    gps.arrived(0.2, fix=(HERE[0] + 2.5 * north, HERE[1]), stamp=100.2)   # 2.5 m of noise
    # Two queued fixes delivered at once: 0.2 s apart by their stamps, not 0 s.
    gps.arrived(0.5, fix=(HERE[0] + 1.4 * north, HERE[1]), stamp=100.4)
    gps.arrived(0.5, fix=(HERE[0] + 2.6 * north, HERE[1]), stamp=100.6)
    gps.arrived(0.5, fix=(HERE[0] + 2.6 * north, HERE[1]), stamp=100.6)   # the same again
    assert state(dog, 'gps', 0.5) == OK
    gps.arrived(0.7, fix=(HERE[0] + 23.0 * north, HERE[1]), stamp=100.8)  # 20 m in 0.2 s
    assert state(dog, 'gps', 0.7) == JUMP


def test_frozen_values_stop_after_frozen_after():
    dog = Watchdog([IMU])
    imu = dog.watches['imu']
    for k in range(5):
        imu.arrived(k * 0.1, (0.01 * k, 0.0), digest=k)
    for k in range(5, 20):
        imu.arrived(k * 0.1, (0.04, 0.0), digest='same')
    assert state(dog, 'imu', 1.5) == OK
    assert state(dog, 'imu', 1.95) == FROZEN and dog.locked(1.95)


def test_a_still_camera_is_frozen_only_while_the_car_moves():
    dog = Watchdog([CAMERA])
    cam = dog.watches['camera']
    for k in range(30):                               # parked: the same picture is fine
        cam.arrived(k * 0.1, digest='street', speed=0.0)
    assert state(dog, 'camera', 2.9) == OK
    for k in range(30, 45):                           # driving: the picture must change
        cam.arrived(k * 0.1, digest='street', speed=1.0)
    assert state(dog, 'camera', 4.4) == FROZEN


def test_the_hud_must_beat_before_and_while_nav2_drives():
    dog = Watchdog([HUD])
    hud = dog.watches['hud']
    assert state(dog, 'hud', 0.0) == NEVER and dog.locked(0.0)     # no screen yet
    for k in range(1, 11):                            # 10 Hz, the frames it has drawn
        hud.arrived(k * 0.1, digest=3 * k)
    assert state(dog, 'hud', 1.5) == OK and not dog.locked(1.5)
    assert state(dog, 'hud', 2.1) == STALE and dog.locked(2.1)     # frozen or dead
    hud.arrived(2.2, digest=0)                        # restarted: its count from 0 again
    assert not dog.locked(2.2)


def test_a_hud_that_beats_without_drawing_is_frozen():
    dog = Watchdog([HUD])
    hud = dog.watches['hud']
    for k in range(1, 30):                            # still sent, the count stuck
        hud.arrived(k * 0.1, digest=42)
    assert state(dog, 'hud', 2.9) == FROZEN and dog.locked(2.9)


def test_a_warn_input_never_stops_the_drivers():
    dog = Watchdog([ODOM, RADAR])
    dog.watches['odom'].arrived(0.0, (0.0,))
    assert not dog.locked(0.3)                        # the radar has never spoken
    assert dog.summary(0.3).startswith('WARN: radar NEVER')
    assert dog.summary(0.6).startswith('STOP: odom STALE')


def test_ground_distance_is_metres():
    north = (HERE[0] + 100 / 111195.0, HERE[1])
    assert watchdog.ground_distance(HERE, north) == pytest.approx(100.0, rel=1e-3)


def test_rules_are_checked():
    with pytest.raises(ValueError):
        Rule('x', '/x', 'lidar', max_age=1.0)
    with pytest.raises(ValueError):
        Rule('x', '/x', 'odom', max_age=0.0)


LEFT = Rule('front_left_stream', '/perception/detections', 'detections', max_age=1.0,
            frame_id='camera_left_link')


def test_a_streamed_camera_is_watched_through_its_detections():
    dog = Watchdog([LEFT])
    left = dog.watches['front_left_stream']
    assert state(dog, 'front_left_stream', 0.0) == NEVER and dog.locked(0.0)
    for k in range(1, 16):                            # 15 a second, boxes or none
        left.arrived(k / 15.0, ())
    assert state(dog, 'front_left_stream', 1.5) == OK and not dog.locked(1.5)
    # The same empty list for seconds is a clear road, not a frozen camera.
    for k in range(16, 60):
        left.arrived(k / 15.0, ())
    assert state(dog, 'front_left_stream', 4.5) == OK
    # The stream, its decoder or its detector stops: no message at all.
    assert state(dog, 'front_left_stream', 5.0) == STALE and dog.locked(5.0)
    left.arrived(5.1, (math.nan, 10.0, 20.0, 30.0, 0.9))     # a broken detector
    assert state(dog, 'front_left_stream', 5.1) == NAN


def test_each_detections_input_counts_only_its_own_camera():
    assert LEFT.counts('camera_left_link')
    assert not LEFT.counts('camera_right_link')       # the other stream, same topic
    assert CAMERA.counts('anything')                  # other kinds have no filter


def test_detections_rules_are_checked():
    with pytest.raises(ValueError, match='frame_id'):
        Rule('x', '/perception/detections', 'detections', max_age=1.0)
    with pytest.raises(ValueError, match='frame_id'):
        Rule('x', '/x', 'image', max_age=1.0, frame_id='camera_left_link')
    with pytest.raises(ValueError, match='frozen'):
        Rule('x', '/perception/detections', 'detections', max_age=1.0,
             frame_id='camera_left_link', frozen_after=1.0)


def test_traffic_is_the_rate_and_the_gaps_for_people():
    watch = Watchdog([IMU]).watches['imu']
    assert watch.traffic(5.0) == (0.0, 0.0, 0.0)      # nothing yet
    for i in range(10):                               # 10 Hz for a second
        watch.arrived(10.0 + i * 0.1, (0.0, 0.0, float(i)), digest=i)
    rate, gap, worst = watch.traffic(10.95)
    assert rate == pytest.approx(10 / 0.95)
    assert gap == pytest.approx(0.1) and worst == pytest.approx(0.1)
    watch.arrived(11.5, (0.0, 0.0, 1.0), digest=10)   # 0.6 s of silence, then one
    rate, gap, worst = watch.traffic(12.0)
    assert rate == pytest.approx(1 / 1.05)
    assert gap == pytest.approx(0.6) and worst == pytest.approx(0.6)


def test_traffic_counts_a_silence_that_has_not_ended():
    watch = Watchdog([ODOM]).watches['odom']
    watch.arrived(1.0, (0.0, 0.0))
    watch.traffic(1.5)
    rate, gap, worst = watch.traffic(4.0)             # silent since 1.0
    assert rate == 0.0 and gap == pytest.approx(3.0) and worst == pytest.approx(3.0)
    watch.arrived(4.1, (0.0, 0.0))
    _, gap, worst = watch.traffic(4.2)
    assert gap == pytest.approx(3.1) and worst == pytest.approx(3.1)
