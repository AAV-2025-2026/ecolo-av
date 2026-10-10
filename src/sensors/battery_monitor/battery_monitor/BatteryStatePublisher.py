from rclpy.node import Node
from sensor_msgs.msg import BatteryState

class BatteryStatePublisher(Node):
  publisher = None

  def __init__(self, name, topic):
    # Name the node
    super().__init__(name)
    
    # Create publisher
    self.publisher = self.create_publisher(BatteryState, topic, 10)
  
  def publish_message(self, msg):
    self.publisher.publish(msg)