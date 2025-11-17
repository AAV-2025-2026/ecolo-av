import json
from rclpy.node import Node
from std_msgs.msg import String

from global_map_router.app.service.google_api_service import get_coordinates, get_route
from global_map_router.app.common.constant import LogMessageCons, GlobalMapRouterCons

class GlobalMapRouter(Node):
    def __init__(self, logger):
        super().__init__(GlobalMapRouterCons.CLASS_GLOBAL_MAP_ROUTER)

        self.logger = logger

        self.create_subscription(String, GlobalMapRouterCons.NODE_TARGET_ADDRESS, self.on_target_address, 10)
        self.create_subscription(String, GlobalMapRouterCons.NODE_CURRENT_COORDINATE, self.on_current_coordinate, 10)
        self.route_pub = self.create_publisher(String, GlobalMapRouterCons.NODE_GLOBAL_MAP_ROUTER, 10)

        self.current_lat = None
        self.current_lon = None

        logger.info(LogMessageCons.SUC_INIT_GMR_2)
        logger.info(LogMessageCons.SUC_INIT_GMR_3)

    def on_current_coordinate(self, msg):
        try:
            lat_str, lon_str = msg.data.split(",")
            self.current_lat = float(lat_str.strip())
            self.current_lon = float(lon_str.strip())
            self.logger.info(LogMessageCons.SUC_RECEIVED_GPS, self.current_lat, self.current_lon)
        except Exception as e:
            self.logger.error(LogMessageCons.FAIL_RECEIVED_GPS, str(e))

    def on_target_address(self, msg):
        destination = msg.data
        self.logger.info(LogMessageCons.LINE_BREAK)
        self.logger.info(LogMessageCons.SUC_RECEIVED_DESTINATION, destination)

        gps_lat = self.current_lat
        gps_lon = self.current_lon

        if gps_lat is None or gps_lon is None:
            self.logger.warn(LogMessageCons.WARN_RECEIVED_GPS)
            return

        dest_lat, dest_lon = get_coordinates(destination, self.logger)
        if dest_lat is None:
            self.logger.error(LogMessageCons.FAIL_GET_DESTINATION_COORDINATES)
            return

        self.logger.info(LogMessageCons.SUC_GET_DESTINATION_COORDINATES, dest_lat, dest_lon)

        routes = get_route((gps_lat, gps_lon), (dest_lat, dest_lon), self.logger)
        if not routes:
            self.logger.error(LogMessageCons.FAIL_GET_ROUTE)
            return

        self.logger.info(LogMessageCons.PRT_ROUTE_1, len(routes))

        for i, route in enumerate(routes):
            self.logger.info(LogMessageCons.PRT_ROUTE_2, i + 1, len(route))
            for j, pt in enumerate(route):
                self.logger.info(LogMessageCons.PRT_ROUTE_3, j + 1, pt[0], pt[1])

        self.publish_routes(routes)

    def publish_routes(self, routes):
        all_routes = []

        for idx, route_points in enumerate(routes):
            single_route = {
                GlobalMapRouterCons.ROUTE_MSG_1: idx,
                GlobalMapRouterCons.ROUTE_MSG_2: [
                    {GlobalMapRouterCons.ROUTE_MSG_3: lat, GlobalMapRouterCons.ROUTE_MSG_4: lon}
                    for lat, lon in route_points
                ],
                GlobalMapRouterCons.ROUTE_MSG_5: GlobalMapRouterCons.ROUTE_MSG_6
            }
            all_routes.append(single_route)

        merged_msg = {GlobalMapRouterCons.ROUTE_MSG_7: all_routes}

        self.route_pub.publish(String(data=json.dumps(merged_msg)))
        self.logger.info(LogMessageCons.PUB_ROUTE, len(all_routes),
                    sum(len(r[GlobalMapRouterCons.ROUTE_MSG_2]) for r in all_routes))