"""
Did Gazebo itself crash while the world was starting? Read from a launch log.

sim-check retries a start-up once when it did: on GitHub's runners, Gazebo with software
rendering (Mesa's llvmpipe) sometimes dies with a segmentation fault before it publishes
anything (nightly runs of 23 and 25 Oct), and then every node after it fails too. A crash
that comes back on the retry is a real failure.
"""

import re

# ros2 launch's line when the gz sim process dies, and the signals that mean a crash.
DIED = re.compile(r'\[ERROR\] \[(gazebo|gz_sim|ruby)-\d+\]: process has died \[pid \d+, '
                  r'exit code (-?\d+)')
CRASH_CODES = {'139', '-11', '134', '-6'}   # SIGSEGV and SIGABRT, as a shell or as Python


def gazebo_crashed(log: str) -> str:
    """Return how Gazebo died ('segmentation fault', 'abort'), or '' if it didn't crash."""
    for match in DIED.finditer(log):
        code = match.group(2)
        if code in CRASH_CODES:
            return 'segmentation fault' if code in ('139', '-11') else 'abort'
    return ''
