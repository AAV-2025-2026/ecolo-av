"""
The CARLA car's state, as our topics want it. No ROS and no `carla` imports.

carla_adapter reads the car actor each tick (its transform, velocity and angular
velocity: plain numbers, CARLA's axes and units) and car_state() turns them into what
the real car's backends publish:

  base_link   the ground under the rear axle, in our map frame (frames.map_frame):
              /vehicle/carla/truth
  speed       forward, m/s, + ahead: /vehicle/odom, /vehicle/status
  yaw rate    rad/s, + left: /vehicle/odom
  antenna     the GPS antenna (vehicle.yaml gps_link), as latitude and longitude round
              the datum: /sensors/gps/fix (carla_adapter adds the noise)

The Pacer keeps a synchronous CARLA in step with the wall clock.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from aav_carla import frames


@dataclass(frozen=True)
class CarState:
    """Where the car is and how it moves, in our map frame (ROS axes, m, rad, s)."""

    x: float              # base_link
    y: float
    yaw: float
    speed: float          # forward
    lateral: float        # leftward, at base_link (0 unless it skids)
    yaw_rate: float


def car_state(location, rotation, velocity, angular_velocity, frame: frames.SpawnFrame,
              rear_axle_x: float) -> CarState:
    """
    Return the car's state from its actor's readings.

    location (m), velocity (m/s): CARLA's x, y, z. rotation: roll, pitch, yaw (degrees);
    angular_velocity: degrees per second about CARLA's x, y, z. rear_axle_x: the rear
    axle's x in the actor's frame (m, frames.rear_axle).
    """
    x, y, _ = frames.location_to_ros(*location)
    _, _, yaw = frames.rotation_to_ros(*rotation)
    vx, vy, _ = frames.location_to_ros(*velocity)
    _, _, yaw_rate = frames.angular_velocity_to_ros(*angular_velocity)
    # The actor's origin is near the car's middle: base_link is rear_axle_x along it.
    bx, by = frames.offset(x, y, yaw, rear_axle_x, 0.0)
    fwd, left = frames.body_velocity(vx, vy, yaw)
    # A rigid body: a point d ahead of the origin moves sideways by yaw_rate * d more, so
    # the rear axle (d < 0) slides less than the middle when the car turns.
    left_rear = left + yaw_rate * rear_axle_x
    mx, my = frame.point(bx, by)
    return CarState(x=mx, y=my, yaw=frame.heading(yaw), speed=fwd, lateral=left_rear,
                    yaw_rate=yaw_rate)


def antenna(state: CarState, gps_xyz, datum_lat: float, datum_lon: float,
            datum_alt: float = 0.0) -> tuple[float, float, float]:
    """
    Return the GPS antenna's latitude, longitude and altitude.

    gps_xyz: the antenna's mount from base_link (vehicle.yaml gps_link, m). Our map frame
    is x east, y north from the datum (navsat.yaml), so its x, y are metres east, north.
    """
    gx, gy = frames.offset(state.x, state.y, state.yaw, float(gps_xyz[0]), float(gps_xyz[1]))
    return frames.enu_to_geodetic(datum_lat, datum_lon, datum_alt, gx, gy, float(gps_xyz[2]))


@dataclass
class Pacer:
    """
    Keep simulated time from running ahead of the wall clock.

    A synchronous CARLA steps as fast as it can when asked: faster than real time on a big
    GPU. Our nodes (Nav2, the EKFs, the HUD) are tuned for real time, so carla_adapter
    waits after a step until the wall clock catches up. realtime=False: no waiting.
    """

    realtime: bool = True
    start_sim: float | None = None
    start_wall: float | None = None

    def wait(self, sim: float, wall: float) -> float:
        """Return how long to sleep (s) after the step that reached sim (s) at wall (s)."""
        if not self.realtime:
            return 0.0
        if self.start_sim is None or sim < self.start_sim:
            # The first step, or the world was reloaded: start again from here.
            self.start_sim, self.start_wall = sim, wall
            return 0.0
        ahead = (sim - self.start_sim) - (wall - self.start_wall)
        if ahead < -1.0:
            # Over a second behind (a slow GPU): don't try to catch up, start again.
            self.start_sim, self.start_wall = sim, wall
            return 0.0
        return max(0.0, ahead)


def covariance_diagonal(values) -> list[float]:
    """Return a row-major covariance matrix with these values on its diagonal."""
    n = len(values)
    out = [0.0] * (n * n)
    for i, v in enumerate(values):
        out[i * n + i] = float(v)
    return out


def finite(*values) -> bool:
    """Return whether every value is a finite number."""
    return all(math.isfinite(v) for v in values)
