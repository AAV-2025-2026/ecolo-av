from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped, TwistStamped
from nav_msgs.msg import Path

from local_path_generator.app.service.osrm_reader_service import load
from local_path_generator.app.service.path_service import get_current_step_by_coordinate


class LocalPathGenerator(Node):
    def __init__(self, logger):
        super().__init__("local_path_generator")
        self.logger = logger

        self.global_route = None
        self.leg_int = None
        self.step_index = None

        self.create_subscription(String, "/global_route_request", self.on_global_route_request, 10)
        self.create_subscription(String, "/current_path_request", self.on_current_path_request, 10)
        self.current_path_pub = self.create_publisher(Path, "/current_path", 10)

        self.logger.info("LocalPathGenerator initialized.")

    def on_global_route_request(self, msg: String):
        global_route_json = msg.data
        self.logger.info("[/global_route_request] received route JSON.")
        try:
            new_route = load(global_route_json)
            self.global_route = new_route
            self.logger.info("[/global_route_request] success build route model.")
        except Exception as e:
            self.logger.error("[/global_route_request] failed to parse route JSON: %s", e)
            self.logger.warning("[/global_route_request] Keeping old route. Driving continues.")

    def on_current_path_request(self, msg: String):
        try:
            lon, lat, leg_int = map(float, msg.data.split(","))
            current_coordinate = (float(lon), float(lat))
            leg_int = int(leg_int)
        except Exception:
            self.logger.error("[/current_path_request] invalid message")
            return
        if self.leg_int != leg_int:
            self.step_index = None
            self.leg_int = leg_int
        result = get_current_step_by_coordinate(current_coordinate, self.global_route.routes[0].legs[self.leg_int].steps, self.step_index)

        if result is None:
            self.logger.warning("[/current_path_request] Not on route or too far.")
            return

        self.step_index = result["step_index"]
        best_segment = result["segment_index"]
        best_point = result["closest_point"]
        best_dist = result["distance"]

        target_speed = self.global_route.routes[0].legs[self.leg_int].steps[self.step_index].reference_speeds[best_segment]

        self.logger.info("[/current_path_request] Responded")
        self.logger.info("%s %s %s %s",self.step_index, best_segment, best_point, best_dist)
        self.logger.info(
            "Target speed at current position: %.2f m/s (%.2f km/h)",
            target_speed,
            target_speed * 3.6
        )
        self.logger.info(
            "step%s speed range: min=%.2f max=%.2f",
            self.step_index,
            min(self.global_route.routes[0].legs[self.leg_int].steps[self.step_index].reference_speeds),
            max(self.global_route.routes[0].legs[self.leg_int].steps[self.step_index].reference_speeds)
        )