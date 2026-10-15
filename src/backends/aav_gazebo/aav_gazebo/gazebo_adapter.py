"""
gazebo_adapter: Gazebo (Harmonic) as the car, behind the same topics as the real one.

Subscribes  ego/actuator_cmd      ackermann_msgs/AckermannDriveStamped
            gazebo/odom           nav_msgs/Odometry   (bridged from the Ackermann system)
            joint_states          sensor_msgs/JointState (bridged: the wheels' spin)
            gazebo/imu            sensor_msgs/Imu     (bridged IMU sensor)
            gazebo/navsat         sensor_msgs/NavSatFix (bridged NavSat sensor)
            gazebo/radar/points   sensor_msgs/PointCloud2, best effort (bridged lidar: the
                                  radar stand-in), only with radar:=true
Publishes   gazebo/cmd_vel        geometry_msgs/Twist (bridged to /model/aav/cmd_vel), at
                                  rate_hz: the actuator model's speed and steering
            vehicle/odom          nav_msgs/Odometry, twist only, like aav_spine
            vehicle/status        aav_interfaces/VehicleStatus (mode COMPUTER, armed)
            vehicle/steering      aav_interfaces/ActuatorState: ego's angle, the model's
            vehicle/throttle      aav_interfaces/ActuatorState: the speed loop's, the model's
            vehicle/brake         aav_interfaces/ActuatorState: the same (NaN with the model off)
            vehicle/wheels        aav_interfaces/WheelSpeeds: each wheel's spin x its radius
            sensors/imu/data_raw  sensor_msgs/Imu, with covariances; forward and sideways
                                  acceleration from the car's motion (imu.py), as Gazebo's
                                  IMU misses it
            sensors/gps/fix       sensor_msgs/NavSatFix, with a covariance
            sensors/radar/points  sensor_msgs/PointCloud2, best effort, in radar_link: only
                                  the rays that hit something, with the TI driver's fields
                                  (radar.py), only with radar:=true
            system/source         aav_interfaces/DataSource, latched: everything above, and
                                  the cameras and lidar Gazebo renders, is SIM (sources.py)

The actuator model (actuator_model.py, READ-ME-FULL-SIMULATION.md step 3) sits between
ego and Gazebo: a stand-in for the spine's speed loop turns ego's speed into throttle and
brake, and the model turns those, and ego's steering angle, into what the car does, with
the numbers in vehicle.yaml's `actuators:` section. actuator_model:=false gives the old
behaviour instead, to compare: the speed within Gazebo's old limits, an instant steer.
Gazebo's own limits (aav.gazebo.xacro) are wide, so the model, not Gazebo, limits. No
/ego/actuator_cmd for cmd_timeout s: the target speed drops to 0, as the spine's watchdog.

Parameters  actuator_model (true), rate_hz (50), cmd_timeout (0.2 s), wheelbase,
            wheel_radius, radar, lidar, and the sensors' noise

So ekf_local, ekf_global, navsat_transform and imu_filter_madgwick run in simulation
with the same configs as on the car, and radar_clusters, Nav2's costmap and
collision_monitor read the radar as they would on the car. radar is true only in a world
that renders the radar stand-in (gazebo.launch.py). Gazebo's ground-truth pose is not
passed on: the road world bridges it to /vehicle/gazebo/truth, for checks only.
"""

import math
import random
import signal

from aav_description import vehicle
from aav_gazebo import imu, radar, sources, wheels
from aav_gazebo.actuator_model import ActuatorConfig, Actuators, Ideal
from aav_interfaces.msg import ActuatorState, DataSource, SensorSource, VehicleStatus
from aav_interfaces.msg import WheelSpeeds
from ackermann_msgs.msg import AckermannDriveStamped
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, qos_profile_sensor_data, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Imu, JointState, NavSatFix, NavSatStatus, PointCloud2, PointField
from sensor_msgs_py import point_cloud2

# The TI driver's fields: x, y, z, intensity, velocity, float32 each.
RADAR_FIELDS = [PointField(name=n, offset=4 * i, datatype=PointField.FLOAT32, count=1)
                for i, n in enumerate(radar.FIELDS)]


def turn_rate(speed, steering, wheelbase):
    """Bicycle model: the yaw rate that gives this steering angle at this speed."""
    return speed * math.tan(steering) / wheelbase


class GazeboAdapter(Node):

    def __init__(self):
        super().__init__('gazebo_adapter')
        self.wheelbase = self.declare_parameter('wheelbase', 1.57).value
        self.speed_var = self.declare_parameter('speed_variance', 0.01).value
        self.gyro_var = self.declare_parameter('gyro_stddev', 0.02).value ** 2
        self.accel_std = self.declare_parameter('accel_stddev', 0.2).value
        self.accel_var = self.accel_std ** 2
        self.gps_var = self.declare_parameter('gps_stddev', 0.5).value ** 2
        self.radar_range = self.declare_parameter('radar_range', 8.4).value   # m
        lidar = self.declare_parameter('lidar', False).value
        self.wheel_radius = self.declare_parameter('wheel_radius', 0.15).value   # m
        self.cmd_timeout = self.declare_parameter('cmd_timeout', 0.2).value     # s
        rate = self.declare_parameter('rate_hz', 50.0).value
        car = vehicle.load()
        config = ActuatorConfig.from_vehicle(car)
        self.imu_x = float(car['sensors']['imu_link']['xyz'][0])   # m ahead of base_link
        if self.declare_parameter('actuator_model', True).value:
            self.model = Actuators(config)
            self.get_logger().info(f'the actuator model, from vehicle.yaml: {config}')
        else:
            self.model = Ideal(config)
            self.get_logger().info("no actuator model: Gazebo's old limits, an instant steer")
        self.cmd = None          # ego's last command
        self.cmd_time = None
        self.last_tick = None
        self.state = None        # the model's last step
        self.speed = 0.0

        self.cmd_pub = self.create_publisher(Twist, 'gazebo/cmd_vel', 10)
        self.odom_pub = self.create_publisher(Odometry, 'vehicle/odom', 10)
        self.status_pub = self.create_publisher(VehicleStatus, 'vehicle/status', 10)
        self.imu_pub = self.create_publisher(Imu, 'sensors/imu/data_raw', 10)
        self.fix_pub = self.create_publisher(NavSatFix, 'sensors/gps/fix', 10)
        self.steering_pub = self.create_publisher(ActuatorState, 'vehicle/steering', 10)
        self.throttle_pub = self.create_publisher(ActuatorState, 'vehicle/throttle', 10)
        self.brake_pub = self.create_publisher(ActuatorState, 'vehicle/brake', 10)
        self.wheels_pub = self.create_publisher(WheelSpeeds, 'vehicle/wheels', 10)
        self.create_subscription(AckermannDriveStamped, 'ego/actuator_cmd', self.on_cmd, 10)
        self.create_subscription(Odometry, 'gazebo/odom', self.on_odom, 10)
        self.create_subscription(Imu, 'gazebo/imu', self.on_imu, 10)
        self.create_subscription(NavSatFix, 'gazebo/navsat', self.on_navsat, 10)
        self.create_subscription(JointState, 'joint_states', self.on_joints, 10)
        self.create_timer(1.0 / rate, self.tick)
        if self.declare_parameter('radar', False).value:
            # Best effort both ways, as the TI driver publishes: its subscribers ask for it.
            self.radar_pub = self.create_publisher(PointCloud2, 'sensors/radar/points',
                                                   qos_profile_sensor_data)
            self.create_subscription(PointCloud2, 'gazebo/radar/points', self.on_radar,
                                     qos_profile_sensor_data)
        self.announce(sources.simulated(rendered=self.get_parameter('radar').value,
                                        lidar=lidar))

    def announce(self, entries):
        """Say once, latched, that all of this is simulated (/system/source)."""
        latched = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                             durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.source_pub = self.create_publisher(DataSource, 'system/source', latched)
        msg = DataSource(announcer=self.get_name())
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.sensors = [SensorSource(name=n, topic=t, source=SensorSource.SIM)
                       for n, t in entries]
        self.source_pub.publish(msg)

    def on_cmd(self, msg):
        self.cmd = msg.drive
        self.cmd_time = self.get_clock().now()

    def tick(self):
        """Step the actuator model on Gazebo's clock, and send Gazebo what it gives."""
        now = self.get_clock().now()
        before, self.last_tick = self.last_tick, now
        if before is None:
            return
        dt = (now - before).nanoseconds * 1e-9
        if dt <= 0.0:
            return                       # the clock stood still, or went back (a reset)
        dt = min(dt, 0.1)                # a stall: don't jump
        fresh = (self.cmd is not None
                 and (now - self.cmd_time).nanoseconds * 1e-9 <= self.cmd_timeout)
        speed = self.cmd.speed if fresh else 0.0
        steer = self.cmd.steering_angle if self.cmd is not None else 0.0
        s = self.state = self.model.step(speed, steer, dt)

        out = Twist()
        out.linear.x = s.speed
        out.angular.z = turn_rate(s.speed, s.steering, self.wheelbase)
        self.cmd_pub.publish(out)

        stamp = now.to_msg()
        for pub, command, measured in ((self.steering_pub, s.steer_command, s.steering),
                                       (self.throttle_pub, s.throttle_command, s.throttle),
                                       (self.brake_pub, s.brake_command, s.brake)):
            a = ActuatorState(command=float(command), measured=float(measured))
            a.header.stamp = stamp
            a.header.frame_id = 'base_link'
            pub.publish(a)

    def on_joints(self, msg):
        w = WheelSpeeds(**wheels.ground_speeds(msg.name, msg.velocity, self.wheel_radius))
        w.header.stamp = msg.header.stamp
        w.header.frame_id = 'base_link'
        self.wheels_pub.publish(w)

    def on_odom(self, msg):
        odom = Odometry()
        odom.header = msg.header
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        speed = msg.twist.twist.linear.x
        self.speed = speed
        odom.twist.twist.linear.x = speed
        odom.twist.twist.angular.z = msg.twist.twist.angular.z
        cov = [0.0] * 36
        cov[0] = self.speed_var
        cov[7] = 1e-4
        cov[14] = cov[21] = cov[28] = 1e3
        cov[35] = 0.02
        odom.twist.covariance = cov
        odom.pose.covariance = [1e3 if i % 7 == 0 else 0.0 for i in range(36)]
        self.odom_pub.publish(odom)

        s = VehicleStatus()
        s.header.stamp = msg.header.stamp
        s.header.frame_id = 'base_link'
        s.mode = VehicleStatus.MODE_COMPUTER
        s.armed = True
        s.speed = speed
        if self.state is not None:
            m = self.state
            s.steering_angle = m.steering
            # The model's levels; with the model off there are none (NaN): say 0.
            s.throttle = m.throttle if math.isfinite(m.throttle) else 0.0
            s.brake = m.brake if math.isfinite(m.brake) else 0.0
        self.status_pub.publish(s)

    def on_imu(self, msg):
        msg.header.frame_id = 'imu_link'
        if self.state is not None:
            # Gazebo's IMU misses the car's own acceleration (imu.py): the model's, plus noise.
            fwd, left = imu.body_acceleration(self.state.accel, self.speed,
                                              msg.angular_velocity.z, x=self.imu_x)
            msg.linear_acceleration.x = fwd + random.gauss(0.0, self.accel_std)
            msg.linear_acceleration.y = left + random.gauss(0.0, self.accel_std)
        msg.orientation_covariance[0] = -1.0     # like the real IMU: no orientation
        for i in (0, 4, 8):
            msg.angular_velocity_covariance[i] = self.gyro_var
            msg.linear_acceleration_covariance[i] = self.accel_var
        self.imu_pub.publish(msg)

    def on_navsat(self, msg):
        msg.header.frame_id = 'gps_link'
        msg.status.status = NavSatStatus.STATUS_FIX
        msg.position_covariance = [self.gps_var, 0.0, 0.0,
                                   0.0, self.gps_var, 0.0,
                                   0.0, 0.0, 4 * self.gps_var]
        msg.position_covariance_type = NavSatFix.COVARIANCE_TYPE_DIAGONAL_KNOWN
        self.fix_pub.publish(msg)

    def on_radar(self, msg):
        xyz = point_cloud2.read_points_numpy(msg, field_names=('x', 'y', 'z'))
        points = radar.ti_points(radar.returns(xyz, self.radar_range), self.speed)
        msg.header.frame_id = 'radar_link'
        self.radar_pub.publish(point_cloud2.create_cloud(msg.header, RADAR_FIELDS, points))


def main(args=None):
    rclpy.init(args=args)
    node = GazeboAdapter()
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
        # Ctrl-C reaches a launched node twice (the terminal, then launch): ignore the
        # second, so it can't interrupt the clean-up with a traceback.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
