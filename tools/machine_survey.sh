#!/usr/bin/env bash
# Survey one car computer, read-only: what it runs, what starts it, what hardware is
# plugged in, which files exist only here (model weights, code, maps, calibration), and
# what has been going wrong (the cameras freezing, brown-outs, crashes).
#
# usage, from a laptop (nothing is saved on the car; the output stays on the laptop):
#   ssh <user>@<ip> 'bash -s' < tools/machine_survey.sh > ~/aav-audit/<label>.txt 2>&1
#   bash tools/survey_car.sh ~/aav-audit/hosts.txt     (every machine in one go)
#
# Read-only, on purpose:
# - no installs, no restarts, no writes outside /tmp (and nothing in /tmp either);
# - never opens a serial port: opening one can pulse DTR and reset an ESP32 or Arduino;
# - never probes I2C (i2cdetect): the actuators share the bus. It only lists /sys;
# - `sudo -n`: uses sudo only if it needs no password, and never asks.
# Secrets: lines that look like a password, token or key are cut to "<redacted>". Still
# read the output before sharing it (docs/audit-friday.md).
#
# Linux (Ubuntu, Raspberry Pi OS, JetPack). On QNX or a Mac, many sections print nothing.

SECONDS_FIND=${SURVEY_FIND_SECONDS:-120}

section() { printf '\n==== %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }
# Run with a time limit if `timeout` exists.
t() { local s=$1; shift; if have timeout; then timeout "$s" "$@"; else "$@"; fi; }
# Try without sudo; if that fails, with sudo only if it needs no password.
maybe_sudo() { "$@" 2>/dev/null || sudo -n "$@" 2>/dev/null; }
# Cut anything that looks like a secret.
redact() {
  sed -E \
    -e 's#(://)[^/@ ]+@#\1<redacted>@#g' \
    -e 's#((pass|passwd|password|psk|token|secret|api_?key|access_?key|auth|ntrip_?user|ntrip_?pass|mountpoint_?pass)[A-Za-z_]*["'"'"']?[[:space:]]*[:=][[:space:]]*)[^[:space:]]+#\1<redacted>#Ig' \
    -e 's#(gh[pousr]_)[A-Za-z0-9]{20,}#\1<redacted>#g' \
    -e 's#(AIza)[A-Za-z0-9_-]{20,}#\1<redacted>#g' \
    -e 's#(-p|--password)[ =][^ ]+#\1 <redacted>#g'
}

HOMES=$(ls -d /home/* /root 2>/dev/null | tr '\n' ' ')

section "who and when"
echo "host: $(hostname)  user: $(id -un)  groups: $(id -nG)"
date; uptime
echo "sudo without a password: $(sudo -n true 2>/dev/null && echo yes || echo no)"

section "os and board"
cat /etc/os-release 2>/dev/null | grep -E '^(PRETTY_NAME|VERSION_ID)='
uname -a
tr -d '\0' < /proc/device-tree/model 2>/dev/null && echo
cat /etc/nv_tegra_release 2>/dev/null                     # Jetson: the L4T (JetPack) version
have nvpmodel && nvpmodel -q 2>/dev/null | head -3
have dpkg && dpkg -l 2>/dev/null | awk '/nvidia-jetpack |nvidia-l4t-core /{print $2, $3}'

section "disk, memory, temperature"
df -h -x tmpfs -x devtmpfs 2>/dev/null || df -h
free -h 2>/dev/null
for z in /sys/class/thermal/thermal_zone*; do
  [[ -r $z/temp ]] && echo "$(cat "$z/type" 2>/dev/null): $(( $(cat "$z/temp") / 1000 )) C"
done

section "power: brown-outs (a Pi) and throttling"
if have vcgencmd; then
  echo "get_throttled: $(vcgencmd get_throttled)  (0x0 = never; bit 0 or 16 = under-voltage)"
  vcgencmd measure_temp; vcgencmd measure_volts core 2>/dev/null
  vcgencmd pmic_read_adc EXT5V_V 2>/dev/null                # Pi 5: the 5 V input
fi
have tegrastats && t 3 tegrastats --interval 1000 2>/dev/null | head -2
maybe_sudo dmesg | grep -iE 'under-?voltage|voltage normali|throttl|brown' | tail -10

section "network"
ip -br addr 2>/dev/null || ifconfig
ip route 2>/dev/null
ip -details link show type can 2>/dev/null                  # CAN interfaces, if any
echo "-- NetworkManager connections (names only):"
have nmcli && nmcli -t -f NAME,TYPE,DEVICE connection show 2>/dev/null
ls /etc/netplan 2>/dev/null
echo "-- listening ports (who owns each; without sudo, root's show no program):"
if have ss; then maybe_sudo ss -tulpn || ss -tuln
elif have netstat; then maybe_sudo netstat -tulpn || netstat -an      # older Linux, QNX
else echo "neither ss nor netstat"; fi
echo "-- connections now (who talks to whom: the lidar's UDP 2368, ROS, the HUD):"
if have ss; then maybe_sudo ss -tunp state established || ss -tun state established
  echo "-- UDP sockets bound (lidar, wheel encoder, DDS):"; maybe_sudo ss -uanp || ss -uan
elif have netstat; then netstat -an 2>/dev/null | grep -iE 'established|udp'; fi

section "ROS environment"
ls /opt/ros 2>/dev/null
printenv | grep -E '^(ROS|RMW|FASTRTPS|CYCLONEDDS|ZENOH|AMENT|COLCON)' | redact
for f in $HOMES; do
  for rc in "$f/.bashrc" "$f/.profile" "$f/.bash_profile" "$f/.zshrc"; do
    [[ -r $rc ]] || continue
    grep -nE 'ROS|source|export|ros2|python|cd ' "$rc" | grep -v '^\s*#' | sed "s#^#$rc:#" | redact
  done
done
echo "-- DDS config files:"
ls -la /etc/fastdds* $HOMES/*/.ros/*.xml $HOMES/*.xml 2>/dev/null

section "running now: the busiest 40"
ps -eo pid,user,etime,pcpu,pmem,args --sort=-pcpu 2>/dev/null | head -41 | cut -c1-250 | redact

section "running now: ROS, Python, cameras, video, containers (full command lines)"
ps -eo pid,user,etime,args 2>/dev/null |
  grep -E 'ros2|_node|launch|python|gst|ffmpeg|rpicam|libcamera|mediamtx|v4l2|flask|flutter|docker|osrm|tile|ntrip|str2str|rtk|ublox|gps|lidar|radar|yolo|node |java|npm|screen|tmux' |
  grep -v grep | cut -c1-300 | redact

section "starts at boot: systemd"
systemctl list-units --type=service --state=running --no-pager --no-legend 2>/dev/null
echo "-- failed:"
systemctl --failed --no-pager --no-legend 2>/dev/null
echo "-- units added by hand (not from a package), and what each runs:"
for u in /etc/systemd/system/*.service /etc/systemd/system/*/*.service /lib/systemd/system/*.service; do
  [[ -f $u ]] || continue
  case $u in /lib/*) have dpkg && dpkg -S "$u" >/dev/null 2>&1 && continue;; esac
  name=$(basename "$u")
  echo "## $u  (enabled: $(systemctl is-enabled "$name" 2>/dev/null), active: $(systemctl is-active "$name" 2>/dev/null), restarts: $(systemctl show -p NRestarts --value "$name" 2>/dev/null))"
  grep -E '^(Description|ExecStart|ExecStartPre|User|WorkingDirectory|Restart|After|Environment)' "$u" | redact
done
echo "-- user services:"
for f in $HOMES; do ls -la "$f/.config/systemd/user" 2>/dev/null && cat "$f"/.config/systemd/user/*.service 2>/dev/null | redact; done
loginctl list-users --no-legend 2>/dev/null; ls /var/lib/systemd/linger 2>/dev/null

section "starts at boot: cron, rc.local, desktop autostart, profile.d"
crontab -l 2>&1 | redact
maybe_sudo crontab -l -u root | redact
ls /etc/cron.d 2>/dev/null; grep -h '@reboot' /etc/crontab /etc/cron.d/* 2>/dev/null | redact
[[ -f /etc/rc.local ]] && { echo "-- /etc/rc.local:"; grep -v '^#' /etc/rc.local | redact; }
for d in $HOMES; do
  for f in "$d"/.config/autostart/*.desktop "$d"/.config/lxsession/*/autostart "$d"/.config/wayfire.ini "$d"/.config/labwc/autostart; do
    [[ -f $f ]] && { echo "-- $f"; grep -iE 'exec|^@|autostart' "$f" | redact; }
  done
done
ls /etc/xdg/autostart 2>/dev/null | head -40
ls -la /etc/profile.d 2>/dev/null

section "containers"
if have docker; then
  maybe_sudo docker ps -a --format '{{.Names}}  {{.Image}}  {{.Status}}' || echo "docker: no access"
  maybe_sudo docker inspect --format '{{.Name}} restart={{.HostConfig.RestartPolicy.Name}}' $(maybe_sudo docker ps -aq) 2>/dev/null
  maybe_sudo docker images --format '{{.Repository}}:{{.Tag}}  {{.Size}}'
fi
have pm2 && pm2 list 2>/dev/null

section "hardware: USB"
have lsusb && { lsusb; lsusb -t 2>/dev/null; }
echo "-- serial ports (listed, never opened):"
ls -l /dev/serial/by-id /dev/serial/by-path 2>/dev/null
SERIAL="/dev/ttyUSB* /dev/ttyACM* /dev/ttyAMA* /dev/ttyTHS* /dev/ttyGS* /dev/rfcomm* /dev/serial0 /dev/serial1 /dev/ser[0-9]*"
ls -l $SERIAL 2>/dev/null                                  # /dev/ser*: QNX's serial ports
echo "-- each one: what's plugged in (from udev; the port itself is not opened):"
for p in $SERIAL; do
  [[ -e $p ]] || continue
  have udevadm || break
  echo "$p: $(udevadm info -q property -n "$p" 2>/dev/null |
    grep -E '^ID_(VENDOR|MODEL|SERIAL_SHORT|USB_DRIVER|PATH)=' | tr '\n' ' ')"
done
echo "-- who holds them open:"
for p in $SERIAL /dev/video*; do
  [[ -e $p ]] || continue
  if have fuser; then o=$(maybe_sudo fuser -v "$p" 2>&1 | tail -n +2)
  elif have lsof; then o=$(maybe_sudo lsof "$p" 2>/dev/null | tail -n +2)
  else o=''; fi
  [[ -n $o ]] && echo "$p: $o"
done
echo "-- serial consoles (a login on a UART: a board on it would read a login prompt):"
grep -oE 'console=[^ ]+' /proc/cmdline 2>/dev/null
systemctl list-units --no-pager --no-legend 'serial-getty@*' 2>/dev/null
echo "-- udev rules added by hand (stable device names):"
ls -la /etc/udev/rules.d 2>/dev/null; cat /etc/udev/rules.d/*.rules 2>/dev/null | grep -v '^#' | grep -v '^$' | head -60

section "hardware: cameras"
ls -l /dev/video* /dev/media* 2>/dev/null
ls -l /dev/v4l/by-id /dev/v4l/by-path 2>/dev/null
have v4l2-ctl && t 10 v4l2-ctl --list-devices 2>&1
# Lists the cameras libcamera sees; doesn't take one. If a program holds it, that shows.
if have rpicam-hello; then t 15 rpicam-hello --list-cameras 2>&1
elif have libcamera-hello; then t 15 libcamera-hello --list-cameras 2>&1; fi
echo "-- camera overlays and UART settings in config.txt:"
grep -vE '^\s*(#|$)' /boot/firmware/config.txt /boot/config.txt 2>/dev/null
echo "-- the kernel's camera messages (errors, timeouts, resets):"
maybe_sudo dmesg | grep -iE 'unicam|rp1-cfe|csi|imx[0-9]+|ov[0-9]{4}|uvcvideo|v4l2|video[0-9]|dma.*timeout|frame.*(drop|timeout)|nvargus|tegra-capture|vi5|nvcsi' | tail -40
echo "-- camera calibration files:"
ls -la $HOMES/*/.ros/camera_info 2>/dev/null

section "hardware: I2C, SPI, GPIO, CAN (listed, never probed)"
ls /dev/i2c-* /dev/spidev* /dev/gpiochip* /dev/can* 2>/dev/null
for d in /sys/bus/i2c/devices/*; do
  [[ -r $d/name ]] && echo "$(basename "$d"): $(cat "$d/name")"
done
have pinctrl && pinctrl get 2>/dev/null | head -30
have raspi-gpio && raspi-gpio get 2>/dev/null | head -30

section "the kernel: USB connects and disconnects, errors"
maybe_sudo dmesg | grep -iE 'usb .*(disconnect|new .*device|reset)|cp210|ch34|ftdi|cdc_acm|u-blox' | tail -30
maybe_sudo dmesg --level=err,crit,alert,emerg 2>/dev/null | tail -30

section "errors in the logs: this boot, and how often it reboots"
journalctl --list-boots --no-pager 2>/dev/null | tail -10
maybe_sudo journalctl -b -p err --no-pager -q | tail -60 | cut -c1-250 | redact
echo "-- the last boot's final lines (a crash or a power cut shows here):"
maybe_sudo journalctl -b -1 -n 25 --no-pager -q | cut -c1-250 | redact

section "ROS logs: the newest runs"
for d in $HOMES; do
  l="$d/.ros/log"
  [[ -d $l ]] || continue
  echo "-- $l: $(ls "$l" | wc -l) entries, $(du -sh "$l" 2>/dev/null | cut -f1)"
  ls -t "$l" | head -5
  newest=$(ls -td "$l"/*/ 2>/dev/null | head -3)
  for n in $newest; do
    echo "## $n"
    grep -rhE '\[(ERROR|FATAL|WARN)\]' "$n" 2>/dev/null | cut -c1-250 | sort | uniq -c | sort -rn | head -15 | redact
  done
done

section "code on this machine (is it on GitHub?)"
# For each git repo: its remote, branch, commit, and what isn't pushed. A dirty or
# unpushed repo holds work that exists nowhere else.
t "$SECONDS_FIND" find $HOMES /opt /srv /usr/local/src -xdev -maxdepth 6 -name .git \
    \( -type d -o -type f \) 2>/dev/null | grep -v '/\.cache/' | while read -r g; do
  r=$(dirname "$g")
  cd "$r" 2>/dev/null || continue
  remote=$(git remote get-url origin 2>/dev/null | redact)
  head=$(git log -1 --format='%h %ci %s' 2>/dev/null | cut -c1-100)
  dirty=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  ahead=$(git rev-list --count '@{upstream}..HEAD' 2>/dev/null || echo '?')
  echo "$r | ${remote:-NO REMOTE} | $(git branch --show-current 2>/dev/null) | $head | changed files: $dirty | unpushed commits: $ahead"
done
echo "-- ROS workspaces (a src folder next to install or build):"
ls -d $HOMES/*/src $HOMES/*/*/src 2>/dev/null | while read -r s; do
  w=$(dirname "$s"); [[ -d $w/install || -d $w/build ]] || continue
  echo "$w: $(ls "$s" | tr '\n' ' ')"
  [[ -d $w/.git ]] || echo "   ^ not a git repo: copy it"
done

section "files that may exist only here: weights, maps, recordings, calibration"
# Model weights; maps and routing data; recordings; calibration. Size, date, path.
t "$SECONDS_FIND" find $HOMES /opt /srv /data /mnt /media -xdev \
  \( -path '*/.cache/pip' -o -path '*/site-packages' -o -path '*/dist-packages' -o -path '*/node_modules' -o -path '*/.git' \) -prune -o \
  -type f \( -iname '*.pt' -o -iname '*.pth' -o -iname '*.onnx' -o -iname '*.engine' -o -iname '*.trt' \
             -o -iname '*.plan' -o -iname '*.tflite' -o -iname '*.weights' -o -iname '*.h5' -o -iname '*.pb' \
             -o -iname '*.safetensors' -o -iname '*.mlpackage' -o -iname '*.etlt' -o -iname '*.hef' \
             -o -iname '*.osrm*' -o -iname '*.mbtiles' -o -iname '*.pbf' -o -iname '*.pmtiles' -o -iname '*.db' \
             -o -iname '*.db3' -o -iname '*.mcap' -o -iname '*.bag' \
             -o -ipath '*camera_info*' -o -iname '*calib*' -o -iname '*.dbc' -o -iname '*.ubx' \) \
  -size +1k -printf '%10s  %TY-%Tm-%Td  %p\n' 2>/dev/null | sort -k3 | head -300
echo "-- the biggest folders in each home (where the data is):"
for d in $HOMES; do t 60 du -xh --max-depth=2 "$d" 2>/dev/null | sort -rh | head -12; done

section "done"
date
