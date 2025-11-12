import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from global_map_router.app.service.google_api_service import get_coordinates, get_route
from global_map_router.app.service.gps_service import get_gps_position
from global_map_router.app.service.logging_service import get_logger
from global_map_router.app.common.constant import LogMessageCons, ApplicationCons

logger = get_logger(LogMessageCons.LOGGER_GLOBAL_MAP_ROUTER)

class GlobalMapRouter(Node):
    def __init__(self):
        super().__init__(ApplicationCons.NODE_GLOBAL_MAP_ROUTER)

        self.create_subscription(String, ApplicationCons.NODE_TARGET_ADDRESS, self.on_address, 10)
        logger.info(LogMessageCons.SUC_INIT_GNN_2)

    def on_address(self, msg):
        destination = msg.data
        logger.info(LogMessageCons.LINE_BREAK)
        logger.info(LogMessageCons.SUC_RECEIVED_DESTINATION, destination)

        gps_lat, gps_lon = get_gps_position()
        logger.info(LogMessageCons.SUC_RECEIVED_GPS, gps_lat, gps_lon)

        dest_lat, dest_lon = get_coordinates(destination, logger)
        if dest_lat is None:
            logger.error(LogMessageCons.FAIL_GET_DESTINATION_COORDINATES)
            return

        logger.info(LogMessageCons.SUC_GET_DESTINATION_COORDINATES, dest_lat, dest_lon)

        route = get_route((gps_lat, gps_lon), (dest_lat, dest_lon), logger)
        if not route:
            logger.error(LogMessageCons.FAIL_GET_ROUTE)
            return

        logger.info(LogMessageCons.SUC_GET_ROUTE, len(route))

        for i, pt in enumerate(route[:10]):
            logger.info(LogMessageCons.PRT_ROUTE, i, pt[0], pt[1])

def main(args=None):
    logger.info(LogMessageCons.SUC_INIT_GNN_1)
    rclpy.init(args=args)
    node = GlobalMapRouter()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == ApplicationCons.MAIN_MODUAL:
    main()