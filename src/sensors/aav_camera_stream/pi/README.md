# The camera Pi's MediaMTX settings

`mediamtx.yml` here is for the **front camera Pi** (a Pi 5, Raspberry Pi OS / Debian 13,
no ROS; the 21 Oct audit's CAM1-PI). MediaMTX already runs there. The whole picture:
[docs/camera-pipeline.md](../../../../docs/camera-pipeline.md).

## What it serves

| Path | Camera | Watch it |
|---|---|---|
| `rtsp://<pi>:8554/front_left` | ribbon camera, port 0 (to check) | the Orin's `camera_stream_front_left` |
| `rtsp://<pi>:8554/front_right` | ribbon camera, port 1 (to check) | the Orin's `camera_stream_front_right` |
| `http://<pi>:8889/front_left` | the same, in a browser (WebRTC) | people |

Each: H.264, 1280x720, 15 fps, about 2 Mbit/s, a key frame every second, no B-frames.

## Install it on the Pi

Not done yet: do it at the car, with the team. It needs `sudo` (the Pi has it).

1. See what's there now, and keep a copy:

   ```bash
   systemctl status mediamtx          # the service, and its settings file
   sudo cp /usr/local/etc/mediamtx.yml /usr/local/etc/mediamtx.yml.2025-26
   mediamtx --version                 # written for v1.21.2
   ```

2. Which camera is on which port:

   ```bash
   rpicam-hello --list-cameras        # 0 and 1: swap rpiCameraCamID if left is 1
   ```

3. Copy ours over it, and restart:

   ```bash
   scp src/sensors/aav_camera_stream/pi/mediamtx.yml <user>@<pi>:/tmp/
   ssh <user>@<pi> 'sudo cp /tmp/mediamtx.yml /usr/local/etc/mediamtx.yml && sudo systemctl restart mediamtx'
   ```

4. Check it, from a laptop: `ffplay -rtsp_transport tcp rtsp://<pi>:8554/front_left`,
   or `http://<pi>:8889/front_left` in a browser.

The paths where the file and the service live are the 2025-26 team's (their camera
README, `docs/reference/2025-26-camera-system/`): check them in step 1.

## Measure on the Pi

| What | How |
|---|---|
| CPU for two H.264 streams | `top` (or `htop`) while both are watched: the `mediamtx-rpicamera` processes |
| Bitrate | `curl http://127.0.0.1:9997/v3/paths/list` twice, 10 s apart: `bytesSent` / 10 s |
| Temperature | `vcgencmd measure_temp`: a Pi 5 slows itself down at 85 °C |

## A USB camera instead

The file's `rear` example (commented out) runs `ffmpeg` on the Pi for a USB camera. If
the camera sends H.264 itself (`v4l2-ctl -d /dev/video0 --list-formats-ext`), copy it
(`-c:v copy`): the Pi does nothing.
