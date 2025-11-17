import rclpy

from local_path_generator.app.common.constant import ApplicationCons
from local_path_generator.app.controller.local_path_generator import LocalPathGenerator
from local_path_generator.app.service.logging_service import get_logger

logger = get_logger()

def main(args=None):
    logger.info()
    rclpy.init(args=args)
    node = LocalPathGenerator(logger)
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == ApplicationCons.MAIN_MODUAL:
    main()