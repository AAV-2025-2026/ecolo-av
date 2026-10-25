#pragma once

#include <cmath>
#include <string>
#include <vector>

#include "local_path_generator_cpp/osrm_models.hpp"

namespace local_path_generator_cpp
{

inline std::vector<PointLL> decode_polyline(const std::string & encoded, int precision = 5)
{
  std::vector<PointLL> points;
  if (encoded.empty()) {
    return points;
  }

  const double factor = std::pow(10.0, precision);
  std::size_t index = 0;
  long lat = 0;
  long lon = 0;

  while (index < encoded.size()) {
    int result = 0;
    int shift = 0;
    int b = 0;

    do {
      if (index >= encoded.size()) {
        return points;
      }
      b = static_cast<int>(encoded[index++]) - 63;
      result |= (b & 0x1f) << shift;
      shift += 5;
    } while (b >= 0x20);

    const long dlat = (result & 1) ? ~(result >> 1) : (result >> 1);
    lat += dlat;

    result = 0;
    shift = 0;
    do {
      if (index >= encoded.size()) {
        return points;
      }
      b = static_cast<int>(encoded[index++]) - 63;
      result |= (b & 0x1f) << shift;
      shift += 5;
    } while (b >= 0x20);

    const long dlon = (result & 1) ? ~(result >> 1) : (result >> 1);
    lon += dlon;

    PointLL p;
    p.lat = static_cast<double>(lat) / factor;
    p.lon = static_cast<double>(lon) / factor;
    points.push_back(p);
  }

  return points;
}

}  // namespace local_path_generator_cpp
