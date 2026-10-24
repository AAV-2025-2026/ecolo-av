#pragma once

#include <optional>
#include <vector>

#include "local_path_generator_cpp/osrm_models.hpp"

namespace local_path_generator_cpp
{

PointXY to_xy(double lon, double lat, double ref_lon, double ref_lat);

StepMatchResult get_current_step_by_coordinate(
  const PointLL & coordinate,
  const std::vector<OSRMStep> & steps,
  std::optional<int> prev_step_index = std::nullopt,
  double tolerance = 50.0);

}  // namespace local_path_generator_cpp
