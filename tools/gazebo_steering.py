#!/usr/bin/env python3
"""
Gazebo's steering against the actuator model's: how much later Gazebo's wheels turn.

The actuator model (aav_gazebo actuator_model.py) steers with vehicle.yaml's steer_rate and
steer_lag; gazebo_adapter sends its angle to Gazebo 50 times a second, and Gazebo's
AckermannSteering plugin turns the joints at steer_p_gain x the error (aav.gazebo.xacro).
That last step is a lag the model doesn't have (docs/vehicle-model.md, section 6): 0.11 s
with steer_p_gain 10, 0.022 s with 100 (TODO 52c). This records both and fits it:

    pixi run sim world:=empty gui:=false rviz:=false nav:=false     (one terminal)
    tools/ros.sh --local python3 tools/gazebo_steering.py --seconds 40   (a second)
    pixi run actuator-test steer-rate --sim                          (a third: the steps)

Subscribes  /joint_states     sensor_msgs/JointState: Gazebo's two steering joints, made
                              into the centre wheel's angle (aav_gazebo wheels.centre_steering)
            /vehicle/steering aav_interfaces/ActuatorState: the model's angle (measured)

Prints the fit (aav_actuator_tests analysis.fit_follower): the first-order lag that best
turns the model's angle into Gazebo's, the error left (rms), and the error with no lag at
all. 0 s would mean Gazebo's car steers exactly as vehicle.yaml says. On Gazebo's clock
(use_sim_time). A busy computer spoils it: gazebo_adapter's 50 Hz ticks then stall (gaps
of up to 0.2 s of Gazebo's time), and the fit grows; run it twice.
"""

import argparse
import math
import sys
import time

from aav_actuator_tests import analysis
from aav_gazebo import wheels
from aav_interfaces.msg import ActuatorState
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from sensor_msgs.msg import JointState


def seconds(stamp):
    """Return a ROS stamp in seconds."""
    return stamp.sec + stamp.nanosec * 1e-9


class Recorder(Node):
    """Gazebo's steering joints and the model's angle, on Gazebo's clock."""

    def __init__(self):
        super().__init__('gazebo_steering', parameter_overrides=[
            Parameter('use_sim_time', value=True)])
        self.model, self.gazebo = [], []
        self.create_subscription(JointState, '/joint_states', self.on_joints, 50)
        self.create_subscription(ActuatorState, '/vehicle/steering', self.on_model, 50)

    def on_joints(self, msg):
        """Keep the centre wheel's angle Gazebo's joints give."""
        angle = wheels.centre_steering(msg.name, msg.position)
        if math.isfinite(angle):
            self.gazebo.append((seconds(msg.header.stamp), angle))

    def on_model(self, msg):
        """Keep the actuator model's angle (what gazebo_adapter sends Gazebo)."""
        self.model.append((seconds(msg.header.stamp), msg.measured))


def main():
    """Record for --seconds, then print the fit."""
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0].strip())
    parser.add_argument('--seconds', type=float, default=40.0,
                        help="how long to record (this computer's time)")
    parser.add_argument('--save', help='also write both angles to this CSV (t, source, rad)')
    args = parser.parse_args()
    rclpy.init()
    rec = Recorder()
    stop = time.monotonic() + args.seconds      # wall time: Gazebo's clock may not run yet
    while time.monotonic() < stop:
        rclpy.spin_once(rec, timeout_sec=0.05)
    got = analysis.fit_follower(rec.model, rec.gazebo)
    if args.save:
        with open(args.save, 'w') as f:
            f.write('t,source,angle\n')
            for source, samples in (('model', rec.model), ('gazebo', rec.gazebo)):
                f.writelines(f'{t:.4f},{source},{a:.5f}\n' for t, a in samples)
    rec.destroy_node()
    rclpy.try_shutdown()
    if got is None:
        print(f'not enough steering to fit ({len(rec.gazebo)} samples): run '
              'pixi run actuator-test steer-rate --sim while this records')
        return 1
    print(f"Gazebo's wheels behind the model's angle, {got.samples} samples:")
    print(f'  no lag:          {got.rms_none * 1000:.1f} mrad rms off')
    print(f'  first-order lag: {got.lag:.3f} s, {got.rms_lagged * 1000:.1f} mrad rms off')
    return 0


if __name__ == '__main__':
    sys.exit(main())
