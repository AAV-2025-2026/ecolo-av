import math
from typing import Tuple, List, Optional, Dict
from local_path_generator.app.model.osrm.osrm_step_model import OSRMStep


_xy_cache: Dict[Tuple[float, float], Dict[int, List[Tuple[float, float]]]] = {}

def _to_xy(lon: float, lat: float, ref_lon: float, ref_lat: float) -> Tuple[float, float]:
    R = 6371000.0
    dlon = math.radians(lon - ref_lon)
    dlat = math.radians(lat - ref_lat)
    x = R * dlon * math.cos(math.radians(ref_lat))
    y = R * dlat
    return x, y

def _distance_to_segment(point, A, B):
    px, py = point
    ax, ay = A
    bx, by = B

    ABx, ABy = (bx - ax), (by - ay)
    APx, APy = (px - ax), (py - ay)
    AB_len2 = ABx * ABx + ABy * ABy

    if AB_len2 == 0:
        return math.dist((px, py), (ax, ay)), (ax, ay), 0.0

    t = (APx * ABx + APy * ABy) / AB_len2
    t = max(0, min(1, t))

    cx = ax + t * ABx
    cy = ay + t * ABy

    return math.dist((px, py), (cx, cy)), (cx, cy), t

def _get_search_range(current_index: int, total_steps: int) -> range:
    start = max(0, current_index - 3)
    end = min(total_steps, current_index + 6)
    return range(start, end)

def _get_xy_for_step(step: OSRMStep, coordinate: Tuple[float, float]) -> List[Tuple[float, float]]:
    ref_lon, ref_lat = coordinate
    cache_key = (ref_lon, ref_lat)

    if cache_key not in _xy_cache:
        _xy_cache[cache_key] = {}

    cache = _xy_cache[cache_key]

    if step.step_index not in cache:
        cache[step.step_index] = [
            _to_xy(lon, lat, ref_lon, ref_lat) for lon, lat in step.geometry
        ]

    return cache[step.step_index]

def get_current_step_by_coordinate(
        coordinate: Tuple[float, float],
        steps: List[OSRMStep],
        prev_step_index: Optional[int] = None,
        tolerance: float = 50.0
):
    best_step = None
    best_dist = float("inf")
    best_segment = None
    best_point = None
    best_t = 0.0

    search_range = (
        _get_search_range(prev_step_index, len(steps))
        if prev_step_index is not None
        else range(len(steps))
    )

    for i in search_range:
        xy = _get_xy_for_step(steps[i], coordinate)
        for j in range(len(xy) - 1):
            d, (cx, cy), t = _distance_to_segment((0, 0), xy[j], xy[j + 1])
            if d < best_dist:
                best_dist = d
                best_step = i
                best_segment = j
                best_point = (cx, cy)
                best_t = t

    if best_step is None or best_dist > tolerance:
        for i in range(len(steps)):
            xy = _get_xy_for_step(steps[i], coordinate)
            for j in range(len(xy) - 1):
                d, (cx, cy), t = _distance_to_segment((0, 0), xy[j], xy[j + 1])
                if d < best_dist:
                    best_dist = d
                    best_step = i
                    best_segment = j
                    best_point = (cx, cy)
                    best_t = t

    if best_step is None or best_dist > tolerance:
        return None

    return {
        "step_index": best_step,
        "segment_index": best_segment,
        "closest_point": best_point,
        "distance": best_dist,
        "t": best_t
    }