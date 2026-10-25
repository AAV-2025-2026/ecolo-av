"""
timecode: a clock time drawn into a picture, to measure a stream's delay end to end.

A row of black and white squares along the top left corner carries the time in
milliseconds (mod 2^32) and a CRC-8 of it. It is drawn before the picture is encoded and
read after it is decoded, on the same computer, so the difference is the whole trip:
encoder, RTSP, MediaMTX, decoder and whatever comes after. Squares 1/80 of the picture
wide (16 px at 1280) survive H.264 at 2 Mbit/s: they line up with its 16 px blocks.

The row: a white and a black square (the reader's levels), 32 time bits, 8 CRC bits,
most significant first. A picture without a code, or with a damaged one, reads as None.
"""

WRAP = 1 << 32
DATA_BITS = 32
CRC_BITS = 8
SQUARES = 2 + DATA_BITS + CRC_BITS


def crc8(value: int) -> int:
    """CRC-8 (polynomial 0x07) of the 4 bytes of value, most significant first."""
    crc = 0
    for byte in value.to_bytes(4, 'big'):
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def square_size(width: int) -> int:
    """Pixels per square for a picture this wide: 1/80 of it, at least 4."""
    return max(4, width // 80)


def bits_of(ms: int):
    """Return the squares' values, 1 = white, for a time in ms."""
    value = ms % WRAP
    word = (value << CRC_BITS) | crc8(value)
    return [1, 0] + [(word >> i) & 1 for i in reversed(range(DATA_BITS + CRC_BITS))]


def stamp(frame, ms: int) -> None:
    """Draw the time ms into the picture (a numpy array, height x width [x channels])."""
    size = square_size(frame.shape[1])
    if frame.shape[0] < size or frame.shape[1] < size * SQUARES:
        raise ValueError(f'a {frame.shape[1]}x{frame.shape[0]} picture is too small '
                         'for the time code')
    for i, bit in enumerate(bits_of(ms)):
        frame[0:size, i * size:(i + 1) * size] = 255 if bit else 0


def read(frame):
    """Return the time in ms drawn into the picture, or None if there is none."""
    size = square_size(frame.shape[1])
    if frame.shape[0] < size or frame.shape[1] < size * SQUARES:
        return None
    # The middle of each square only: its edges blur in the encoder.
    lo, hi = size // 4, size - size // 4
    levels = [float(frame[lo:hi, i * size + lo:i * size + hi].mean()) for i in range(SQUARES)]
    white, black = levels[0], levels[1]
    if white - black < 64:
        return None                     # no reference squares: no code here
    middle = (white + black) / 2
    word = 0
    for level in levels[2:]:
        word = (word << 1) | (level > middle)
    value, crc = word >> CRC_BITS, word & 0xFF
    return value if crc8(value) == crc else None


def now_ms(wall_s: float) -> int:
    """Return a wall-clock time in s as the code's ms, mod 2^32."""
    return int(round(wall_s * 1000.0)) % WRAP


def age_s(sent_ms: int, wall_s: float) -> float:
    """Seconds from the code's time to wall_s, across the 2^32 ms wrap (49 days)."""
    diff = (now_ms(wall_s) - sent_ms) % WRAP
    if diff >= WRAP // 2:
        diff -= WRAP                    # sent after wall_s: a clock step, or a misread
    return diff / 1000.0
