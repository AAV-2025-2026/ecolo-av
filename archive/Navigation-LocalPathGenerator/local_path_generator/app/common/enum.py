from enum import Enum

class OSRMCode(Enum):
    OK = "Ok"
    INVALID_URL = "InvalidUrl"
    INVALID_SERVICE = "InvalidService"
    INVALID_VERSION = "InvalidVersion"
    INVALID_OPTIONS = "InvalidOptions"
    INVALID_QUERY = "InvalidQuery"
    INVALID_VALUE = "InvalidValue"
    NO_SEGMENT = "NoSegment"
    TOO_BIG = "TooBig"
    NO_ROUTE = "NoRoute"
    UNKNOWN = "UNKNOWN"

class OSRMWeightName(Enum):
    ROUTABILITY = "routability"
    DURATION = "duration"
    DISTANCE = "distance"
    SHORTEST = "shortest"
    FASTEST = "fastest"
    UNKNOWN = "UNKNOWN"

class OSRMMode(Enum):
    DRIVING = "driving"
    CYCLING = "cycling"
    WALKING = "walking"
    FERRY = "ferry"
    UNKNOWN = "UNKNOWN"

class OSRMDrivingSide(Enum):
    RIGHT = "right"
    LEFT = "left"
    UNKNOWN = "UNKNOWN"

class OSRMManeuverType(Enum):
    TURN = "turn"
    NEW_NAME = "new name"
    DEPART = "depart"
    ARRIVE = "arrive"
    MERGE = "merge"
    ON_RAMP = "on ramp"
    OFF_RAMP = "off ramp"
    FORK = "fork"
    END_OF_ROAD = "end of road"
    CONTINUE = "continue"
    ROUNDABOUT = "roundabout"
    ROTARY = "rotary"
    ROUNDABOUT_TURN="roundabout turn"
    NOTIFICATION = "notification"
    EXIT_ROUNDABOUT = "exit roundabout"
    EXIT_ROTARY = "exit rotary"
    UNKNOWN = "UNKNOWN"

class OSRMModifier(Enum):
    UTURN = "uturn"
    SHARP_RIGHT = "sharp right"
    RIGHT = "right"
    SLIGHT_RIGHT = "slight right"
    STRAIGHT = "straight"
    SLIGHT_LEFT = "slight left"
    LEFT = "left"
    SHARP_LEFT = "sharp left"
    UNKNOWN = "UNKNOWN"

class OSRMIndication(Enum):
    NONE = "none"
    UTURN = "uturn"
    SHARP_RIGHT = "sharp right"
    RIGHT = "right"
    SLIGHT_RIGHT = "slight right"
    STRAIGHT = "straight"
    SLIGHT_LEFT = "slight left"
    LEFT = "left"
    SHARP_LEFT = "sharp left"
    UNKNOWN = "UNKNOWN"
