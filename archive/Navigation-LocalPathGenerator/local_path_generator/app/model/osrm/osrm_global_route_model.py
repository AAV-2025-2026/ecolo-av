#osrm
from typing import List

from local_path_generator.app.common.enum import OSRMCode
from local_path_generator.app.model.osrm.osrm_route_model import OSRMRoute
from local_path_generator.app.model.osrm.osrm_waypoint_model import OSRMWaypoint


class OSRMGlobalRoute:
    def __init__(self, code: OSRMCode = OSRMCode.UNKNOWN, routes: List[OSRMRoute] = None, waypoints: List[OSRMWaypoint] = None):
        self.code = code
        self.routes = routes if routes is not None else []
        self.waypoints = waypoints if waypoints is not None else []