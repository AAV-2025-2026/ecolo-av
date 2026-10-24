"""
The ESP32 firmware in QEMU: check it brakes when the Motor-Pi's frames stop.

`pixi run esp-qemu-check` (tools/esp32.sh qemu) builds the Rust firmware with
`--features qemu`, makes a flash image, and runs this. No ROS here, so the tests run
anywhere (tools/tests/test_esp32_qemu.py). docs/esp32-bench.md, "Before the board: the
emulator", has the picture and the results.

  this script --frames--> unix socket --> QEMU UART1 --> the firmware's LegacyLink
  this script <--lines--- unix socket <-- QEMU UART0 <-- the firmware's log

The frames are the real protocol: aav_legacy's own `pack_frame`, at the bridge's 50 Hz,
with its drive and stale-stop values. The firmware logs three kinds of line (src/main.rs):

  EVENT   t=<ms> mode=.. armed=.. estop=.. throttle=.. brake=.. ... faults=..  on a change
  STATUS  the same, every 200 ms
  DEVICES t=<ms> steering=<Jrk> brake=<Jrk> dac=<code> expander=..  what the stand-in
          devices were last told: the bytes the car's Jrks and DAC would get

Each cycle: stop frames (the arming edge), drive frames, silence (the heartbeat stops),
drive frames again without a stop (it must stay latched). The next cycle's stop frames
re-arm it.

Times: `t` is the firmware's clock (esp-hal's Instant, from QEMU's virtual clock, which
follows the host's clock without -icount). The host notes when each line arrives;
the smallest (arrival - t) maps one clock to the other (ClockMap).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from typing import Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/backends/aav_legacy'))
from aav_legacy.legacy_protocol import LegacyMapping, pack_frame, stop_command, to_legacy  # noqa: E402,E501

# The firmware's numbers (spine-core's SpineConfig, spine-board's Calibration::TODAY).
TIMEOUT_MS = 100            # cmd_timeout_ms
LIMIT_MS = 200              # what the bench test asks for: within 0.2 s (esp32-bench.md 8)
CMD_TIMEOUT = 0x0001        # faults::CMD_TIMEOUT
BRAKE_FULL = 3500           # the brake Jrk's target, full on
BRAKE_RELEASED = 400

RATE_HZ = 50.0              # legacy_uart_bridge's rate_hz
DRIVE = (0.6, 0.0)          # ego's command while driving: 0.6 m/s, straight
EFUSE_REV3 = bytes.fromhex(  # chip revision 3, as ESP-IDF's `idf.py qemu` writes it
    '00000000000000000000000000800000000000000000100000000000000000000000000000000000'
    + '00' * 80 + '00000000')

ANSI = re.compile(r'\x1b\[[0-9;]*m')
FIELD = re.compile(r'(\w+)=(\S+)')


# --- The firmware's lines -------------------------------------------------------------

@dataclass
class Line:
    """One line of the firmware's log, and when it reached this computer."""

    host: float                 # s, time.monotonic()
    kind: str                   # EVENT, STATUS, DEVICES, or TEXT
    t: Optional[int] = None     # the firmware's ms since boot
    fields: dict = field(default_factory=dict)
    text: str = ''

    def get(self, key):
        """Return a field as a number or a word (bool for true/false)."""
        value = self.fields[key]
        if value in ('true', 'false'):
            return value == 'true'
        try:
            return int(value, 0)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value


def parse_line(text: str, host: float) -> Line:
    """Read one log line; anything that isn't EVENT, STATUS or DEVICES is TEXT."""
    text = ANSI.sub('', text).strip()
    for kind in ('EVENT', 'STATUS', 'DEVICES'):
        marker = kind + ' t='
        at = text.find(marker)
        if at >= 0:
            fields = dict(FIELD.findall(text[at + len(kind):]))
            return Line(host, kind, int(fields['t']), fields, text)
    return Line(host, 'TEXT', text=text)


@dataclass
class ClockMap:
    """The firmware's clock against the host's, from the lines' arrival times."""

    offset: float               # s: host = firmware + offset, for the fastest line
    rate: float                 # firmware seconds per host second, over the run

    @classmethod
    def fit(cls, lines: Iterable[Line]) -> 'ClockMap':
        timed = [ln for ln in lines if ln.t is not None]
        if len(timed) < 2:
            raise ValueError('need two timed lines to map the clocks')
        offset = min(ln.host - ln.t / 1000 for ln in timed)
        first, last = timed[0], timed[-1]
        span = last.host - first.host
        rate = (last.t - first.t) / 1000 / span if span > 0 else 1.0
        return cls(offset, rate)

    def to_firmware_ms(self, host: float) -> float:
        """Return the firmware's ms at a host time."""
        return (host - self.offset) * 1000


# --- One cycle, judged ----------------------------------------------------------------

@dataclass
class Cycle:
    """What was sent in one cycle (host times, s)."""

    stop_from: float
    drive_from: float
    last_frame: float           # the last drive frame before the silence
    resume_from: float          # drive frames again, without a stop
    end: float


@dataclass
class Result:
    """One cycle's findings. `None`: it didn't happen."""

    drove: bool = False                     # armed, throttle on, brake released
    dac_rose: int = 0                       # the DAC's highest code while driving
    timeout_fw_ms: Optional[float] = None   # last frame -> the timeout event, firmware clock
    timeout_host_ms: Optional[float] = None  # the same, as the host saw the line arrive
    brake_full_fw_ms: Optional[float] = None  # last frame -> brake Jrk 3500 and DAC 0
    fault_bit: bool = False                 # the timeout event has CMD_TIMEOUT
    stopped: bool = False                   # it says throttle 0, brake 1.00, not armed
    latched: Optional[bool] = None          # fresh frames without a stop didn't drive
    problems: List[str] = field(default_factory=list)

    @property
    def ok(self):
        """Return True if this cycle did all it should."""
        return not self.problems


def judge(cycle: Cycle, lines: List[Line], clock: ClockMap) -> Result:
    """Check one cycle against what the firmware logged."""
    r = Result()
    fw = clock.to_firmware_ms
    t_drive, t_last = fw(cycle.drive_from), fw(cycle.last_frame)
    t_resume, t_end = fw(cycle.resume_from), fw(cycle.end)
    timed = [ln for ln in lines if ln.t is not None]
    status = [ln for ln in timed if ln.kind in ('EVENT', 'STATUS')]
    devices = [ln for ln in timed if ln.kind == 'DEVICES']

    driving = [ln for ln in status if t_drive <= ln.t <= t_last
               and ln.get('armed') and ln.get('mode') == 'Computer'
               and ln.get('throttle') > 0 and ln.get('brake') == 0]
    r.drove = bool(driving)
    while_driving = [ln for ln in devices if t_drive <= ln.t <= t_last]
    r.dac_rose = max((ln.get('dac') for ln in while_driving), default=0)
    if not r.drove:
        r.problems.append('never drove: no armed Computer line with throttle on')
    elif not any(ln.get('brake') == BRAKE_RELEASED for ln in while_driving):
        r.problems.append('the brake Jrk was never released while driving')

    tripped = next((ln for ln in timed if ln.kind == 'EVENT' and ln.t > t_last
                    and ln.get('faults') & CMD_TIMEOUT), None)
    if tripped is None:
        r.problems.append('no timeout event after the frames stopped')
    else:
        r.fault_bit = True
        r.timeout_fw_ms = tripped.t - t_last
        r.timeout_host_ms = (tripped.host - cycle.last_frame) * 1000
        r.stopped = (tripped.get('throttle') == 0 and tripped.get('brake') == 1.0
                     and not tripped.get('armed'))
        if not r.stopped:
            r.problems.append(f'the timeout event did not stop the car: {tripped.text}')
        if not TIMEOUT_MS <= r.timeout_fw_ms <= LIMIT_MS:
            r.problems.append(f'timeout after {r.timeout_fw_ms:.0f} ms, '
                              f'not {TIMEOUT_MS}-{LIMIT_MS}')
    braked = next((ln for ln in devices if ln.t > t_last
                   and ln.get('brake') == BRAKE_FULL and ln.get('dac') == 0), None)
    if braked is None:
        r.problems.append('the brake Jrk never got 3500 with the DAC at 0')
    else:
        r.brake_full_fw_ms = braked.t - t_last
        if r.brake_full_fw_ms > LIMIT_MS:
            r.problems.append(f'full brake after {r.brake_full_fw_ms:.0f} ms')

    # Fresh frames, no stop first: it must stay stopped (esp32-bench.md step 9).
    resumed = [ln for ln in status if t_resume <= ln.t <= t_end]
    moved = [ln for ln in resumed if ln.get('armed') or ln.get('throttle') > 0
             or ln.get('brake') < 1.0]
    moved_devices = [ln for ln in devices if t_resume <= ln.t <= t_end
                     and (ln.get('dac') > 0 or ln.get('brake') != BRAKE_FULL)]
    if not resumed:
        r.problems.append('no lines while the frames came back')
    else:
        r.latched = not moved and not moved_devices
        if not r.latched:
            r.problems.append('fresh frames without a stop drove again: '
                              + (moved or moved_devices)[0].text)
        elif not all(ln.get('faults') & CMD_TIMEOUT for ln in resumed):
            r.problems.append('the timeout fault bit cleared without a stop')
    return r


# --- The run --------------------------------------------------------------------------

class Firmware:
    """QEMU running the flash image, with its log and the Motor-Pi's UART on sockets."""

    def __init__(self, qemu: Path, flash: Path, workdir: Path):
        self.lines: List[Line] = []
        self.lock = threading.Lock()
        efuse = workdir / 'efuse.bin'
        efuse.write_bytes(EFUSE_REV3)
        log_sock, motor_sock = workdir / 'log.sock', workdir / 'motor.sock'
        self.proc = subprocess.Popen(
            [str(qemu), '-machine', 'esp32', '-m', '4M', '-display', 'none',
             '-monitor', 'none', '-nic', 'none',
             '-drive', f'file={flash},if=mtd,format=raw',
             '-drive', f'file={efuse},if=none,format=raw,id=efuse',
             '-global', 'driver=nvram.esp32.efuse,property=drive,value=efuse',
             '-serial', f'unix:{log_sock},server=on,wait=on',      # UART0: the log
             '-serial', f'unix:{motor_sock},server=on,wait=on',    # UART1: the Motor-Pi
             '-serial', 'null'],                                   # UART2: iBUS, silent
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        self.log = self._connect(log_sock)
        self.motor = self._connect(motor_sock)
        threading.Thread(target=self._read, daemon=True).start()

    def _connect(self, path: Path, wait: float = 20.0) -> socket.socket:
        deadline = time.monotonic() + wait
        while True:
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(str(path))
                return s
            except OSError:
                s.close()
                if time.monotonic() > deadline or self.proc.poll() is not None:
                    out = self.proc.stdout.read().decode(errors='replace') if \
                        self.proc.poll() is not None else ''
                    raise RuntimeError(f'QEMU did not open {path.name}: {out}')
                time.sleep(0.05)

    def _read(self):
        buf = b''
        while True:
            try:
                chunk = self.log.recv(4096)
            except OSError:
                return
            if not chunk:
                return
            now = time.monotonic()
            buf += chunk
            *done, buf = buf.split(b'\n')
            with self.lock:
                self.lines.extend(parse_line(d.decode(errors='replace'), now) for d in done)

    def snapshot(self) -> List[Line]:
        with self.lock:
            return list(self.lines)

    def wait_for(self, pred, timeout: float) -> Line:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            found = next((ln for ln in self.snapshot() if pred(ln)), None)
            if found:
                return found
            if self.proc.poll() is not None:
                break
            time.sleep(0.02)
        raise RuntimeError('timed out waiting for the firmware; its log:\n'
                           + '\n'.join(ln.text for ln in self.snapshot()[-30:]))

    def send_for(self, values: Tuple[float, float, float], seconds: float) -> float:
        """Send one frame every 20 ms for `seconds`; return when the last one went."""
        frame = pack_frame(*values)
        start = time.monotonic()
        n = 0
        last = start
        while True:
            due = start + n / RATE_HZ
            if due - start >= seconds:
                return last
            pause = due - time.monotonic()
            if pause > 0:
                time.sleep(pause)
            self.motor.sendall(frame)
            last = time.monotonic()
            n += 1

    def stop(self):
        for s in (self.motor, self.log):
            s.close()
        self.proc.kill()
        self.proc.wait()


def run(qemu: Path, flash: Path, cycles: int) -> Tuple[List[Result], ClockMap, List[Line]]:
    """Boot the firmware, run the cycles, and judge each one."""
    mapping = LegacyMapping()
    drive = to_legacy(*DRIVE, mapping)
    stale = stop_command(mapping)
    with tempfile.TemporaryDirectory(prefix='esp-qemu-', dir='/tmp') as tmp:
        fw = Firmware(qemu, flash, Path(tmp))
        try:
            fw.wait_for(lambda ln: ln.kind == 'STATUS', timeout=30)
            plan = []
            for _ in range(cycles):
                stop_from = time.monotonic()
                fw.send_for(stale, 0.3)
                drive_from = time.monotonic()
                last = fw.send_for(drive, 1.0)
                time.sleep(0.6)
                resume_from = time.monotonic()
                fw.send_for(drive, 0.6)
                plan.append(Cycle(stop_from, drive_from, last, resume_from, time.monotonic()))
            time.sleep(0.3)
            lines = fw.snapshot()
        finally:
            fw.stop()
    clock = ClockMap.fit(lines)
    return [judge(c, lines, clock) for c in plan], clock, lines


def table(results: List[Result], clock: ClockMap) -> str:
    """Return the results as a markdown table, for the docs."""
    def ms(v):
        return '-' if v is None else f'{v:.0f}'
    rows = ['| Cycle | Drove (DAC peak) | Timeout, firmware ms | Seen on host, ms '
            '| Full brake + DAC 0, ms | Fault bit 1 | Latched until a stop | Result |',
            '|---|---|---|---|---|---|---|---|']
    for i, r in enumerate(results, 1):
        rows.append(
            f'| {i} | {"yes" if r.drove else "no"} ({r.dac_rose}) | {ms(r.timeout_fw_ms)} '
            f'| {ms(r.timeout_host_ms)} | {ms(r.brake_full_fw_ms)} '
            f'| {"yes" if r.fault_bit else "no"} | {"yes" if r.latched else "no"} '
            f'| {"pass" if r.ok else "FAIL"} |')
    rows.append('')
    rows.append(f'Clocks: firmware {clock.rate:.3f} s per host s over the run.')
    return '\n'.join(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--qemu', type=Path, required=True, help='qemu-system-xtensa')
    ap.add_argument('--flash', type=Path, required=True, help='the merged 4 MB flash image')
    ap.add_argument('--cycles', type=int, default=3)
    ap.add_argument('--log', type=Path, help='save the firmware log here')
    args = ap.parse_args(argv)
    results, clock, lines = run(args.qemu, args.flash, args.cycles)
    if args.log:
        args.log.write_text(''.join(f'{ln.host:.4f} {ln.text}\n' for ln in lines))
    boot = next((ln.text for ln in lines if 'spine-esp32-umod' in ln.text), '(no boot line)')
    print(boot)
    print(table(results, clock))
    for i, r in enumerate(results, 1):
        for p in r.problems:
            print(f'cycle {i}: {p}')
    ok = all(r.ok for r in results)
    print('PASS: it brakes when the frames stop, and stays braked until a stop frame'
          if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
