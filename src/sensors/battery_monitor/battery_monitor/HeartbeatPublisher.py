import time

from rclpy.node import Node
from std_msgs.msg import String


class TimePublisher(Node):
    publisher = None

    def __init__(self, name, topic):
        super().__init__(name)

        self.publisher = self.create_publisher(String, topic, 10)

    def publish_time(self):
        msg = String()
        msg.data = f'Current Time: {time.ctime()}'
        self.publisher.publish(msg)
