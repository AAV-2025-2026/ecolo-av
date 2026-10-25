"""
Carleton as a CARLA map, lined up with our datum. No ROS and no `carla` imports.

The datum (aav_localization navsat.yaml) is map (0, 0): x east, y north. Nav2's maps, the
GPS goals and the map window all use it. For CARLA's GPS to agree, a map of Carleton must
put its world origin on the datum too. Two ways to build one (docs/carla.md):

  1. OpenStreetMap -> OpenDRIVE with CARLA's own converter (carla.Osm2Odr, in the Python
     client), then client.generate_opendrive_world(): roads only, no buildings, minutes.
     carla_adapter does it with osm:=<file>; osm_settings() below is the recipe.
  2. CARLA's Digital Twin Tool (an Unreal editor plug-in): roads AND buildings, from the
     same .osm, but a source build of CARLA and hours. Give it the same projection.

Either way the projection is a transverse Mercator centred on the datum, so the datum
projects to (0, 0) and the map's x points east: proj_string().

tools/get_carla_osm.sh downloads the .osm, for bbox() around the datum.
"""

from __future__ import annotations

import math
import re

from aav_carla.frames import enu_to_geodetic

# Carleton's campus and the streets round it, from the datum (m): west, south, east, north.
# About 1.6 x 1.6 km: the campus between Bronson Avenue, the canal and the Rideau River.
CARLETON = (900.0, 900.0, 700.0, 700.0)


def proj_string(lat0: float, lon0: float) -> str:
    """Return a PROJ transverse Mercator centred on (lat0, lon0)."""
    return (f'+proj=tmerc +lat_0={lat0:.7f} +lon_0={lon0:.7f} +k=1 +x_0=0 +y_0=0 '
            '+datum=WGS84 +units=m +no_defs')


def bbox(lat0: float, lon0: float, around=CARLETON) -> tuple[float, float, float, float]:
    """
    Return the box round the datum, as OpenStreetMap wants it.

    The box round the datum, as OpenStreetMap wants it: (west lon, south lat, east lon,
    north lat), degrees. around: metres west, south, east and north of the datum.
    """
    west, south, east, north = (float(v) for v in around)
    if min(west, south, east, north) < 0.0:
        raise ValueError(f'the box goes the wrong way round the datum: {around}')
    s_lat, w_lon, _ = enu_to_geodetic(lat0, lon0, 0.0, -west, -south, 0.0)
    n_lat, e_lon, _ = enu_to_geodetic(lat0, lon0, 0.0, east, north, 0.0)
    return (round(w_lon, 5), round(s_lat, 5), round(e_lon, 5), round(n_lat, 5))


def overpass_url(box, roads_only: bool = False,
                 server: str = 'https://overpass-api.de/api') -> str:
    """
    Return where to download the box's OpenStreetMap data.

    Where to download the box's OpenStreetMap data. The whole map (roads and buildings,
    for the Digital Twin Tool), or the roads alone (all Osm2Odr reads; much smaller).
    """
    w, s, e, n = box
    if not roads_only:
        return f'{server}/map?bbox={w},{s},{e},{n}'
    # Overpass wants south, west, north, east.
    query = f'[out:xml][timeout:90];(way["highway"]({s},{w},{n},{e});>;);out body;'
    return f'{server}/interpreter?data=' + query.replace(' ', '%20').replace('"', '%22')


def osm_settings(lat0: float, lon0: float, traffic_lights: bool = True) -> dict:
    """
    Return carla.Osm2OdrSettings' fields that keep the map's origin on the datum.

    carla.Osm2OdrSettings' fields, so the OpenDRIVE map's origin is the datum: our
    projection, and no recentring or offsets (they would move the origin off it).
    """
    return {'proj_string': proj_string(lat0, lon0),
            'center_map': False,
            'use_offsets': False,
            'offset_x': 0.0,
            'offset_y': 0.0,
            'default_lane_width': 3.5,
            'generate_traffic_lights': traffic_lights,
            'all_junctions_with_traffic_lights': False}


# carla.OpendriveGenerationParameters, as CARLA's own config.py --osm-path uses them.
OPENDRIVE_PARAMETERS = {'vertex_distance': 2.0,
                        'max_road_length': 500.0,
                        'wall_height': 0.0,
                        'additional_width': 0.6,
                        'smooth_junctions': True,
                        'enable_mesh_visibility': True}


def georeference(xodr: str) -> dict:
    """
    Return the latitude and longitude of an OpenDRIVE map's origin.

    The latitude and longitude of an OpenDRIVE map's origin, from its header's
    <geoReference> (a PROJ string): {'lat_0': ..., 'lon_0': ..., 'proj': ...}. Empty when
    the map has none, as most of CARLA's towns.
    """
    m = re.search(r'<geoReference>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</geoReference>',
                  xodr, re.S)
    if not m:
        return {}
    proj = m.group(1).strip()
    out = {'proj': proj}
    for key in ('lat_0', 'lon_0'):
        v = re.search(rf'\+{key}=([-+0-9.eE]+)', proj)
        if v:
            out[key] = float(v.group(1))
    return out


def parse_spawn(text: str):
    """
    Read the spawn parameter.

    The spawn parameter: '' (CARLA's first spawn point), 'N' (spawn point N), or
    'x,y,yaw' (m, m, rad: our map frame, for a map lined up with the datum).
    Returns None, an int, or a tuple of three floats.
    """
    text = str(text).strip()
    if not text:
        return None
    parts = [p.strip() for p in text.split(',')]
    if len(parts) == 1:
        try:
            n = int(parts[0])
        except ValueError:
            raise ValueError(f"spawn:={text}: a spawn point's number, or x,y,yaw") from None
        if n < 0:
            raise ValueError(f'spawn:={text}: spawn points count from 0')
        return n
    if len(parts) == 3:
        try:
            x, y, yaw = (float(p) for p in parts)
        except ValueError:
            raise ValueError(f'spawn:={text}: x,y,yaw are numbers (m, m, rad)') from None
        if not all(math.isfinite(v) for v in (x, y, yaw)):
            raise ValueError(f'spawn:={text}: not a place')
        return (x, y, yaw)
    raise ValueError(f"spawn:={text}: a spawn point's number, or x,y,yaw")


def datum_from_navsat(text: str) -> tuple[float, float, float]:
    """Read navsat.yaml's datum: [lat, lon, yaw], as text."""
    m = re.search(r'^\s*datum:\s*\[([^\]]*)\]', text, re.M)
    if not m:
        raise ValueError('navsat.yaml has no datum: [lat, lon, yaw]')
    values = [float(v) for v in m.group(1).split(',')]
    if len(values) != 3:
        raise ValueError(f'the datum is [lat, lon, yaw], not {values}')
    lat, lon, yaw = values
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError(f'the datum is not on the earth: {values}')
    return (lat, lon, yaw)


def main(argv=None):
    """Print the box round navsat.yaml's datum (tools/get_carla_osm.sh's helper)."""
    import argparse
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument('navsat', help="aav_localization's config/navsat.yaml")
    p.add_argument('--around', default=','.join(str(v) for v in CARLETON),
                   help='m west,south,east,north of the datum')
    a = p.parse_args(argv)
    with open(a.navsat) as f:
        lat, lon, _ = datum_from_navsat(f.read())
    around = [float(v) for v in a.around.split(',')]
    if len(around) != 4:
        p.error('--around is west,south,east,north (m)')
    print(lat, lon, *bbox(lat, lon, around))


if __name__ == '__main__':
    main()
