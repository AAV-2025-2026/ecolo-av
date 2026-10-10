"""spine_bridge: the ROS side of the CAN spine.

Subscribes  ego/actuator_cmd  ackermann_msgs/AckermannDriveStamped
            estop             std_msgs/Bool
            from_can_bus      can_msgs/Frame  (ros2_socketcan receiver)
Publishes   to_can_bus        can_msgs/Frame  (ros2_socketcan sender)
            vehicle/odom      nav_msgs/Odometry  (twist only, in base_link)
            vehicle/status    aav_interfaces/VehicleStatus
            vehicle/joint_states  sensor_msgs/JointState  (front steering joints, for RViz;
                                  joint_state_publisher merges it into /joint_states)
Service     spine/arm         std_srvs/SetBool

Frames are defined in firmware/can/aav.dbc and packed by can_codec.
DRIVE_CMD goes out at 50 Hz only while /ego/actuator_cmd is fresh. If ego
stops, the bridge stops sending and the spine's own watchdog brakes the car.
"""

import math

from ackermann_msgs.msg import AckermannDriveStamped
from can_msgs.msg import Frame
from nav_msgs.msg import Odometry
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool
from std_srvs.srv import SetBool

from aav_interfaces.msg import VehicleStatus
from aav_spine import can_codec as cc


class SpineBridge(Node):

    def __init__(self):
        super().__init__('spine_bridge')
        self.wheelbase = self.declare_parameter('wheelbase', 1.57).value
        self.track = self.declare_parameter('track', 0.77).value
        self.cmd_timeout = self.declare_parameter('cmd_timeout', 0.3).value
        drive_hz = self.declare_parameter('drive_rate_hz', 50.0).value
        estop_hz = self.declare_parameter('estop_rate_hz', 10.0).value
        self.speed_var = self.declare_parameter('speed_variance', 0.01).value
        self.yaw_rate_var = self.declare_parameter('yaw_rate_variance', 0.02).value
        self.joints = self.declare_parameter(
            'steering_joints', ['front_left_steering_joint', 'front_right_steering_joint']).value

        self.cmd = None
        self.cmd_time = None
        self.armed = False
        self.disarm_frames = 0   # armed=0 frames still to send before arming
        self.estop = False
        self.counters = {}
        self.feedback = None
        self.bad_frames = 0

        self.to_can = self.create_publisher(Frame, 'to_can_bus', 50)
        self.odom_pub = self.create_publisher(Odometry, 'vehicle/odom', 10)
        self.status_pub = self.create_publisher(VehicleStatus, 'vehicle/status', 10)
        self.joint_pub = self.create_publisher(JointState, 'vehicle/joint_states', 10)
        self.create_subscription(AckermannDriveStamped, 'ego/actuator_cmd', self.on_cmd, 10)
        self.create_subscription(Bool, 'estop', self.on_estop, 10)
        self.create_subscription(Frame, 'from_can_bus', self.on_frame, 100)
        self.create_service(SetBool, 'spine/arm', self.on_arm)
        self.create_timer(1.0 / drive_hz, self.send_drive)
        self.create_timer(1.0 / estop_hz, self.send_estop)

    # Orin -> spine

    def on_cmd(self, msg):
        self.cmd = msg.drive
        self.cmd_time = self.get_clock().now()

    def on_estop(self, msg):
        changed = msg.data != self.estop
        self.estop = msg.data
        if self.estop:
            self.armed = False
        if changed:
            self.send_estop()

    def on_arm(self, request, response):
        if request.data and self.estop:
            response.success = False
            response.message = 'e-stop is active; clear /estop first'
            return response
        if request.data and not self.armed:
            self.disarm_frames = 3   # the spine re-arms on armed 0 -> 1
        self.armed = request.data
        response.success = True
        response.message = 'armed' if self.armed else 'disarmed'
        self.get_logger().info(response.message)
        return response

    def _next(self, can_id):
        self.counters[can_id] = (self.counters.get(can_id, 0) + 1) & 0x0F
        return self.counters[can_id]

    def _send(self, can_id, data):
        f = Frame()
        f.header.stamp = self.get_clock().now().to_msg()
        f.id = can_id
        f.dlc = len(data)
        f.data = list(data) + [0] * (8 - len(data))
        self.to_can.publish(f)

    def send_drive(self):
        if self.cmd is None:
            return
        age = (self.get_clock().now() - self.cmd_time).nanoseconds * 1e-9
        if age > self.cmd_timeout:
            self.get_logger().warn('no fresh /ego/actuator_cmd; the spine will brake',
                                   throttle_duration_sec=2.0)
            return
        armed = self.armed and self.disarm_frames == 0
        if self.disarm_frames:
            self.disarm_frames -= 1
        self._send(cc.DRIVE_CMD_ID, cc.pack(cc.DRIVE_CMD_ID, {
            'target_speed': self.cmd.speed,
            'steering_angle': self.cmd.steering_angle,
            'accel_limit': abs(self.cmd.acceleration),
            'steer_rate_limit': abs(self.cmd.steering_angle_velocity),
            'armed': armed,
            'counter': self._next(cc.DRIVE_CMD_ID),
        }))

    def send_estop(self):
        self._send(cc.ESTOP_CMD_ID, cc.pack(cc.ESTOP_CMD_ID, {
            'estop_request': self.estop,
            'counter': self._next(cc.ESTOP_CMD_ID),
        }))

    # spine -> Orin

    def on_frame(self, f):
        if f.is_error or f.is_rtr or f.id not in (cc.VEHICLE_FEEDBACK_ID, cc.VEHICLE_STATUS_ID):
            return
        try:
            values = cc.unpack(f.id, bytes(f.data[:f.dlc]))
        except cc.FrameError as e:
            self.bad_frames += 1
            self.get_logger().warn(f'{e} ({self.bad_frames} so far)', throttle_duration_sec=2.0)
            return
        if f.id == cc.VEHICLE_FEEDBACK_ID:
            self.publish_feedback(values)
        else:
            self.publish_status(values)

    def publish_feedback(self, v):
        self.feedback = v
        now = self.get_clock().now().to_msg()
        speed = v['measured_speed']
        steer = v['measured_steering_angle']
        odom = Odometry()
        odom.header.stamp = now
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.twist.twist.linear.x = speed
        odom.twist.twist.angular.z = speed * math.tan(steer) / self.wheelbase
        cov = [0.0] * 36
        cov[0] = self.speed_var          # vx
        cov[7] = 1e-4                    # vy: a car doesn't slide sideways
        cov[14] = cov[21] = cov[28] = 1e3  # vz, roll and pitch rates: not measured
        cov[35] = self.yaw_rate_var      # yaw rate
        odom.twist.covariance = cov
        odom.pose.covariance = [1e3 if i % 7 == 0 else 0.0 for i in range(36)]
        self.odom_pub.publish(odom)

        js = JointState()
        js.header.stamp = now
        js.name = list(self.joints)
        js.position = list(self.wheel_angles(steer))
        self.joint_pub.publish(js)

    def wheel_angles(self, steer):
        """Return the left and right wheel angles for a virtual centre angle (Ackermann)."""
        if abs(steer) < 1e-6:
            return 0.0, 0.0
        radius = self.wheelbase / math.tan(steer)   # signed, positive turning left
        left = math.atan(self.wheelbase / (radius - self.track / 2))
        right = math.atan(self.wheelbase / (radius + self.track / 2))
        return left, right

    def publish_status(self, v):
        s = VehicleStatus()
        s.header.stamp = self.get_clock().now().to_msg()
        s.header.frame_id = 'base_link'
        s.mode = int(v['mode'])
        s.armed = bool(v['armed'])
        s.estop_active = bool(v['estop_active'])
        s.throttle = v['throttle'] / 100.0
        s.brake = v['brake'] / 100.0
        s.faults = int(v['faults'])
        if self.feedback:
            s.speed = self.feedback['measured_speed']
            s.steering_angle = self.feedback['measured_steering_angle']
        self.status_pub.publish(s)


def main(args=None):
    rclpy.init(args=args)
    node = SpineBridge()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except Exception:
        # Ctrl-C reaches a launched node twice (terminal and launch), and Jazzy can then
        # raise RCLError ("context is not valid"). Only a live context means a real error.
        if rclpy.ok():
            raise
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
