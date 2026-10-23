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
| What the ROS graph suggests counts once it lasts (discovery takes a moment) | Hold |
| Pass the target's commands on, wait, or latch a stop | Gate |

Every rule errs towards "this is the real car, and something is wrong": an unknown source
number is never REAL, and a silent sensor mux closes the gate. Evidence (an announcement
of another source) latches a stop; doubt (a silent sensor mux, a graph finding still
young) only holds the gate shut.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Collection, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

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
    """
    The sensor mux's verdict.

    problems: an announcement says another source: certain, at once. doubts: what the ROS
    graph suggests (two publishers on a sensor, one nobody announces): discovery and a
    late announcement can show these for a moment, so Hold turns a doubt into a problem
    only once it lasts. The output mux latches on a problem, and waits on a doubt.
    """

    source: int                     # what source:= asked for
    ok: bool                        # no problems and no doubts
    problems: Tuple[str, ...]
    doubts: Tuple[str, ...]
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
    doubts = []
    sensors = []
    for name, topic in watched:
        pubs = tuple(sorted(set(publishers.get(topic, ()))))
        if not pubs:
            continue
        if len(pubs) > 1:
            doubts.append(f'{name}: {len(pubs)} publishers on {topic} ({", ".join(pubs)}): '
                          'two sources at once')
        kinds = {e.kind for e in entries if e.topic == topic}
        if not kinds:
            kind = REAL
            if expected != REAL:
                doubts.append(f'{name}: {topic} from {", ".join(pubs)}, which nobody '
                              'announces on /system/source: a real driver?')
        else:
            # One that isn't the source asked for is already a problem (foreign, above).
            kind = expected if kinds == {expected} else min(kinds - {expected})
        sensors.append(Sensor(name, topic, kind, pubs))
    return Check(expected, not problems and not doubts, tuple(problems), tuple(doubts),
                 tuple(sensors))


@dataclass
class Hold:
    """Turn a doubt into a problem once it has lasted `hold` s (the sensor mux's memory)."""

    hold: float = 5.0
    since: Dict[str, float] = field(default_factory=dict)

    def judge(self, now: float, check: Check) -> Check:
        """Return the check with each doubt that has lasted long enough as a problem."""
        self.since = {d: self.since.get(d, now) for d in check.doubts}
        lasting = tuple(d for d in check.doubts if now - self.since[d] >= self.hold)
        doubts = tuple(d for d in check.doubts if d not in lasting)
        problems = check.problems + lasting
        return replace(check, ok=not problems and not doubts, problems=problems,
                       doubts=doubts)


@dataclass(frozen=True)
class Report:
    """The sensor mux's last verdict, as the output mux heard it."""

    time: float                     # s, when it arrived (a steady clock)
    source: int
    ok: bool
    problems: Tuple[str, ...] = ()
    doubts: Tuple[str, ...] = ()


@dataclass
class Gate:
    """
    The output mux's rule: pass the target's commands on, or latch a stop.

    Open only when the sensor mux, heard within stale_after s, says ok for the target's
    source; nothing on /system/source says otherwise; and both have held for settle s.

    Evidence latches a stop until clear(), which a person calls and which works only once
    the evidence has gone: an announcement of another source, the sensor mux's problems,
    or a sensor mux checking for another source. Doubt only waits, closed, and reopens
    after settle s of all clear: the sensor mux not heard yet or quiet, or its doubts.
    """

    target: str
    settle: float = 2.0             # s of all clear before commands flow
    stale_after: float = 3.0        # s: a quieter sensor mux closes the gate (waits)
    report: Optional[Report] = None
    entries: List[Entry] = field(default_factory=list)
    latched: Tuple[str, ...] = ()   # why it stopped, while latched
    clear_since: Optional[float] = None

    def __post_init__(self):
        self.expected = target_of(self.target)

    def judge(self, now: float) -> Tuple[List[str], List[str]]:
        """Return (problems, waits) now: what latches a stop, and what only holds it shut."""
        if self.report is None:
            return [], ['waiting for the sensor mux (/system/sensor_mux/state)']
        problems, waits = [], []
        age = now - self.report.time
        if age > self.stale_after:
            waits.append(f'the sensor mux is quiet ({age:.1f} s)')
        if self.report.source != self.expected:
            problems.append(f'the sensor mux checks for {kind_name(self.report.source)}, '
                            f'target {self.target} needs {kind_name(self.expected)}')
        elif not self.report.ok:
            problems += self.report.problems
            waits += [f'unsure: {d}' for d in self.report.doubts]
            if not self.report.problems and not self.report.doubts:
                problems.append('the sensor mux says no')
        problems += foreign(self.entries, self.expected)
        return problems, waits

    def update(self, now: float) -> None:
        """Re-judge, after a report, an announcement, a command or a tick."""
        if self.latched:
            return
        problems, waits = self.judge(now)
        if problems:
            self.latched = tuple(problems)
            self.clear_since = None
        elif waits:
            self.clear_since = None
        elif self.clear_since is None:
            self.clear_since = now

    def is_open(self, now: float) -> bool:
        """Whether a command arriving now goes on to the target."""
        self.update(now)
        return (not self.latched and self.clear_since is not None
                and now - self.clear_since >= self.settle)

    def clear(self, now: float) -> Tuple[bool, str]:
        """Unlatch, if the evidence has gone: a person's reset. Commands flow after settle."""
        problems, waits = self.judge(now)
        if problems:
            return False, 'still wrong: ' + '; '.join(problems)
        was = self.latched
        self.latched = ()
        self.clear_since = None if waits else now
        then = ('once ' + '; '.join(waits) + ' passes') if waits else f'in {self.settle:g} s'
        return True, (f'cleared ({"; ".join(was)}): commands flow {then}'
                      if was else 'nothing was latched')

    def state(self, now: float) -> str:
        """One line for people: OPEN, WAIT or STOP, the target, and why."""
        want = kind_name(self.expected)
        if self.is_open(now):
            return f'OPEN - {self.target}: every source {want}'
        if self.latched:
            return (f'STOP - target {self.target} needs {want} - ' + '; '.join(self.latched)
                    + ' - latched: /safety/output_mux/clear')
        _, waits = self.judge(now)
        if waits:
            return f'WAIT - {self.target}: ' + '; '.join(waits)
        return f'WAIT - {self.target}: all {want}, settling for {self.settle:g} s'
