import math

from local_path_generator.app.service.path_service import _to_xy

TURN_TYPES = {"turn", "roundabout", "merge", "fork", "end of road"}

def compute_reference_speeds(global_route, decel_dist=15.0, v_turn=3.0):
    for route in global_route.routes:
        for leg in route.legs:
            for step in leg.steps:
                n = len(step.geometry)
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

                ref_lon, ref_lat = step.geometry[0]
                xy = [
                    _to_xy(lon, lat, ref_lon, ref_lat)
                    for lon, lat in step.geometry
                ]

                n = len(step.geometry)
                if n < 2:
                    continue

                dist_from_end = 0.0
                start_idx = n - 1
                for i in range(n - 2, -1, -1):
                    x1, y1 = xy[i]
                    x2, y2 = xy[i + 1]
                    ds = math.hypot(x2 - x1, y2 - y1)
                    dist_from_end += ds
                    start_idx = i
                    if dist_from_end >= decel_dist:
                        break

                # 2) 对 start_idx..n-1 做线性插值：从 base_speed 过渡到 v_turn
                ramp_len = (n - 1) - start_idx
                if ramp_len <= 0:
                    step.reference_speeds[n - 1] = min(step.reference_speeds[n - 1], v_turn)
                else:
                    for k in range(start_idx, n):
                        alpha = (k - start_idx) / ramp_len  # 0 -> 1
                        v = (1.0 - alpha) * base_speed + alpha * v_turn
                        # 更保守：取 min，避免加速
                        step.reference_speeds[k] = min(step.reference_speeds[k], v)