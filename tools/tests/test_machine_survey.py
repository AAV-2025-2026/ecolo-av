"""Tests for tools/machine_survey.sh: it hides secrets, and runs to the end."""

from pathlib import Path
import subprocess

SCRIPT = Path(__file__).resolve().parents[1] / 'machine_survey.sh'


def redact(text):
    """Pass some text through the script's own redaction function."""
    body = SCRIPT.read_text()
    func = body[body.index('redact() {'):]
    func = func[:func.index('\n}\n') + 3]
    done = subprocess.run(['bash', '-c', func + 'redact'], input=text,
                          capture_output=True, text=True, check=True)
    return done.stdout


def test_secrets_are_cut():
    lines = [
        'export NTRIP_PASSWORD=hunter2',
        'password: "hunter2"',
        'wifi psk=hunter2',
        'git remote https://someone:hunter2@github.com/x/y.git',
        'TOKEN=ghp_' + 'a' * 36,
        'apiKey: AIza' + 'b' * 35,
        'str2str -in ntrip://user:hunter2@rtk2go.com:2101/MOUNT',
        'mosquitto_pub -p hunter2',
    ]
    out = redact('\n'.join(lines) + '\n')
    assert 'hunter2' not in out
    assert 'a' * 36 not in out and 'b' * 35 not in out
    assert out.count('<redacted>') >= len(lines)


def test_ordinary_lines_stay():
    text = 'export ROS_DOMAIN_ID=10\nsource /opt/ros/humble/setup.bash\n'
    assert redact(text) == text


def test_runs_to_the_end_here():
    done = subprocess.run(['bash', str(SCRIPT)], capture_output=True, text=True,
                          timeout=300, env={'PATH': '/usr/bin:/bin:/usr/sbin:/sbin',
                                            'SURVEY_FIND_SECONDS': '20'})
    assert '==== done' in done.stdout
    assert '==== hardware: cameras' in done.stdout
