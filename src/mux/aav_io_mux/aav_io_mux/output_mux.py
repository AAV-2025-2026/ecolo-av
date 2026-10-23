"""
output_mux: passes ego's commands to one target, only while every source is that target's.

Subscribes  ego/actuator_cmd          ackermann_msgs/AckermannDriveStamped (ego, 50 Hz)
            system/sensor_mux/state   aav_interfaces/SourceCheck (the sensor mux, 2 Hz)
            system/source             aav_interfaces/DataSource, latched
Publishes   control/<target>/actuator_cmd  ackermann_msgs/AckermannDriveStamped: ego's
                                      command, unchanged, while the gate is open
            safety/output_mux/state   std_msgs/String, 2 Hz and on each change: OPEN, WAIT
                                      or STOP, the target, and why
Serves      safety/output_mux/clear   std_srvs/Trigger: a person reopens a latched stop

Parameters  target (car; gazebo, turtle, carla or bench), settle (2.0 s), stale_after
            (3.0 s)

The target decides the source its data must come from: car REAL; gazebo, turtle and
carla SIM; bench BENCH (provenance.TARGETS). Each backend reads only its own target's
topic, so a simulator's ego can never reach the real car's backend.

The gate (provenance.Gate) opens once the sensor mux says ok for that source, nothing on
/system/source says otherwise, and both have held for `settle` s. Closed, nothing goes
out, and each backend's own timeout brakes the car (spine_bridge 0.1 s, then the spine's
100 ms watchdog; legacy_uart_bridge 0.3 s; Gazebo 0.2 s).

Evidence latches the stop: an announcement of another source, or the sensor mux's
problems. It stays stopped until a person calls /safety/output_mux/clear, which works
only once the evidence has gone. Doubt only holds it shut, and it reopens by itself after
`settle` s of all clear: a sensor mux not heard yet or quiet for `stale_after` s, or its
doubts. Its clock is a steady one, not simulated time.
"""

import signal
import time

from aav_interfaces.msg import DataSource, SourceCheck
from aav_io_mux import provenance
from aav_io_mux.sensor_mux import ANNOUNCEMENTS, announcers_alive, entries_of
from ackermann_msgs.msg import AckermannDriveStamped
import rclpy
from rclpy.clock import Clock, ClockType
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import Trigger


class OutputMux(Node):

    def __init__(self):
        super().__init__('output_mux')
        self.target = self.declare_parameter('target', 'car').value
        topic = provenance.command_topic(self.target)
        self.gate = provenance.Gate(self.target,
                                    settle=self.declare_parameter('settle', 2.0).value,
                                    stale_after=self.declare_parameter('stale_after', 3.0).value)
        self.heard = {}
        self.last_state = None
        self.out = self.create_publisher(AckermannDriveStamped, topic, 10)
        self.state_pub = self.create_publisher(String, 'safety/output_mux/state', 10)
        self.create_subscription(AckermannDriveStamped, 'ego/actuator_cmd', self.on_cmd, 10)
        self.create_subscription(SourceCheck, 'system/sensor_mux/state', self.on_check, 10)
        self.create_subscription(DataSource, 'system/source', self.on_source, ANNOUNCEMENTS)
        self.create_service(Trigger, 'safety/output_mux/clear', self.on_clear)
        steady = Clock(clock_type=ClockType.STEADY_TIME)
        self.create_timer(0.1, self.tick, clock=steady)
        self.create_timer(0.5, self.publish_state, clock=steady)
        self.get_logger().info(f'target:={self.target}: ego/actuator_cmd -> {topic}, while '
                               f'every source is {provenance.kind_name(self.gate.expected)}')

    def on_check(self, msg):
        self.gate.report = provenance.Report(time.monotonic(), msg.source, msg.ok,
                                             tuple(msg.problems), tuple(msg.doubts))
        self.tick()

    def on_source(self, msg):
        self.heard[msg.announcer] = entries_of(msg)
        self.tick()

    def tick(self):
        """Re-judge: the live announcements, the sensor mux's age."""
        self.gate.entries = provenance.live_entries(self.heard, announcers_alive(self))
        self.gate.update(time.monotonic())
        self.publish_state(changes_only=True)

    def on_cmd(self, msg):
        if self.gate.is_open(time.monotonic()):
            self.out.publish(msg)

    def on_clear(self, request, response):
        self.tick()
        response.success, response.message = self.gate.clear(time.monotonic())
        log = self.get_logger().warning if response.success else self.get_logger().error
        log(f'clear: {response.message}')
        self.publish_state(changes_only=True)
        return response

    def publish_state(self, changes_only=False):
        state = self.gate.state(time.monotonic())
        if changes_only and state == self.last_state:
            return
        if state != self.last_state:
            if state.startswith('STOP'):
                self.get_logger().error(state)
            else:
                self.get_logger().info(state)
            self.last_state = state
        self.state_pub.publish(String(data=state))


def main(args=None):
    rclpy.init(args=args)
    node = OutputMux()
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
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
