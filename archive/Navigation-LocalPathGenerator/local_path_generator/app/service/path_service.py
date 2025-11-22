import math
from typing import Tuple, List, Optional, Dict
from local_path_generator.app.model.osrm.osrm_step_model import OSRMStep

class PathService:
    _xy_cache: Dict[Tuple[float, float], Dict[int, List[Tuple[float, float]]]] = {}

    @staticmethod
    def _to_xy(lon: float, lat: float, ref_lon: float, ref_lat: float) -> Tuple[float, float]:
        R = 6371000.0
        dlon = math.radians(lon - ref_lon)
        dlat = math.radians(lat - ref_lat)
        x = R * dlon * math.cos(math.radians(ref_lat))
        y = R * dlat
        return x, y

    @staticmethod
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

    @staticmethod
    def _get_search_range(current_index: int, total_steps: int) -> range:
        start = max(0, current_index - 3)
        end = min(total_steps, current_index + 6)
        return range(start, end)

    @staticmethod
    def _get_xy_for_step(step: OSRMStep, gps: Tuple[float, float]) -> List[Tuple[float, float]]:
        ref_lon, ref_lat = gps
        cache_key = (ref_lon, ref_lat)

        if cache_key not in PathService._xy_cache:
            PathService._xy_cache[cache_key] = {}

        cache = PathService._xy_cache[cache_key]

        if step.step_index not in cache:
            cache[step.step_index] = [
                PathService._to_xy(lon, lat, ref_lon, ref_lat) for lon, lat in step.geometry
            ]

        return cache[step.step_index]

    @staticmethod
    def get_current_step_by_gps(
            gps: Tuple[float, float],
            steps: List[OSRMStep],
            prev_step_index: Optional[int] = None,
            tolerance: float = 50.0
    ):
        best_step = None
        best_dist = float("inf")
        best_segment = None
        best_point = None

        search_range = (
            PathService._get_search_range(prev_step_index, len(steps))
            if prev_step_index is not None
            else range(len(steps))
        )

        for i in search_range:
            xy = PathService._get_xy_for_step(steps[i], gps)
            for j in range(len(xy) - 1):
                d, (cx, cy), _ = PathService._distance_to_segment((0, 0), xy[j], xy[j + 1])
                if d < best_dist:
                    best_dist = d
                    best_step = i
                    best_segment = j
                    best_point = (cx, cy)

        if best_step is None or best_dist > tolerance:
            for i in range(len(steps)):
                xy = PathService._get_xy_for_step(steps[i], gps)
                for j in range(len(xy) - 1):
                    d, (cx, cy), _ = PathService._distance_to_segment((0, 0), xy[j], xy[j + 1])
                    if d < best_dist:
                        best_dist = d
                        best_step = i
                        best_segment = j
                        best_point = (cx, cy)

        if best_step is None or best_dist > tolerance:
            return None

        return {
            "step_index": best_step,
            "segment_index": best_segment,
            "closest_point": best_point,
            "distance": best_dist
        }

'''
A note to myself(Ruangfafa), don't care about this if you see it OvO

1. tolerance 动态根据速度调整
*高速时位置误差更大，应加大 tolerance。

2. 如果 step 找到但距离 > 20m，建议判定偏离路线（偏航）

3. 如果车辆实际跑得比地图快，可以提前切 step 或者至少避免 GPS 把你拉回上一个 step！！！
'''