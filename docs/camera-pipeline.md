# The camera pipeline: Pi to detections (24 October)

Ben decided it on 23 Oct ("mediamtx on the pi to the orin seems like the best choice";
[decisions](decisions.md#decided-on-22-and-23-october)). This page is how it's built, the
settings and why, what was measured on a Mac, and what to check at the car.

!!! tip "The short version"
    - The camera Pi streams **H.264** (1280x720, 15 fps, 2 Mbit/s) with **MediaMTX**.
    - On the Orin, **one program per camera** (`camera_stream`) unpacks it, undistorts
      it and runs **RF-DETR Nano**. Raw pictures never cross the network.
    - On a Mac, the whole chain takes **26 ms** from the picture to its detections
      (GStreamer decoding). Measured with `pixi run stream-check`.

## The picture

```text
 camera Pi (Pi 5, no ROS)                         Orin (ROS)
 ────────────────────────                         ──────────
 ribbon camera 0 ─┐                               camera_stream_front_left
 ribbon camera 1 ─┤ MediaMTX        RTSP, TCP     ┌──────────────────────────────┐
                  │ (OpenH264,  ────────────────► │ decoder (child program)      │
                  │  software)      2 Mbit/s each │  GStreamer nvv4l2decoder     │
                  │ :8554/front_left              │ undistort (OpenCV)           │
                  │ :8554/front_right             │ RF-DETR Nano (aav_yolo)      │
                  │ :8889 WebRTC ──► a browser    └──────┬───────────────────────┘
                                                         ▼
                        /perception/detections   (~0.5 kB, every picture)
                        /perception/camera/front_left/preview/compressed (4 kB, 1 Hz)
                        /sensors/camera/front_left/camera_info (with a calibration)
                        /diagnostics             (its numbers, 1 Hz)
```

The same for `front_right`, in a second program.

## What is where

| Part | File | Note |
|---|---|---|
| The Pi's settings | `src/sensors/aav_camera_stream/pi/mediamtx.yml` | install: `pi/README.md` [[untested]] on the Pi |
| The node | `aav_camera_stream/camera_stream.py` | one per camera |
| Its logic, no ROS | `decoders.py`, `reader.py`, `latest.py`, `lens.py`, `timecode.py`, `models.py` | 41 tests |
| The detector | `aav_yolo.detectors.load_detector` | imported, not copied |
| Start it | `ros2 launch aav_camera_stream camera_stream.launch.py host:=<pi> decoder:=gst-nvidia` | on the Orin |
| Test it | `pixi run -e ml stream-check` | a Mac, no car |

## The settings, and why

| Setting | Value | Why |
|---|---|---|
| Codec | H.264 | about 10 times smaller than JPEG; every decoder has it |
| Encoder | MediaMTX's `softwareH264` (OpenH264) | the Pi 5 has **no** H.264 hardware |
| Size, rate | 1280x720, 15 fps | enough for the detector (it shrinks to 384 px); half the Pi's work of 1080p |
| Bitrate | 2 Mbit/s (max 2.4) | 4 Mbit/s for both: 0.4% of the Orin's cable |
| Key frame | every 15 frames = 1 s | a lost or new reader waits at most 1 s for a picture |
| Profile | baseline | no B-frames: no picture waits for a later one |
| Focus | fixed, at infinity | a lens that refocuses changes its calibration |
| Transport | RTSP over TCP | wired, so nothing is lost; a frame never arrives broken |
| Who may publish | the Pi itself only | anyone may watch |
| Decoder, Orin | GStreamer `nvv4l2decoder` | NVIDIA's hardware; JetPack's own `/usr/bin/gst-launch-1.0` |
| Decoder, Mac | GStreamer `avdec_h264` (`--gst`) | ffmpeg holds back 2 frames (below) |
| Newest only | yes | a slow detector drops frames, never falls behind |
| Stamp | arrival − `delay` (0.06 s) | an **estimate**: measure it at the car |

!!! note "Why the decoder is a child program"
    NVIDIA's GStreamer plugins come with JetPack, not Pixi. The node runs JetPack's
    `gst-launch-1.0` and reads raw pictures from its pipe (2.7 MB each, 41 MB/s:
    nothing for a pipe). So the node needs no GStreamer of its own, and the same code
    runs on a Mac with ffmpeg or GStreamer. `decoder:=opencv` decodes inside the
    process instead, with an OpenCV built with GStreamer or FFmpeg.

## Measured on a Mac (24 Oct)

`pixi run -e ml stream-check`, Ben's Mac (Apple silicon), load average 2-5, other
helpers' work running. Gazebo's road world, the car rolling at 0.3 m/s towards the stop
sign, 60 s each. **measured**:

| Decoder | Time code → decoded | → detections published | Detector |
|---|---|---|---|
| GStreamer (`--gst`) | **3 ms** median, 6 p95, 8 worst | **26 ms** median, 36 p95, 42 worst | 21 ms |
| ffmpeg (the default) | 136 ms median, 144 p95, 173 worst | 160 ms median, 174 p95, 215 worst | 22 ms |

| What | Gazebo | Noisy photo (`--pattern`) |
|---|---|---|
| On the wire | 0.13 Mbit/s (simple scenery compresses well) | **2.04 Mbit/s**: a real camera's noise fills the 2 Mbit/s |
| Frames | 15.0 fps in, 15.0 worked on, 2-3 dropped a minute | the same |
| Detections | 15 a second, 489 bytes each | the same |
| Previews | 1 a second, 4.0 kB | 5.2 kB |
| Stop sign | in 902 of 906 pictures, from **25 m** down to 7 m | in every picture |
| CPU, encoder (stands in for the Pi) | 2% of a core | 7% of a core |
| CPU, `camera_stream` + its decoder | 29% of a core | 32% |

!!! warning "ffmpeg's 135 ms"
    Measured hop by hop: OpenH264 and x264 encode in 2 ms; MediaMTX adds nothing
    measurable; **ffmpeg's decoder program** holds back about 2 frames, with every
    low-delay flag tried (`-flags low_delay`, slice threads, one thread, `-fflags
    nobuffer`). GStreamer doesn't. So the Orin uses GStreamer, and so should a Mac
    (`--gst`). OpenCV's FFmpeg reader was worse (over 1 s behind).

The time code: a row of black and white squares in the top left corner, carrying the
time in ms, drawn before encoding and read after decoding (`timecode.py`). It survives
OpenH264 at 2 Mbit/s (a test checks).

## What it can't measure here

| Not measured | Why | Estimate |
|---|---|---|
| The camera's exposure and readout, libcamera | no Pi camera here | 20-40 ms |
| The Pi 5 encoding two streams | its CPU isn't this Mac's | 20-30% of a core each (a Pi 5 core is about 3-4 times slower) |
| The cable, Pi to Orin | one computer | under 1 ms |
| The Orin's hardware decoder | no Orin here | a few ms |
| RF-DETR Nano in TensorRT on the Orin | no Orin here | to time (PLAN T8.3) |

So on the car, camera to detections: about **50-100 ms** (a guess).

## At the car: what to check

| Check | How | Good |
|---|---|---|
| Which camera is which | `rpicam-hello --list-cameras` on the Pi | swap `rpiCameraCamID` if left is 1 |
| The Pi's CPU, two streams | `top` while the Orin reads both | under 50% of the Pi in all; `vcgencmd measure_temp` under 80 °C |
| Bitrate | `curl http://127.0.0.1:9997/v3/paths/list` on the Pi, twice, 10 s apart | about 2 Mbit/s each |
| The Orin decodes | `ros2 launch aav_camera_stream camera_stream.launch.py host:=<pi> decoder:=gst-nvidia detector:=none`, then `/diagnostics` | `fps_in` 15 |
| Delay, end to end | film a phone's stopwatch next to the Orin's screen, which shows the preview (or the stopwatch itself) | under 150 ms |
| Stamp error | the same: the stopwatch in the picture vs the detection's stamp | set `delay` to the difference |
| Clock | `chronyc tracking` on the Pi and the Orin | under 1 ms apart |

## Still open

| Item | Note |
|---|---|
| Calibrations | the ribbon cameras have none: `config/cameras.yaml` leaves them empty (no undistortion). The 2024-25 `left.ini` is another camera's (Q22) |
| `car.launch.py` | doesn't start the streams yet: a machine part for the Orin, with `decoder:=gst-nvidia` |
| The sensor watchdog | watches `/sensors/camera/front_left/image_raw`, which this node publishes only with `publish_image:=true`. Watch its `/diagnostics` instead? |
| Lane finder and HUD | read `image_raw` too: `publish_image:=true` on the Orin (no network), or the preview |
| A rear camera | the QNX Pi's doesn't work today; a USB camera's `ffmpeg` example is in `pi/mediamtx.yml` |
