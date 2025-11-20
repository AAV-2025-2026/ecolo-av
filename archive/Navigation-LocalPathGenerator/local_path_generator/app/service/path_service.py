import math
from typing import Tuple, List
from local_path_generator.app.model.osrm.osrm_step_model import OSRMStep

class PathService:

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
            return math.dist((px, py), (ax, ay))

        t = (APx * ABx + APy * ABy) / AB_len2
        t = max(0, min(1, t))

        cx = ax + t * ABx
        cy = ay + t * ABy

        return math.dist((px, py), (cx, cy))

    @staticmethod
    def get_current_step(gps: Tuple[float, float], steps: List[OSRMStep], tolerance: float = 50.0) -> OSRMStep:
        closest_step = None
        min_dist = float("inf")

        ref_lon, ref_lat = gps

        for step in steps:
            geo = step.geometry

            xy = [PathService._to_xy(lon, lat, ref_lon, ref_lat) for lon, lat in geo]

            for i in range(len(xy) - 1):
                d = PathService._distance_to_segment((0, 0), xy[i], xy[i + 1])
                if d < min_dist:
                    min_dist = d
                    closest_step = step

        return closest_step if min_dist <= tolerance else None
