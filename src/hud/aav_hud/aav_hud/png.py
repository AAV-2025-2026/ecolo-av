"""
A camera picture (the fields of a sensor_msgs/Image) as a PNG file.

No ROS imports, and only Python's standard library: it has zlib, but no JPEG encoder,
and the HUD shouldn't need another dependency for this. PNG files are bigger than JPEG
ones, but the app reads them from its own computer.
"""

import struct
import zlib

# ROS encoding: (bytes per pixel, PNG colour type, the order that makes it RGB or RGBA)
FORMATS = {
    'rgb8': (3, 2, None),
    'bgr8': (3, 2, (2, 1, 0)),
    'rgba8': (4, 6, None),
    'bgra8': (4, 6, (2, 1, 0, 3)),
    'mono8': (1, 0, None),
    '8UC1': (1, 0, None),
}

SIGNATURE = b'\x89PNG\r\n\x1a\n'


def _chunk(kind, data):
    crc = zlib.crc32(kind + data) & 0xffffffff
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', crc)


def encode(width, height, encoding, step, data, level=1):
    """
    Make a PNG file from an image's fields. Raise ValueError if it can't.

    step is the bytes in one row, padding included. level is zlib's: 1 is fast.
    """
    if encoding not in FORMATS:
        raise ValueError(f'camera encoding {encoding!r} is not one of {", ".join(FORMATS)}')
    size, colour, order = FORMATS[encoding]
    row = width * size
    data = bytes(data)      # rclpy gives an array.array
    if width <= 0 or height <= 0 or step < row or len(data) < step * (height - 1) + row:
        raise ValueError(f'{len(data)} bytes are too few for {width}x{height} {encoding}')
    rows = [data[y * step:y * step + row] for y in range(height)]
    pixels = b''.join(rows)
    if order is not None:
        swapped = bytearray(len(pixels))
        for to, source in enumerate(order):
            swapped[to::size] = pixels[source::size]
        pixels = bytes(swapped)
    # Each PNG row starts with its filter type: 0, none.
    raw = b''.join(b'\x00' + pixels[y * row:(y + 1) * row] for y in range(height))
    header = struct.pack('>IIBBBBB', width, height, 8, colour, 0, 0, 0)
    return (SIGNATURE + _chunk(b'IHDR', header) + _chunk(b'IDAT', zlib.compress(raw, level))
            + _chunk(b'IEND', b''))
