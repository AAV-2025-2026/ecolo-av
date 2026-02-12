import math

from local_path_generator.app.service.path_service import _to_xy

TURN_TYPES = {"turn", "roundabout", "merge", "fork", "end of road"}

def compute_reference_speeds(global_route, decel_dist=15.0):
    for route in global_route.routes:
        for leg in route.legs:
            for step in leg.steps:
                n = max(0, len(step.geometry) - 1)
                if n == 0:
                    step.reference_speeds = []
                    continue

                base_speed = step.distance / step.duration if step.duration > 0 else 0.0
                step.reference_speeds = [base_speed] * n

                mt = getattr(step, "maneuver_type", None)
                mt_val = getattr(mt, "value", None)
                mt_str = (mt_val or str(mt or "")).lower()
                need_decel = any(t in mt_str for t in TURN_TYPES)

                if not need_decel:
                    continue

                v_turn = min(3.0, base_speed * 0.5)

                remain = 0.0
                for i in range(n - 1, -1, -1):
                    lon1, lat1 = step.geometry[i]
                    lon2, lat2 = step.geometry[i + 1]
                    dx, dy = _to_xy(lon2, lat2, lon1, lat1)
                    seg_len = math.hypot(dx, dy)
                    remain += seg_len
                    if remain > decel_dist:
                        break
                    ratio = max(0.0, min(1.0, remain / decel_dist))
                    step.reference_speeds[i] = v_turn + (base_speed - v_turn) * ratio