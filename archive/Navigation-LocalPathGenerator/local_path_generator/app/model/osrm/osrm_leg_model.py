#osrm/routes[]/legs[]
from typing import List

from local_path_generator.app.model.osrm.osrm_annotation_model import OSRMAnnotation
from local_path_generator.app.model.osrm.osrm_step_model import OSRMStep


class OSRMLeg:
    def __init__(self, distance: float = 0.0, duration: float = 0.0, weight: float = 0.0, summary: str = "", steps: List[OSRMStep] = None, annotation: OSRMAnnotation = None):
        self.distance = distance
        self.duration = duration
        self.weight = weight
        self.summary = summary
        self.steps = steps if steps is not None else []
        self.annotation = annotation