"""Tests for png.py: camera pictures as PNG files."""

import array
import io
import struct
import zlib

from aav_hud import png
import pytest

try:
    from PIL import Image as PillowImage     # only to cross-check; not a dependency
except ImportError:
    PillowImage = None


def read_png(data):
    """Return (width, height, colour type, pixel bytes) of a PNG that png.encode made."""
    assert data[:8] == png.SIGNATURE
    pos, chunks = 8, {}
    while pos < len(data):
        length, kind = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        (crc,) = struct.unpack('>I', data[pos + 8 + length:pos + 12 + length])
        assert crc == zlib.crc32(kind + body) & 0xffffffff
        chunks[kind] = chunks.get(kind, b'') + body
        pos += 12 + length
    width, height, depth, colour = struct.unpack('>IIBB', chunks[b'IHDR'][:10])
    assert depth == 8 and b'IEND' in chunks
    raw = zlib.decompress(chunks[b'IDAT'])
    row = len(raw) // height
    assert all(raw[y * row] == 0 for y in range(height))     # filter: none
    pixels = b''.join(raw[y * row + 1:(y + 1) * row] for y in range(height))
    return width, height, colour, pixels


def test_rgb8_keeps_its_pixels():
    data = bytes(range(2 * 3 * 3))      # 3 x 2 pixels
    assert read_png(png.encode(3, 2, 'rgb8', 9, data)) == (3, 2, 2, data)


def test_bgr8_becomes_rgb():
    blue_then_red = bytes([255, 0, 0, 0, 0, 255])
    _, _, colour, pixels = read_png(png.encode(2, 1, 'bgr8', 6, blue_then_red))
    assert colour == 2
    assert pixels == bytes([0, 0, 255, 255, 0, 0])


def test_bgra8_and_mono8():
    _, _, colour, pixels = read_png(png.encode(1, 1, 'bgra8', 4, bytes([1, 2, 3, 4])))
    assert (colour, pixels) == (6, bytes([3, 2, 1, 4]))
    _, _, colour, pixels = read_png(png.encode(2, 2, 'mono8', 2, bytes([0, 64, 128, 255])))
    assert (colour, pixels) == (0, bytes([0, 64, 128, 255]))


def test_row_padding_is_dropped():
    # Rows of 2 RGB pixels (6 bytes) stored with a step of 8: 2 bytes of padding each.
    data = bytes([1, 2, 3, 4, 5, 6, 0, 0, 7, 8, 9, 10, 11, 12, 0, 0])
    _, _, _, pixels = read_png(png.encode(2, 2, 'rgb8', 8, data))
    assert pixels == bytes([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])


def test_rclpy_arrays_work():
    data = array.array('B', [9, 8, 7])
    assert read_png(png.encode(1, 1, 'rgb8', 3, data))[3] == bytes([9, 8, 7])


@pytest.mark.parametrize('args', [
    (2, 2, 'yuv422', 4, bytes(8)),      # an encoding it doesn't know
    (2, 2, 'rgb8', 6, bytes(11)),       # too few bytes
    (2, 2, 'rgb8', 5, bytes(12)),       # a step shorter than a row
    (0, 2, 'rgb8', 0, b''),
])
def test_bad_pictures_raise(args):
    with pytest.raises(ValueError):
        png.encode(*args)


@pytest.mark.skipif(PillowImage is None, reason='Pillow is not installed')
def test_pillow_reads_it():
    data = bytes([10, 20, 30, 40, 50, 60])
    image = PillowImage.open(io.BytesIO(png.encode(2, 1, 'bgr8', 6, data)))
    assert image.size == (2, 1)
    assert image.convert('RGB').tobytes() == bytes([30, 20, 10, 60, 50, 40])
