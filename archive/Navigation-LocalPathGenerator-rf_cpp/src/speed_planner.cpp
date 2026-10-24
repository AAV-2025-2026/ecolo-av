#include "local_path_generator_cpp/speed_planner.hpp"

#include <algorithm>
#include <cmath>
#include <set>
#include <string>
#include <vector>

#include "local_path_generator_cpp/path_service.hpp"

namespace local_path_generator_cpp
{

namespace
{

bool needs_decel(const std::string & maneuver_type)
{
  static const std::vector<std::string> turn_types = {
    "turn", "roundabout", "merge", "fork", "end of road"
  };
  for (const auto & key : turn_types) {
    if (maneuver_type.find(key) != std::string::npos) {
      return true;
    }
  }
  return false;
}

}  // namespace

void compute_reference_speeds(OSRMGlobalRoute & global_route, double decel_dist, double v_turn)
{
  for (auto & route : global_route.routes) {
    for (auto & leg : route.legs) {
      for (auto & step : leg.steps) {
        const int n = static_cast<int>(step.geometry.size());
        if (n == 0) {
          step.reference_speeds.clear();
          continue;
        }

        const double MAX_SPEED = 30.0 / 3.6;  // 30 km/h

		const double base_speed =
		  step.duration > 0.0 ? std::min(step.distance / step.duration, MAX_SPEED) : 0.0;
        step.reference_speeds.assign(n, base_speed);

        if (!needs_decel(step.maneuver_type)) {
          continue;
        }

        if (n < 2) {
          continue;
        }

        const double ref_lon = step.geometry.front().lon;
        const double ref_lat = step.geometry.front().lat;

        std::vector<PointXY> xy;
        xy.reserve(step.geometry.size());
        for (const auto & p : step.geometry) {
          xy.push_back(to_xy(p.lon, p.lat, ref_lon, ref_lat));
        }

        double dist_from_end = 0.0;
        int start_idx = n - 1;
        for (int i = n - 2; i >= 0; --i) {
          const double dx = xy[i + 1].x - xy[i].x;
          const double dy = xy[i + 1].y - xy[i].y;
          dist_from_end += std::hypot(dx, dy);
          start_idx = i;
          if (dist_from_end >= decel_dist) {
            break;
          }
        }

        const int ramp_len = (n - 1) - start_idx;
        if (ramp_len <= 0) {
          step.reference_speeds[n - 1] = std::min(step.reference_speeds[n - 1], v_turn);
        } else {
          for (int k = start_idx; k < n; ++k) {
            const double alpha = static_cast<double>(k - start_idx) / static_cast<double>(ramp_len);
            const double v = (1.0 - alpha) * base_speed + alpha * v_turn;
            step.reference_speeds[k] = std::min(step.reference_speeds[k], v);
          }
        }
      }
    }
  }
}

double evaluate_target_speed(const OSRMStep & step, int segment_index, double t)
{
  const auto & v = step.reference_speeds;
  const int geom_n = static_cast<int>(step.geometry.size());
  const int v_n = static_cast<int>(v.size());
  const int seg = segment_index;

  if (v_n == 0) {
    return 0.0;
  }

  if (v_n == geom_n) {
    if (seg >= v_n - 1) {
      return v.back();
    }
    const double v0 = v[seg];
    const double v1 = v[seg + 1];
    return v0 * (1.0 - t) + v1 * t;
  }

  if (v_n == geom_n - 1) {
    const int idx = std::min(seg, v_n - 1);
    return v[idx];
  }

  return v.back();
}

}  // namespace local_path_generator_cpp
