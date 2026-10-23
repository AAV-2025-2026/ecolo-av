"""
Where the data comes from, and whether a target may act on it. No ROS here.

The sensor mux (sensor_mux.py) and the output mux (output_mux.py) ask these functions:

| Rule | Where |
|---|---|
| The sources and targets, and each target's topic and source | SOURCES, TARGETS, command_topic |
| A launch's target:= and source:=, checked before anything starts | choose |
| Forget an announcement once its announcer has gone | live_entries |
| Any announcement that isn't the source this run asked for | foreign |
| Each sensor: one publisher, from the source asked for | check_sensors |
| Pass the target's commands on, or latch a stop | Gate |

Every rule errs towards "this is the real car, and something is wrong": an unknown source
number is never REAL, and a silent sensor mux closes the gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Collection, Iterable, List, Mapping, Optional, Sequence, Tuple

# aav_interfaces/SensorSource's values.
REAL, SIM, BENCH, REPLAY = 0, 1, 2, 3
NAMES = {REAL: 'REAL', SIM: 'SIM', BENCH: 'BENCH', REPLAY: 'REPLAY'}
# source:= on the sensor mux: where this run's sensor data must come from.
SOURCES = {'real': REAL, 'sim': SIM, 'bench': BENCH, 'replay': REPLAY}
# target:= on the output mux: who plays the car, and the source its data must come from.
TARGETS = {'car': REAL, 'gazebo': SIM, 'turtle': SIM, 'carla': SIM, 'bench': BENCH}

# The sensor topics the sensor mux watches: the raw data, as each driver or stand-in
# publishes it. The derived topics (/sensors/imu/data, the EKFs) follow from these.
SENSORS = (
    ('imu', '/sensors/imu/data_raw'),
    ('gps', '/sensors/gps/fix'),
    ('camera_front_left', '/sensors/camera/front_left/image_raw'),
    ('camera_front_right', '/sensors/camera/front_right/image_raw'),
    ('camera_rear', '/sensors/camera/rear/image_raw'),
    ('radar', '/sensors/radar/points'),
    ('lidar', '/sensors/lidar/points'),
    ('odometry', '/vehicle/odom'),
    ('wheels', '/vehicle/wheels'),
    ('vehicle', '/vehicle/status'),
    ('battery', '/vehicle/battery'),
)


def kind_name(kind: int) -> str:
    """REAL, SIM, BENCH, REPLAY; a number newer than this code shows as UNKNOWN(n)."""
    return NAMES.get(kind, f'UNKNOWN({kind})')


def source_of(source: str) -> int:
    """Return the SensorSource value for source:=real|sim|bench|replay, or raise ValueError."""
    if source not in SOURCES:
        raise ValueError(f'source:={source}: use one of {", ".join(SOURCES)}')
    return SOURCES[source]


def target_of(target: str) -> int:
    """Return the source a target needs (car: REAL...), or raise ValueError."""
    if target not in TARGETS:
        raise ValueError(f'target:={target}: use one of {", ".join(TARGETS)}')
    return TARGETS[target]


def command_topic(target: str) -> str:
    """Return the topic the output mux sends this target's commands on."""
    target_of(target)
    return f'/control/{target}/actuator_cmd'


def choose(target: str, source: str) -> Tuple[str, str]:
    """
    Return (target, source) for a launch: source defaults to the target's own.

    Raise ValueError for an unknown name, for neither, or for a source the target can't
    take: the output mux would refuse every command, so say so before anything starts.
    """
    if not target and not source:
        raise ValueError('give target:= (car, gazebo, bench, turtle, carla) or source:=')
    if target:
        needs = target_of(target)
        if not source:
            source = next(s for s, k in SOURCES.items() if k == needs)
        elif source_of(source) != needs:
            raise ValueError(f'target:={target} needs source:={kind_name(needs).lower()}, '
                             f'not {source}: the output mux would refuse every command')
    source_of(source)
    return target, source


@dataclass(frozen=True)
class Entry:
    """One sensor in one /system/source announcement."""

    announcer: str   # the node that says so
    name: str        # imu, gps, camera_front_left, actuators...
    topic: str       # its main topic; '' if it has none
    kind: int        # REAL, SIM, BENCH or REPLAY


def live_entries(announcements: Mapping[str, Sequence[Entry]],
                 alive: Collection[str]) -> List[Entry]:
    """
    Every entry whose announcer still publishes /system/source (alive: their node names).

    An announcement is latched, so it outlives nothing: once Gazebo stops, its SIM entries
    stop counting, and a latched stop can be cleared.
    """
    return [e for announcer, entries in announcements.items() if announcer in alive
            for e in entries]


def foreign(entries: Iterable[Entry], expected: int) -> List[str]:
    """One line per announced entry whose source isn't the one this run asked for."""
    return [f'{e.name} is {kind_name(e.kind)} ({e.announcer})'
            for e in entries if e.kind != expected]


@dataclass(frozen=True)
class Sensor:
    """One watched sensor topic, as found."""

    name: str
    topic: str
    kind: int                       # the source found: announced, or REAL if unannounced
    publishers: Tuple[str, ...]


@dataclass(frozen=True)
class Check:
    """The sensor mux's verdict."""

    source: int                     # what source:= asked for
    ok: bool
    problems: Tuple[str, ...]
    sensors: Tuple[Sensor, ...]     # the watched topics that have a publisher


def check_sensors(expected: int, entries: Sequence[Entry],
                  publishers: Mapping[str, Sequence[str]],
                  watched: Sequence[Tuple[str, str]] = SENSORS) -> Check:
    """
    Check that each watched sensor topic comes from exactly one source: `expected`.

    entries: the live /system/source entries. publishers: topic -> the nodes publishing
    it now. A topic nobody publishes is absent, not a fault (the sensor watchdog minds
    silence). A publisher nobody announced counts as REAL: the car's stock drivers
    (ublox_gps, velodyne, usb_cam) can't announce, and a stand-in always does.
    """
    problems = foreign(entries, expected)
    sensors = []
    for name, topic in watched:
        pubs = tuple(sorted(set(publishers.get(topic, ()))))
        if not pubs:
            continue
        if len(pubs) > 1:
            problems.append(f'{name}: {len(pubs)} publishers on {topic} ({", ".join(pubs)}): '
                            'two sources at once')
        kinds = {e.kind for e in entries if e.topic == topic}
        if not kinds:
            kind = REAL
            if expected != REAL:
                problems.append(f'{name}: {topic} from {", ".join(pubs)}, which nobody '
                                'announces on /system/source: a real driver?')
        else:
            # One that isn't the source asked for is already a problem (foreign, above).
            kind = expected if kinds == {expected} else min(kinds - {expected})
        sensors.append(Sensor(name, topic, kind, pubs))
    return Check(expected, not problems, tuple(problems), tuple(sensors))


@dataclass(frozen=True)
class Report:
    """The sensor mux's last verdict, as the output mux heard it."""

    time: float                     # s, when it arrived (a steady clock)
    source: int
    ok: bool
    problems: Tuple[str, ...] = ()


@dataclass
class Gate:
    """
    The output mux's rule: pass the target's commands on, or latch a stop.

    Open only when the sensor mux, heard within stale_after s, says ok for the target's
    source; nothing on /system/source says otherwise; and both have held for settle s.
    Any problem after the sensor mux was first heard latches a stop until clear(), which
    a person calls and which works only once nothing is wrong. Before the sensor mux is
    heard at all, the gate waits, closed, without latching (start-up).
    """

    target: str
    settle: float = 2.0             # s of all clear before commands flow
    stale_after: float = 1.0        # s: a quieter sensor mux closes the gate
    report: Optional[Report] = None
    entries: List[Entry] = field(default_factory=list)
    latched: Tuple[str, ...] = ()   # why it stopped, while latched
    clear_since: Optional[float] = None

    def __post_init__(self):
        self.expected = target_of(self.target)

    def problems(self, now: float) -> List[str]:
        """Everything wrong now; an empty list when the target may be driven."""
        want = kind_name(self.expected)
        if self.report is None:
            return ['waiting for the sensor mux (/system/sensor_mux/state)']
        found = []
        age = now - self.report.time
        if age > self.stale_after:
            found.append(f'the sensor mux went quiet ({age:.1f} s)')
        if self.report.source != self.expected:
            found.append(f'the sensor mux checks for {kind_name(self.report.source)}, '
                         f'target {self.target} needs {want}')
        elif not self.report.ok:
            found += list(self.report.problems) or ['the sensor mux says no']
        found += foreign(self.entries, self.expected)
        return found

    def update(self, now: float) -> None:
        """Re-judge, after a report, an announcement, a command or a tick."""
        if self.latched:
            return
        if self.report is None:
            self.clear_since = None
            return
        found = self.problems(now)
        if found:
            self.latched = tuple(found)
            self.clear_since = None
        elif self.clear_since is None:
            self.clear_since = now

    def is_open(self, now: float) -> bool:
        """Whether a command arriving now goes on to the target."""
        self.update(now)
        return (not self.latched and self.clear_since is not None
                and now - self.clear_since >= self.settle)

    def clear(self, now: float) -> Tuple[bool, str]:
        """Reopen (after settle s) if nothing is wrong now: a person's reset."""
        found = self.problems(now)
        if found:
            return False, 'still wrong: ' + '; '.join(found)
        was = self.latched
        self.latched = ()
        self.clear_since = now
        return True, (f'cleared ({"; ".join(was)}): commands flow in {self.settle:g} s'
                      if was else 'nothing was latched')

    def state(self, now: float) -> str:
        """One line for people: OPEN, WAIT or STOP, the target, and why."""
        want = kind_name(self.expected)
        if self.latched:
            return (f'STOP - target {self.target} needs {want} - ' + '; '.join(self.latched)
                    + ' - latched: /safety/output_mux/clear')
        if self.is_open(now):
            return f'OPEN - {self.target}: every source {want}'
        if self.report is None:
            return f'WAIT - {self.target}: waiting for the sensor mux'
        return f'WAIT - {self.target}: all {want}, settling for {self.settle:g} s'
