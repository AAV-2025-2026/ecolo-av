#include <algorithm>
#include <cmath>
#include <sstream>
#include <string>
#include <vector>

#include "local_path_generator_cpp/osrm_reader_service.hpp"
#include "local_path_generator_cpp/path_service.hpp"

namespace local_path_generator_cpp
{

struct TurnEvalResult
{
  bool found = false;
  int segment_index = -1;
  int target_geom_index = -1;
  double target_heading_deg = 0.0;
  double turn_deg = 0.0;
};

namespace
{

double normalize_deg(double deg)
{
  while (deg > 180.0) {
    deg -= 360.0;
  }
  while (deg < -180.0) {
    deg += 360.0;
  }
  return deg;
}

double rad2deg(double rad)
{
  return rad * 180.0 / M_PI;
}

double compute_target_heading_deg(
  const PointLL & current_coordinate,
  const PointLL & target_coordinate)
{
  const auto target_xy = to_xy(
    target_coordinate.lon,
    target_coordinate.lat,
    current_coordinate.lon,
    current_coordinate.lat);

  return rad2deg(std::atan2(target_xy.y, target_xy.x));
}

}  // namespace

bool parse_turn_request(
  const std::string & raw,
  PointLL & coordinate,
  int & leg_index,
  double & current_heading_deg)
{
  std::stringstream ss(raw);
  std::string item;
  std::vector<std::string> parts;

  while (std::getline(ss, item, ',')) {
    parts.push_back(item);
  }

  if (parts.size() != 4) {
    return false;
  }

  try {
    coordinate.lon = std::stod(parts[0]);
    coordinate.lat = std::stod(parts[1]);
    leg_index = std::stoi(parts[2]);
    current_heading_deg = std::stod(parts[3]);
  } catch (...) {
    return false;
  }

  return true;
}

TurnEvalResult evaluate_turn_angle(
  const PointLL & current_coordinate,
  const OSRMStep & step,
  int segment_index,
  double current_heading_deg,
  int lookahead_points)
{
  TurnEvalResult out;

  if (step.geometry.size() < 2) {
    return out;
  }

  const int geom_size = static_cast<int>(step.geometry.size());

  int target_index = std::min(segment_index + lookahead_points, geom_size - 1);
  if (target_index <= segment_index) {
    target_index = std::min(segment_index + 1, geom_size - 1);
  }

  if (target_index < 0 || target_index >= geom_size) {
    return out;
  }

  const PointLL & target_coordinate = step.geometry[target_index];
  const double target_heading_deg =
    compute_target_heading_deg(current_coordinate, target_coordinate);
  const double turn_deg =
    normalize_deg(target_heading_deg - current_heading_deg);

  out.found = true;
  out.segment_index = segment_index;
  out.target_geom_index = target_index;
  out.target_heading_deg = target_heading_deg;
  out.turn_deg = turn_deg;

  return out;
}

}  // namespace local_path_generator_cpp