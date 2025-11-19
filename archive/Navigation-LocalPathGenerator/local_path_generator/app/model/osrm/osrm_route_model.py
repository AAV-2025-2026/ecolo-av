#osrm/routes[]
from typing import List

from local_path_generator.app.common.enum import OSRMWeightName
from local_path_generator.app.model.osrm.osrm_leg_model import OSRMLeg


class OSRMRoute:
    def __init__(self, distance: float = 0.0, duration: float = 0.0, geometry: str = "", weight: float = 0.0, weight_name: OSRMWeightName = OSRMWeightName.UNKNOWN, legs: List[OSRMLeg] = None):
        self.distance = distance
        self.duration = duration
        self.geometry = geometry
        self.weight = weight
        self.weight_name = weight_name
        self.legs = legs if legs is not None else []