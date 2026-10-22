"""
Sensor faults on purpose, in Gazebo: what a broken sensor sends instead. No ROS here.

Each of Gazebo's sensor nodes passes its sensor on through a Fault (NODES; READ-ME-FULL-
SIMULATION.md step 6; docs/simulation.md, "Sensor failures on purpose"). Set one while the
sim runs:

    pixi run sim-fault gps stop        (ros2 param set /gazebo_gps fault.gps stop)
    pixi run sim-fault gps ok          (back to normal)

The modes, and what they stand for on the car:

  ok      passed on as it is
  stop    nothing sent: a cable pulled, a driver crashed, a GPS under a bridge
  freeze  the last good message again, with fresh stamps: a driver stuck in a loop.
          It looks alive: only the values give it away
  nan     NaN in every number: a driver that parsed garbage
  jump    the GPS only: the position jumps JUMP_NORTH m north and stays there (a bad
          multipath fix, an RTK fix on the wrong integer)

The sensors: gps (/sensors/gps/fix), imu (/sensors/imu/data_raw), odom (the wheels:
/vehicle/odom and /vehicle/wheels), radar (/sensors/radar/points) and camera (the front
left camera's picture, only with faults:=true, which routes it through gazebo_camera).
"""

import copy
from typing import Optional

SENSORS = {
    'gps': ('ok', 'stop', 'freeze', 'nan', 'jump'),
    'imu': ('ok', 'stop', 'freeze', 'nan'),
    'odom': ('ok', 'stop', 'freeze', 'nan'),
    'radar': ('ok', 'stop', 'freeze'),
    'camera': ('ok', 'stop', 'freeze'),
}
# Which node passes each sensor on, and so takes its fault.<sensor> parameter: one node
# per sensor (relay.py); the wheels go with the car, in gazebo_adapter.
NODES = {
    'gps': 'gazebo_gps',
    'imu': 'gazebo_imu',
    'odom': 'gazebo_adapter',
    'radar': 'gazebo_radar',
    'camera': 'gazebo_camera',
}
JUMP_NORTH = 20.0               # m
METRES_PER_DEGREE = 111195.0    # of latitude, on a 6371 km Earth


def check(sensor: str, mode: str) -> Optional[str]:
    """Return why this sensor can't have this fault, or None if it can."""
    if sensor not in SENSORS:
        return f'no sensor {sensor!r}: pick one of {", ".join(SENSORS)}'
    if mode not in SENSORS[sensor]:
        return f'{sensor} has no {mode!r} fault: pick one of {", ".join(SENSORS[sensor])}'
    return None


def jumped(latitude: float, metres: float = JUMP_NORTH) -> float:
    """Return the latitude `metres` further north."""
    return latitude + metres / METRES_PER_DEGREE


class Fault:
    """One sensor's fault: decides what goes out in place of each message."""

    def __init__(self, sensor: str):
        self.sensor = sensor
        self.mode = 'ok'
        self.held = None        # the last message passed on while ok: what freeze repeats

    def switch(self, mode: str):
        why = check(self.sensor, mode)
        if why is not None:
            raise ValueError(why)
        self.mode = mode

    def apply(self, msg, nan=None, jump=None):
        """
        Return what to send for msg, or None to send nothing.

        nan(msg) and jump(msg) change a message in place: the caller knows its type. They
        get a copy, so the held message stays good.
        """
        if self.mode == 'ok':
            self.held = msg
            return msg
        if self.mode == 'stop':
            return None
        if self.mode == 'freeze':
            return copy.deepcopy(self.held) if self.held is not None else None
        out = copy.deepcopy(msg)
        (nan if self.mode == 'nan' else jump)(out)
        return out


CAMERA = '/sensors/camera/front_left/image_raw'
CAMERA_RELAYED = '/gazebo/camera/front_left/image_raw'


def relayed(bridge):
    """
    Return the road bridge's entries with the front left picture sent to gazebo_camera.

    bridge is bridge_road.yaml, loaded. The picture goes to CAMERA_RELAYED instead, for
    gazebo_camera to pass on through its fault (gazebo.launch.py faults:=true).
    """
    out = copy.deepcopy(bridge)
    for entry in out:
        if entry['ros_topic_name'] == CAMERA:
            entry['ros_topic_name'] = CAMERA_RELAYED
    return out
