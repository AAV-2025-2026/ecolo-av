"""The ego node, in this process: its trace, and its lead turning off for a lag-aware driver."""

import os
import time

import pytest

try:
    from aav_ego.ego_node import Ego
    from geometry_msgs.msg import TwistStamped
    from nav_msgs.msg import Path
    import rclpy
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.parameter import Parameter
    from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
    from std_msgs.msg import Bool
    HAVE_ROS = True
except ImportError:
    HAVE_ROS = False

pytestmark = pytest.mark.skipif(not HAVE_ROS, reason='needs ROS and the built workspace')

VEHICLE_YAML = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'bringup',
                            'aav_description', 'config', 'vehicle.yaml')


@pytest.fixture
def graph():
    """Start a private ROS context (its own domain), ego, and a test node."""
    domain = int(os.environ.get('ROS_DOMAIN_ID', '0')) or 101
    context = rclpy.Context()
    rclpy.init(context=context, domain_id=domain)
    ego = Ego(context=context, parameter_overrides=[
        Parameter('lag_lead', value='on'),
        Parameter('vehicle_yaml', value=os.path.abspath(VEHICLE_YAML))])
    other = rclpy.create_node('ego_test', context=context)
    executor = SingleThreadedExecutor(context=context)
    executor.add_node(ego)
    executor.add_node(other)
    yield ego, other, executor
    executor.shutdown()
    ego.destroy_node()
    other.destroy_node()
    rclpy.shutdown(context=context)


def spin(executor, seconds, until=lambda: False):
    end = time.monotonic() + seconds
    while time.monotonic() < end and not until():
        executor.spin_once(timeout_sec=0.02)


def twist(node, v, w):
    msg = TwistStamped()
    msg.header.stamp = node.get_clock().now().to_msg()
    msg.header.frame_id = 'base_link'
    msg.twist.linear.x = v
    msg.twist.angular.z = w
    return msg


def test_the_trace_goes_ahead_and_left_in_base_link(graph):
    ego, other, executor = graph
    traces = []
    other.create_subscription(Path, '/ego/trace', traces.append, 10)
    cmd = other.create_publisher(TwistStamped, '/control/cmd_vel', 10)
    for _ in range(40):
        cmd.publish(twist(other, 0.8, 0.3))
        spin(executor, 0.05)
    assert traces, 'no /ego/trace'
    last = traces[-1]
    assert last.header.frame_id == 'base_link'
    assert len(last.poses) == 21
    end = last.poses[-1].pose.position
    assert end.x > 0.3 and end.y > 0.0
    assert ego.lead_on    # lag_lead on, and no lag-aware driver


def test_the_lead_turns_off_while_a_lag_aware_driver_drives(graph):
    ego, other, executor = graph
    latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                         reliability=ReliabilityPolicy.RELIABLE)
    aware = other.create_publisher(Bool, '/drivers/nav/lag_aware', latched)
    nav = other.create_publisher(TwistStamped, '/drivers/nav/cmd_vel', 10)
    mux = other.create_publisher(TwistStamped, '/control/cmd_vel', 10)
    aware.publish(Bool(data=True))
    spin(executor, 1.0, until=lambda: ego.watch.aware['nav'])
    assert ego.watch.aware['nav']
    for _ in range(30):     # twist_mux passes nav's message on unchanged
        msg = twist(other, 0.8, 0.0)
        nav.publish(msg)
        mux.publish(msg)
        spin(executor, 0.05)
    assert not ego.lead_on
    for _ in range(30):     # someone else's command: the lead runs again
        mux.publish(twist(other, 0.8, 0.0))
        spin(executor, 0.05)
    assert ego.lead_on
