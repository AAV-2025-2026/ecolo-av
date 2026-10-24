"""
decoders: turn an RTSP H.264 stream into pictures (numpy BGR arrays), one way per machine.

Each computer decodes its own way, picked by the node's decoder parameter:

  decoder      runs                                   where
  ffmpeg       ffmpeg, in software (or hwaccel)       any Mac or Linux, Pixi's own ffmpeg
  gst-nvidia   gst-launch-1.0 with nvv4l2decoder      the Orin: NVIDIA's video hardware
  gst-soft     gst-launch-1.0 with avdec_h264         any Linux with GStreamer's plugins
  gst-mac      gst-launch-1.0 with vtdec              a Mac with GStreamer's plugins
  opencv       OpenCV's VideoCapture, in this process an OpenCV with FFmpeg (or GStreamer,
                                                      given a pipeline ending in appsink)

The ffmpeg and gst-* ones run the decoder as a child program that writes raw pictures to
a pipe (width x height x 3 bytes each). So the node needs no GStreamer of its own: on the
Orin it runs JetPack's /usr/bin/gst-launch-1.0, whose NVIDIA plugins Pixi doesn't have,
from Pixi's Python. Every way scales the picture to width x height, so each frame's size
is known before it arrives.

pipeline overrides a preset: a gst-launch-1.0 pipeline with {url}, {width}, {height} and
{protocols}, ending in `fdsink` (or, for opencv, in `appsink`).
"""

import os
import shlex
import signal
import subprocess
import threading

DECODERS = ('ffmpeg', 'gst-nvidia', 'gst-soft', 'gst-mac', 'opencv')

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
# What a program from outside Pixi must not inherit from it: Pixi's libraries and plugins.
PIXI_ONLY = ('LD_LIBRARY_PATH', 'GST_PLUGIN_PATH', 'GST_PLUGIN_PATH_1_0',
             'GST_PLUGIN_SYSTEM_PATH', 'GST_PLUGIN_SYSTEM_PATH_1_0', 'GST_PLUGIN_SCANNER',
             'GST_PLUGIN_SCANNER_1_0', 'GST_REGISTRY', 'GST_REGISTRY_1_0', 'GIO_MODULE_DIR')


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
    if decoder == 'ffmpeg' and not pipeline:
        return ffmpeg_command(url, width, height, transport, program, hwaccel)
    if decoder == 'gst-nvidia' and not program:
        program = SYSTEM_GST
    return gst_command(pipeline or GST.get(decoder, GST['gst-soft']), url, width, height,
                       transport, program)


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
            except ProcessLookupError:
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
