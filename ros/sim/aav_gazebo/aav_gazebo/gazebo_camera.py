"""
gazebo_camera: the front left camera's picture, through its fault on purpose.

Subscribes  gazebo/camera/front_left/image_raw   sensor_msgs/Image (the road bridge's)
Publishes   sensors/camera/front_left/image_raw  sensor_msgs/Image

Parameters  fault.camera (ok; stop, freeze)

Only with faults:=true (gazebo.launch.py camera_relay), which sends the road bridge's
picture here instead of straight to the car's topic. Reliable, the newest only: best
effort loses whole pictures over UDP (docs/mac.md). One process of its own (relay.py):
pictures are big.
"""

from aav_gazebo.relay import run, SensorRelay
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image


class GazeboCamera(SensorRelay):

    def __init__(self):
        super().__init__('gazebo_camera', 'camera')
        picture = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE)
        self.pub = self.create_publisher(Image, 'sensors/camera/front_left/image_raw', picture)
        self.create_subscription(Image, 'gazebo/camera/front_left/image_raw', self.on_camera,
                                 picture)

    def on_camera(self, msg):
        out = self.faulty(msg)
        if out is not None:
            self.pub.publish(out)


def main(args=None):
    run(GazeboCamera, args)


if __name__ == '__main__':
    main()
