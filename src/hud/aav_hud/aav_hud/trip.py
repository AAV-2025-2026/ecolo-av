"""
The route the HUD sent to Nav2, and the nav_state event the map page shows.

No ROS imports, so the tests run anywhere. hud_server tells a Trip what the
follow_gps_waypoints action did (accepted, feedback, result); the Trip says what to show:

  {'distance': m, 'status': word, 'waypoint': n, 'waypoints': total, 'message': text}

The app reads 'distance' and 'status' ("Distance: 12.0 m", "Status: navigating").
"""

from aav_hud.route import remaining

# Status words, shown as they are. Two are the 2025-26 navigation's own words.
IDLE = 'waiting_for_goal'        # 2025-26: no route sent yet
SENDING = 'sending_goal'         # sent; Nav2 hasn't answered yet
NO_NAV2 = 'nav2_not_running'     # nobody serves /follow_gps_waypoints
REJECTED = 'rejected'            # Nav2 refused the goal
NAVIGATING = 'navigating'
CANCELING = 'canceling'
REACHED = 'goal_reached'         # 2025-26: every waypoint reached
MISSED = 'missed_waypoints'      # finished, but Nav2 skipped some waypoints
ABORTED = 'aborted'              # Nav2 gave up, or a newer goal replaced this one
CANCELED = 'canceled'

ACTIVE = (SENDING, NAVIGATING, CANCELING)

# action_msgs/msg/GoalStatus (test_trip checks them)
STATUS_SUCCEEDED = 4
STATUS_CANCELED = 5
STATUS_ABORTED = 6


class Trip:
    """One route sent to Nav2, from sending to its result."""

    def __init__(self, waypoints=(), status=None):
        self.waypoints = list(waypoints)
        self.status = status or (SENDING if self.waypoints else IDLE)
        self.index = 0      # the waypoint Nav2 is driving to (0 = the first)
        self.message = ''

    @property
    def active(self):
        """Say whether the goal is out: from sending it until its result."""
        return self.status in ACTIVE

    def answered(self, accepted):
        """Note Nav2's answer: it took the goal or refused it. False: cancel it."""
        if not accepted:
            # Nav2 gives no reason. It refuses goals until its lifecycle manager has
            # activated the waypoint follower, a few seconds after it starts.
            self.status = REJECTED
            self.message = 'Nav2 refused the route: is it still starting?'
            return True
        if self.status == CANCELING:
            return False
        self.status = NAVIGATING
        return True

    def cancel(self):
        """Stop following the route, as the person asked. False if nothing to stop."""
        if not self.active:
            return False
        self.status = CANCELING
        return True

    def feedback(self, index):
        """Note Nav2's current waypoint. True if it changed."""
        index = max(0, min(int(index), len(self.waypoints)))
        if index == self.index:
            return False
        self.index = index
        return True

    def finished(self, code, missed=0, error=''):
        """Take the action's result: its GoalStatus code and the missed waypoints."""
        if code == STATUS_SUCCEEDED and missed == 0:
            self.status, self.message = REACHED, ''
            self.index = len(self.waypoints)
        elif code == STATUS_SUCCEEDED:
            # The missed one may be the destination: the distance stays the true one.
            self.status = MISSED
            self.message = f'missed {missed} of {len(self.waypoints)} waypoints'
        elif code == STATUS_CANCELED:
            self.status, self.message = CANCELED, ''
        elif code == STATUS_ABORTED:
            self.status = ABORTED
            self.message = error or 'no reason given: a newer goal ends an older one this way'
        else:
            self.status, self.message = ABORTED, error or f'goal status {code}'

    def distance(self, position=None):
        """Metres left; from the car's (lat, lon) when it is known."""
        if self.status == REACHED:
            return 0.0
        return remaining(self.waypoints, self.index, position)

    def event(self, position=None):
        """Build the nav_state payload."""
        total = len(self.waypoints)
        return {
            'distance': round(self.distance(position), 1),
            'status': self.status,
            'waypoint': min(self.index + 1, total),
            'waypoints': total,
            'message': self.message,
        }
