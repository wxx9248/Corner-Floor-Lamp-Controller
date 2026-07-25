"""Layer-1 self-consistency: every builder must match the device-verified
spec (duoCo-StripX-BLE-protocol.md §4/§6/§9) byte-for-byte."""
import pytest

from duoco_stripx import protocol

CASES = [
    # (builder result, spec hex)
    (protocol.power(True), "7E 04 04 01 00 01 FF 00 EF"),          # §4.1
    (protocol.power(False), "7E 04 04 00 00 00 FF 00 EF"),         # §4.1
    (protocol.brightness(50, 1), "7E 04 01 32 01 FF FF 00 EF"),    # §4.2 example
    (protocol.brightness(100, 0), "7E 04 01 64 00 FF FF 00 EF"),   # §4.2
    (protocol.rgb(255, 0, 0), "7E 07 05 03 FF 00 00 10 EF"),       # §4.3 example
    (protocol.rgb(0, 0, 255), "7E 07 05 03 00 00 FF 10 EF"),       # §4.3 example
    (protocol.cct(100, 0), "7E 06 05 02 64 00 FF 08 EF"),          # §4.4 example
    (protocol.cct(0, 100), "7E 06 05 02 00 64 FF 08 EF"),          # §4.4 example
    (protocol.mode(0), "7E 05 03 00 06 FF FF 00 EF"),              # §4.5 Auto Play
    (protocol.mode(193), "7E 05 03 C1 06 FF FF 00 EF"),            # §4.5 7-Color Jump
    (protocol.speed(5), "7E 04 02 05 FF FF FF 00 EF"),             # §4.6
    (protocol.scene(1), "7E 05 31 01 07 FF FF 01 EF"),             # §4.7 Sunrise
    (protocol.single_color(50), "7E 05 05 01 32 FF FF 08 EF"),     # §4.8
    (protocol.mic_on(True), "7E 04 07 01 FF FF FF 00 EF"),         # §6
    (protocol.mic_on(False), "7E 04 07 00 FF FF FF 00 EF"),        # §6
    (protocol.mic_sensitive(100), "7E 04 06 64 FF FF FF 00 EF"),   # §6
    (protocol.mic_eq(0), "7E 07 03 80 04 FF FF 00 EF"),            # §6 Energic
    (protocol.mic_eq(7), "7E 07 03 87 04 FF FF 00 EF"),            # §6 Rolling Two
    (protocol.music_amp(255, 0, 0), "7E 07 05 03 FF 00 00 20 EF"), # §6
    (protocol.symphony(80), "7E 07 21 50 00 00 FF 00 EF"),         # §6.1 (80 px, LE)
    (protocol.symphony(300), "7E 07 21 2C 01 00 FF 00 EF"),        # 16-bit LE
    (protocol.pin_sequence(2, 1, 3), "7E 06 81 02 01 03 FF 00 EF"),  # §6.1 correct MELK-OC21 value
    (protocol.system_time(12, 0, 0, 2), "7E 07 83 0C 00 00 02 FF EF"),  # §6
    (protocol.timing_status(12, 2, 0, 0, 0xFF), "7E 08 82 0C 02 00 00 FF EF"),  # §6.1 verified alarm
]


@pytest.mark.parametrize("frame,expected", CASES, ids=[c[1] for c in CASES])
def test_frame_bytes(frame: bytes, expected: str) -> None:
    assert protocol.hexf(frame) == expected


def test_frames_are_nine_bytes() -> None:
    for frame, _ in CASES:
        assert len(frame) == 9
        assert frame[0] == 0x7E
        assert frame[-1] == 0xEF
