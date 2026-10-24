"""The decoder commands, the child's environment, a pipe source and the reader thread."""

import sys
import time

from aav_camera_stream import decoders
from aav_camera_stream.latest import Latest
from aav_camera_stream.reader import Reader
import numpy
import pytest

URL = 'rtsp://192.168.1.108:8554/front_left'


def test_ffmpeg_low_delay_raw_bgr():
    argv = decoders.command('ffmpeg', URL, 1280, 720)
    assert argv[0] == 'ffmpeg'
    assert argv[argv.index('-rtsp_transport') + 1] == 'tcp'
    assert argv[argv.index('-i') + 1] == URL
    for flag in ('nobuffer', 'low_delay', 'passthrough', 'bgr24', 'rawvideo', 'scale=1280:720'):
        assert flag in argv
    assert argv[-1] == '-'                  # the pictures go to stdout
    assert '-hwaccel' not in argv
    hw = decoders.command('ffmpeg', URL, 1280, 720, hwaccel='videotoolbox')
    assert hw[hw.index('-hwaccel') + 1] == 'videotoolbox'


def test_nvidia_uses_jetpacks_gstreamer():
    argv = decoders.command('gst-nvidia', URL, 1280, 720)
    assert argv[:2] == [decoders.SYSTEM_GST, '-q']   # -q: progress off stdout
    assert f'location={URL}' in argv and 'protocols=tcp' in argv
    assert 'nvv4l2decoder' in argv and 'fdsink' in argv
    assert 'video/x-raw,format=BGRx,width=1280,height=720' in argv
    assert decoders.command('gst-nvidia', URL, 640, 360, program='/opt/gst')[0] == '/opt/gst'


def test_soft_and_mac_gstreamer():
    assert 'avdec_h264' in decoders.command('gst-soft', URL, 1280, 720)
    assert 'vtdec' in decoders.command('gst-mac', URL, 1280, 720)
    assert decoders.command('gst-soft', URL, 1280, 720)[0] == 'gst-launch-1.0'


def test_a_pipeline_of_ones_own():
    argv = decoders.command('gst-soft', URL, 640, 360, transport='udp',
                            pipeline='rtspsrc location={url} protocols={protocols} ! fakesink '
                                     'caps=w{width}h{height}')
    assert argv == ['gst-launch-1.0', '-q', 'rtspsrc', f'location={URL}', 'protocols=udp', '!',
                    'fakesink', 'caps=w640h360']


def test_bad_choices():
    with pytest.raises(ValueError, match='decoder'):
        decoders.command('nvdec', URL, 1, 1)
    with pytest.raises(ValueError, match='transport'):
        decoders.command('ffmpeg', URL, 1, 1, transport='http')
    with pytest.raises(ValueError, match='this process'):
        decoders.command('opencv', URL, 1, 1)


def test_auto_must_be_chosen_first():
    with pytest.raises(ValueError, match='choose'):
        decoders.command('auto', URL, 1, 1)


def fake_works(answers):
    """Return a works() that answers per preset ('' = it works), keeping what it was asked."""
    asked = []

    def works(program, decoder):
        asked.append((program, decoder))
        return answers[decoder]
    works.asked = asked
    return works


def gst_env(tmp_path):
    program = tmp_path / decoders.PIXI_GST
    program.parent.mkdir(parents=True)
    program.write_text('#!/bin/sh\n')
    program.chmod(0o755)
    return str(program)


def test_auto_on_a_mac_is_vtdec_from_the_gst_environment(tmp_path):
    program = gst_env(tmp_path)
    works = fake_works({'gst-mac': '', 'gst-soft': ''})
    assert decoders.choose('auto', root=str(tmp_path), platform='darwin',
                           works=works) == ('gst-mac', program, '')
    assert works.asked == [(program, 'gst-mac')]
    argv = decoders.command('gst-mac', URL, 1280, 720, program=program)
    assert argv[0] == program and 'vtdec' in argv


def test_auto_on_a_mac_without_videotoolbox_decodes_in_software(tmp_path):
    program = gst_env(tmp_path)
    works = fake_works({'gst-mac': 'vtdec could not decode', 'gst-soft': ''})
    choice = decoders.choose('auto', root=str(tmp_path), platform='darwin', works=works)
    assert choice[:2] == ('gst-soft', program)
    assert 'vtdec could not decode' in choice.warning and 'avdec_h264' in choice.warning


def test_auto_falls_back_to_ffmpeg_and_says_so(tmp_path):
    none = decoders.choose('auto', root=str(tmp_path), platform='darwin',
                           works=fake_works({}))       # no gst environment: never asked
    assert none[:2] == ('ffmpeg', '')
    assert 'pixi install -e gst' in none.warning and '135 ms' in none.warning
    gst_env(tmp_path)
    broken = decoders.choose('auto', root=str(tmp_path), platform='darwin',
                             works=fake_works({'gst-mac': 'no rtspsrc', 'gst-soft': 'no rtspsrc'}))
    assert broken[:2] == ('ffmpeg', '') and 'no rtspsrc' in broken.warning


def test_auto_on_linux_is_software_gstreamer(tmp_path):
    assert decoders.choose('auto', root=str(tmp_path), platform='linux',
                           works=fake_works({})).decoder == 'ffmpeg'
    program = gst_env(tmp_path)
    works = fake_works({'gst-soft': ''})
    assert decoders.choose('auto', root=str(tmp_path), platform='linux',
                           works=works) == ('gst-soft', program, '')
    assert works.asked == [(program, 'gst-soft')]           # no vtdec off a Mac


def test_named_decoders_stay(tmp_path):
    program = gst_env(tmp_path)
    asked = fake_works({})
    assert decoders.choose('gst-nvidia', root=str(tmp_path),
                           works=asked) == ('gst-nvidia', '', '')
    # gst-mac or gst-soft by name: the gst environment's program, unless one is given.
    assert decoders.choose('gst-soft', root=str(tmp_path), works=asked).program == program
    assert decoders.choose('gst-mac', '/opt/gst', str(tmp_path), works=asked).program == '/opt/gst'
    assert decoders.choose('gst-mac', root=str(tmp_path / 'none'), works=asked).program == ''
    assert asked.asked == []                # named decoders aren't tested: they're asked for


class Ran:
    def __init__(self, failing=()):
        self.failing, self.argvs = failing, []

    def __call__(self, argv, **kwargs):
        self.argvs.append(argv)
        failed = any(word in argv for word in self.failing)
        return type('Done', (), {'returncode': 1 if failed else 0})()


def test_gst_works_checks_each_element_then_decodes():
    run = Ran()
    assert decoders.gst_works('/g/bin/gst-launch-1.0', 'gst-mac', run=run) == ''
    inspected = [a[2] for a in run.argvs if a[0] == '/g/bin/gst-inspect-1.0']
    assert inspected == list(decoders.ELEMENTS['gst-mac'])
    assert run.argvs[-1][:2] == ['/g/bin/gst-launch-1.0', '-q'] and 'vtdec' in run.argvs[-1]
    soft = Ran()
    assert decoders.gst_works('/g/bin/gst-launch-1.0', 'gst-soft', run=soft) == ''
    assert all(a[0].endswith('gst-inspect-1.0') for a in soft.argvs)   # no test decode
    assert 'no vtdec' in decoders.gst_works('/g/bin/gst-launch-1.0', 'gst-mac',
                                            run=Ran(failing=('vtdec',)))
    assert 'test picture' in decoders.gst_works('/g/bin/gst-launch-1.0', 'gst-mac',
                                                run=Ran(failing=('-q',)))

    def missing(argv, **kwargs):
        raise FileNotFoundError(argv[0])
    assert 'gst-inspect-1.0' in decoders.gst_works('/g/bin/gst-launch-1.0', 'gst-soft',
                                                   run=missing)


ROOT = __file__.rsplit('/src/', 1)[0]


@pytest.mark.skipif(sys.platform != 'darwin' or not decoders.pixi_gst(ROOT),
                    reason='a Mac with the gst environment (pixi install -e gst)')
def test_this_macs_gst_environment_decodes_with_videotoolbox():
    assert decoders.choose('auto', root=ROOT).decoder == 'gst-mac'


def test_a_system_program_loses_pixis_paths():
    env = {'LD_LIBRARY_PATH': '/pixi/lib', 'GST_PLUGIN_PATH': '/pixi/lib/gstreamer-1.0',
           'HOME': '/home/aav'}
    outside = decoders.child_env(env, '/usr/bin/gst-launch-1.0', '/pixi')
    assert outside == {'HOME': '/home/aav'}
    inside = decoders.child_env(env, '/pixi/bin/gst-launch-1.0', '/pixi')
    assert inside == env
    on_path = decoders.child_env(env, 'ffmpeg', '/pixi')     # found on PATH: Pixi's own
    assert on_path == env


FAKE = """
import sys
n, w, h = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
for i in range(n):
    sys.stdout.buffer.write(bytes([i % 256]) * (w * h * 3))
    sys.stdout.buffer.flush()
"""


def fake_decoder(tmp_path, frames, width=8, height=4):
    script = tmp_path / 'fake_decoder.py'
    script.write_text(FAKE)
    return [sys.executable, '-I', str(script), str(frames), str(width), str(height)]


def test_pipe_source_reads_whole_frames(tmp_path):
    source = decoders.PipeSource(fake_decoder(tmp_path, 3), 8, 4)
    source.start()
    frames = [source.read() for _ in range(4)]
    source.stop()
    assert [f[0, 0, 0] for f in frames[:3]] == [0, 1, 2]
    assert frames[0].shape == (4, 8, 3) and frames[0].dtype == numpy.uint8
    assert frames[3] is None                # the stream ended
    source.stop()                           # twice is fine


def test_reader_restarts_an_ended_stream(tmp_path):
    latest = Latest()
    logs = []
    reader = Reader(lambda: decoders.PipeSource(fake_decoder(tmp_path, 2), 8, 4), latest,
                    retry=0.05, log=logs.append)
    reader.start()
    deadline = time.monotonic() + 10.0
    while reader.starts < 3 and time.monotonic() < deadline:
        time.sleep(0.02)
    reader.stop()
    assert reader.starts >= 3
    assert reader.frames >= 4
    frame, arrived_ns = latest.take(0.1)
    assert frame.shape == (4, 8, 3) and arrived_ns > 0
    assert 'stream: pictures coming' in logs


def test_reader_backs_off_when_nothing_comes(tmp_path):
    class Broken:
        def start(self):
            raise OSError('no such camera')

        def read(self):
            return None

        def stop(self):
            pass

    logs = []
    reader = Reader(Broken, Latest(), retry=0.01, retry_max=0.04, log=logs.append)
    reader.start()
    time.sleep(0.3)
    reader.stop()
    assert not reader.connected
    assert 'stream: no such camera' in logs
    assert 2 <= reader.starts <= 12          # the pause grew to 0.04 s, not 0.01
