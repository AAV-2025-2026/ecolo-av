"""
Check the bridge's DRIVE_CMD stream: the arming edge, and going quiet with ego.

Needs ROS sourced (rclpy and aav_interfaces): `colcon test` runs it, tools/test.sh skips it.
"""

import pytest

# Not pytest.importorskip: ROS's launch_testing pytest plugin turns a module-level skip
# into a skip of every test in the folder, and it also overrides collect_ignore.
try:
    from aav_spine import can_codec as cc
    from aav_spine.spine_bridge import SpineBridge
    from ackermann_msgs.msg import AckermannDrive
    import rclpy
    from rclpy.duration import Duration
    from std_msgs.msg import Bool
    from std_srvs.srv import SetBool
except ImportError:
    SpineBridge = None

pytestmark = pytest.mark.skipif(SpineBridge is None, reason='needs ROS sourced: colcon test')


@pytest.fixture
def bridge():
    rclpy.init()
    node = SpineBridge()
    node.sent = []
    node._send = lambda can_id, data: node.sent.append(cc.unpack(can_id, data))
    yield node
    node.destroy_node()
    rclpy.shutdown()


def fresh_command(node, speed=1.0):
    node.cmd = AckermannDrive(speed=speed)
    node.cmd_time = node.get_clock().now()


def arm(node, on=True):
    return node.on_arm(SetBool.Request(data=on), SetBool.Response())


def armed_flags(node, frames):
    node.sent.clear()
    for _ in range(frames):
        node.send_drive()
    return [bool(f['armed']) for f in node.sent]


def test_arming_sends_the_edge(bridge):
    fresh_command(bridge)
    assert armed_flags(bridge, 2) == [False, False]
    assert arm(bridge).success
    assert armed_flags(bridge, 5) == [False, False, False, True, True]


def test_arming_again_sends_the_edge_again(bridge):
    # The spine may have latched without the bridge knowing: a hardware e-stop, a
    # timeout, a driver fault or a reboot. Arming again has to clear that.
    fresh_command(bridge)
    arm(bridge)
    armed_flags(bridge, 5)
    arm(bridge)
    assert armed_flags(bridge, 5) == [False, False, False, True, True]


def test_estop_disarms_and_refuses_arming(bridge):
    fresh_command(bridge)
    arm(bridge)
    bridge.on_estop(Bool(data=True))
    assert not arm(bridge).success
    assert armed_flags(bridge, 5) == [False] * 5


def test_stale_command_stops_the_stream(bridge):
    fresh_command(bridge)
    arm(bridge)
    bridge.cmd_time = bridge.get_clock().now() - Duration(seconds=0.15)
    assert armed_flags(bridge, 3) == []
