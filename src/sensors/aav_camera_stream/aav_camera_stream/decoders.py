"""
decoders: turn an RTSP H.264 stream into pictures (numpy BGR arrays), one way per machine.

Each computer decodes its own way, picked by the node's decoder parameter:

  decoder      runs                                   where
  auto         the best this computer has (choose())  the default
  ffmpeg       ffmpeg, in software (or hwaccel)       any Mac or Linux, Pixi's own ffmpeg
  gst-nvidia   gst-launch-1.0 with nvv4l2decoder      the Orin: NVIDIA's video hardware
  gst-soft     gst-launch-1.0 with avdec_h264         any computer with GStreamer's plugins
  gst-mac      gst-launch-1.0 with vtdec              a Mac: VideoToolbox, Apple's hardware
  opencv       OpenCV's VideoCapture, in this process an OpenCV with FFmpeg (or GStreamer,
                                                      given a pipeline ending in appsink)

auto runs the gst environment's GStreamer (pixi install -e gst): on a Mac gst-mac, if
vtdec decodes a test picture, else gst-soft; on Linux gst-soft. Without it, ffmpeg, with
a warning (ffmpeg holds back about 2 frames: 135 ms). The Orin's machine file says
gst-nvidia: no gst environment there (linux-aarch64).

The ffmpeg and gst-* ones run the decoder as a child program that writes raw pictures to
a pipe (width x height x 3 bytes each). So the node needs no GStreamer of its own: on the
Orin it runs JetPack's /usr/bin/gst-launch-1.0, whose NVIDIA plugins Pixi doesn't have,
and on a Mac the gst environment's, from Pixi's Python. Every way scales the picture to
width x height, so each frame's size is known before it arrives.

pipeline overrides a preset: a gst-launch-1.0 pipeline with {url}, {width}, {height} and
{protocols}, ending in `fdsink` (or, for opencv, in `appsink`).
"""

from collections import namedtuple
import os
import shlex
import signal
import subprocess
import sys
import threading

DECODERS = ('auto', 'ffmpeg', 'gst-nvidia', 'gst-soft', 'gst-mac', 'opencv')

# The GStreamer presets: rtspsrc pulls (latency=0: no jitter buffer; on a wired network
# packets come in order), the depayloader and parser hand H.264 to a decoder, then the
# picture is scaled and turned into BGR for OpenCV.
GST = {
    # nvvidconv converts and scales in NVIDIA's hardware too; disable-dpb: the stream has
    # no B-frames (baseline), so the decoder needn't hold frames back to reorder them.
    'gst-nvidia': ('rtspsrc location={url} protocols={protocols} latency=0 '
                   '! rtph264depay ! h264parse '
                   '! nvv4l2decoder enable-max-performance=true disable-dpb=true '
                   '! nvvidconv ! video/x-raw,format=BGRx,width={width},height={height} '
                   '! videoconvert ! video/x-raw,format=BGR ! fdsink sync=false'),
    'gst-soft': ('rtspsrc location={url} protocols={protocols} latency=0 '
                 '! rtph264depay ! h264parse ! avdec_h264 max-threads=1 '
                 '! videoconvert ! videoscale '
                 '! video/x-raw,format=BGR,width={width},height={height} '
                 '! fdsink sync=false'),
    'gst-mac': ('rtspsrc location={url} protocols={protocols} latency=0 '
                '! rtph264depay ! h264parse ! vtdec '
                '! videoconvert ! videoscale '
                '! video/x-raw,format=BGR,width={width},height={height} '
                '! fdsink sync=false'),
}
# JetPack's own GStreamer, not Pixi's (which has no NVIDIA plugins).
SYSTEM_GST = '/usr/bin/gst-launch-1.0'
# A Mac's GStreamer: the gst environment in pixi.toml (pixi install -e gst), not the one the
# node runs in, so adding it changed no other environment.
PIXI_GST = os.path.join('.pixi', 'envs', 'gst', 'bin', 'gst-launch-1.0')
# What each preset needs, checked with gst-inspect-1.0 --exists before auto picks it.
ELEMENTS = {
    'gst-soft': ('rtspsrc', 'rtph264depay', 'h264parse', 'avdec_h264', 'videoconvert',
                 'videoscale', 'fdsink'),
    'gst-mac': ('rtspsrc', 'rtph264depay', 'h264parse', 'vtdec', 'videoconvert',
                'videoscale', 'fdsink'),
}
# A Mac's hardware can be missing (a virtual machine): encode three small test pictures
# with VideoToolbox and decode them with vtdec, as the stream's would be (0.2 s).
VTDEC_TEST = ('videotestsrc num-buffers=3 ! video/x-raw,width=64,height=64 ! vtenc_h264 '
              '! h264parse ! vtdec ! videoconvert ! video/x-raw,format=BGR ! fakesink')
FFMPEG_SLOWER = 'ffmpeg holds back about 2 frames: 135 ms more delay'
Choice = namedtuple('Choice', 'decoder program warning')
# What a program from outside Pixi must not inherit from it: Pixi's libraries and plugins.
PIXI_ONLY = ('LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH', 'DYLD_FALLBACK_LIBRARY_PATH',
             'GST_PLUGIN_PATH', 'GST_PLUGIN_PATH_1_0', 'GST_PLUGIN_SYSTEM_PATH',
             'GST_PLUGIN_SYSTEM_PATH_1_0', 'GST_PLUGIN_SCANNER', 'GST_PLUGIN_SCANNER_1_0',
             'GST_REGISTRY', 'GST_REGISTRY_1_0', 'GIO_MODULE_DIR')


def check(decoder: str, transport: str) -> None:
    """Raise ValueError for a decoder or transport this module doesn't know."""
    if decoder not in DECODERS:
        raise ValueError(f'decoder:={decoder}: use one of {", ".join(DECODERS)}')
    if transport not in ('tcp', 'udp'):
        raise ValueError(f'transport:={transport}: use tcp or udp')


def ffmpeg_command(url, width, height, transport='tcp', program='', hwaccel=''):
    """Return the argv of an ffmpeg writing the pictures to stdout, as raw BGR."""
    return [program or 'ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin',
            # Low delay: no input buffer, no waiting to guess the stream's format (the
            # RTSP description already says), and slice threads only: frame threads hold
            # back one frame per thread.
            '-fflags', 'nobuffer', '-flags', 'low_delay', '-probesize', '32768',
            '-analyzeduration', '0', '-thread_type', 'slice',
            *(['-hwaccel', hwaccel] if hwaccel else []),
            '-rtsp_transport', transport, '-i', url, '-an',
            # Each decoded picture once: no frames repeated or dropped to keep a rate.
            '-fps_mode', 'passthrough',
            '-vf', f'scale={width}:{height}', '-pix_fmt', 'bgr24', '-f', 'rawvideo', '-']


def gst_command(pipeline, url, width, height, transport='tcp', program=''):
    """Return the argv of a quiet gst-launch-1.0 running this pipeline, filled in."""
    filled = pipeline.format(url=url, width=width, height=height,
                             protocols='tcp' if transport == 'tcp' else 'udp')
    # -q: gst-launch prints its progress on stdout, where the pictures go.
    return [program or 'gst-launch-1.0', '-q', *shlex.split(filled)]


def command(decoder, url, width, height, transport='tcp', program='', pipeline='',
            hwaccel=''):
    """Return the child program's argv for a pipe decoder (every one but opencv)."""
    check(decoder, transport)
    if decoder == 'opencv':
        raise ValueError('decoder:=opencv decodes in this process: it has no command')
    if decoder == 'auto':
        raise ValueError('decoder:=auto: choose() picks the decoder first')
    if decoder == 'ffmpeg' and not pipeline:
        return ffmpeg_command(url, width, height, transport, program, hwaccel)
    if decoder == 'gst-nvidia' and not program:
        program = SYSTEM_GST
    return gst_command(pipeline or GST.get(decoder, GST['gst-soft']), url, width, height,
                       transport, program)


def pixi_gst(root):
    """Return the gst environment's gst-launch-1.0 under the workspace root, or ''."""
    path = os.path.join(root, PIXI_GST) if root else ''
    return path if path and os.access(path, os.X_OK) else ''


def gst_works(program, decoder, env=None, run=subprocess.run):
    """
    Return '' if this gst-launch-1.0 can run the decoder's preset, or say why not.

    Every element must exist (gst-inspect-1.0 --exists, next to the program); for gst-mac,
    vtdec must also decode VTDEC_TEST's pictures.
    """
    inspect = os.path.join(os.path.dirname(program), 'gst-inspect-1.0')
    try:
        for element in ELEMENTS[decoder]:
            if run([inspect, '--exists', element], env=env, capture_output=True,
                   timeout=20).returncode != 0:
                return f'no {element} in {os.path.dirname(program)}'
        if decoder == 'gst-mac':
            done = run([program, '-q', *shlex.split(VTDEC_TEST)], env=env,
                       capture_output=True, timeout=20)
            if done.returncode != 0:
                return 'vtdec could not decode a test picture (no VideoToolbox here?)'
    except (OSError, subprocess.TimeoutExpired) as e:
        return f'{program}: {e}'
    return ''


def choose(decoder, program='', root='', platform=sys.platform, works=gst_works):
    """
    Return the Choice (decoder, program, warning) the node runs.

    auto picks GStreamer from the gst environment under root (or program): on a Mac,
    gst-mac (vtdec) if it decodes, else gst-soft (avdec_h264); on Linux, gst-soft. With no
    GStreamer that works, ffmpeg, with a warning. gst-mac and gst-soft given with no
    program run the gst environment's, if it's there. works(program, decoder) returns ''
    or why that GStreamer can't run that decoder.
    """
    gst = program or pixi_gst(root)
    if decoder in ('gst-mac', 'gst-soft'):
        return Choice(decoder, gst, '')
    if decoder != 'auto':
        return Choice(decoder, program, '')
    if not gst:
        return Choice('ffmpeg', '', f'decoder auto: no GStreamer, so ffmpeg ({FFMPEG_SLOWER}).'
                                    ' On a Mac or a Linux PC, install it once: '
                                    'pixi install -e gst')
    why = works(gst, 'gst-mac') if platform == 'darwin' else ''
    if platform == 'darwin' and not why:
        return Choice('gst-mac', gst, '')
    soft = works(gst, 'gst-soft')
    if not soft:
        return Choice('gst-soft', gst,
                      f'decoder auto: {why}; avdec_h264 (software) instead' if why else '')
    return Choice('ffmpeg', '', f"decoder auto: GStreamer can't decode here "
                                f"({'; '.join(w for w in (why, soft) if w)}), "
                                f'so ffmpeg ({FFMPEG_SLOWER})')


def child_env(environ, program, prefix):
    """
    Return the environment for the decoder program.

    One from inside this Pixi environment (prefix) gets it all. One from outside, such as
    JetPack's /usr/bin/gst-launch-1.0, loses Pixi's library and plugin paths, so it loads
    its own system's.
    """
    env = dict(environ)
    path = os.path.abspath(program) if os.path.isabs(program) else ''
    if prefix and path and not path.startswith(os.path.abspath(prefix) + os.sep):
        for name in PIXI_ONLY:
            env.pop(name, None)
    return env


class PipeSource:
    """A decoder program writing raw BGR pictures to a pipe; read() returns the next."""

    def __init__(self, argv, width, height, env=None):
        self.argv = argv
        self.size = width * height * 3
        self.shape = (height, width, 3)
        self.env = env
        self.proc = None
        self._lock = threading.Lock()   # stop() may come from two threads at once

    def start(self):
        # Its own process group, so stop() reaches its children too (gst's, ffmpeg's).
        self.proc = subprocess.Popen(self.argv, stdout=subprocess.PIPE, stdin=subprocess.DEVNULL,
                                     env=self.env, start_new_session=True,
                                     bufsize=self.size)

    def read(self):
        """Return the next picture (height x width x 3, uint8), or None at the end."""
        import numpy
        proc = self.proc
        if proc is None:
            return None
        try:
            data = proc.stdout.read(self.size)
        except ValueError:              # closed by stop() meanwhile
            return None
        if data is None or len(data) < self.size:
            return None
        return numpy.frombuffer(data, numpy.uint8).reshape(self.shape)

    def stop(self):
        with self._lock:
            proc, self.proc = self.proc, None
        if proc is None:
            return
        for sig in (signal.SIGTERM, signal.SIGKILL):
            if proc.poll() is not None:
                break
            try:
                os.killpg(proc.pid, sig)
            except (ProcessLookupError, PermissionError):
                # Gone already. macOS says EPERM, not ESRCH, for a group whose last
                # member has exited but not been reaped (TODO 41, 24 Oct).
                break
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                continue
        proc.stdout.close()


class OpenCvSource:
    """OpenCV's VideoCapture: the URL through FFmpeg, or a GStreamer pipeline (appsink)."""

    def __init__(self, url, width, height, transport='tcp', pipeline=''):
        self.url, self.width, self.height = url, width, height
        self.transport, self.pipeline = transport, pipeline
        self.cap = None

    def start(self):
        import cv2
        if self.pipeline:
            target = self.pipeline.format(url=self.url, width=self.width, height=self.height,
                                          protocols=self.transport)
            self.cap = cv2.VideoCapture(target, cv2.CAP_GSTREAMER)
        else:
            # Read by OpenCV's FFmpeg as it opens the stream.
            os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = (
                f'rtsp_transport;{self.transport}|fflags;nobuffer|flags;low_delay')
            self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        if not self.cap.isOpened():
            raise OSError(f'OpenCV could not open {target if self.pipeline else self.url}')

    def read(self):
        import cv2
        ok, frame = self.cap.read()
        if not ok:
            return None
        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)
        return frame

    def stop(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
