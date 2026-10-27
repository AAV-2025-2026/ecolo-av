# tools/screens

What makes the car's two screens start at login: the HUD full screen on the dash's
small screen, the map window on the big one. The whole story: `docs/car-screens.md`.

## Overview

`tools/car_screens_install.sh` copies these files into the user's `~/.config`. At
login, systemd starts both units; each runs `tools/car_screen.sh`, which reads
`screens.env` and starts the window on its monitor.

```
login ─> aav-hud.service ─> ~/aav-jazzy/aav.sh tools/car_screen.sh hud
      └> aav-map.service ─> ~/aav-jazzy/aav.sh tools/car_screen.sh map
                                   reads ~/.config/aav/screens.env
```

## Interface

| File | Installed to | Is |
|---|---|---|
| `aav-hud.service` | `~/.config/systemd/user/` | systemd user unit: the HUD (instrument cluster) |
| `aav-map.service` | `~/.config/systemd/user/` | systemd user unit: the map window |
| `aav-screens.desktop` | `~/.config/autostart/` | for desktops that don't start `graphical-session.target`: shares `DISPLAY` with systemd, starts both units |
| `screens.env` | `~/.config/aav/screens.env` | the settings template; kept if it exists already |

`screens.env` keys:

| Key | Means |
|---|---|
| `AAV_HUD_MONITOR`, `AAV_MAP_MONITOR` | the monitor, by name (`HDMI-1`) or number (0 = first). Empty: that screen doesn't start |
| `AAV_ROS_DOMAIN_ID` | the ROS domain: 42, the car's |
| `AAV_STREET_MAP`, `AAV_PLACES` | the map window's offline files; `@PREFIX@` is filled in by the installer |

## Invariants

- User units: they run as the logged-in user, need no sudo.
- `Restart=always` after 5 s, and no start limit: the car's screen must not stay dark.
- Except exit 78: `screens.env` is wrong. The units don't retry it; fix it, then
  `systemctl --user restart aav-hud aav-map`.
- `screens.env` is read, never sourced: one `KEY=value` a line, no spaces round `=`, no
  `$VARIABLES`, no `~`, only the keys above.
- Never `systemctl --user disable` them; `stop` holds until the next boot.

## Side Effects

Once installed: two windows full screen at every login, restarted on any crash; logs in
the journal (`journalctl --user -u aav-hud -f`). The files themselves do nothing in git.

## Verification

```sh
python3 -m pytest -q tools/tests/test_car_screens.py   # also in tools/test.sh
bash tools/car_screens_install.sh --dry-run             # the plan; writes nothing
```

The test parses the units and the desktop entry, and runs `car_screen.sh --print`.
There is no `systemd-analyze` on a Mac.
