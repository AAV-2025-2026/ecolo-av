import rclpy

from global_map_router.app.controller.global_map_router import GlobalMapRouter
from global_map_router.app.service.logging_service import get_logger
from global_map_router.app.common.constant import LogMessageCons, ApplicationCons

logger = get_logger(LogMessageCons.LOGGER_GLOBAL_MAP_ROUTER)

def main(args=None):
    logger.info(LogMessageCons.SUC_INIT_GMR_1)
    rclpy.init(args=args)
    node = GlobalMapRouter(logger)
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == ApplicationCons.MAIN_MODUAL:
    main()