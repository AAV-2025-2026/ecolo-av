"""
The lane follower's slow-down rule, with no ROS imports (aav, 26 Oct 2026).

control_interface.py slows the car with it when the lane lines are lost, or when no
lane message has come for `stop_wait_s`. test/test_lane_speed.py tests it.
"""

# twist_mux forgets the AI slot when /drivers/ai/cmd_vel has been quiet this long
# (ros/command_mux/aav_command_mux/config/twist_mux.yaml, input `ai`). Then ego stops
# the car on its own, at its max_deceleration. The test checks the two match.
AI_SLOT_TIMEOUT_S = 0.5


def slow_down(speed: float, decel_rate: float, dt: float) -> float:
    """
    Return the speed (m/s) after slowing at decel_rate (m/s^2) for dt seconds.

    Never below 0. A decel_rate of 0 or less would never stop, so it stops at once.
    A negative dt (the clock went back) changes nothing.
    """
    if decel_rate <= 0.0:
        return 0.0
    return max(0.0, speed - decel_rate * max(dt, 0.0))


def stopping_speed(speed: float, decel_rate: float, dt: float, quiet_s: float) -> float:
    """
    Return the next speed to command while the follower slows down to a stop.

    quiet_s is how long (s) since the follower last published a command. From
    AI_SLOT_TIMEOUT_S on, twist_mux has dropped the slot and ego is already stopping
    the car: the answer is 0, because a slow-down started from the old speed would make
    the car pull away again.
    """
    if quiet_s >= AI_SLOT_TIMEOUT_S:
        return 0.0
    return slow_down(speed, decel_rate, dt)
