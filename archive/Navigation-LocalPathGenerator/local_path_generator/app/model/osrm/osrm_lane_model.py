#osrm/routes[]/legs[]/steps[]/intersections[]/lanes[]
from typing import List

from local_path_generator.app.common.enum import OSRMIndication

class OSRMLane:
    def __init__(self, valid: bool = False, indications: List[OSRMIndication] = None):
        self.valid = valid
        self.indications = indications if indications is not None else []