"""Tests for tools/survey_car.sh: each machine's login, and nothing secret on the way."""

import os
from pathlib import Path
import subprocess

TOOLS = Path(__file__).resolve().parents[1]

# A stand-in for ssh: it records its arguments and the password helper's settings.
FAKE_SSH = """#!/usr/bin/env bash
{ printf 'args:%s\\n' "$*"
  printf 'entry:%s\\n' "${AAV_KEYCHAIN_ENTRY:-}"
  printf 'askpass:%s\\n' "${SSH_ASKPASS:-}"
  printf 'require:%s\\n' "${SSH_ASKPASS_REQUIRE:-}"; } >> "$SSH_LOG"
cat > /dev/null
echo '==== done'
"""


def survey(tmp_path, hosts):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    (bin_dir / 'ssh').write_text(FAKE_SSH)
    (bin_dir / 'ssh').chmod(0o755)
    (tmp_path / 'hosts.txt').write_text(hosts)
    log = tmp_path / 'ssh.log'
    env = {**os.environ, 'PATH': f'{bin_dir}:{os.environ["PATH"]}',
           'SSH_LOG': str(log), 'SURVEY_OUT': str(tmp_path / 'out')}
    env.pop('SSH_ASKPASS', None)
    done = subprocess.run(['bash', str(TOOLS / 'survey_car.sh'), str(tmp_path / 'hosts.txt')],
                          capture_output=True, text=True, env=env, timeout=60, check=True)
    lines = log.read_text().splitlines()   # four lines a call: args, entry, askpass, require
    calls = [dict(line.split(':', 1) for line in lines[i:i + 4]) for i in range(0, len(lines), 4)]
    return done.stdout, calls


def test_a_keychain_entry_feeds_ssh_and_none_leaves_it_asking(tmp_path):
    out, calls = survey(tmp_path, '# the car\n'
                                  'CAM2-PI   aav@192.168.1.118   aav-cam2   # a comment\n'
                                  'CORTEX    aav@192.168.1.120              # no entry\n'
                                  'MOTOR-PI  pi@192.168.1.193\n')
    assert [c['entry'] for c in calls] == ['aav-cam2', '', '']
    assert calls[0]['askpass'] == str(TOOLS / 'keychain_askpass.sh')
    assert calls[0]['require'] == 'force'
    assert calls[1]['askpass'] == '' and calls[2]['askpass'] == ''
    for c in calls:
        assert 'StrictHostKeyChecking=accept-new' in c['args']
        assert 'NumberOfPasswordPrompts=1' in c['args']
    assert out.count('OK') == 3


def test_the_helper_answers_only_a_password_prompt():
    helper = str(TOOLS / 'keychain_askpass.sh')
    env = {**os.environ, 'AAV_KEYCHAIN_ENTRY': 'aav-cam2'}
    for prompt in ('Are you sure you want to continue connecting (yes/no)?', ''):
        assert subprocess.run(['bash', helper, prompt], env=env,
                              capture_output=True).returncode == 1
    no_entry = {k: v for k, v in os.environ.items() if k != 'AAV_KEYCHAIN_ENTRY'}
    assert subprocess.run(['bash', helper, "aav@x's password: "], env=no_entry,
                          capture_output=True).returncode == 1
