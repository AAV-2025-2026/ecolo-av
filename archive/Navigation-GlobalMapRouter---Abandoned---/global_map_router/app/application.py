import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from global_map_router.app.service.google_api_service import get_coordinates, get_route
from global_map_router.app.service.gps_service import get_gps_position
from global_map_router.app.service.logging_service import get_logger

logger = get_logger("global_map_router")

class GlobalMapRouter(Node):
    def __init__(self):
        super().__init__("global_nav_node")

        self.create_subscription(String, "/target_address", self.on_address, 10)
        logger.info("✅ Waiting for /target_address...")

    def on_address(self, msg):
        destination = msg.data
        logger.info(f"📍 Received destination: {destination}")

        gps_lat, gps_lon = get_gps_position()
        logger.info(f"📍 Current GPS: lat={gps_lat}, lon={gps_lon}")

        dest_lat, dest_lon = get_coordinates(destination, logger)
        if dest_lat is None:
            logger.error("❌ Failed to get destination coordinates")
            return

        logger.info(f"✅ Destination: lat={dest_lat}, lon={dest_lon}")

        route = get_route((gps_lat, gps_lon), (dest_lat, dest_lon), logger)
        if not route:
            logger.error("❌ Failed to get route")
            return

        logger.info(f"✅ Route received: {len(route)} points")

        for i, pt in enumerate(route[:10]):
            logger.info(f"  Point {i}: lat={pt[0]}, lon={pt[1]}")

def main(args=None):
    logger.info("🚀 Starting Global Navigation Node")
    rclpy.init(args=args)
    node = GlobalMapRouter()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()