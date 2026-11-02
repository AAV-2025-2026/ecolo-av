"""
Tests for tools/car_setup.sh: its dry run changes nothing, and --apply needs the role typed.

Each run gets an empty HOME in a temporary folder: the test checks it stays empty.
"""

import configparser
from pathlib import Path
import re
import subprocess

import pytest

TOOLS = Path(__file__).resolve().parents[1]
SCRIPT = TOOLS / 'car_setup.sh'
ROLES = ['orin', 'motor_pi', 'localization', 'dash', 'camera_pi', 'lab_desktop']


def run(home, *args, stdin='', os_release=None):
    env = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'HOME': str(home)}
    if os_release:
        path = home.parent / 'os-release'
        path.write_text(os_release)
        env['AAV_OS_RELEASE'] = str(path)
    return subprocess.run(['bash', str(SCRIPT), *args], input=stdin, capture_output=True,
                          text=True, timeout=60, env=env)


@pytest.fixture
def home(tmp_path):
    h = tmp_path / 'home'
    h.mkdir()
    return h


UBUNTU_22 = 'ID=ubuntu\nVERSION_ID="22.04"\nPRETTY_NAME="Ubuntu 22.04.5 LTS"\n'
PI_OS = 'ID=debian\nVERSION_ID="13"\nPRETTY_NAME="Debian GNU/Linux 13 (trixie)"\n'


@pytest.mark.parametrize('role', ROLES)
def test_a_dry_run_prints_every_step_and_changes_nothing(home, role):
    done = run(home, role)
    assert done.returncode == 0, done.stdout + done.stderr
    assert 'Dry run: nothing changes' in done.stdout
    for step in ('backup', 'upgrade', 'install', 'services', 'check'):
        assert f'== {step}' in done.stdout
    assert list(home.iterdir()) == []


def test_no_role_or_a_wrong_one_lists_the_roles(home):
    for args in ((), ('jetson',)):
        done = run(home, *args)
        assert done.returncode == 2
        assert all(r in done.stderr for r in ROLES)


def test_a_wrong_step_or_option_is_refused(home):
    assert run(home, 'orin', 'reflash').returncode == 2
    assert run(home, 'orin', '--yes').returncode == 2
    assert run(home, 'orin', '--address', '192.168.1.140').returncode == 2


def test_steps_can_be_picked(home):
    done = run(home, 'orin', 'check')
    assert '== check' in done.stdout and '== backup' not in done.stdout


def test_apply_without_the_role_typed_changes_nothing(home):
    # On Linux: the wrong word stops it. On a Mac: refused before it asks.
    done = run(home, 'motor_pi', 'backup', 'services', '--apply', stdin='orin\n')
    assert done.returncode == 1
    assert 'Nothing changed' in done.stderr or 'Refused' in done.stderr
    assert list(home.iterdir()) == []


def test_ubuntu_22_prints_the_release_upgrade_but_runs_it_only_when_asked(home):
    plain = run(home, 'motor_pi', 'upgrade', os_release=UBUNTU_22).stdout
    assert 'would run: sudo do-release-upgrade' not in plain
    assert 'sudo do-release-upgrade' in plain and 'add --release-upgrade' in plain
    asked = run(home, 'motor_pi', 'upgrade', '--release-upgrade', os_release=UBUNTU_22).stdout
    assert 'would run: sudo do-release-upgrade' in asked
    assert 'port 1022' in asked


def test_the_orin_and_pi_os_never_release_upgrade(home):
    orin = run(home, 'orin', 'upgrade', '--release-upgrade', os_release=UBUNTU_22).stdout
    assert 'do-release-upgrade' in orin and 'would run: sudo do-release-upgrade' not in orin
    assert 'reflash' in orin
    pi = run(home, 'camera_pi', 'upgrade', '--release-upgrade', os_release=PI_OS).stdout
    assert 'would run: sudo do-release-upgrade' not in pi
    assert 'new SD card' in pi


def test_services_by_role(home):
    orin = run(home, 'orin', 'services').stdout
    assert 'allow 192.168.1.0/24' in orin
    assert 'AAV_MACHINE=orin' in orin
    assert 'loginctl enable-linger' in orin
    assert 'systemctl --user enable aav-car' in orin
    pi = run(home, 'motor_pi', 'services', '--machine', 'motor_pi_alone').stdout
    assert 'server 192.168.1.140' in pi and 'AAV_MACHINE=motor_pi_alone' in pi
    for role in ('localization', 'dash', 'camera_pi', 'lab_desktop'):
        assert 'enable aav-car' not in run(home, role, 'services').stdout
    assert 'enable mediamtx' in run(home, 'camera_pi', 'services').stdout


def test_a_fixed_address_goes_beside_dhcp(home):
    out = run(home, 'localization', 'services', '--address', '192.168.1.113/24',
              '--interface', 'eth0', os_release=UBUNTU_22).stdout
    assert 'dhcp4: true' in out and 'addresses: [192.168.1.113/24]' in out
    assert 'netplan try' in out


def test_bash_3_2_only():
    body = SCRIPT.read_text()
    for bash4 in (r'declare -A', r'\$\{\w+,,\}', r'\$\{\w+\^\^\}', r'\bmapfile\b',
                  r'\breadarray\b', r'\|&', r'&>>', r'\bcoproc\b'):
        assert not re.search(bash4, body), bash4
    subprocess.run(['bash', '-n', str(SCRIPT)], check=True)


def test_the_unit_runs_our_stack_from_car_env():
    unit = configparser.ConfigParser(interpolation=None, strict=False)
    unit.read(TOOLS / 'systemd' / 'aav-car.service')
    assert unit['Service']['EnvironmentFile'] == '%h/.config/aav/car.env'
    assert unit['Service']['ExecStart'].startswith(
        '%h/aav-jazzy/aav.sh ros2 launch aav_bringup car.launch.py machine:=${AAV_MACHINE}')
    assert unit['Service']['KillSignal'] == 'SIGINT'
    assert unit['Install']['WantedBy'] == 'default.target'
    env = (TOOLS / 'systemd' / 'car.env').read_text()
    keys = [line.split('=', 1)[0] for line in env.splitlines()
            if line and not line.startswith('#')]
    assert keys == ['AAV_MACHINE', 'AAV_CAR_ARGS']


def test_every_machine_the_units_name_exists():
    machines = TOOLS.parent / 'ros' / 'bringup' / 'aav_bringup' / 'config' / 'machines'
    for name in ('orin', 'motor_pi', 'motor_pi_alone'):
        assert (machines / f'{name}.yaml').is_file()
