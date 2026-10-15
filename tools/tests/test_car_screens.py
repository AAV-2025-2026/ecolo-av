"""
Tests for the car's two screens at boot (docs/car-screens.md).

- tools/screens/*.service: systemd user units. No systemd-analyze on a Mac, so a small
  parser checks what systemd would refuse or ignore: unknown sections and keys, inline
  comments, ExecStart's script.
- tools/screens/aav-screens.desktop: the desktop's autostart entry.
- tools/car_screen.sh: its config reading, with --print (it runs nothing).
- tools/car_screens_install.sh: only --dry-run, in a made-up home: it must change nothing.
"""

from pathlib import Path
import platform
import shlex
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCREENS = ROOT / 'tools' / 'screens'
SCREEN = ROOT / 'tools' / 'car_screen.sh'
INSTALL = ROOT / 'tools' / 'car_screens_install.sh'

# What these units may use (systemd.unit(5), systemd.service(5), systemd.exec(5)).
UNIT_KEYS = {
    'Unit': {'Description', 'Documentation', 'After', 'PartOf', 'StartLimitIntervalSec'},
    'Service': {'Type', 'ExecStart', 'Restart', 'RestartSec', 'RestartPreventExitStatus',
                'TimeoutStopSec', 'SyslogIdentifier'},
    'Install': {'WantedBy'},
}


def parse_ini(path):
    """Sections of KEY=value, as systemd and the desktop-entry spec read them."""
    sections, current = {}, None
    for n, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line[0] in '#;':
            continue
        if line.startswith('[') and line.endswith(']'):
            current = line[1:-1]
            assert current not in sections, f'{path.name}:{n}: [{current}] twice'
            sections[current] = {}
            continue
        assert current is not None, f'{path.name}:{n}: a key before any [section]'
        assert '=' in line, f'{path.name}:{n}: not KEY=value: {line}'
        key, value = (part.strip() for part in line.split('=', 1))
        assert key not in sections[current], f'{path.name}:{n}: {key} twice'
        sections[current][key] = value
    return sections


@pytest.mark.parametrize('which', ['hud', 'map'])
def test_unit_files_are_valid(which):
    unit = parse_ini(SCREENS / f'aav-{which}.service')
    assert set(unit) == set(UNIT_KEYS)
    for section, keys in unit.items():
        unknown = set(keys) - UNIT_KEYS[section]
        assert not unknown, f'[{section}] has keys systemd would ignore here: {unknown}'
        for key, value in keys.items():
            # systemd has no inline comments: a # would become part of the value.
            assert ' #' not in value and ' ;' not in value, f'{key}: inline comment?'
    service = unit['Service']
    exe, *args = shlex.split(service['ExecStart'])
    assert exe == '%h/aav-jazzy/aav.sh', 'aav.sh, where car_install.sh puts it'
    assert args == ['tools/car_screen.sh', which]
    assert service['Restart'] == 'always' and int(service['RestartSec']) > 0
    assert service['RestartPreventExitStatus'] == '78', "car_screen.sh's EX_CONFIG"
    assert service['SyslogIdentifier'] == f'aav-{which}'
    assert unit['Unit']['StartLimitIntervalSec'] == '0', 'never give up'
    assert unit['Unit']['PartOf'] == 'graphical-session.target'
    assert unit['Install']['WantedBy'] == 'graphical-session.target'


def test_autostart_entry_starts_both():
    entry = parse_ini(SCREENS / 'aav-screens.desktop')['Desktop Entry']
    assert entry['Type'] == 'Application'
    words = shlex.split(entry['Exec'])
    assert words[:2] == ['sh', '-c'] and len(words) == 3
    assert 'import-environment DISPLAY' in words[2]
    assert 'start aav-hud.service aav-map.service' in words[2]


def test_the_config_template_has_every_key():
    keys = [line.split('=', 1)[0] for line in (SCREENS / 'screens.env').read_text().splitlines()
            if line and not line.startswith('#')]
    assert keys == ['AAV_HUD_MONITOR', 'AAV_MAP_MONITOR', 'AAV_ROS_DOMAIN_ID',
                    'AAV_STREET_MAP', 'AAV_PLACES']


def write_config(tmp_path, **values):
    """Write the template, with @PREFIX@ filled in and some keys set."""
    text = (SCREENS / 'screens.env').read_text().replace('@PREFIX@', str(tmp_path))
    lines = []
    for line in text.splitlines():
        key = line.split('=', 1)[0]
        lines.append(f'{key}={values.pop(key)}' if key in values else line)
    lines += [f'{k}={v}' for k, v in values.items()]
    path = tmp_path / 'screens.env'
    path.write_text('\n'.join(lines) + '\n')
    return path


def screen(which, config, *extra):
    return subprocess.run(['bash', str(SCREEN), which, '--config', str(config), '--print',
                           *extra], capture_output=True, text=True)


def test_hud_runs_full_screen_on_its_monitor(tmp_path):
    cfg = write_config(tmp_path, AAV_HUD_MONITOR='HDMI-1', AAV_MAP_MONITOR='HDMI-2')
    done = screen('hud', cfg)
    assert done.returncode == 0, done.stderr
    env, cmd = done.stdout.splitlines()
    assert env == 'ROS_DOMAIN_ID=42'
    assert shlex.split(cmd) == ['ros2', 'launch', 'aav_hud_raylib', 'hud.launch.py',
                                'fullscreen:=true', 'monitor:=HDMI-1']


def test_map_gets_its_monitor_and_files(tmp_path):
    cfg = write_config(tmp_path, AAV_HUD_MONITOR='0', AAV_MAP_MONITOR='"Studio Display"',
                       AAV_ROS_DOMAIN_ID='7')
    done = screen('map', cfg)
    assert done.returncode == 0, done.stderr
    env, cmd = done.stdout.splitlines()
    assert env == 'ROS_DOMAIN_ID=7'
    assert shlex.split(cmd) == [
        'ros2', 'launch', 'aav_hud_raylib', 'map.launch.py', 'fullscreen:=true',
        'monitor:=Studio Display',
        f'streets:={tmp_path}/aav/maps/streets/ottawa.pmtiles',
        f'places:={tmp_path}/aav/maps/places/ottawa.db']
    assert "isn't there" in done.stderr, 'missing map files are noted, not fatal'


@pytest.mark.parametrize('values, says', [
    ({}, 'AAV_HUD_MONITOR is empty'),
    ({'AAV_HUD_MONITOR': 'HDMI-1', 'AAV_ROS_DOMAIN_ID': 'forty'}, 'from 0 to 232'),
    ({'AAV_HUD_MONITOR': 'HDMI-1', 'AAV_ROS_DOMAIN_ID': '300'}, 'from 0 to 232'),
    ({'AAV_HUD_MONITOR': 'HDMI-1', 'AAV_SCREEN': 'x'}, 'unknown key AAV_SCREEN'),
    ({'AAV_HUD_MONITOR': 'HDMI-1', 'AAV_PLACES': '~/ottawa.db'}, 'full path'),
])
def test_a_bad_config_stops_with_78(tmp_path, values, says):
    done = screen('hud', write_config(tmp_path, **values))
    assert done.returncode == 78, done
    assert says in done.stderr


def test_no_config_stops_with_78(tmp_path):
    done = screen('map', tmp_path / 'none.env')
    assert done.returncode == 78 and 'no config file' in done.stderr


def test_one_monitor_for_both_is_only_a_note(tmp_path):
    cfg = write_config(tmp_path, AAV_HUD_MONITOR='0', AAV_MAP_MONITOR='0')
    done = screen('hud', cfg)
    assert done.returncode == 0 and 'one hides the other' in done.stderr


@pytest.mark.parametrize('script', [SCREEN, INSTALL])
def test_scripts_parse(script):
    subprocess.run(['bash', '-n', str(script)], check=True)


def install(home, *args):
    """Run the installer in a made-up home, with a pretend aav-jazzy in it."""
    prefix = home / 'aav-jazzy'
    (prefix / 'aav' / 'install' / 'aav_hud_raylib' / 'lib' / 'aav_hud_raylib').mkdir(
        parents=True, exist_ok=True)
    for exe in ('hud', 'map'):
        (prefix / 'aav' / 'install' / 'aav_hud_raylib' / 'lib' / 'aav_hud_raylib' / exe
         ).write_text('')
    (prefix / 'aav.sh').write_text('')
    env = {'HOME': str(home), 'PATH': '/usr/bin:/bin'}
    return subprocess.run(['bash', str(INSTALL), *args], capture_output=True, text=True,
                          env=env)


def files_in(path):
    return sorted(str(p.relative_to(path)) for p in path.rglob('*'))


@pytest.mark.parametrize('action', ['install', 'uninstall'])
def test_installer_dry_run_changes_nothing(tmp_path, action):
    home = tmp_path / 'home'
    home.mkdir()
    done = install(home, '--dry-run')   # creates the pretend aav-jazzy first
    before = files_in(home)
    done = install(home, action, '--dry-run')
    assert files_in(home) == before, 'a dry run wrote something'
    out = done.stdout
    assert 'Dry run' in out, out + done.stderr
    if action == 'install':
        assert '.config/systemd/user/aav-hud.service' in out
        assert '.config/systemd/user/aav-map.service' in out
        assert '.config/autostart/aav-screens.desktop' in out
        assert '.config/aav/screens.env' in out
        assert 'systemctl --user enable aav-hud.service aav-map.service' in out
    else:
        assert 'systemctl --user disable --now aav-hud.service aav-map.service' in out
    if platform.system() != 'Linux':
        assert done.returncode == 1 and 'STOP' in out, 'not Linux: it must refuse'


def test_installer_refuses_for_real_off_linux(tmp_path):
    if platform.system() == 'Linux':
        pytest.skip('only off Linux: on Linux it would really install')
    home = tmp_path / 'home'
    home.mkdir()
    done = install(home, 'install')
    assert done.returncode == 1
    assert not (home / '.config').exists(), 'it wrote into the home folder'


def test_car_install_knows_screens():
    script = ROOT / 'tools' / 'car_install.sh'
    help_text = subprocess.run(['bash', str(script), '--help'], capture_output=True,
                               text=True, check=True).stdout
    assert '--screens' in help_text and 'car_screens_install.sh' in help_text
    # Away from a kit it stops at its checks, --screens or not.
    done = subprocess.run(['bash', str(script), '--dry-run', '--no-verify', '--screens'],
                          capture_output=True, text=True)
    assert done.returncode == 1 and 'nothing was changed' in done.stdout
