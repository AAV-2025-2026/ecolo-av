"""
A pretend `carla` module: just enough of CARLA's Python API for link.py's tests.

It follows CARLA's documented conventions, the ones our conversions depend on: Unreal's
left-handed axes (x forward, y RIGHT, z up), yaw in degrees and + to the right, steering
+ to the right, wheel positions in world centimetres (0.9.x), angular velocity in degrees
per second. Its car is a kinematic bicycle that does what the Ackermann command says.
"""

from dataclasses import dataclass, field
import math


@dataclass
class Location:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


Vector3D = Location


@dataclass
class Rotation:
    pitch: float = 0.0
    yaw: float = 0.0
    roll: float = 0.0


@dataclass
class Transform:
    location: Location = field(default_factory=Location)
    rotation: Rotation = field(default_factory=Rotation)


@dataclass
class GeoLocation:
    latitude: float
    longitude: float
    altitude: float = 0.0


class Osm2OdrSettings:
    def __init__(self):
        self.proj_string = '+proj=tmerc'
        self.center_map = False
        self.use_offsets = False


class Osm2Odr:
    calls = []

    @staticmethod
    def convert(osm, settings):
        Osm2Odr.calls.append((osm, settings))
        return f'<OpenDRIVE><geoReference>{settings.proj_string}</geoReference></OpenDRIVE>'


class OpendriveGenerationParameters:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


@dataclass
class VehicleControl:
    throttle: float = 0.0
    steer: float = 0.0
    brake: float = 0.0
    hand_brake: bool = False
    reverse: bool = False


@dataclass
class VehicleAckermannControl:
    steer: float = 0.0
    steer_speed: float = 0.0
    speed: float = 0.0
    acceleration: float = 0.0
    jerk: float = 0.0


class VehicleWheelLocation:
    FL_Wheel = 0
    FR_Wheel = 1
    BL_Wheel = 2
    BR_Wheel = 3


class Blueprint:
    def __init__(self, bp_id, attributes=()):
        self.id = bp_id
        self.attributes = dict.fromkeys(attributes, '')

    def has_attribute(self, key):
        return key in self.attributes

    def set_attribute(self, key, value):
        assert isinstance(value, str), 'CARLA takes attributes as strings'
        self.attributes[key] = value


SENSOR_ATTRIBUTES = {
    'sensor.camera.rgb': ('image_size_x', 'image_size_y', 'fov', 'sensor_tick'),
    'sensor.other.imu': ('sensor_tick',),
    'sensor.other.radar': ('horizontal_fov', 'vertical_fov', 'range', 'points_per_second',
                           'sensor_tick'),
    'sensor.lidar.ray_cast': ('channels', 'range', 'upper_fov', 'lower_fov',
                              'rotation_frequency', 'points_per_second', 'sensor_tick'),
}


class Library(list):
    def filter(self, pattern):  # noqa: A003 (CARLA's own name)
        prefix = pattern.rstrip('*')
        return [b for b in self if b.id.startswith(prefix)]

    def find(self, bp_id):
        for b in self:
            if b.id == bp_id:
                return b
        raise IndexError(bp_id)


@dataclass
class Wheel:
    position: Location
    max_steer_angle: float


@dataclass
class Physics:
    wheels: list


@dataclass
class Box:
    location: Location
    extent: Location


class Actor:
    def __init__(self, world, blueprint, transform, parent=None):
        self.world = world
        self.blueprint = blueprint
        self.transform = transform
        self.parent = parent
        self.alive = True
        self.callback = None

    def destroy(self):
        self.alive = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.callback = None


class Vehicle(Actor):
    WHEELBASE = 2.9            # m: CARLA's cars are bigger than ours
    HALF_TRACK = 0.8
    MAX_STEER = 70.0           # degrees

    def __init__(self, *args):
        super().__init__(*args)
        self.speed = 0.0
        self.yaw_rate = 0.0    # deg/s, + right (Unreal)
        self.steer_deg = 0.0   # + right
        self.control = VehicleControl()
        self.bounding_box = Box(Location(0.0, 0.0, 0.75), Location(2.3, 1.0, 0.75))

    def get_transform(self):
        return self.transform

    def get_velocity(self):
        yaw = math.radians(self.transform.rotation.yaw)
        return Location(self.speed * math.cos(yaw), self.speed * math.sin(yaw), 0.0)

    def get_angular_velocity(self):
        return Location(0.0, 0.0, self.yaw_rate)

    def get_physics_control(self):
        t = self.transform
        yaw = math.radians(t.rotation.yaw)
        half = self.WHEELBASE / 2
        body = [(half, -self.HALF_TRACK), (half, self.HALF_TRACK),
                (-half, -self.HALF_TRACK), (-half, self.HALF_TRACK)]   # FL, FR, RL, RR
        wheels = []
        for x, y in body:
            wx = t.location.x + x * math.cos(yaw) - y * math.sin(yaw)
            wy = t.location.y + x * math.sin(yaw) + y * math.cos(yaw)
            wheels.append(Wheel(Location(wx * 100, wy * 100, 30.0), self.MAX_STEER))
        return Physics(wheels)

    def get_wheel_steer_angle(self, where):
        return self.steer_deg

    def get_control(self):
        return self.control

    def apply_ackermann_control(self, c):
        self.speed = c.speed
        self.steer_deg = math.degrees(c.steer)
        self.control = VehicleControl(throttle=0.3 if c.speed else 0.0)

    def apply_control(self, c):
        self.control = c
        self.steer_deg = c.steer * self.MAX_STEER
        push = c.throttle * (-1 if c.reverse else 1) - c.brake * math.copysign(1, self.speed)
        self.speed += push * 0.1

    def step(self, dt):
        # The kinematic bicycle, in Unreal's axes: steering right turns right (yaw +).
        self.yaw_rate = math.degrees(self.speed * math.tan(math.radians(self.steer_deg))
                                     / self.WHEELBASE)
        r = self.transform.rotation
        loc = self.transform.location
        yaw = math.radians(r.yaw)
        loc.x += self.speed * math.cos(yaw) * dt
        loc.y += self.speed * math.sin(yaw) * dt
        r.yaw += self.yaw_rate * dt


@dataclass
class Waypoint:
    transform: Transform


class Map:
    def __init__(self, origin=(0.0, 0.0), spawn_points=None):
        self.origin = origin
        self.spawn_points = spawn_points if spawn_points is not None else [
            Transform(Location(10.0, 20.0, 0.5), Rotation(yaw=90.0)),
            Transform(Location(-5.0, 0.0, 0.5), Rotation(yaw=0.0))]

    def transform_to_geolocation(self, location):
        return GeoLocation(*self.origin)

    def get_spawn_points(self):
        return self.spawn_points

    def get_waypoint(self, location):
        return Waypoint(Transform(Location(location.x, location.y, 0.2)))


@dataclass
class Settings:
    synchronous_mode: bool = False
    fixed_delta_seconds: float = None


@dataclass
class Timestamp:
    elapsed_seconds: float


@dataclass
class Snapshot:
    timestamp: Timestamp


class World:
    def __init__(self, name='Town10HD_Opt', town_map=None):
        self.name = name
        self.map = town_map or Map()
        self.settings = Settings()
        self.time = 0.0
        self.actors = []
        self.library = Library(
            [Blueprint('vehicle.lincoln.mkz', ('role_name',)),
             Blueprint('vehicle.mini.cooper', ('role_name',)),
             Blueprint('walker.pedestrian.0001')]
            + [Blueprint(k, v) for k, v in SENSOR_ATTRIBUTES.items()])
        self.blocked = False

    def get_settings(self):
        return Settings(self.settings.synchronous_mode, self.settings.fixed_delta_seconds)

    def apply_settings(self, s):
        self.settings = s

    def get_map(self):
        return self.map

    def get_blueprint_library(self):
        return self.library

    def try_spawn_actor(self, blueprint, transform):
        if self.blocked:
            return None
        v = Vehicle(self, blueprint, Transform(Location(**vars(transform.location)),
                                               Rotation(**vars(transform.rotation))))
        self.actors.append(v)
        return v

    def spawn_actor(self, blueprint, transform, attach_to=None):
        a = Actor(self, blueprint, transform, attach_to)
        self.actors.append(a)
        return a

    def tick(self):
        dt = self.settings.fixed_delta_seconds or 0.05
        self.time += dt
        for a in self.actors:
            if isinstance(a, Vehicle) and a.alive:
                a.step(dt)
        return int(self.time / dt)

    def get_snapshot(self):
        return Snapshot(Timestamp(self.time))

    def wait_for_tick(self):
        self.tick()
        return self.get_snapshot()


class Client:
    def __init__(self, host, port):
        self.host, self.port = host, port
        self.world = World()
        self.timeout = None
        self.generated = None

    def set_timeout(self, seconds):
        self.timeout = seconds

    def get_server_version(self):
        return '0.10.0'

    def get_client_version(self):
        return '0.10.0'

    def get_world(self):
        return self.world

    def load_world(self, town):
        self.world = World(town)
        return self.world

    def generate_opendrive_world(self, xodr, params):
        self.generated = (xodr, params)
        self.world = World('OpenDRIVE', Map(origin=(45.3860, -75.6960)))
        return self.world
