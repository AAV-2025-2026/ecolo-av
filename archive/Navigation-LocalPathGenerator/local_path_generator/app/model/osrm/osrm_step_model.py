#osrm/routes[]/legs[]/steps[]
from typing import List, Tuple

from local_path_generator.app.common.enum import OSRMMode, OSRMDrivingSide
from local_path_generator.app.model.osrm.osrm_intersection_model import OSRMIntersection
from local_path_generator.app.model.osrm.osrm_maneuver_model import OSRMManeuver


class OSRMStep:
    def __init__(self, distance: float = 0.0, duration: float = 0.0, geometry: List[Tuple[float, float]] = None, weight: float = 0.0, name: str = "", ref: str = "", pronunciation: str = "", destinations: str = "", exits: str = "", mode: OSRMMode = OSRMMode.UNKNOWN, maneuver: OSRMManeuver = None, intersections: List[OSRMIntersection] = None, rotary_name: str = "", rotary_pronunciation: str = "", driving_side: OSRMDrivingSide = OSRMDrivingSide.UNKNOWN):
        self.distance = distance
        self.duration = duration
        self.geometry = geometry if geometry is not None else []
        self.reference_speeds: List[float] = [0.0] * len(self.geometry)
        self.weight = weight
        self.name = name
        self.ref = ref
        self.pronunciation = pronunciation
        self.destinations = destinations
        self.exits = exits
        self.mode = mode
        self.maneuver = maneuver
        self.intersections = intersections if intersections is not None else []
        self.rotary_name = rotary_name
        self.rotary_pronunciation = rotary_pronunciation
        self.driving_side = driving_side

        self.step_index = None
        self.is_last_step = False
        self.maneuver_type = None
        self.maneuver_modifier = None