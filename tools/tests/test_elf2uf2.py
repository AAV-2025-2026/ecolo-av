"""Tests for tools/elf2uf2.py: Pico 2 programs into UF2 files, on made-up ELF files."""

from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import elf2uf2  # noqa: E402
import pytest  # noqa: E402

FLASH = 0x1000_0000
START, END = 0xFFFF_DED3, 0xAB12_3579        # a block's markers (datasheet Table 487)
SECURE_ARM_EXE = 0x1021                       # IMAGE_TYPE flags (Table 493)


def words(*values):
    return struct.pack(f'<{len(values)}I', *values)


def image_def(flags=SECURE_ARM_EXE, link=0):
    """Return Embassy's ImageDef::secure_exe() (embassy-rp 0.10, src/block.rs)."""
    return words(START, flags << 16 | 0x0142, 0x0000_01FF, link & 0xFFFF_FFFF, END)


def ignored_block(link, size=1):
    """Return a block whose only item is IGNORED (2-byte size), linking on."""
    return words(START, size << 8 | 0xFE, *[0] * (size - 1), size << 8 | 0xFF, link, END)


def program(block=None, at=0x40, size=600):
    """Return a program: a vector table's worth of bytes, the block at `at`, code."""
    block = image_def() if block is None else block
    data = bytearray(range(256)) * (size // 256 + 1)
    data[at:at + len(block)] = block
    return bytes(data[:size])


def elf(*segments, machine=40):
    """Return a 32-bit Arm ELF file with these (virtual, physical address, bytes) parts."""
    phoff, phsize = 52, 32
    offset = phoff + phsize * len(segments)
    headers, body = b'', b''
    for vaddr, paddr, data in segments:
        headers += words(1, offset + len(body), vaddr, paddr, len(data), len(data), 5, 4)
        body += data
    header = b'\x7fELF\x01\x01\x01' + bytes(9) + struct.pack(
        '<HHIIIIIHHHHHH', 2, machine, 1, FLASH | 1, phoff, 0, 0x0500_0400, 52, phsize,
        len(segments), 40, 0, 0)
    return header + headers + body


def blocks(uf2):
    """Return each UF2 block as (its eight header words, its payload, its end word)."""
    assert len(uf2) % 512 == 0
    return [(struct.unpack_from('<8I', uf2, i), uf2[i + 32:i + 508],
             struct.unpack_from('<I', uf2, i + 508)[0]) for i in range(0, len(uf2), 512)]


def test_a_program_becomes_256_byte_blocks_for_the_rp2350():
    code = program(size=600)
    uf2, found = elf2uf2.convert(elf((FLASH, FLASH, code)))
    assert found == (FLASH + 0x40, SECURE_ARM_EXE)
    got = blocks(uf2)
    assert len(got) == 3                          # 600 bytes: three pages of 256
    for number, (header, payload, end) in enumerate(got):
        assert header == (0x0A32_4655, 0x9E5D_5157, 0x2000, FLASH + 256 * number, 256,
                          number, 3, 0xE48B_FF59)  # the family ID: rp2350_arm_s
        assert end == 0x0AB1_6F30
        assert payload[256:] == bytes(220)
    image = b''.join(payload[:256] for _, payload, _ in got)
    assert image[:600] == code and image[600:] == bytes(168)


def test_initialised_data_goes_where_it_loads_from_in_flash():
    data = b'initial values'
    uf2, _ = elf2uf2.convert(elf((FLASH, FLASH, program(size=256)),
                                 (0x2000_0000, FLASH + 0x400, data)))
    (_, _, _, address, *_), payload, _ = blocks(uf2)[1]
    assert address == FLASH + 0x400
    assert payload[:len(data)] == data


def test_only_the_pages_with_something_in_them_are_written():
    uf2, _ = elf2uf2.convert(elf((FLASH, FLASH, program(size=300)),
                                 (FLASH + 0x1010, FLASH + 0x1010, b'\x01\x02')))
    got = blocks(uf2)
    assert [header[3] for header, _, _ in got] == [FLASH, FLASH + 0x100, FLASH + 0x1000]
    assert [header[5:7] for header, _, _ in got] == [(0, 3), (1, 3), (2, 3)]
    assert got[2][1][0x10:0x12] == b'\x01\x02' and got[2][1][:0x10] == bytes(16)


def test_a_program_with_no_image_def_is_refused():
    with pytest.raises(elf2uf2.Uf2Error, match='no IMAGE_DEF.*5.9.5'):
        elf2uf2.convert(elf((FLASH, FLASH, program(block=b''))))


def test_an_image_def_past_the_first_4_kb_is_refused():
    for at in (4096, 4092):                       # it starts after them, or runs past them
        with pytest.raises(elf2uf2.Uf2Error, match='no IMAGE_DEF'):
            elf2uf2.convert(elf((FLASH, FLASH, program(at=at, size=5000))))
    _, found = elf2uf2.convert(elf((FLASH, FLASH, program(at=4076, size=5000))))
    assert found[0] == FLASH + 4076               # its last word is the 4 kB's last


@pytest.mark.parametrize('flags, why', [
    (0x0021, 'not for the RP2350'),               # an RP2040 image
    (0x1011, 'not a Secure image'),               # Non-secure: the rp2350_arm_ns family
    (0x1121, 'not for the Arm cores'),            # RISC-V
    (0x1022, 'not an executable'),                # data
])
def test_an_image_def_for_another_kind_of_image_is_refused(flags, why):
    with pytest.raises(elf2uf2.Uf2Error, match=why):
        elf2uf2.convert(elf((FLASH, FLASH, program(block=image_def(flags)))))


@pytest.mark.parametrize('block', [
    image_def()[:-4] + words(0x1234_5678),          # no end marker
    image_def()[:8] + words(0x0000_02FF) + image_def()[12:],  # LAST gives the wrong size
    image_def(link=0x100),                           # links to nothing: no closed loop
    words(START, SECURE_ARM_EXE << 16 | 0x0142, 99 << 8 | 0xFE) + bytes(4 * 98)
    + words(100 << 8 | 0xFF, 0, END),                # 416 bytes: an IMAGE_DEF over 384
    image_def()[4:],                                 # no start marker
])
def test_a_broken_block_is_no_image_def(block):
    with pytest.raises(elf2uf2.Uf2Error, match='no IMAGE_DEF'):
        elf2uf2.convert(elf((FLASH, FLASH, program(block=block, size=1024))))


def loop_of_two(first, second):
    """Return a program with `first` at 0x40, linking to `second` at 0x240, and back."""
    code = bytearray(program(block=first, size=1024))
    code[0x240:0x240 + len(second)] = second
    return elf((FLASH, FLASH, bytes(code)))


def test_a_loop_of_two_blocks_boots_its_last_image_def():
    _, found = elf2uf2.convert(loop_of_two(ignored_block(0x200, size=50), image_def(link=-0x200)))
    assert found == (FLASH + 0x240, SECURE_ARM_EXE)
    _, found = elf2uf2.convert(loop_of_two(image_def(link=0x200), image_def(link=-0x200)))
    assert found == (FLASH + 0x240, SECURE_ARM_EXE)
    with pytest.raises(elf2uf2.Uf2Error, match='0x10000040.*not for the RP2350'):
        elf2uf2.convert(loop_of_two(image_def(0x0021, 0x200), image_def(link=-0x200)))


@pytest.mark.parametrize('data, why', [
    (b'hello', 'not a 32-bit little-endian ELF'),
    (b'\x7fELF\x02\x01' + bytes(58), 'not a 32-bit little-endian ELF'),   # 64-bit
    (elf((FLASH, FLASH, program()), machine=62), 'not Arm'),
    (elf((FLASH, FLASH, program()))[:100], 'cut short'),
    (elf()[:30], 'cut short'),
    (elf(), 'nothing to load'),
    (elf((0x2000_0000, 0x2000_0000, program())), 'not in flash'),         # a RAM program
])
def test_what_is_not_a_pico_2_program_is_refused(data, why):
    with pytest.raises(elf2uf2.Uf2Error, match=why):
        elf2uf2.convert(data)


def test_the_command_writes_the_uf2_next_to_the_elf(tmp_path, capsys):
    path = tmp_path / 'spine-pico2'
    path.write_bytes(elf((FLASH, FLASH, program())))
    assert elf2uf2.main(['elf2uf2.py', str(path)]) == 0
    assert len((tmp_path / 'spine-pico2.uf2').read_bytes()) == 3 * 512
    out = capsys.readouterr().out
    assert '3 blocks' in out and 'IMAGE_DEF at 0x10000040 (flags 0x1021' in out
    assert elf2uf2.main(['elf2uf2.py', str(path), str(tmp_path / 'other.uf2')]) == 0
    assert (tmp_path / 'other.uf2').exists()


def test_the_command_says_what_went_wrong(tmp_path, capsys):
    assert elf2uf2.main(['elf2uf2.py']) == 2
    assert capsys.readouterr().err.startswith('usage: tools/elf2uf2.py')
    assert elf2uf2.main(['elf2uf2.py', str(tmp_path / 'missing')]) == 1
    assert 'missing' in capsys.readouterr().err
    (tmp_path / 'plain').write_bytes(elf((FLASH, FLASH, program(block=b''))))
    assert elf2uf2.main(['elf2uf2.py', str(tmp_path / 'plain')]) == 1
    assert 'no IMAGE_DEF' in capsys.readouterr().err
    assert not (tmp_path / 'plain.uf2').exists()
