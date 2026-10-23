"""
A simulated source can't drive the real car's backend (PLAN.md S-4).

The real nodes, in one process, on a private ROS domain on this computer: sensor_mux
(source real), output_mux (target car) and spine_bridge (source real: the real car's CAN
backend). Ego's commands go in on /ego/actuator_cmd; what reaches the car is spine_bridge's
DRIVE_CMD frames on /can/tx.

  all REAL                      -> DRIVE_CMD frames flow
  Gazebo announces SIM as well  -> no DRIVE_CMD frame at all, and the output mux says STOP
  a simulator's own ego         -> spine_bridge doesn't even listen to /ego/actuator_cmd
"""

import os
import random
import time

import pytest

try:
    from aav_interfaces.msg import DataSource, SensorSource
    from aav_io_mux.output_mux import OutputMux
    from aav_io_mux.sensor_mux import SensorMux
    from aav_spine import can_codec as cc
    from aav_spine.spine_bridge import SpineBridge
    from ackermann_msgs.msg import AckermannDriveStamped
    from can_msgs.msg import Frame
    import rclpy
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
    from std_msgs.msg import String
    HAVE_ROS = True
except ImportError:
    HAVE_ROS = False

pytestmark = pytest.mark.skipif(not HAVE_ROS, reason='needs ROS 2 and the built workspace')

LATCHED = None if not HAVE_ROS else QoSProfile(
    depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)
ARGS = ['--ros-args', '-p', 'sensor_mux:startup:=0.0', '-p', 'sensor_mux:source:=real',
        '-p', 'output_mux:target:=car', '-p', 'output_mux:settle:=0.5',
        '-p', 'spine_bridge:source:=real']


class Run:
    """The three nodes and a test node, spun together."""

    def __init__(self, gazebo=False):
        os.environ['ROS_AUTOMATIC_DISCOVERY_RANGE'] = 'LOCALHOST'
        rclpy.init(args=ARGS, domain_id=random.randint(150, 230))
        self.executor = SingleThreadedExecutor()
        self.nodes = [SensorMux(), OutputMux(), SpineBridge()]
        self.test = rclpy.create_node('guard_test')
        self.nodes.append(self.test)
        self.drive_frames = 0
        self.state = ''
        self.ego = self.test.create_publisher(AckermannDriveStamped, '/ego/actuator_cmd', 10)
        self.test.create_subscription(Frame, '/can/tx', self.on_frame, 100)
        self.test.create_subscription(String, '/safety/output_mux/state', self.on_state, 10)
        if gazebo:
            # As gazebo_adapter announces: under its name, so it counts as alive.
            self.gazebo = rclpy.create_node('gazebo_adapter')
            self.nodes.append(self.gazebo)
            pub = self.gazebo.create_publisher(DataSource, '/system/source', LATCHED)
            pub.publish(DataSource(announcer='gazebo_adapter', sensors=[SensorSource(
                name='camera_front_left', topic='/sensors/camera/front_left/image_raw',
                source=SensorSource.SIM)]))
        for n in self.nodes:
            self.executor.add_node(n)

    def on_frame(self, f):
        if f.id == cc.DRIVE_CMD_ID:
            self.drive_frames += 1

    def on_state(self, msg):
        self.state = msg.data

    def drive(self, seconds):
        """Send ego's command at 50 Hz for this long, spinning everything."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            cmd = AckermannDriveStamped()
            cmd.drive.speed = 0.5
            self.ego.publish(cmd)
            self.executor.spin_once(timeout_sec=0.02)

    def close(self):
        for n in self.nodes:
            n.destroy_node()
        self.executor.shutdown()
        rclpy.shutdown()


@pytest.fixture
def run(request):
    r = Run(gazebo=request.param)
    yield r
    r.close()


@pytest.mark.parametrize('run', [False], indirect=True)
def test_all_real_reaches_the_cars_backend(run):
    run.drive(4.0)
    assert run.state == 'OPEN - car: every source REAL'
    assert run.drive_frames > 20


@pytest.mark.parametrize('run', [True], indirect=True)
def test_a_simulated_source_cant_drive_the_real_backend(run):
    run.drive(4.0)
    assert run.state.startswith('STOP - target car needs REAL'), run.state
    assert 'camera_front_left is SIM (gazebo_adapter)' in run.state
    assert run.drive_frames == 0


@pytest.mark.parametrize('run', [False], indirect=True)
def test_the_real_backend_never_hears_ego_directly(run):
    run.drive(1.0)
    topics = {name for name, _ in
              run.test.get_subscriber_names_and_types_by_node('spine_bridge', '/')}
    assert '/ego/actuator_cmd' not in topics
    assert '/control/car/actuator_cmd' in topics
