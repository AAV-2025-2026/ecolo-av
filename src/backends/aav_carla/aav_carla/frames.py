"""
CARLA's frames to ours (REP-103, REP-105). No ROS and no `carla` imports.

CARLA is Unreal Engine: a LEFT-handed frame, and degrees.

  CARLA (Unreal)                     ROS (ours)
  x forward                          x forward
  y RIGHT                            y LEFT
  z up                               z up
  pitch + = nose up      (degrees)   pitch + = nose DOWN  (radians)
  yaw   + = turn right   (degrees)   yaw   + = turn LEFT  (radians)
  roll  + = right side down          roll  + = right side down
  metres (the Python API)            metres

So a point or a velocity flips its y; an orientation keeps roll and flips pitch and yaw.
These are the same rules as CARLA's own ROS bridge (carla-simulator/ros-bridge,
carla_common/transforms.py, MIT).

The map frame: map (0, 0) is navsat.yaml's datum, x east, and the car starts there facing
east, on the bench and in Gazebo alike (the EKFs start at the origin, facing east, and
the IMU has no compass). A CARLA car starts at a town's spawn point instead, so SpawnFrame
moves and turns CARLA's world until the spawn point is the origin, facing east. GPS and
the truth are made in that frame; GPS then turns it into latitude and longitude around
the datum.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

# The earth, for the flat-earth step from metres to degrees near the datum (WGS-84).
EARTH_A = 6378137.0                   # m, equatorial radius
EARTH_E2 = 6.69437999014e-3           # first eccentricity squared


def location_to_ros(x: float, y: float, z: float) -> tuple[float, float, float]:
    """A CARLA point or vector (m, m/s, m/s^2) in ROS axes: y flips."""
    return (x, -y, z)


def ros_to_location(x: float, y: float, z: float) -> tuple[float, float, float]:
    """A ROS point in CARLA axes: y flips back."""
    return (x, -y, z)


def rotation_to_ros(roll: float, pitch: float, yaw: float) -> tuple[float, float, float]:
    """CARLA's roll, pitch, yaw (degrees) as ROS's (radians): pitch and yaw flip."""
    return (math.radians(roll), -math.radians(pitch), -math.radians(yaw))


def ros_to_rotation(roll: float, pitch: float, yaw: float) -> tuple[float, float, float]:
    """ROS's roll, pitch, yaw (radians) as CARLA's (degrees)."""
    return (math.degrees(roll), -math.degrees(pitch), -math.degrees(yaw))


def angular_velocity_to_ros(x: float, y: float, z: float) -> tuple[float, float, float]:
    """
    An actor's angular velocity (Actor.get_angular_velocity: degrees per second, about
    CARLA's x, y and z) in rad/s about ROS's axes, as the rotation above: pitch and yaw
    rates flip.
    """
    return (math.radians(x), -math.radians(y), -math.radians(z))


def gyroscope_to_ros(x: float, y: float, z: float) -> tuple[float, float, float]:
    """
    The IMU sensor's gyroscope (rad/s) about ROS's axes, as CARLA's ROS bridge does it
    (ros-bridge carla_ros_bridge/imu.py: -x, y, -z). The yaw rate (z), the one our
    EKFs fuse, flips: turning left reads negative in CARLA. The roll and pitch rates follow
    the bridge and are untested here (docs/carla.md).
    """
    return (-x, y, -z)


def quaternion(roll: float, pitch: float, yaw: float) -> tuple[float, float, float, float]:
    """Roll, pitch, yaw (radians, applied yaw then pitch then roll) as x, y, z, w."""
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return (sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy,
            cr * cp * cy + sr * sp * sy)


def wrap(angle: float) -> float:
    """An angle in (-pi, pi]."""
    a = math.fmod(angle + math.pi, 2 * math.pi)
    if a <= 0.0:
        a += 2 * math.pi
    return a - math.pi


def body_velocity(vx: float, vy: float, yaw: float) -> tuple[float, float]:
    """A velocity in the world's ROS axes, as forward and leftward speed in the car's."""
    c, s = math.cos(yaw), math.sin(yaw)
    return (c * vx + s * vy, -s * vx + c * vy)


@dataclass(frozen=True)
class SpawnFrame:
    """
    CARLA's world (already in ROS axes) moved and turned so the spawn point is the origin,
    facing east: where the car starts on the bench and in Gazebo.

    x0, y0: the spawn point (m, ROS axes); yaw0: the car's heading there (rad, ROS).
    """

    x0: float
    y0: float
    yaw0: float

    def point(self, x: float, y: float) -> tuple[float, float]:
        """A world point (ROS axes) in this frame."""
        dx, dy = x - self.x0, y - self.y0
        c, s = math.cos(-self.yaw0), math.sin(-self.yaw0)
        return (c * dx - s * dy, s * dx + c * dy)

    def vector(self, vx: float, vy: float) -> tuple[float, float]:
        """A world vector (a velocity) in this frame: only turned."""
        c, s = math.cos(-self.yaw0), math.sin(-self.yaw0)
        return (c * vx - s * vy, s * vx + c * vy)

    def heading(self, yaw: float) -> float:
        """A world heading (rad, ROS) in this frame."""
        return wrap(yaw - self.yaw0)


def enu_to_geodetic(lat0: float, lon0: float, alt0: float,
                    east: float, north: float, up: float) -> tuple[float, float, float]:
    """
    Metres east, north and up of (lat0, lon0, alt0) as latitude, longitude (degrees) and
    altitude (m). A flat earth at the datum: good to centimetres over a few kilometres,
    which is all a CARLA town is.
    """
    phi = math.radians(lat0)
    w = math.sqrt(1.0 - EARTH_E2 * math.sin(phi) ** 2)
    meridian = EARTH_A * (1.0 - EARTH_E2) / w ** 3      # m per radian of latitude
    normal = EARTH_A / w                                # m per radian of longitude / cos
    lat = lat0 + math.degrees(north / meridian)
    lon = lon0 + math.degrees(east / (normal * math.cos(phi)))
    return (lat, lon, alt0 + up)


@dataclass(frozen=True)
class Mount:
    """Where a sensor sits on the CARLA car: CARLA's location (m) and rotation (deg)."""

    x: float
    y: float
    z: float
    roll: float
    pitch: float
    yaw: float


def mount(xyz, rpy, rear_axle_x: float, ground_z: float) -> Mount:
    """
    A sensor's vehicle.yaml mount (from base_link: ROS axes, m and rad) as a CARLA
    attachment to the car actor.

    base_link is on the ground under the rear axle; a CARLA car's own origin is
    somewhere else (near its middle). rear_axle_x is the rear axle's x, and ground_z the
    ground's z, in the actor's frame (m, CARLA axes): see rear_axle() and the bounding box.
    """
    x, y, z = ros_to_location(*(float(v) for v in xyz))
    roll, pitch, yaw = ros_to_rotation(*(float(v) for v in rpy))
    return Mount(x + rear_axle_x, y, z + ground_z, roll, pitch, yaw)


def to_actor(px: float, py: float, ax: float, ay: float, yaw_deg: float) -> tuple[float, float]:
    """A world point (CARLA axes, m) in the frame of an actor at (ax, ay), turned yaw_deg."""
    dx, dy = px - ax, py - ay
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    # Turning by -yaw undoes the actor's turn. The same formula holds in a left-handed
    # frame, as yaw there is measured from x towards y, too.
    return (c * dx + s * dy, -s * dx + c * dy)


def rear_axle(wheels_xy: list[tuple[float, float]]) -> tuple[float, float]:
    """
    The rear axle's x, and the wheelbase (m), from the four wheels' x, y in the actor's
    frame, in CARLA's order: front left, front right, rear left, rear right.
    """
    if len(wheels_xy) != 4:
        raise ValueError(f'a car has 4 wheels in CARLA, not {len(wheels_xy)}')
    front = (wheels_xy[0][0] + wheels_xy[1][0]) / 2
    rear = (wheels_xy[2][0] + wheels_xy[3][0]) / 2
    wheelbase = front - rear
    if wheelbase <= 0.0:
        raise ValueError(f'the front wheels are not ahead of the rear ones: {wheels_xy}')
    return (rear, wheelbase)


def offset(x: float, y: float, yaw: float, dx: float, dy: float) -> tuple[float, float]:
    """The point (dx, dy) ahead and left of a car at (x, y) heading yaw (ROS axes, m, rad)."""
    c, s = math.cos(yaw), math.sin(yaw)
    return (x + c * dx - s * dy, y + s * dx + c * dy)


def split_seconds(seconds: float) -> tuple[int, int]:
    """CARLA's simulated time (s, a float) as a ROS stamp's sec and nanosec."""
    nanoseconds = round(seconds * 1e9)
    return (nanoseconds // 1_000_000_000, nanoseconds % 1_000_000_000)
