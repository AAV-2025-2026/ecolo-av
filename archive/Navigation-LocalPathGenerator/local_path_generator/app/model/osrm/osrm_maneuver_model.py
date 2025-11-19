#osrm/routes[]/legs[]/steps[]/maneuver

from typing import Tuple

from local_path_generator.app.common.enum import OSRMManeuverType, OSRMModifier


class OSRMManeuver:
    def __init__(self, location: Tuple[float, float] = (0.0, 0.0), bearing_before: int = 0, bearing_after: int = 0, type: OSRMManeuverType = OSRMManeuverType.UNKNOWN, modifier: OSRMModifier = OSRMModifier.UNKNOWN, exit: int = 0):
        self.location = location
        self.bearing_before = self._clamp_bearing(bearing_before)
        self.bearing_after = self._clamp_bearing(bearing_after)
        self.type = type
        self.modifier = modifier
        self.exit = exit

    @staticmethod
    def _clamp_bearing(value: int) -> int:
        if value < 0: return 0
        if value > 359: return 359
        return value