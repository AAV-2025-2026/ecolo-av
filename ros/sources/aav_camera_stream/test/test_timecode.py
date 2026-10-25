"""The time code: drawn, read back, through noise, blur and a real H.264 encoder."""

import shutil
import subprocess

from aav_camera_stream import timecode
import numpy
import pytest


def picture(width=1280, height=720, seed=1):
    rng = numpy.random.default_rng(seed)
    return rng.integers(0, 256, (height, width, 3), dtype=numpy.uint8)


@pytest.mark.parametrize('ms', [0, 1, 123456789, timecode.WRAP - 1])
def test_round_trip(ms):
    frame = picture()
    timecode.stamp(frame, ms)
    assert timecode.read(frame) == ms


def test_small_pictures_too():
    frame = picture(640, 360)
    timecode.stamp(frame, 4242)
    assert timecode.read(frame) == 4242


def test_no_code_reads_none():
    assert timecode.read(picture()) is None
    assert timecode.read(numpy.zeros((720, 1280, 3), numpy.uint8)) is None


def test_a_damaged_code_reads_none():
    frame = picture()
    timecode.stamp(frame, 1000)
    size = timecode.square_size(1280)
    frame[0:size, 10 * size:11 * size] = 255 - frame[0:size, 10 * size:11 * size]  # flip a bit
    assert timecode.read(frame) is None


def test_survives_noise_and_blur():
    cv2 = pytest.importorskip('cv2')
    frame = picture()
    timecode.stamp(frame, 987654)
    noisy = numpy.clip(frame.astype(int) + numpy.random.default_rng(2).integers(
        -40, 40, frame.shape), 0, 255).astype(numpy.uint8)
    blurred = cv2.GaussianBlur(noisy, (5, 5), 1.5)
    assert timecode.read(blurred) == 987654


def test_too_small_to_stamp():
    with pytest.raises(ValueError):
        timecode.stamp(numpy.zeros((10, 100, 3), numpy.uint8), 1)


def test_age_across_the_wrap():
    sent = timecode.WRAP - 50                       # 50 ms before the wrap
    assert timecode.age_s(sent, (timecode.WRAP + 70) / 1000.0) == pytest.approx(0.120)
    assert timecode.age_s(timecode.now_ms(10.0), 10.25) == pytest.approx(0.25)
    assert timecode.age_s(timecode.now_ms(10.25), 10.0) == pytest.approx(-0.25)


@pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='needs ffmpeg')
def test_survives_h264_at_2_mbit():
    """Through OpenH264 (MediaMTX's own software encoder) at the car's settings."""
    width, height, n = 1280, 720, 15
    frames = []
    for i in range(n):
        frame = picture(seed=i)
        timecode.stamp(frame, 1000 + i)
        frames.append(frame)
    encoders = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], capture_output=True,
                              text=True).stdout
    codec = 'libopenh264' if 'libopenh264' in encoders else 'libx264'
    encoded = subprocess.run(
        ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24',
         '-s', f'{width}x{height}', '-framerate', '15', '-i', '-', '-c:v', codec,
         '-b:v', '2M', '-g', '15', '-bf', '0', '-f', 'h264', '-'],
        input=b''.join(f.tobytes() for f in frames), capture_output=True, check=True).stdout
    decoded = subprocess.run(
        ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'h264', '-i', '-',
         '-pix_fmt', 'bgr24', '-f', 'rawvideo', '-'],
        input=encoded, capture_output=True, check=True).stdout
    size = width * height * 3
    got = [timecode.read(numpy.frombuffer(decoded[i:i + size], numpy.uint8).reshape(
        height, width, 3)) for i in range(0, len(decoded), size)]
    assert got == [1000 + i for i in range(n)]
