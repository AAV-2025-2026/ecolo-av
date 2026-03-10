#include "local_path_generator_cpp/path_service.hpp"

#include <algorithm>
#include <cmath>
#include <limits>

namespace local_path_generator_cpp
{

namespace
{

double point_distance(const PointXY & a, const PointXY & b)
{
  const double dx = a.x - b.x;
  const double dy = a.y - b.y;
  return std::sqrt(dx * dx + dy * dy);
}

StepMatchResult distance_to_segment(const PointXY & point, const PointXY & a, const PointXY & b)
{
  StepMatchResult result;
  const double abx = b.x - a.x;
  const double aby = b.y - a.y;
  const double apx = point.x - a.x;
  const double apy = point.y - a.y;
  const double ab_len2 = abx * abx + aby * aby;

  PointXY closest = a;
  double t = 0.0;

  if (ab_len2 > 0.0) {
    t = (apx * abx + apy * aby) / ab_len2;
    t = std::max(0.0, std::min(1.0, t));
    closest.x = a.x + t * abx;
    closest.y = a.y + t * aby;
  }

  result.found = true;
  result.closest_point = closest;
  result.distance = point_distance(point, closest);
  result.t = t;
  return result;
}

std::pair<int, int> get_search_window(int current_index, int total_steps)
{
  const int start = std::max(0, current_index - 3);
  const int end = std::min(total_steps, current_index + 6);
  return {start, end};
}

}  // namespace

PointXY to_xy(double lon, double lat, double ref_lon, double ref_lat)
{
  const double r = 6371000.0;
  const double dlon = (lon - ref_lon) * M_PI / 180.0;
  const double dlat = (lat - ref_lat) * M_PI / 180.0;

  PointXY p;
  p.x = r * dlon * std::cos(ref_lat * M_PI / 180.0);
  p.y = r * dlat;
  return p;
}

StepMatchResult get_current_step_by_coordinate(
  const PointLL & coordinate,
  const std::vector<OSRMStep> & steps,
  std::optional<int> prev_step_index,
  double tolerance)
{
  StepMatchResult best;
  best.distance = std::numeric_limits<double>::infinity();

  auto search_range = [&](int start, int end) {
    for (int i = start; i < end; ++i) {
      const auto & step = steps[i];
      if (step.geometry.size() < 2) {
        continue;
      }

      std::vector<PointXY> xy;
      xy.reserve(step.geometry.size());
      for (const auto & p : step.geometry) {
        xy.push_back(to_xy(p.lon, p.lat, coordinate.lon, coordinate.lat));
      }

      for (int j = 0; j < static_cast<int>(xy.size()) - 1; ++j) {
        const auto result = distance_to_segment(PointXY{0.0, 0.0}, xy[j], xy[j + 1]);
        if (result.distance < best.distance) {
          best = result;
          best.step_index = i;
          best.segment_index = j;
        }
      }
    }
  };

  if (prev_step_index.has_value()) {
    const auto [start, end] = get_search_window(*prev_step_index, static_cast<int>(steps.size()));
    search_range(start, end);
  } else {
    search_range(0, static_cast<int>(steps.size()));
  }

  if (!best.found || best.distance > tolerance) {
    best = StepMatchResult{};
    best.distance = std::numeric_limits<double>::infinity();
    search_range(0, static_cast<int>(steps.size()));
  }

  if (!best.found || best.distance > tolerance) {
    return StepMatchResult{};
  }

  best.found = true;
  return best;
}

}  // namespace local_path_generator_cpp
