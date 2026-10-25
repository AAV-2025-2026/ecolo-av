#pragma once

#include <optional>
#include <string>
#include <vector>

namespace local_path_generator_cpp
{

struct PointLL
{
  double lon = 0.0;
  double lat = 0.0;
};

struct PointXY
{
  double x = 0.0;
  double y = 0.0;
};

struct OSRMLane
{
  bool valid = false;
  std::vector<std::string> indications;
};

struct OSRMIntersection
{
  PointLL location;
  std::vector<int> bearings;
  std::string classes;
  std::vector<bool> entry;
  int p_in = 0;
  int p_out = 0;
  std::vector<OSRMLane> lanes;
};

struct OSRMManeuver
{
  PointLL location;
  int bearing_before = 0;
  int bearing_after = 0;
  std::string type = "UNKNOWN";
  std::string modifier = "UNKNOWN";
  int exit = 0;
};

struct OSRMStep
{
  double distance = 0.0;
  double duration = 0.0;
  std::vector<PointLL> geometry;
  std::vector<double> reference_speeds;

  double weight = 0.0;
  std::string name;
  std::string ref;
  std::string pronunciation;
  std::string destinations;
  std::string exits;
  std::string mode = "UNKNOWN";
  std::optional<OSRMManeuver> maneuver;
  std::vector<OSRMIntersection> intersections;
  std::string rotary_name;
  std::string rotary_pronunciation;
  std::string driving_side = "UNKNOWN";

  int step_index = -1;
  bool is_last_step = false;
  std::string maneuver_type = "UNKNOWN";
  std::string maneuver_modifier = "UNKNOWN";
};

struct OSRMLeg
{
  double distance = 0.0;
  double duration = 0.0;
  double weight = 0.0;
  std::string summary;
  std::vector<OSRMStep> steps;
};

struct OSRMRoute
{
  double distance = 0.0;
  double duration = 0.0;
  std::string geometry;
  double weight = 0.0;
  std::string weight_name = "UNKNOWN";
  std::vector<OSRMLeg> legs;
};

struct OSRMWaypoint
{
  std::string name;
  PointLL location;
  double distance = 0.0;
  std::string hint;
};

struct OSRMGlobalRoute
{
  std::string code = "UNKNOWN";
  std::vector<OSRMRoute> routes;
  std::vector<OSRMWaypoint> waypoints;
};

struct StepMatchResult
{
  bool found = false;
  int step_index = -1;
  int segment_index = -1;
  PointXY closest_point;
  double distance = 0.0;
  double t = 0.0;
};

struct SpeedEvalResult
{
  double target_speed_mps = 0.0;
  double target_speed_kmph = 0.0;
  int leg_index = -1;
  int step_index = -1;
  int segment_index = -1;
  double t = 0.0;
  double distance = 0.0;
};

}  // namespace local_path_generator_cpp
