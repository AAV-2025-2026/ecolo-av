"""georef.py: Carleton as a CARLA map, lined up with our datum."""

import os

from aav_carla import frames, georef
import pytest

NAVSAT = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'localization',
                      'aav_localization', 'config', 'navsat.yaml')
DATUM = (45.3860, -75.6960)


def test_the_datum_comes_from_navsat_yaml():
    with open(NAVSAT) as f:
        lat, lon, yaw = georef.datum_from_navsat(f.read())
    assert 45.3 < lat < 45.5 and -75.8 < lon < -75.6       # Carleton
    assert yaw == 0.0                                      # x stays east (navsat.yaml)


@pytest.mark.parametrize('text', ['no datum here', 'datum: [1.0, 2.0]', 'datum: [99, 0, 0]'])
def test_a_bad_datum_is_refused(text):
    with pytest.raises(ValueError):
        georef.datum_from_navsat(text)


def test_the_projection_is_centred_on_the_datum():
    p = georef.proj_string(*DATUM)
    assert '+proj=tmerc' in p and '+lat_0=45.3860000' in p and '+lon_0=-75.6960000' in p
    assert georef.georeference(f'<geoReference><![CDATA[{p}]]></geoReference>') == {
        'proj': p, 'lat_0': 45.386, 'lon_0': -75.696}


def test_the_box_holds_the_datum_and_is_the_right_size():
    w, s, e, n = georef.bbox(*DATUM)
    assert w < DATUM[1] < e and s < DATUM[0] < n
    west, south, _ = frames.geodetic_to_enu(*DATUM, 0.0, s, w, 0.0)
    east, north, _ = frames.geodetic_to_enu(*DATUM, 0.0, n, e, 0.0)
    assert (west, south, east, north) == pytest.approx((-900, -900, 700, 700), abs=1.0)
    with pytest.raises(ValueError):
        georef.bbox(*DATUM, around=(-1, 0, 0, 0))


def test_overpass_urls():
    box = (-75.7, 45.38, -75.69, 45.39)
    assert georef.overpass_url(box).endswith('/map?bbox=-75.7,45.38,-75.69,45.39')
    roads = georef.overpass_url(box, roads_only=True)
    assert 'highway' in roads and '(45.38,-75.7,45.39,-75.69)' in roads
    assert ' ' not in roads and '"' not in roads


def test_the_osm_settings_keep_the_origin_on_the_datum():
    s = georef.osm_settings(*DATUM)
    assert s['proj_string'] == georef.proj_string(*DATUM)
    assert s['center_map'] is False and s['use_offsets'] is False


def test_a_town_without_a_georeference():
    assert georef.georeference('<OpenDRIVE><header/></OpenDRIVE>') == {}
    plain = '<geoReference>+proj=tmerc +lat_0=4.9e1 +lon_0=8</geoReference>'
    assert georef.georeference(plain)['lat_0'] == 49.0


@pytest.mark.parametrize('text, want', [('', None), ('  ', None), ('3', 3),
                                        ('10, -2.5, 1.57', (10.0, -2.5, 1.57))])
def test_parse_spawn(text, want):
    assert georef.parse_spawn(text) == want


@pytest.mark.parametrize('text', ['-1', 'north', '1,2', '1,2,x', 'nan,0,0'])
def test_parse_spawn_refuses(text):
    with pytest.raises(ValueError):
        georef.parse_spawn(text)


def test_the_helper_prints_the_box(capsys):
    georef.main([NAVSAT])
    lat, lon, w, s, e, n = (float(v) for v in capsys.readouterr().out.split())
    assert w < lon < e and s < lat < n
