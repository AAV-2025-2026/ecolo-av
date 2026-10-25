"""
Body roll and the roof lidar: when does flat ground look like an obstacle? No ROS here.

lidar_scan (scan.py) keeps points between min_height (0.3 m) and max_height above the
road, measured in base_link: it takes the car's body as level. In a turn the body leans
outwards on its springs (docs/learn-state-space.md section 10). base_link leans with it,
so on the outside of the turn the flat road rises in base_link, about

    height = (how far out to the side) x tan(roll)

A VLP-16's lower beams reach the road 7-16 m out; tilted 2 degrees towards it, they reach
it closer, and those points can sit above min_height: an obstacle that isn't there.

    ground_hit()          one beam: where it meets the flat road, as base_link sees it
    worst_ground_height() every VLP-16 beam all the way round: the highest road point
                          within a range (the costmap's obstacle_max_range)
    max_safe_roll()       the most roll before that point reaches min_height

TODO 52e. Gazebo has no suspension, so it can't show this; these sums can.
"""

import math
from typing import Iterable, Optional, Sequence, Tuple

# The VLP-16's 16 lasers: -15 to +15 degrees, 2 degrees apart (its manual; velodyne's
# VLP16db.yaml calibration).
VLP16_ELEVATIONS = tuple(math.radians(e) for e in range(-15, 16, 2))


def ground_hit(roll: float, lidar: Sequence[float], elevation: float,
               azimuth: float) -> Optional[Tuple[float, float]]:
    """
    Return where one beam meets the flat road, as base_link sees it: (range, height), or None.

    roll: the body's lean (rad, REP-103: positive = the right side down), about the x axis
    through base_link, on the road; lidar: (x, y, z) of the lidar in base_link (m), level
    with the body; elevation, azimuth: the beam's direction in the lidar's frame (rad).
    range is measured flat from base_link, height above base_link: what scan.py compares
    with its heights. None: the beam never comes down to the road.
    """
    lx, ly, lz = lidar
    dx = math.cos(elevation) * math.cos(azimuth)
    dy = math.cos(elevation) * math.sin(azimuth)
    dz = math.sin(elevation)
    # A point (y, z) in base_link is sin(roll) y + cos(roll) z above the road (the body
    # turned by roll about x). The road is where that is 0.
    s, c = math.sin(roll), math.cos(roll)
    start = s * ly + c * lz          # the lidar's height above the road
    down = s * dy + c * dz           # how fast the beam climbs, in the road's frame
    if down >= 0.0:
        return None
    t = -start / down
    x, y, z = lx + t * dx, ly + t * dy, lz + t * dz
    return math.hypot(x, y), z


def worst_ground_height(roll: float, lidar: Sequence[float], max_range: float,
                        elevations: Iterable[float] = VLP16_ELEVATIONS,
                        step: float = math.radians(1.0)) -> Tuple[float, float, float, float]:
    """
    Return the highest road point within max_range: (height, range, elevation, azimuth).

    Every beam, all the way round, step apart. Height and range as ground_hit(); -inf
    when no beam reaches the road within max_range.
    """
    best = (-math.inf, math.nan, math.nan, math.nan)
    turns = int(round(2.0 * math.pi / step))
    for elevation in elevations:
        for i in range(turns):
            azimuth = i * step - math.pi
            hit = ground_hit(roll, lidar, elevation, azimuth)
            if hit is not None and hit[0] <= max_range and hit[1] > best[0]:
                best = (hit[1], hit[0], elevation, azimuth)
    return best


def max_safe_roll(lidar: Sequence[float], min_height: float, max_range: float,
                  elevations: Iterable[float] = VLP16_ELEVATIONS,
                  limit: float = math.radians(10.0)) -> float:
    """
    Return the most roll (rad) at which no road point within max_range reaches min_height.

    The same either way: a lean to the left shows the road rising on the left.
    """
    elevations = tuple(elevations)
    low, high = 0.0, limit
    for _ in range(30):
        mid = 0.5 * (low + high)
        if worst_ground_height(mid, lidar, max_range, elevations)[0] < min_height:
            low = mid
        else:
            high = mid
    return low
