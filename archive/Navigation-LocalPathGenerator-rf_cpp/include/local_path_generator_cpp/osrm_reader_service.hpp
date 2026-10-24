#pragma once

#include <string>

#include "local_path_generator_cpp/osrm_models.hpp"

namespace local_path_generator_cpp
{

OSRMGlobalRoute load_osrm_route(const std::string & json_data);

}  // namespace local_path_generator_cpp
