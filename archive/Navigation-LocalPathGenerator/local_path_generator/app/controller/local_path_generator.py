from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped, TwistStamped
from nav_msgs.msg import Path

class LocalPathGenerator(Node):
    def __init__(self, logger):
        super().__init__("local_path_generator")
        self.logger = logger

        self.global_route = None
        self.current_pose = None
        self.current_velocity = 0.0

        self.create_subscription(String, "/global_route", self.on_global_route, 10)
        self.create_subscription(PoseStamped, "/current_pose", self.on_current_pose, 10)
        self.create_subscription(TwistStamped, "/current_velocity", self.on_current_velocity, 10)
        self.local_path_pub = self.create_publisher(Path, "/local_path", 10)

        self.logger.info("LocalPathGenerator initialized.")

    def on_global_route(self, msg: String):
        self.global_route = msg.data
        self.logger.info("[/global_route] received route JSON.")

    def on_current_pose(self, msg: PoseStamped):
        self.current_pose = msg
        self.logger.info_throttle(2000, "[/current_pose] updated")

    def on_current_velocity(self, msg: TwistStamped):
        self.current_velocity = msg.twist.linear.x
        self.logger.info_throttle(2000, "[/current_velocity] updated")
