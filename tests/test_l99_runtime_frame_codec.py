"""Unit tests for AULA L99 Short Runtime Frame Codec.

Tests cover:
- Known CRC16 test vectors
- Valid read frame encoding/decoding
- Valid write frame encoding/decoding
- Encode/decode round trip
- Invalid magic rejection
- Invalid length rejection
- Invalid CRC rejection
- Truncated packet rejection
- Unsupported opcode rejection
- Empty write payload rejection
- Maximum supported frame length
- Address boundary validation
- Deterministic output
"""

import pytest
from scripts.research.l99_runtime_frame_codec import (
    crc16_modbus,
    encode_read_frame,
    encode_write_frame,
    decode_frame,
    decode_read_body,
    decode_write_body,
    round_trip_test_read,
    round_trip_test_write,
    InvalidMagicError,
    InvalidLengthError,
    InvalidCRCError,
    TruncatedFrameError,
    UnsupportedOpcodeError,
    InvalidAddressError,
    InvalidWordCountError,
    EmptyWritePayloadError,
    MAX_READ_WORD_COUNT,
    MAX_BODY_LENGTH,
    ADDRESS_MAX,
)


class TestCRC16:
    """Test CRC16/MODBUS implementation against known vectors."""

    def test_known_vector_123456789(self):
        """Test standard MODBUS CRC16 test vector."""
        assert crc16_modbus(b'123456789') == 0x4B37

    def test_empty_input(self):
        """Test CRC16 of empty input equals initial value."""
        assert crc16_modbus(b'') == 0xFFFF

    def test_single_byte(self):
        """Test CRC16 of single byte."""
        assert crc16_modbus(b'\x00') == 0x40BF
        assert crc16_modbus(b'\xFF') == 0x00FF

    def test_deterministic(self):
        """Verify deterministic output for same input."""
        data = b'test data for crc'
        crc1 = crc16_modbus(data)
        crc2 = crc16_modbus(data)
        assert crc1 == crc2


class TestValidReadFrame:
    """Test valid read frame encoding and decoding."""

    def test_signature_read(self):
        """Test encoding documented signature read at 0x0638."""
        frame = encode_read_frame(0x0638, 2)
        body = decode_frame(frame)
        addr, count = decode_read_body(body)
        assert addr == 0x0638
        assert count == 2

    def test_pv_power_read(self):
        """Test encoding read at PV power address 0x0600."""
        frame = encode_read_frame(0x0600, 1)
        body = decode_frame(frame)
        addr, count = decode_read_body(body)
        assert addr == 0x0600
        assert count == 1

    def test_max_word_count(self):
        """Test read with maximum word count (8)."""
        frame = encode_read_frame(0x0600, 8)
        body = decode_frame(frame)
        addr, count = decode_read_body(body)
        assert addr == 0x0600
        assert count == 8

    def test_address_boundary_zero(self):
        """Test read at minimum address 0x0000."""
        frame = encode_read_frame(0x0000, 1)
        body = decode_frame(frame)
        addr, count = decode_read_body(body)
        assert addr == 0x0000

    def test_address_boundary_max(self):
        """Test read at maximum address 0xFFFF."""
        frame = encode_read_frame(0xFFFF, 1)
        body = decode_frame(frame)
        addr, count = decode_read_body(body)
        assert addr == 0xFFFF

    def test_read_body_structure(self):
        """Verify read body has correct structure: 03 | addr:BE16 | count:BE16."""
        frame = encode_read_frame(0x1234, 2)
        body = decode_frame(frame)
        assert body[0] == 0x03
        assert struct.unpack('>H', body[1:3])[0] == 0x1234
        assert struct.unpack('>H', body[3:5])[0] == 2

    def test_read_frame_deterministic(self):
        """Verify deterministic frame output for same inputs."""
        frame1 = encode_read_frame(0x0638, 2)
        frame2 = encode_read_frame(0x0638, 2)
        assert frame1 == frame2


class TestValidWriteFrame:
    """Test valid write frame encoding and decoding."""

    def test_single_word_write(self):
        """Test write frame with single word."""
        frame = encode_write_frame(0x0600, [0x454E])
        body = decode_frame(frame)
        addr, words = decode_write_body(body)
        assert addr == 0x0600
        assert words == [0x454E]

    def test_multi_word_write(self):
        """Test write frame with multiple words."""
        words = [0x454E, 0x4531, 0x1234, 0x5678]
        frame = encode_write_frame(0x0600, words)
        body = decode_frame(frame)
        addr, decoded = decode_write_body(body)
        assert addr == 0x0600
        assert decoded == words

    def test_write_body_structure(self):
        """Verify write body structure: 10 | addr:BE16 | word_0:BE16 | word_1:BE16 | ..."""
        frame = encode_write_frame(0x1234, [0xABCD, 0xEF01])
        body = decode_frame(frame)
        assert body[0] == 0x10
        assert struct.unpack('>H', body[1:3])[0] == 0x1234
        assert struct.unpack('>H', body[3:5])[0] == 0xABCD
        assert struct.unpack('>H', body[5:7])[0] == 0xEF01

    def test_max_address_write(self):
        """Test write at maximum address."""
        frame = encode_write_frame(0xFFFF, [0x0000])
        body = decode_frame(frame)
        addr, words = decode_write_body(body)
        assert addr == 0xFFFF
        assert words == [0x0000]

    def test_write_frame_deterministic(self):
        """Verify deterministic frame output for same inputs."""
        frame1 = encode_write_frame(0x0600, [0x454E, 0x4531])
        frame2 = encode_write_frame(0x0600, [0x454E, 0x4531])
        assert frame1 == frame2


class TestRoundTrip:
    """Test encode/decode round trips."""

    def test_read_round_trip_various(self):
        """Test round trip for various read parameters."""
        assert round_trip_test_read(0x0600, 1)
        assert round_trip_test_read(0x0638, 2)
        assert round_trip_test_read(0xFFFF, 8)
        assert round_trip_test_read(0x0000, 1)

    def test_write_round_trip_various(self):
        """Test round trip for various write parameters."""
        assert round_trip_test_write(0x0600, [0x0000])
        assert round_trip_test_write(0x0610, [0x1234, 0x5678, 0x9ABC, 0xDEF0])
        assert round_trip_test_write(0xFFFF, [0xFFFF])
        assert round_trip_test_write(0x0000, [0x0000, 0x0001, 0x0002])


class TestInvalidMagic:
    """Test rejection of invalid magic bytes."""

    def test_wrong_magic_bytes(self):
        """Test rejection of completely wrong magic."""
        with pytest.raises(InvalidMagicError):
            decode_frame(b'\x00\x00\x05\x03\x00\x00\x01\x00\x00')

    def test_partial_magic(self):
        """Test rejection of partial magic match."""
        with pytest.raises(InvalidMagicError):
            decode_frame(b'\x5a\x00\x05\x03\x00\x00\x01\x00\x00')

    def test_reversed_magic(self):
        """Test rejection of reversed magic bytes."""
        with pytest.raises(InvalidMagicError):
            decode_frame(b'\xa5\x5a\x05\x03\x00\x00\x01\x00\x00')


class TestInvalidLength:
    """Test rejection of invalid length fields."""

    def test_length_too_short(self):
        """Test rejection when packet shorter than declared length."""
        with pytest.raises((InvalidLengthError, TruncatedFrameError)):
            decode_frame(b'\x5a\xa5\x10\x03\x00\x00\x01')

    def test_length_mismatch_extra_bytes(self):
        """Test rejection when packet has extra trailing bytes."""
        frame = encode_read_frame(0x0600, 1)
        with pytest.raises(InvalidLengthError):
            decode_frame(frame + b'\x00')

    def test_zero_length(self):
        """Test rejection of zero length field."""
        with pytest.raises((InvalidLengthError, TruncatedFrameError)):
            decode_frame(b'\x5a\xa5\x00')

    def test_body_too_short(self):
        """Test rejection when body shorter than minimum."""
        with pytest.raises(TruncatedFrameError):
            decode_frame(b'\x5a\xa5\x04\x03\x00\x00')


class TestInvalidCRC:
    """Test rejection of invalid CRC."""

    def test_wrong_crc(self):
        """Test rejection when CRC doesn't match."""
        frame = encode_read_frame(0x0600, 1)
        corrupted = frame[:-2] + b'\x00\x00'
        with pytest.raises(InvalidCRCError):
            decode_frame(corrupted)

    def test_crc_off_by_one(self):
        """Test rejection when CRC off by one."""
        frame = encode_read_frame(0x0600, 1)
        crc_bytes = frame[-2:]
        crc_val = struct.unpack('<H', crc_bytes)[0]
        corrupted_crc = struct.pack('<H', (crc_val + 1) & 0xFFFF)
        corrupted = frame[:-2] + corrupted_crc
        with pytest.raises(InvalidCRCError):
            decode_frame(corrupted)


class TestTruncatedPacket:
    """Test rejection of truncated packets."""

    def test_only_magic(self):
        """Test rejection of only magic bytes."""
        with pytest.raises(TruncatedFrameError):
            decode_frame(b'\x5a\xa5')

    def test_magic_and_length_only(self):
        """Test rejection of magic + length only."""
        with pytest.raises(TruncatedFrameError):
            decode_frame(b'\x5a\xa5\x05')

    def test_incomplete_body(self):
        """Test rejection of incomplete body."""
        with pytest.raises(TruncatedFrameError):
            decode_frame(b'\x5a\xa5\x05\x03\x00')

    def test_missing_crc(self):
        """Test rejection when CRC bytes missing."""
        frame = encode_read_frame(0x0600, 1)
        with pytest.raises(TruncatedFrameError):
            decode_frame(frame[:-1])


class TestUnsupportedOpcode:
    """Test rejection of unsupported opcodes."""

    def test_invalid_read_opcode(self):
        """Test rejection of non-0x03 opcode in read body."""
        body = b'\x99\x00\x00\x00\x01'
        with pytest.raises(UnsupportedOpcodeError):
            decode_read_body(body)

    def test_invalid_write_opcode(self):
        """Test rejection of non-0x10 opcode in write body."""
        body = b'\x99\x00\x00\x00\x00'
        with pytest.raises(UnsupportedOpcodeError):
            decode_write_body(body)

    def test_opcode_0x00(self):
        """Test rejection of opcode 0x00."""
        body = b'\x00\x00\x00\x00\x01'
        with pytest.raises(UnsupportedOpcodeError):
            decode_read_body(body)

    def test_opcode_0xFF(self):
        """Test rejection of opcode 0xFF."""
        body = b'\xff\x00\x00\x00\x01'
        with pytest.raises(UnsupportedOpcodeError):
            decode_read_body(body)


class TestEmptyWritePayload:
    """Test rejection of empty write payload."""

    def test_empty_words_list(self):
        """Test rejection when words list is empty."""
        with pytest.raises(EmptyWritePayloadError):
            encode_write_frame(0x0600, [])

    def test_write_body_no_words(self):
        """Test rejection when write body has no word data."""
        body = b'\x10\x00\x00'
        with pytest.raises(EmptyWritePayloadError):
            decode_write_body(body)


class TestMaxFrameLength:
    """Test maximum supported frame length handling."""

    def test_max_body_length_read(self):
        """Test read frame at max body length (5 bytes for read)."""
        frame = encode_read_frame(0x0600, 8)
        assert len(frame) == 3 + 5 + 2  # magic(2) + length(1) + body(5) + crc(2)

    def test_max_body_length_write(self):
        """Test write frame at max body length."""
        max_words = (MAX_BODY_LENGTH - 3) // 2
        words = [0x0000] * max_words
        frame = encode_write_frame(0x0600, words)
        body = decode_frame(frame)
        assert len(body) == MAX_BODY_LENGTH

    def test_write_exceeds_max_length(self):
        """Test rejection when write would exceed max frame length."""
        max_words = (MAX_BODY_LENGTH - 3) // 2 + 1
        words = [0x0000] * max_words
        with pytest.raises(InvalidWordCountError):
            encode_write_frame(0x0600, words)


class TestAddressValidation:
    """Test address boundary validation."""

    def test_address_negative(self):
        """Test rejection of negative address."""
        with pytest.raises(InvalidAddressError):
            encode_read_frame(-1, 1)

    def test_address_above_max(self):
        """Test rejection of address > 0xFFFF."""
        with pytest.raises(InvalidAddressError):
            encode_read_frame(0x10000, 1)

    def test_write_address_negative(self):
        """Test rejection of negative write address."""
        with pytest.raises(InvalidAddressError):
            encode_write_frame(-1, [0x0000])

    def test_write_address_above_max(self):
        """Test rejection of write address > 0xFFFF."""
        with pytest.raises(InvalidAddressError):
            encode_write_frame(0x10000, [0x0000])


class TestWordCountValidation:
    """Test word count validation."""

    def test_read_zero_count(self):
        """Test rejection of zero word count for read."""
        with pytest.raises(InvalidWordCountError):
            encode_read_frame(0x0600, 0)

    def test_read_negative_count(self):
        """Test rejection of negative word count."""
        with pytest.raises(InvalidWordCountError):
            encode_read_frame(0x0600, -1)

    def test_read_count_exceeds_max(self):
        """Test rejection of read word count > 8."""
        with pytest.raises(InvalidWordCountError):
            encode_read_frame(0x0600, 9)

    def test_write_word_value_out_of_range(self):
        """Test rejection of word value > 0xFFFF."""
        with pytest.raises(InvalidWordCountError):
            encode_write_frame(0x0600, [0x10000])

    def test_write_negative_word_value(self):
        """Test rejection of negative word value."""
        with pytest.raises(InvalidWordCountError):
            encode_write_frame(0x0600, [-1])


class TestDeterministicOutput:
    """Test deterministic encoding output."""

    def test_same_input_same_output_read(self):
        """Multiple encodings of same read produce identical frames."""
        for _ in range(10):
            frame1 = encode_read_frame(0x1234, 3)
            frame2 = encode_read_frame(0x1234, 3)
            assert frame1 == frame2

    def test_same_input_same_output_write(self):
        """Multiple encodings of same write produce identical frames."""
        words = [0x1111, 0x2222, 0x3333]
        for _ in range(10):
            frame1 = encode_write_frame(0x1234, words)
            frame2 = encode_write_frame(0x1234, words)
            assert frame1 == frame2

    def test_crc_deterministic(self):
        """CRC16 produces same output for same input."""
        data = b'deterministic test data'
        crc1 = crc16_modbus(data)
        crc2 = crc16_modbus(data)
        assert crc1 == crc2
        assert crc1 == 0x8255  # Verified value


import struct

if __name__ == '__main__':
    pytest.main([__file__, '-v'])