"""
Check the bridge's DRIVE_CMD stream (the arming edge, going quiet with ego), and its odometry.

Needs ROS sourced (rclpy and aav_interfaces): `colcon test` runs it, tools/test.sh skips it.
"""

import pytest

# Not pytest.importorskip: ROS's launch_testing pytest plugin turns a module-level skip
# into a skip of every test in the folder, and it also overrides collect_ignore.
try:
    from aav_spine import can_codec as cc
    from aav_spine.spine_bridge import SpineBridge
    from ackermann_msgs.msg import AckermannDrive
    from can_msgs.msg import Frame
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
    try:
        node = SpineBridge()
        node.sent = []
        node._send = lambda can_id, data: node.sent.append(cc.unpack(can_id, data))
        yield node
        node.destroy_node()
    finally:
        # Even when the node fails to start: otherwise every later test fails on init.
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


def receive(node, can_id, values):
    data = cc.pack(can_id, values)
    node.on_frame(Frame(id=can_id, dlc=len(data), data=list(data) + [0] * (8 - len(data))))


def capture(publisher):
    out = []
    publisher.publish = out.append
    return out


def test_odometry_uses_fresh_wheel_speeds(bridge):
    odom = capture(bridge.odom_pub)
    wheels = capture(bridge.wheel_pub)
    feedback = {'measured_speed': -0.5, 'measured_steering_angle': 0.0}
    receive(bridge, cc.VEHICLE_FEEDBACK_ID, feedback)
    assert odom[-1].twist.twist.linear.x == pytest.approx(-0.5)   # no wheel frames yet

    for _ in range(2):   # the first left frame goes out alone; then they pair up
        for can_id, v in ((cc.WHEEL_SPEED_L_ID, 1.0), (cc.WHEEL_SPEED_R_ID, 1.2)):
            receive(bridge, can_id, {'wheel_speed': v, 'pulse_count': 3})
    assert wheels[-1].left == pytest.approx(-1.0)    # signed by the spine's reverse
    assert wheels[-1].right == pytest.approx(-1.2)
    assert wheels[-1].left_fresh and wheels[-1].right_fresh
    receive(bridge, cc.VEHICLE_FEEDBACK_ID, feedback)
    assert odom[-1].twist.twist.linear.x == pytest.approx(-1.1)


def test_odometry_falls_back_when_the_wheels_go_quiet(bridge):
    odom = capture(bridge.odom_pub)
    for can_id in cc.WHEEL_SPEED_IDS:
        receive(bridge, can_id, {'wheel_speed': 2.0})
    for w in bridge.wheels.wheels.values():
        w.time -= 1.0
    receive(bridge, cc.VEHICLE_FEEDBACK_ID, {'measured_speed': 0.7})
    assert odom[-1].twist.twist.linear.x == pytest.approx(0.7)
