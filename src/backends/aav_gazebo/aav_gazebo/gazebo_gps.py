"""
gazebo_gps: Gazebo's NavSat sensor, made to read like the car's GPS.

Subscribes  gazebo/navsat         sensor_msgs/NavSatFix (bridged NavSat sensor)
Publishes   sensors/gps/fix       sensor_msgs/NavSatFix, in gps_link, a fix, with a
                                  covariance

Parameters  gps_stddev (0.5 m: GPS without RTK), fault.gps (ok; stop, freeze, nan, jump)

One process of its own (relay.py).
"""

from aav_gazebo import faults
from aav_gazebo.relay import run, SensorRelay
from sensor_msgs.msg import NavSatFix, NavSatStatus


def gps_nan(msg):
    msg.latitude = msg.longitude = msg.altitude = float('nan')


def gps_jump(msg):
    msg.latitude = faults.jumped(msg.latitude)


class GazeboGps(SensorRelay):

    def __init__(self):
        super().__init__('gazebo_gps', 'gps')
        self.gps_var = self.declare_parameter('gps_stddev', 0.5).value ** 2
        self.pub = self.create_publisher(NavSatFix, 'sensors/gps/fix', 10)
        self.create_subscription(NavSatFix, 'gazebo/navsat', self.on_navsat, 10)

    def on_navsat(self, msg):
        msg.header.frame_id = 'gps_link'
        msg.status.status = NavSatStatus.STATUS_FIX
        msg.position_covariance = [self.gps_var, 0.0, 0.0,
                                   0.0, self.gps_var, 0.0,
                                   0.0, 0.0, 4 * self.gps_var]
        msg.position_covariance_type = NavSatFix.COVARIANCE_TYPE_DIAGONAL_KNOWN
        msg = self.faulty(msg, nan=gps_nan, jump=gps_jump)
        if msg is not None:
            self.pub.publish(msg)


def main(args=None):
    run(GazeboGps, args)


if __name__ == '__main__':
    main()
