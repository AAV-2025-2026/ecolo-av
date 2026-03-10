#include "local_path_generator_cpp/osrm_reader_service.hpp"

#include <algorithm>
#include <cctype>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

#include "local_path_generator_cpp/polyline.hpp"
#include "local_path_generator_cpp/speed_planner.hpp"

namespace local_path_generator_cpp
{

namespace
{

using json = nlohmann::json;

std::string normalize_or_unknown(const json & obj, const char * key)
{
  if (!obj.contains(key) || obj[key].is_null()) {
    return "UNKNOWN";
  }
  return obj[key].get<std::string>();
}

int clamp_bearing(int value)
{
  if (value < 0) {
    return 0;
  }
  if (value > 359) {
    return 359;
  }
  return value;
}

OSRMLane parse_lane(const json & j)
{
  OSRMLane lane;
  lane.valid = j.value("valid", false);
  if (j.contains("indications") && j["indications"].is_array()) {
    for (const auto & ind : j["indications"]) {
      lane.indications.push_back(ind.is_string() ? ind.get<std::string>() : "UNKNOWN");
    }
  }
  return lane;
}

OSRMIntersection parse_intersection(const json & j)
{
  OSRMIntersection intersection;
  if (j.contains("location") && j["location"].is_array() && j["location"].size() >= 2) {
    intersection.location.lon = j["location"][0].get<double>();
    intersection.location.lat = j["location"][1].get<double>();
  }

  if (j.contains("bearings") && j["bearings"].is_array()) {
    for (const auto & b : j["bearings"]) {
      intersection.bearings.push_back(b.get<int>());
    }
  }

  if (j.contains("entry") && j["entry"].is_array()) {
    for (const auto & e : j["entry"]) {
      intersection.entry.push_back(e.get<bool>());
    }
  }

  if (j.contains("classes") && !j["classes"].is_null()) {
    if (j["classes"].is_string()) {
      intersection.classes = j["classes"].get<std::string>();
    } else if (j["classes"].is_array()) {
      std::string merged;
      for (std::size_t i = 0; i < j["classes"].size(); ++i) {
        if (j["classes"][i].is_string()) {
          if (!merged.empty()) {
            merged += ",";
          }
          merged += j["classes"][i].get<std::string>();
        }
      }
      intersection.classes = merged;
    }
  }
  intersection.p_in = j.value("in", 0);
  intersection.p_out = j.value("out", 0);

  if (j.contains("lanes") && j["lanes"].is_array()) {
    for (const auto & lane : j["lanes"]) {
      intersection.lanes.push_back(parse_lane(lane));
    }
  }

  return intersection;
}

std::optional<OSRMManeuver> parse_maneuver(const json & j)
{
  if (j.is_null() || !j.is_object()) {
    return std::nullopt;
  }

  OSRMManeuver maneuver;
  if (j.contains("location") && j["location"].is_array() && j["location"].size() >= 2) {
    maneuver.location.lon = j["location"][0].get<double>();
    maneuver.location.lat = j["location"][1].get<double>();
  }

  maneuver.bearing_before = clamp_bearing(j.value("bearing_before", 0));
  maneuver.bearing_after = clamp_bearing(j.value("bearing_after", 0));
  maneuver.type = j.value("type", std::string{"UNKNOWN"});
  maneuver.modifier = j.value("modifier", std::string{"UNKNOWN"});
  maneuver.exit = j.value("exit", 0);
  return maneuver;
}

OSRMStep parse_step(const json & j)
{
  OSRMStep step;
  step.distance = j.value("distance", 0.0);
  step.duration = j.value("duration", 0.0);
  step.weight = j.value("weight", 0.0);
  step.name = j.value("name", std::string{});
  step.ref = j.value("ref", std::string{});
  step.pronunciation = j.value("pronunciation", std::string{});
  step.destinations = j.value("destinations", std::string{});
  if (j.contains("exits")) {
    if (j["exits"].is_string()) {
      step.exits = j["exits"].get<std::string>();
    } else if (j["exits"].is_number_integer()) {
      step.exits = std::to_string(j["exits"].get<int>());
    }
  }
  step.mode = normalize_or_unknown(j, "mode");
  step.maneuver = parse_maneuver(j.contains("maneuver") ? j["maneuver"] : json{});
  if (step.maneuver.has_value()) {
    step.maneuver_type = step.maneuver->type;
    step.maneuver_modifier = step.maneuver->modifier;
  }
  step.rotary_name = j.value("rotary_name", std::string{});
  step.rotary_pronunciation = j.value("rotary_pronunciation", std::string{});
  step.driving_side = normalize_or_unknown(j, "driving_side");

  if (j.contains("intersections") && j["intersections"].is_array()) {
    for (const auto & intersection : j["intersections"]) {
      step.intersections.push_back(parse_intersection(intersection));
    }
  }

  if (j.contains("geometry") && j["geometry"].is_string()) {
    step.geometry = decode_polyline(j["geometry"].get<std::string>());
  }

  step.reference_speeds.assign(step.geometry.size(), 0.0);
  return step;
}

OSRMLeg parse_leg(const json & j)
{
  OSRMLeg leg;
  leg.distance = j.value("distance", 0.0);
  leg.duration = j.value("duration", 0.0);
  leg.weight = j.value("weight", 0.0);
  leg.summary = j.value("summary", std::string{});

  if (j.contains("steps") && j["steps"].is_array()) {
    for (const auto & step : j["steps"]) {
      leg.steps.push_back(parse_step(step));
    }
  }
  return leg;
}

OSRMRoute parse_route(const json & j)
{
  OSRMRoute route;
  route.distance = j.value("distance", 0.0);
  route.duration = j.value("duration", 0.0);
  route.geometry = j.value("geometry", std::string{});
  route.weight = j.value("weight", 0.0);
  route.weight_name = normalize_or_unknown(j, "weight_name");

  if (j.contains("legs") && j["legs"].is_array()) {
    for (const auto & leg : j["legs"]) {
      route.legs.push_back(parse_leg(leg));
    }
  }

  int flat_index = 0;
  int total = 0;
  for (const auto & leg : route.legs) {
    total += static_cast<int>(leg.steps.size());
  }

  for (auto & leg : route.legs) {
    for (auto & step : leg.steps) {
      step.step_index = flat_index;
      step.is_last_step = (flat_index == total - 1);
      ++flat_index;
    }
  }

  return route;
}

OSRMWaypoint parse_waypoint(const json & j)
{
  OSRMWaypoint waypoint;
  waypoint.name = j.value("name", std::string{});
  waypoint.distance = j.value("distance", 0.0);
  waypoint.hint = j.value("hint", std::string{});
  if (j.contains("location") && j["location"].is_array() && j["location"].size() >= 2) {
    waypoint.location.lon = j["location"][0].get<double>();
    waypoint.location.lat = j["location"][1].get<double>();
  }
  return waypoint;
}

}  // namespace

OSRMGlobalRoute load_osrm_route(const std::string & json_data)
{
  const auto root = json::parse(json_data);

  OSRMGlobalRoute global_route;
  global_route.code = root.value("code", std::string{"UNKNOWN"});

  if (root.contains("routes") && root["routes"].is_array()) {
    for (const auto & route : root["routes"]) {
      global_route.routes.push_back(parse_route(route));
    }
  }

  if (root.contains("waypoints") && root["waypoints"].is_array()) {
    for (const auto & waypoint : root["waypoints"]) {
      global_route.waypoints.push_back(parse_waypoint(waypoint));
    }
  }

  compute_reference_speeds(global_route);
  return global_route;
}

}  // namespace local_path_generator_cpp
