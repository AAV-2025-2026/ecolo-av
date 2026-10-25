"""
link.py against a pretend CARLA (fake_carla.py), with no server.

Every call carla_adapter makes, and a drive that checks the signs end to end: ego says
left, the CARLA car turns left, and our topics say it turned left.
"""

import importlib.util
import math
import os

from aav_carla import control, frames, georef, sensors, state
from aav_carla.link import CarlaLink, load_carla
import pytest

# The pretend carla module, beside this file.
_spec = importlib.util.spec_from_file_location(
    'fake_carla', os.path.join(os.path.dirname(__file__), 'fake_carla.py'))
fake_carla = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake_carla)

DATUM = (45.3860, -75.6960)


def started(**load):
    link = CarlaLink(fake_carla, '10.0.0.5', 2000, 20.0)
    link.load(**load, datum=DATUM)
    link.configure(True, 0.05)
    return link


def car_on(link, spawn=None, frame=None):
    link.spawn('', link.spawn_transform(spawn, frame), 'ego_vehicle')
    g = link.geometry()
    return g, control.Geometry(1.57, 0.5, g['wheelbase'], g['max_steer'])


def test_the_client_connects_and_reports_versions():
    link = CarlaLink(fake_carla, '10.0.0.5', 2000, 20.0)
    assert (link.client.host, link.client.port, link.client.timeout) == ('10.0.0.5', 2000, 20.0)
    assert link.versions() == ('0.10.0', '0.10.0')


def test_a_town_loads_and_runs_synchronously_until_closed():
    link = started(town='Town10HD_Opt')
    assert link.world.name == 'Town10HD_Opt'
    assert link.world.settings.synchronous_mode
    assert link.world.settings.fixed_delta_seconds == 0.05
    car_on(link)
    link.close()
    assert not link.world.settings.synchronous_mode      # the server's own settings back
    assert all(not a.alive for a in link.world.actors)


def test_openstreetmap_is_converted_with_our_projection():
    fake_carla.Osm2Odr.calls.clear()
    link = started(osm='<osm/>')
    (osm, settings), = fake_carla.Osm2Odr.calls
    assert osm == '<osm/>'
    assert settings.proj_string == georef.proj_string(*DATUM)
    assert settings.center_map is False and settings.use_offsets is False
    xodr, params = link.client.generated
    assert georef.georeference(xodr)['lat_0'] == pytest.approx(DATUM[0])
    assert params.wall_height == 0.0


def test_the_car_and_its_sizes():
    link = started()
    g, _ = car_on(link)
    assert link.vehicle.blueprint.id == 'vehicle.mini.cooper'    # the smallest it has
    assert link.vehicle.blueprint.attributes['role_name'] == 'ego_vehicle'
    assert g['wheelbase'] == pytest.approx(2.9)
    assert g['rear_axle_x'] == pytest.approx(-1.45)
    assert g['max_steer'] == pytest.approx(math.radians(70))
    assert g['ground_z'] == pytest.approx(0.0)


def test_a_blocked_spawn_point_says_so():
    link = started()
    link.world.blocked = True
    with pytest.raises(RuntimeError):
        car_on(link)
    with pytest.raises(ValueError):
        link.spawn_transform(7)


def test_a_place_needs_the_world_frame():
    link = started(xodr='<OpenDRIVE/>')
    with pytest.raises(ValueError):
        link.spawn_transform((10.0, 5.0, 0.0), None)
    frame, kind = frames.map_frame(*link.origin_geolocation(), *DATUM, (0.0, 0.0, 0.0))
    assert kind == 'world'
    t = link.spawn_transform((10.0, 5.0, math.pi / 2), frame)
    # 10 m east and 5 m north of the datum: CARLA's x 10, y -5 (its y points right),
    # facing north: CARLA's yaw -90 degrees.
    assert (t.location.x, t.location.y) == pytest.approx((10.0, -5.0))
    assert t.rotation.yaw == pytest.approx(-90.0)


def test_sensors_attach_where_vehicle_yaml_says_with_string_attributes():
    link = started()
    g, _ = car_on(link)
    seen = []
    for s in sensors.chosen():
        m = frames.mount([1.75, 0.29, 1.55], [0.0, 0.0, 0.0], g['rear_axle_x'], g['ground_z'])
        actor = link.attach(s, m, seen.append)
        assert actor.parent is link.vehicle
        assert actor.blueprint.attributes['sensor_tick'] == s.attributes['sensor_tick']
    cam = link.sensors[1]
    assert cam.transform.location.y == pytest.approx(-0.29)    # left of the car: CARLA's -y
    cam.callback('a picture')
    assert seen == ['a picture']
    link.close()
    assert link.sensors == []


@pytest.mark.parametrize('mode', ['ackermann', 'pedals'])
def test_ego_says_left_and_the_car_turns_left(mode):
    link = started()
    g, geo = car_on(link, spawn=0)      # spawn point 0 faces CARLA's +y, yaw 90
    here = state.car_state(**link.readings(), frame=frames.SpawnFrame(0.0, 0.0, 0.0),
                           rear_axle_x=g['rear_axle_x'])
    frame = frames.SpawnFrame(here.x, here.y, here.yaw)
    loop = control.SpeedLoop()
    s = state.car_state(**link.readings(), frame=frame, rear_axle_x=g['rear_axle_x'])
    assert (s.x, s.y, s.yaw) == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)   # facing east
    for _ in range(60):                  # 3 s at 1.5 m/s, 0.2 rad left
        if mode == 'ackermann':
            command = control.ackermann(geo, 1.5, 0.2)
        else:
            command = control.pedals(geo, loop, 1.5, 0.2, s.speed, 0.05)
        link.drive(command)
        link.tick()
        s = state.car_state(**link.readings(), frame=frame, rear_axle_x=g['rear_axle_x'])
    assert s.speed > 0.0
    assert s.yaw_rate > 0.0              # left is + (REP-103)
    assert s.yaw > 0.0
    assert s.y > 0.0                     # it went left of where it faced
    if mode == 'ackermann':
        # On our car's circle: yaw rate = v tan(steer) / our wheelbase.
        assert s.yaw_rate == pytest.approx(1.5 * math.tan(0.2) / 1.57, rel=1e-6)
        assert geo.our_angle(*link.front_wheels_deg()) == pytest.approx(0.2)
    lat, lon, _ = state.antenna(s, [0.8, 0.0, 1.5], *DATUM)
    assert lat > DATUM[0]                # left of east is north


def test_the_estop_brakes():
    link = started()
    car_on(link)
    link.drive(control.stopped())
    c = link.vehicle.get_control()
    assert c.brake == 1.0 and c.hand_brake
    assert link.pedal_levels() == (0.0, 1.0)


def test_asynchronous_waits_for_the_servers_step():
    link = CarlaLink(fake_carla, 'h', 2000, 5.0)
    link.load()
    link.configure(False, 0.05)
    assert link.world.settings.fixed_delta_seconds is None
    assert link.tick() > 0.0


def test_no_client_says_how_to_get_one():
    try:
        import carla  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError, match='docs/carla.md'):
            load_carla()
    else:
        assert load_carla() is not None
