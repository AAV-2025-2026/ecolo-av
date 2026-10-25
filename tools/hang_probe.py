#!/usr/bin/env python3
"""
Run a command; if it hasn't finished in SECONDS, say where it is stuck, as annotations.

TEMPORARY (TODO 42), for the Mac nightly's hang: GitHub hides a job's log from anyone not
signed in, but not its annotations. On a hang this prints, for each process of the
command: its native threads' stacks (lldb, macOS) and Python's own (faulthandler, through
SIGABRT); then it stops the command and fails.

  python3 tools/hang_probe.py SECONDS COMMAND...
"""

import os
import re
import signal
import subprocess
import sys
import time


def escape(text):
    return text.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')


def native_stacks(pid, frames=14):
    """Each thread's top frames, from lldb; '' where lldb can't attach."""
    try:
        out = subprocess.run(['sudo', '-n', 'lldb', '-p', str(pid), '--batch',
                              '-o', 'thread backtrace all', '-o', 'detach'],
                             capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        return f'lldb: {e}'
    keep, depth = [], 0
    for line in out.splitlines():
        if re.match(r'\s*\*? *thread #\d+', line):
            keep.append(line.strip()[:140])
            depth = 0
        elif re.match(r'\s*\*? *frame #\d+', line):
            depth += 1
            if depth <= frames:
                # Drop the address; keep the library and the function.
                keep.append('  ' + re.sub(r'0x[0-9a-f]+ ', '', line.strip())[:160])
    return '\n'.join(keep) or out[-3000:]


def main(argv):
    seconds, cmd = float(argv[1]), argv[2:]
    env = dict(os.environ, PYTHONFAULTHANDLER='1')
    log_path = f'hang-probe-{os.getpid()}.log'
    with open(log_path, 'w') as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env,
                                start_new_session=True)
        start = time.monotonic()
        try:
            code = proc.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            code = None
    with open(log_path, errors='replace') as f:
        print(f.read(), end='')
    if code is not None:
        print(f'hang_probe: finished in {time.monotonic() - start:.1f} s, exit {code}')
        return code

    pids = subprocess.run(['pgrep', '-g', str(proc.pid)], capture_output=True,
                          text=True).stdout.split()
    pids = pids or [str(proc.pid)]
    print(f'hang_probe: still running after {seconds:.0f} s: processes {" ".join(pids)}')
    for pid in pids[:4]:
        ps = subprocess.run(['ps', '-o', 'pid,ppid,stat,etime,command', '-p', pid],
                            capture_output=True, text=True).stdout
        stacks = native_stacks(pid)
        print(stacks)
        print(f'::error title=hang_probe native stacks of {pid}::{escape(ps + stacks)}')
    # Python's own stacks, every thread: faulthandler prints them on SIGABRT.
    size = os.path.getsize(log_path)
    for pid in pids:
        try:
            os.kill(int(pid), signal.SIGABRT)
        except OSError:
            pass
    time.sleep(5)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        pass
    with open(log_path, errors='replace') as f:
        f.seek(size)
        dump = f.read()
    print(dump)
    lines = [line[:200] for line in dump.strip().splitlines()[-120:]]
    print(f'::error title=hang_probe Python stacks::{escape(chr(10).join(lines))}')
    with open(log_path, errors='replace') as f:
        before = f.read(size).strip().splitlines()[-30:]
    print(f'::error title=hang_probe output before the hang::{escape(chr(10).join(before))}')
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
