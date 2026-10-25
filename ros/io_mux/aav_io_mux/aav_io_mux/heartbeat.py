"""
The output mux's heartbeat: the Orin's proof of life, carried to the ESP32 (TODO 50).

No ROS here. The output mux publishes Counter.beat() on /control/<target>/heartbeat with
every command it passes on, and only then: while its gate is OPEN. The Motor Pi's
legacy_uart_bridge copies the counter into each serial frame; the ESP32 brakes when it
hasn't changed for 100 ms (docs/rust-firmware.md, "The heartbeat").
"""


def heartbeat_topic(target: str) -> str:
    """Return the heartbeat's topic for a target, beside its command topic."""
    return f'/control/{target}/heartbeat'


class Counter:
    """+1 for each command passed on, in a byte: 1, 2 ... 255, 0, 1 ..."""

    def __init__(self):
        self.value = 0

    def beat(self) -> int:
        """Count one command passed on; return the new counter."""
        self.value = (self.value + 1) & 0xFF
        return self.value
