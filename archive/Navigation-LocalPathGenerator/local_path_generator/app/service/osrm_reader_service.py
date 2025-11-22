import json, polyline

from local_path_generator.app.common.enum import (
    OSRMCode, OSRMWeightName, OSRMMode, OSRMDrivingSide,
    OSRMManeuverType, OSRMModifier, OSRMIndication
)
from local_path_generator.app.model.osrm.osrm_global_route_model import OSRMGlobalRoute
from local_path_generator.app.model.osrm.osrm_route_model import OSRMRoute
from local_path_generator.app.model.osrm.osrm_leg_model import OSRMLeg
from local_path_generator.app.model.osrm.osrm_step_model import OSRMStep
from local_path_generator.app.model.osrm.osrm_maneuver_model import OSRMManeuver
from local_path_generator.app.model.osrm.osrm_intersection_model import OSRMIntersection
from local_path_generator.app.model.osrm.osrm_lane_model import OSRMLane
from local_path_generator.app.model.osrm.osrm_waypoint_model import OSRMWaypoint

class OSRMReader:

    @staticmethod
    def load(json_data: str) -> OSRMGlobalRoute:
        data = json.loads(json_data)
        return OSRMGlobalRoute(
            code=OSRMReader._parse_enum(OSRMCode, data.get("code")),
            routes=[OSRMReader._parse_route(r) for r in data.get("routes", [])],
            waypoints=[OSRMReader._parse_waypoint(w) for w in data.get("waypoints", [])]
        )

    @staticmethod
    def _parse_route(r: dict) -> OSRMRoute:
        route = OSRMRoute(
            distance=float(r.get("distance", 0.0)),
            duration=float(r.get("duration", 0.0)),
            geometry=r.get("geometry", ""),
            weight=float(r.get("weight", 0.0)),
            weight_name=OSRMReader._parse_enum(OSRMWeightName, r.get("weight_name")),
            legs=[OSRMReader._parse_leg(l) for l in r.get("legs", [])]
        )

        steps_flat = []

        for leg in route.legs:
            for step in leg.steps:
                steps_flat.append(step)

        total = len(steps_flat)
        for i, step in enumerate(steps_flat):
            step.step_index = i
            step.is_last_step = (i == total - 1)
            if step.maneuver:
                step.maneuver_type = step.maneuver.type
                step.maneuver_modifier = step.maneuver.modifier

        return route

    @staticmethod
    def _parse_leg(l: dict) -> OSRMLeg:
        return OSRMLeg(
            distance=float(l.get("distance", 0.0)),
            duration=float(l.get("duration", 0.0)),
            weight=float(l.get("weight", 0.0)),
            summary=l.get("summary", ""),
            steps=[OSRMReader._parse_step(s) for s in l.get("steps", [])]
        )

    @staticmethod
    def _parse_step(s: dict) -> OSRMStep:
        raw = s.get("geometry", "")
        decoded = polyline.decode(raw) if raw else []
        return OSRMStep(
            distance=float(s.get("distance", 0.0)),
            duration=float(s.get("duration", 0.0)),
            geometry = [(lon, lat) for (lat, lon) in decoded],
            weight=float(s.get("weight", 0.0)),
            name=s.get("name", ""),
            ref=s.get("ref", ""),
            pronunciation=s.get("pronunciation", ""),
            destinations=s.get("destinations", ""),
            exits=str(s.get("exits", "")),
            mode=OSRMReader._parse_enum(OSRMMode, s.get("mode")),
            maneuver=OSRMReader._parse_maneuver(s.get("maneuver")),
            intersections=[OSRMReader._parse_intersection(i) for i in s.get("intersections", [])],
            rotary_name=s.get("rotary_name", ""),
            rotary_pronunciation=s.get("rotary_pronunciation", ""),
            driving_side=OSRMReader._parse_enum(OSRMDrivingSide, s.get("driving_side"))
        )

    @staticmethod
    def _parse_maneuver(m: dict) -> OSRMManeuver:
        if m is None:
            return None
        loc = m.get("location", [0.0, 0.0])
        return OSRMManeuver(
            location=(float(loc[0]), float(loc[1])),
            bearing_before=int(m.get("bearing_before", 0)),
            bearing_after=int(m.get("bearing_after", 0)),
            type=OSRMReader._parse_enum(OSRMManeuverType, m.get("type")),
            modifier=OSRMReader._parse_enum(OSRMModifier, m.get("modifier")),
            exit=int(m.get("exit", 0))
        )

    @staticmethod
    def _parse_intersection(i: dict) -> OSRMIntersection:
        loc = i.get("location", [0.0, 0.0])
        lanes = []
        if "lanes" in i and isinstance(i["lanes"], list):
            for l in i["lanes"]:
                lanes.append(OSRMLane(
                    valid=bool(l.get("valid", False)),
                    indications=[OSRMReader._parse_enum(OSRMIndication, ind) for ind in l.get("indications", [])]
                ))

        return OSRMIntersection(
            location=(float(loc[0]), float(loc[1])),
            bearings=i.get("bearings", []),
            classes=i.get("classes", ""),
            entry=i.get("entry", []),
            p_in=i.get("in", 0),
            p_out=i.get("out", 0),
            lanes=lanes
        )

    @staticmethod
    def _parse_waypoint(w: dict) -> OSRMWaypoint:
        loc = w.get("location", [0.0, 0.0])
        return OSRMWaypoint(
            name=w.get("name", ""),
            location=(float(loc[0]), float(loc[1])),
            distance=float(w.get("distance", 0.0)),
            hint=w.get("hint", "")
        )

    @staticmethod
    def _parse_enum(enum_type, value):
        if value is None:
            return enum_type.UNKNOWN
        for e in enum_type:
            if e.value == value:
                return e
        return enum_type.UNKNOWN
