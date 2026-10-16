"""
ghost: place or remove the pretend obstacle from a terminal (pixi run ghost ...).

    pixi run ghost ahead 10        a ghost 10 m in front of the car's bumper
    pixi run ghost at 20 0         a ghost at map x 20, y 0
    pixi run ghost size 0.3 1.2    a post instead of a person
    pixi run ghost off             take it away

Calls  /ghost_obstacle/set_parameters_atomically (rcl_interfaces): every value of one
       command at once, so the ghost never lands at a half-changed place. The command's
       meaning is in ghost.py (command).
"""

import sys

from aav_ghost.ghost import command
import rclpy
from rclpy.parameter import Parameter
from rclpy.parameter_client import AsyncParameterClient

NODE = '/ghost_obstacle'


def main(args=None):
    words = sys.argv[1:] if args is None else args
    try:
        values = command(words)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    rclpy.init()
    node = rclpy.create_node('ghost_cli')
    try:
        client = AsyncParameterClient(node, NODE)
        if not client.wait_for_services(timeout_sec=10.0):
            print(f'No {NODE}: start Gazebo or the car with ghost:=true', file=sys.stderr)
            return 1
        future = client.set_parameters_atomically(
            [Parameter(name, value=value) for name, value in values.items()])
        rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)
        result = future.result()
        if result is None or not result.result.successful:
            reason = result.result.reason if result is not None else 'no answer in 10 s'
            print(f'{NODE} refused: {reason}', file=sys.stderr)
            return 1
        print('ghost: ' + ', '.join(f'{k} {v}' for k, v in values.items()))
        return 0
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    sys.exit(main())
