#pragma once

#include "local_path_generator_cpp/osrm_models.hpp"

namespace local_path_generator_cpp
{

void compute_reference_speeds(OSRMGlobalRoute & global_route, double decel_dist = 15.0, double v_turn = 3.0);

double evaluate_target_speed(const OSRMStep & step, int segment_index, double t);

}  // namespace local_path_generator_cpp
