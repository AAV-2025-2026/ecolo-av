import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from global_map_router.app.service.google_api_service import get_coordinates, get_route
from global_map_router.app.service.logging_service import get_logger
from global_map_router.app.common.constant import LogMessageCons, ApplicationCons

logger = get_logger(LogMessageCons.LOGGER_GLOBAL_MAP_ROUTER)

class GlobalMapRouter(Node):
    def __init__(self):
        super().__init__(ApplicationCons.NODE_GLOBAL_MAP_ROUTER)

        self.create_subscription(String, ApplicationCons.NODE_TARGET_ADDRESS, self.on_target_address, 10)
        self.create_subscription(String, ApplicationCons.NODE_CURRENT_COORDINATE, self.on_current_coordinate, 10)

        self.current_lat = None
        self.current_lon = None

        logger.info(LogMessageCons.SUC_INIT_GMRN_2)
        logger.info(LogMessageCons.SUC_INIT_GMRN_3)

    def on_current_coordinate(self, msg):
        try:
            lat_str, lon_str = msg.data.split(",")
            self.current_lat = float(lat_str.strip())
            self.current_lon = float(lon_str.strip())
            logger.info(LogMessageCons.SUC_RECEIVED_GPS, self.current_lat, self.current_lon)
        except Exception as e:
            logger.error(LogMessageCons.FAIL_RECEIVED_GPS, str(e))

    def on_target_address(self, msg):
        destination = msg.data
        logger.info(LogMessageCons.LINE_BREAK)
        logger.info(LogMessageCons.SUC_RECEIVED_DESTINATION, destination)

        gps_lat = self.current_lat
        gps_lon = self.current_lon

        if gps_lat is None or gps_lon is None:
            logger.warn(LogMessageCons.WARN_RECEIVED_GPS)
            return

        dest_lat, dest_lon = get_coordinates(destination, logger)
        if dest_lat is None:
            logger.error(LogMessageCons.FAIL_GET_DESTINATION_COORDINATES)
            return

        logger.info(LogMessageCons.SUC_GET_DESTINATION_COORDINATES, dest_lat, dest_lon)

        routes = get_route((gps_lat, gps_lon), (dest_lat, dest_lon), logger)
        if not routes:
            logger.error(LogMessageCons.FAIL_GET_ROUTE)
            return

        logger.info(LogMessageCons.PRT_ROUTE_1, len(routes))

        for i, route in enumerate(routes):
            logger.info(LogMessageCons.PRT_ROUTE_2, i + 1, len(route))
            for j, pt in enumerate(route):
                logger.info(LogMessageCons.PRT_ROUTE_3, j + 1, pt[0], pt[1])


def main(args=None):
    logger.info(LogMessageCons.SUC_INIT_GMRN_1)
    rclpy.init(args=args)
    node = GlobalMapRouter()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == ApplicationCons.MAIN_MODUAL:
    main()