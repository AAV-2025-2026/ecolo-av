#osrm/waypoints[]
from typing import Tuple


class OSRMWaypoint:
    def __init__(self, name: str = "", location: Tuple[float, float] = (0.0, 0.0), distance: float = 0.0, hint:str = ""):
        self.name = name
        self.location = location
        self.distance = distance
        self.hint = hint

    @property
    def lon(self) -> float:
        return self.location[0]

    @property
    def lat(self) -> float:
        return self.location[1]