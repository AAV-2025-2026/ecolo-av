"""
carla_adapter: a CARLA car as the car, behind the same topics as the real one.

It talks to the CARLA server through CARLA's own Python client (TCP, host:port), not
through ROS: no carla-ros-bridge, and not CARLA's built-in ROS 2 (which stalls on Jazzy,
docs/carla.md). So it works with CARLA 0.10 (Unreal Engine 5) and 0.9.16 (Unreal Engine 4)
alike, and ROS discovery can stay on this computer while the server is anywhere.

Subscribes  ego/actuator_cmd      ackermann_msgs/AckermannDriveStamped: the speed and the
                                  steering angle, sized for our car (vehicle.yaml)
            safety/estop          std_msgs/Bool: true brakes at once, until false
Publishes   clock                 rosgraph_msgs/Clock: CARLA's simulated time, each step
            vehicle/odom          nav_msgs/Odometry, twist only, like aav_spine
            vehicle/status        aav_interfaces/VehicleStatus (mode COMPUTER, armed)
            vehicle/steering      aav_interfaces/ActuatorState: ego's angle, the CARLA car's
            vehicle/throttle      aav_interfaces/ActuatorState: CARLA's pedal (measured)
            vehicle/brake         aav_interfaces/ActuatorState: the same
            vehicle/wheels        aav_interfaces/WheelSpeeds: from the car's motion
            vehicle/carla/truth   nav_msgs/Odometry: where the car really is (map frame)
            sensors/imu/data_raw  sensor_msgs/Imu: CARLA's IMU, in imu_link, no orientation
            sensors/gps/fix       sensor_msgs/NavSatFix: the antenna round our datum, + noise
            sensors/camera/{front_left,front_right,rear}/image_raw and camera_info,
                                  with cameras:=true
            sensors/radar/points  sensor_msgs/PointCloud2, best effort, the TI driver's
                                  fields, with radar:=true
            sensors/lidar/points  sensor_msgs/PointCloud2, with lidar:=true
            system/source         aav_interfaces/DataSource, latched: all of it SIM

The maths is elsewhere, without ROS, and tested: frames.py (CARLA's left-handed degrees to
REP-103), control.py (ego's command to CARLA's), sensors.py, state.py, georef.py (the
Carleton map), link.py (every call to the CARLA server).

Parameters  host, port, timeout (s), town ('' keeps the server's), osm or xodr (a file:
            Carleton's roads, CARLA 0.9.x), sync (true), fixed_delta (0.05 s), realtime
            (true), vehicle (''), role_name, spawn ('', N or x,y,yaw), frame (auto, world
            or spawn), control (ackermann or pedals), cameras, radar, lidar, cmd_timeout,
            datum_lat, datum_lon (navsat.yaml's, from carla.launch.py), noise stddevs
"""

import random
import signal
import threading
import time

from aav_carla import control, frames, georef, sensors, state
from aav_carla.link import CarlaLink, load_carla
from aav_description import vehicle
from aav_interfaces.msg import ActuatorState, DataSource, SensorSource, VehicleStatus
from aav_interfaces.msg import WheelSpeeds
from ackermann_msgs.msg import AckermannDriveStamped
from builtin_interfaces.msg import Time
from nav_msgs.msg import Odometry
import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, qos_profile_sensor_data, QoSProfile, ReliabilityPolicy
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import CameraInfo, Image, Imu, NavSatFix, NavSatStatus, PointCloud2
from sensor_msgs.msg import PointField
from std_msgs.msg import Bool

RADAR_FIELDS = [PointField(name=n, offset=4 * i, datatype=PointField.FLOAT32, count=1)
                for i, n in enumerate(('x', 'y', 'z', 'intensity', 'velocity'))]
LIDAR_FIELDS = RADAR_FIELDS[:4]


def stamp(seconds):
    sec, nanosec = frames.split_seconds(seconds)
    return Time(sec=sec, nanosec=nanosec)


def cloud(seconds, frame_id, points, fields):
    """Return a PointCloud2 of N x len(fields) float32 points."""
    points = np.ascontiguousarray(points, dtype=np.float32)
    msg = PointCloud2()
    msg.header.stamp = stamp(seconds)
    msg.header.frame_id = frame_id
    msg.height = 1
    msg.width = len(points)
    msg.fields = fields
    msg.is_bigendian = False
    msg.point_step = 4 * len(fields)
    msg.row_step = msg.point_step * msg.width
    msg.is_dense = True
    msg.data = points.tobytes()
    return msg


class CarlaAdapter(Node):

    def __init__(self):
        super().__init__('carla_adapter')
        p = self.declare_parameter
        self.host = p('host', '127.0.0.1').value
        self.port = p('port', 2000).value
        self.timeout = p('timeout', 20.0).value
        self.town = p('town', '').value
        self.osm = p('osm', '').value
        self.xodr = p('xodr', '').value
        self.sync = p('sync', True).value
        self.fixed_delta = p('fixed_delta', 0.05).value
        self.pacer = state.Pacer(realtime=p('realtime', True).value)
        self.vehicle_name = p('vehicle', '').value
        self.role_name = p('role_name', 'ego_vehicle').value
        self.spawn = georef.parse_spawn(p('spawn', '').value)
        self.frame_choice = p('frame', 'auto').value
        self.mode = p('control', 'ackermann').value
        if self.mode not in ('ackermann', 'pedals'):
            raise ValueError(f'control:={self.mode}: use ackermann or pedals')
        self.chosen = sensors.chosen(cameras=p('cameras', True).value,
                                     radar=p('radar', True).value,
                                     lidar=p('lidar', True).value)
        self.watchdog = control.Watchdog(timeout=p('cmd_timeout', 0.2).value)
        self.datum = (p('datum_lat', 45.3860).value, p('datum_lon', -75.6960).value)
        self.gps_std = p('gps_stddev', 0.5).value
        self.gyro_var = p('gyro_stddev', 0.02).value ** 2
        self.accel_var = p('accel_stddev', 0.2).value ** 2
        self.speed_var = p('speed_variance', 0.01).value

        car = vehicle.load()
        self.car = car
        self.wheelbase = float(car['vehicle']['wheelbase'])
        self.track = float(car['vehicle']['track'])
        self.max_steer = float(car['vehicle']['max_steering_angle'])
        self.max_accel = float(car['actuators']['max_accel'])
        self.gps_xyz = car['sensors']['gps_link']['xyz']

        self.cmd = None
        self.estop = False
        self.sim_now = 0.0
        self.loop = control.SpeedLoop()
        self.speed = 0.0
        self.running = True

        self.clock_pub = self.create_publisher(Clock, 'clock', 10)
        self.odom_pub = self.create_publisher(Odometry, 'vehicle/odom', 10)
        self.truth_pub = self.create_publisher(Odometry, 'vehicle/carla/truth', 10)
        self.status_pub = self.create_publisher(VehicleStatus, 'vehicle/status', 10)
        self.steering_pub = self.create_publisher(ActuatorState, 'vehicle/steering', 10)
        self.throttle_pub = self.create_publisher(ActuatorState, 'vehicle/throttle', 10)
        self.brake_pub = self.create_publisher(ActuatorState, 'vehicle/brake', 10)
        self.wheels_pub = self.create_publisher(WheelSpeeds, 'vehicle/wheels', 10)
        self.imu_pub = self.create_publisher(Imu, 'sensors/imu/data_raw', 10)
        self.fix_pub = self.create_publisher(NavSatFix, 'sensors/gps/fix', 10)
        reliable = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)
        self.create_subscription(AckermannDriveStamped, 'ego/actuator_cmd', self.on_cmd, 10)
        self.create_subscription(Bool, 'safety/estop', self.on_estop, reliable)
        self.announce(sensors.sources(self.chosen))

        carla = load_carla()
        self.link = CarlaLink(carla, self.host, self.port, self.timeout,
                              log=self.get_logger().warning)
        try:
            self.start()
        except Exception:
            # Give the server back as it was: synchronous mode left on would freeze it.
            self.link.close()
            raise
        self.thread = threading.Thread(target=self.run, name='carla_tick', daemon=True)
        self.thread.start()

    # --- start-up ---

    def start(self):
        link, log = self.link, self.get_logger()
        server, client = link.versions()
        log.info(f'CARLA server {server}, client {client} at {self.host}:{self.port}')
        if server != client:
            log.warning(f'the client ({client}) is not the server ({server}): install the '
                        "server's own wheel (docs/carla.md)")
        osm = xodr = ''
        if self.osm:
            with open(self.osm) as f:
                osm = f.read()
        elif self.xodr:
            with open(self.xodr) as f:
                xodr = f.read()
        loaded = link.load(town=self.town, osm=osm, xodr=xodr, datum=self.datum)
        link.configure(self.sync, self.fixed_delta)
        log.info(f'world: {loaded}; {"synchronous" if self.sync else "asynchronous"}')

        origin = link.origin_geolocation()
        world_frame, kind = frames.map_frame(*origin, *self.datum, spawn=(0.0, 0.0, 0.0),
                                             frame=self.frame_choice)
        transform = link.spawn_transform(self.spawn, world_frame if kind == 'world' else None)
        name = link.spawn(self.vehicle_name, transform, self.role_name)
        g = link.geometry()
        self.rear_axle_x = g['rear_axle_x']
        self.geometry = control.Geometry(self.wheelbase, self.max_steer, g['wheelbase'],
                                         g['max_steer'])
        log.info(f'car: {name}, wheelbase {g["wheelbase"]:.2f} m (ours {self.wheelbase:.2f} m)')
        if kind == 'world':
            self.frame = world_frame
            log.info(f"map frame: CARLA's world, its origin at {origin[0]:.6f}, "
                     f'{origin[1]:.6f}: lined up with the datum')
        else:
            here = state.car_state(**link.readings(), frame=frames.SpawnFrame(0.0, 0.0, 0.0),
                                   rear_axle_x=self.rear_axle_x)
            self.frame = frames.SpawnFrame(here.x, here.y, here.yaw)
            log.info('map frame: the spawn point, facing east (the map is not round the datum)')
        for s in self.chosen:
            link_name = s.link
            xyz = self.car['sensors'][link_name]['xyz']
            rpy = self.car['sensors'][link_name]['rpy']
            m = frames.mount(xyz, rpy, self.rear_axle_x, g['ground_z'])
            link.attach(s, m, self.sensor_callback(s))

    def announce(self, entries):
        latched = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                             durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.source_pub = self.create_publisher(DataSource, 'system/source', latched)
        msg = DataSource(announcer=self.get_name())
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.sensors = [SensorSource(name=n, topic=t, source=SensorSource.SIM)
                       for n, t in entries]
        self.source_pub.publish(msg)

    # --- ROS in ---

    def on_cmd(self, msg):
        self.cmd = msg.drive
        self.watchdog.fed(self.sim_now)

    def on_estop(self, msg):
        if msg.data != self.estop:
            self.get_logger().warning('E-STOP' if msg.data else 'e-stop cleared')
        self.estop = msg.data

    # --- the loop: one CARLA step at a time ---

    def run(self):
        last = None
        while self.running and rclpy.ok():
            try:
                now = self.link.tick()
            except RuntimeError as e:          # the server went away, or timed out
                self.get_logger().error(f'CARLA: {e}')
                time.sleep(1.0)
                continue
            self.sim_now = now
            self.clock_pub.publish(Clock(clock=stamp(now)))
            dt = self.fixed_delta if last is None else max(now - last, 1e-3)
            last = now
            self.publish_state(now)
            self.drive(dt)
            wait = self.pacer.wait(now, time.monotonic())
            if wait > 0.0:
                time.sleep(wait)

    def drive(self, dt):
        fresh = self.watchdog.fresh(self.sim_now)
        speed = self.cmd.speed if (fresh and self.cmd is not None) else 0.0
        steer = self.cmd.steering_angle if self.cmd is not None else 0.0
        if self.estop:
            command = control.stopped()
        elif self.mode == 'ackermann':
            accel = self.cmd.acceleration if (fresh and self.cmd is not None) else 0.0
            command = control.ackermann(self.geometry, speed, steer, accel,
                                        max_accel=self.max_accel)
        else:
            command = control.pedals(self.geometry, self.loop, speed, steer, self.speed, dt)
        self.link.drive(command)
        self.steer_command = steer

    def publish_state(self, now):
        s = state.car_state(**self.link.readings(), frame=self.frame,
                            rear_axle_x=self.rear_axle_x)
        self.speed = s.speed
        t = stamp(now)

        odom = Odometry()
        odom.header.stamp = t
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.twist.twist.linear.x = s.speed
        odom.twist.twist.angular.z = s.yaw_rate
        odom.twist.covariance = state.covariance_diagonal(
            [self.speed_var, 1e-4, 1e3, 1e3, 1e3, 0.02])
        odom.pose.covariance = state.covariance_diagonal([1e3] * 6)
        self.odom_pub.publish(odom)

        truth = Odometry()
        truth.header.stamp = t
        truth.header.frame_id = 'map'
        truth.child_frame_id = 'base_link'
        truth.pose.pose.position.x = s.x
        truth.pose.pose.position.y = s.y
        q = frames.quaternion(0.0, 0.0, s.yaw)
        o = truth.pose.pose.orientation
        o.x, o.y, o.z, o.w = q
        truth.twist.twist.linear.x = s.speed
        truth.twist.twist.linear.y = s.lateral
        truth.twist.twist.angular.z = s.yaw_rate
        self.truth_pub.publish(truth)

        lat, lon, alt = state.antenna(s, self.gps_xyz, *self.datum)
        fix = NavSatFix()
        fix.header.stamp = t
        fix.header.frame_id = 'gps_link'
        fix.status.status = NavSatStatus.STATUS_FIX
        fix.status.service = NavSatStatus.SERVICE_GPS
        n_lat, n_lon, _ = frames.enu_to_geodetic(lat, lon, 0.0,
                                                 random.gauss(0.0, self.gps_std),
                                                 random.gauss(0.0, self.gps_std), 0.0)
        fix.latitude, fix.longitude, fix.altitude = n_lat, n_lon, alt
        var = self.gps_std ** 2
        fix.position_covariance = [var, 0.0, 0.0, 0.0, var, 0.0, 0.0, 0.0, 4 * var]
        fix.position_covariance_type = NavSatFix.COVARIANCE_TYPE_DIAGONAL_KNOWN
        self.fix_pub.publish(fix)

        wheels = sensors.wheel_speeds(s.speed, s.yaw_rate, self.wheelbase, self.track)
        w = WheelSpeeds(direction_measured=True, **wheels)
        w.header.stamp = t
        w.header.frame_id = 'base_link'
        self.wheels_pub.publish(w)

        front = self.link.front_wheels_deg()
        measured = self.geometry.our_angle(*front) if front is not None else float('nan')
        pedals = self.link.pedal_levels()
        status = VehicleStatus()
        status.header.stamp = t
        status.header.frame_id = 'base_link'
        status.mode = VehicleStatus.MODE_COMPUTER
        status.armed = True
        status.estop_active = bool(self.estop)
        status.speed = s.speed
        status.steering_angle = measured if front is not None else 0.0
        status.throttle, status.brake = pedals
        self.status_pub.publish(status)
        command = getattr(self, 'steer_command', 0.0)
        for pub, cmd, got in ((self.steering_pub, command, measured),
                              (self.throttle_pub, float('nan'), pedals[0]),
                              (self.brake_pub, float('nan'), pedals[1])):
            a = ActuatorState(command=float(cmd), measured=float(got))
            a.header.stamp = t
            a.header.frame_id = 'base_link'
            pub.publish(a)

    # --- sensors: called on CARLA's threads ---

    def sensor_callback(self, s):
        if s.blueprint == 'sensor.other.imu':
            return self.on_imu
        if s.blueprint == 'sensor.camera.rgb':
            image_pub = self.create_publisher(
                Image, s.topic, QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE))
            info_pub = self.create_publisher(CameraInfo, sensors.info_topic(s.topic), 10)
            return lambda data: self.on_camera(data, s, image_pub, info_pub)
        if s.blueprint == 'sensor.other.radar':
            pub = self.create_publisher(PointCloud2, s.topic, qos_profile_sensor_data)
            return lambda data: pub.publish(cloud(data.timestamp, s.link,
                                                  sensors.radar_points(bytes(data.raw_data)),
                                                  RADAR_FIELDS))
        if s.blueprint == 'sensor.lidar.ray_cast':
            pub = self.create_publisher(PointCloud2, s.topic, 10)
            return lambda data: pub.publish(cloud(data.timestamp, s.link,
                                                  sensors.lidar_points(bytes(data.raw_data)),
                                                  LIDAR_FIELDS))
        raise ValueError(f'no publisher for {s.blueprint}')

    def on_imu(self, data):
        msg = Imu()
        msg.header.stamp = stamp(data.timestamp)
        msg.header.frame_id = 'imu_link'
        a, g = data.accelerometer, data.gyroscope
        ax, ay, az = frames.location_to_ros(a.x, a.y, a.z)
        gx, gy, gz = frames.gyroscope_to_ros(g.x, g.y, g.z)
        msg.linear_acceleration.x, msg.linear_acceleration.y = ax, ay
        msg.linear_acceleration.z = az
        msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z = gx, gy, gz
        msg.orientation_covariance[0] = -1.0      # like the real IMU: no orientation
        for i in (0, 4, 8):
            msg.angular_velocity_covariance[i] = self.gyro_var
            msg.linear_acceleration_covariance[i] = self.accel_var
        self.imu_pub.publish(msg)

    def on_camera(self, data, s, image_pub, info_pub):
        t = stamp(data.timestamp)
        img = Image()
        img.header.stamp = t
        img.header.frame_id = s.link
        img.width, img.height = data.width, data.height
        img.encoding = 'bgr8'
        img.step = 3 * data.width
        img.data = sensors.bgra_to_bgr(bytes(data.raw_data), data.width, data.height)
        image_pub.publish(img)
        info = CameraInfo(**sensors.camera_matrix(data.width, data.height, data.fov))
        info.header.stamp = t
        info.header.frame_id = s.link
        info_pub.publish(info)

    def stop(self):
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=2.0)
        self.link.close()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = CarlaAdapter()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except RuntimeError as e:
        # No client, no server: say why in one line, not a traceback.
        if rclpy.ok():
            print(f'carla_adapter: {e}')
            raise SystemExit(1)
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if node is not None:
            if hasattr(node, 'thread'):
                node.stop()
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
