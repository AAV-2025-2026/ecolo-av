"""
legacy_uart_bridge: drive today's ESP32 firmware from ego's commands.

Interim backend until the CAN spine exists. Runs on the computer wired to
the ESP32's UART (today the Motor Pi, /dev/ttyAMA0).

Subscribes  control/car/actuator_cmd  ackermann_msgs/AckermannDriveStamped: ego's command,
                              from the output mux (aav_io_mux, target car), which sends it
                              only while every source is REAL. Never /ego/actuator_cmd
            safety/estop      std_msgs/Bool (true: full brake now, until false)
Publishes   system/source     aav_interfaces/DataSource, latched: the actuators are REAL
Writes      13-byte frames at rate_hz on the serial port (see legacy_protocol)

Throttle is open loop: speed / full_throttle_speed. If the command goes stale (ego or the
output mux stopped), or /safety/estop is true, the bridge sends brake frames. It can't
protect against its own crash, because the firmware has no timeout; fix that in the
firmware first.
"""

import signal

from aav_interfaces.msg import DataSource, SensorSource
from aav_legacy.legacy_protocol import LegacyMapping, pack_frame, stop_command, to_legacy
from ackermann_msgs.msg import AckermannDriveStamped
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
import serial
from std_msgs.msg import Bool


class LegacyUartBridge(Node):

    def __init__(self):
        super().__init__('legacy_uart_bridge')
        port = self.declare_parameter('port', '/dev/ttyAMA0').value
        baud = self.declare_parameter('baud', 115200).value
        rate = self.declare_parameter('rate_hz', 50.0).value
        self.timeout = self.declare_parameter('cmd_timeout', 0.3).value
        defaults = LegacyMapping()
        self.mapping = LegacyMapping(**{
            k: self.declare_parameter(k, v).value for k, v in vars(defaults).items()})
        self.serial = serial.Serial(port, baud, timeout=0)
        self.cmd = None
        self.cmd_time = None
        self.last_steering = 0.0
        self.estop = False
        self.create_subscription(AckermannDriveStamped, 'control/car/actuator_cmd',
                                 self.on_cmd, 10)
        self.create_subscription(Bool, 'safety/estop', self.on_estop, 10)
        self.create_timer(1.0 / rate, self.tick)
        # Say once, latched, that this drives the real car (/system/source).
        latched = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                             durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.source_pub = self.create_publisher(DataSource, 'system/source', latched)
        announcement = DataSource(announcer=self.get_name())
        announcement.header.stamp = self.get_clock().now().to_msg()
        announcement.sensors = [SensorSource(name='actuators', topic='',
                                             source=SensorSource.REAL)]
        self.source_pub.publish(announcement)
        self.get_logger().warning(
            'legacy firmware has no command timeout; keep the e-stop in reach')

    def on_cmd(self, msg):
        self.cmd = msg.drive
        self.cmd_time = self.get_clock().now()

    def on_estop(self, msg):
        if msg.data != self.estop:
            self.get_logger().warning('e-stop ON: braking' if msg.data else 'e-stop released')
        self.estop = msg.data

    def tick(self):
        fresh = self.cmd is not None and (
            self.get_clock().now() - self.cmd_time).nanoseconds * 1e-9 <= self.timeout
        if fresh and not self.estop:
            values = to_legacy(self.cmd.speed, self.cmd.steering_angle, self.mapping)
            self.last_steering = values[0]
        else:
            values = stop_command(self.mapping, self.last_steering)
        try:
            self.serial.write(pack_frame(*values))
        except serial.SerialException as e:
            self.get_logger().error(f'serial write failed: {e}', throttle_duration_sec=2.0)

    def destroy_node(self):
        try:
            for _ in range(5):   # leave the car braked
                self.serial.write(pack_frame(*stop_command(self.mapping, self.last_steering)))
            self.serial.close()
        except serial.SerialException:
            pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = LegacyUartBridge()
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
