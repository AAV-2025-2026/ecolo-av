#osrm/routes[]/legs[]/steps[]/intersections[]
from typing import Tuple, List

from local_path_generator.app.model.osrm.osrm_lanes_model import OSRMLanes


class OSRMIntersection:
    def __init__(self, location: Tuple[float, float] = (0.0, 0.0), bearings: List[int] = None, classes: str = "", entry: List[bool] = None, p_in: int = 0, p_out: int = 0, lanes: OSRMLanes = None):
        self.location = location
        self.bearings = bearings if bearings is not None else []
        self.classes = classes
        self.entry = entry if entry is not None else []
        self.p_in = p_in
        self.p_out = p_out
        self.lanes = lanes