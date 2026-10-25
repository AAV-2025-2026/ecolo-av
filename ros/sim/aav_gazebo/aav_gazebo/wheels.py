"""
Each wheel's ground speed from Gazebo's joint states, for /vehicle/wheels. No ROS here.

The wheel joints turn about their +y axis (aav.urdf.xacro): positive spin rolls the car
forward, so speed = spin (rad/s) x the wheel's radius.
"""

import math

# WheelSpeeds field -> the URDF's joint.
JOINTS = {
    'front_left': 'front_left_wheel_joint',
    'front_right': 'front_right_wheel_joint',
    'rear_left': 'rear_left_wheel_joint',
    'rear_right': 'rear_right_wheel_joint',
}


def ground_speeds(names, velocities, radius):
    """Return {field: m/s} for each wheel; NaN for a wheel the message doesn't have."""
    spin = dict(zip(names, velocities))
    return {field: spin[joint] * radius if joint in spin else math.nan
            for field, joint in JOINTS.items()}
