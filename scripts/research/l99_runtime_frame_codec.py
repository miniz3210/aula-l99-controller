"""AULA L99 Short Runtime Frame Codec - Offline Implementation.

Deterministic offline encoder/decoder for the documented AULA L99 short
runtime USB protocol. No hardware access. No external dependencies.

Frame format:
  5A A5 | length:u8 | body | CRC16(body):LE16
  length = len(body) + 2
  CRC16: reflected polynomial 0xA001, init 0xFFFF

Read body:  03 | word_address:BE16 | word_count:BE16
Write body: 10 | word_address:BE16 | word_0:BE16 | word_1:BE16 | ...

Address range: 0x0000 - 0xFFFF (16-bit word indices)
Max word count per read: 8 (per documented chunking)
Max frame body length: 253 bytes (length field is u8, minus 2 for CRC)
"""

import struct
from typing import Tuple, List, Optional

MAGIC = b'\x5a\xa5'
OPCODE_READ = 0x03
OPCODE_WRITE = 0x10

MIN_BODY_LENGTH = 3
MAX_BODY_LENGTH = 253
MAX_READ_WORD_COUNT = 8
ADDRESS_MIN = 0x0000
ADDRESS_MAX = 0xFFFF


class L99CodecError(Exception):
    """Base exception for L99 codec errors."""
    pass


class InvalidMagicError(L99CodecError):
    """Raised when frame magic bytes are invalid."""
    pass


class InvalidLengthError(L99CodecError):
    """Raised when frame length is invalid."""
    pass


class InvalidCRCError(L99CodecError):
    """Raised when CRC validation fails."""
    pass


class TruncatedFrameError(L99CodecError):
    """Raised when frame is truncated."""
    pass


class UnsupportedOpcodeError(L99CodecError):
    """Raised when opcode is not supported."""
    pass


class InvalidAddressError(L99CodecError):
    """Raised when address is out of range."""
    pass


class InvalidWordCountError(L99CodecError):
    """Raised when word count is invalid."""
    pass


class EmptyWritePayloadError(L99CodecError):
    """Raised when write payload is empty."""
    pass


def crc16_modbus(data: bytes) -> int:
    """Compute CRC16/MODBUS (reflected polynomial 0xA001, init 0xFFFF).

    Args:
        data: Input bytes to compute CRC over.

    Returns:
        16-bit CRC value.
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xA001 if crc & 1 else 0)
    return crc & 0xFFFF


def encode_read_frame(word_address: int, word_count: int) -> bytes:
    """Encode a short runtime read frame.

    Args:
        word_address: 16-bit word address (big-endian on wire).
        word_count: Number of words to read (1-8).

    Returns:
        Complete frame bytes including magic, length, body, and CRC.

    Raises:
        InvalidAddressError: If address out of range.
        InvalidWordCountError: If word count out of range.
    """
    if not (ADDRESS_MIN <= word_address <= ADDRESS_MAX):
        raise InvalidAddressError(f'Address 0x{word_address:04X} out of range [0x{ADDRESS_MIN:04X}, 0x{ADDRESS_MAX:04X}]')

    if not (1 <= word_count <= MAX_READ_WORD_COUNT):
        raise InvalidWordCountError(f'Word count {word_count} out of range [1, {MAX_READ_WORD_COUNT}]')

    body = struct.pack('>BHH', OPCODE_READ, word_address, word_count)
    return _encode_frame(body)


def encode_write_frame(word_address: int, words: List[int]) -> bytes:
    """Encode a short runtime write frame.

    Args:
        word_address: 16-bit word address (big-endian on wire).
        words: List of 16-bit words to write (big-endian on wire).

    Returns:
        Complete frame bytes including magic, length, body, and CRC.

    Raises:
        InvalidAddressError: If address out of range.
        EmptyWritePayloadError: If words list is empty.
        InvalidWordCountError: If resulting frame would exceed max length.
    """
    if not (ADDRESS_MIN <= word_address <= ADDRESS_MAX):
        raise InvalidAddressError(f'Address 0x{word_address:04X} out of range [0x{ADDRESS_MIN:04X}, 0x{ADDRESS_MAX:04X}]')

    if not words:
        raise EmptyWritePayloadError('Write payload cannot be empty')

    body = bytearray()
    body.append(OPCODE_WRITE)
    body.extend(struct.pack('>H', word_address))
    for word in words:
        if not (0 <= word <= 0xFFFF):
            raise InvalidWordCountError(f'Word value 0x{word:04X} out of 16-bit range')
        body.extend(struct.pack('>H', word))

    if len(body) > MAX_BODY_LENGTH:
        raise InvalidWordCountError(f'Write frame body length {len(body)} exceeds maximum {MAX_BODY_LENGTH}')

    return _encode_frame(bytes(body))


def _encode_frame(body: bytes) -> bytes:
    """Internal frame encoding with magic, length, and CRC."""
    if not (MIN_BODY_LENGTH <= len(body) <= MAX_BODY_LENGTH):
        raise InvalidLengthError(f'Body length {len(body)} out of range [{MIN_BODY_LENGTH}, {MAX_BODY_LENGTH}]')

    length = len(body) + 2
    crc = crc16_modbus(body)
    return MAGIC + bytes([length]) + body + struct.pack('<H', crc)


def decode_frame(packet: bytes) -> bytes:
    """Decode and validate a short runtime frame.

    Args:
        packet: Complete frame bytes.

    Returns:
        Body bytes (without magic, length, CRC).

    Raises:
        InvalidMagicError: If magic bytes don't match.
        InvalidLengthError: If length field doesn't match packet.
        TruncatedFrameError: If packet too short for claimed length.
        InvalidCRCError: If CRC validation fails.
    """
    if len(packet) < 4:
        raise TruncatedFrameError(f'Packet too short: {len(packet)} bytes, minimum 4')

    if packet[:2] != MAGIC:
        raise InvalidMagicError(f'Invalid magic: {packet[:2].hex()} != 5aa5')

    declared_length = packet[2]
    expected_total = declared_length + 3

    if len(packet) < expected_total:
        raise TruncatedFrameError(f'Truncated: need {expected_total} bytes, got {len(packet)}')

    if len(packet) > expected_total:
        raise InvalidLengthError(f'Extra trailing bytes: expected {expected_total}, got {len(packet)}')

    body = packet[3:-2]
    received_crc = struct.unpack('<H', packet[-2:])[0]
    computed_crc = crc16_modbus(body)

    if received_crc != computed_crc:
        raise InvalidCRCError(f'CRC mismatch: received 0x{received_crc:04X}, computed 0x{computed_crc:04X}')

    return body


def decode_read_body(body: bytes) -> Tuple[int, int]:
    """Decode a read command body.

    Args:
        body: Frame body bytes.

    Returns:
        Tuple of (word_address, word_count).

    Raises:
        UnsupportedOpcodeError: If opcode is not 0x03.
        InvalidWordCountError: If word count out of range.
    """
    if len(body) != 5:
        raise InvalidWordCountError(f'Read body length {len(body)} != 5')

    opcode = body[0]
    if opcode != OPCODE_READ:
        raise UnsupportedOpcodeError(f'Unsupported opcode 0x{opcode:02X} for read')

    word_address = struct.unpack('>H', body[1:3])[0]
    word_count = struct.unpack('>H', body[3:5])[0]

    if not (1 <= word_count <= MAX_READ_WORD_COUNT):
        raise InvalidWordCountError(f'Read word count {word_count} out of range [1, {MAX_READ_WORD_COUNT}]')

    return word_address, word_count


def decode_write_body(body: bytes) -> Tuple[int, List[int]]:
    """Decode a write command body.

    Args:
        body: Frame body bytes.

    Returns:
        Tuple of (word_address, words_list).

    Raises:
        UnsupportedOpcodeError: If opcode is not 0x10.
        EmptyWritePayloadError: If no words in payload.
        InvalidWordCountError: If body length invalid.
    """
    if len(body) < 4:
        raise EmptyWritePayloadError(f'Write body too short: {len(body)} bytes')

    opcode = body[0]
    if opcode != OPCODE_WRITE:
        raise UnsupportedOpcodeError(f'Unsupported opcode 0x{opcode:02X} for write')

    if len(body) < 3:
        raise InvalidWordCountError(f'Write body too short: {len(body)} bytes')

    if (len(body) - 3) % 2 != 0:
        raise InvalidWordCountError(f'Write body payload length {len(body) - 3} not even')

    word_address = struct.unpack('>H', body[1:3])[0]
    words = []
    for i in range(3, len(body), 2):
        words.append(struct.unpack('>H', body[i:i+2])[0])

    if not words:
        raise EmptyWritePayloadError('Write payload contains no words')

    return word_address, words


def round_trip_test_read(word_address: int, word_count: int) -> bool:
    """Test encode/decode round trip for read frame.

    Args:
        word_address: Test address.
        word_count: Test word count.

    Returns:
        True if round trip succeeds.
    """
    encoded = encode_read_frame(word_address, word_count)
    body = decode_frame(encoded)
    decoded_addr, decoded_count = decode_read_body(body)
    return decoded_addr == word_address and decoded_count == word_count


def round_trip_test_write(word_address: int, words: List[int]) -> bool:
    """Test encode/decode round trip for write frame.

    Args:
        word_address: Test address.
        words: Test word values.

    Returns:
        True if round trip succeeds.
    """
    encoded = encode_write_frame(word_address, words)
    body = decode_frame(encoded)
    decoded_addr, decoded_words = decode_write_body(body)
    return decoded_addr == word_address and decoded_words == words


if __name__ == '__main__':
    print('AULA L99 Short Runtime Frame Codec - Offline Tests')
    print('=' * 55)

    # CRC16 test vectors
    assert crc16_modbus(b'123456789') == 0x4B37, 'CRC16 test vector failed'
    assert crc16_modbus(b'') == 0xFFFF, 'CRC16 empty input failed'
    print('CRC16 test vectors: PASS')

    # Valid read frame
    read_frame = encode_read_frame(0x0638, 2)
    body = decode_frame(read_frame)
    addr, count = decode_read_body(body)
    assert addr == 0x0638 and count == 2, 'Read frame decode failed'
    print(f'Valid read frame: {read_frame.hex(" ")}')

    # Valid write frame
    write_frame = encode_write_frame(0x0600, [0x454E, 0x4531])
    body = decode_frame(write_frame)
    addr, words = decode_write_body(body)
    assert addr == 0x0600 and words == [0x454E, 0x4531], 'Write frame decode failed'
    print(f'Valid write frame: {write_frame.hex(" ")}')

    # Round trip tests
    assert round_trip_test_read(0x0600, 1)
    assert round_trip_test_read(0x0638, 2)
    assert round_trip_test_read(0xFFFF, 8)
    assert round_trip_test_write(0x0600, [0x0000])
    assert round_trip_test_write(0x0610, [0x1234, 0x5678, 0x9ABC, 0xDEF0])
    print('Round trip tests: PASS')

    # Error cases
    try:
        decode_frame(b'\x00\x00\x00\x00')
        assert False, 'Should reject invalid magic'
    except InvalidMagicError:
        pass

    try:
        decode_frame(b'\x5a\xa5\x10\x03\x00\x00\x00\x00')
        assert False, 'Should reject invalid length'
    except (InvalidLengthError, TruncatedFrameError):
        pass

    try:
        bad_crc = b'\x5a\xa5\x05\x03\x00\x00\x01\x00\x00'  # length=5 means 5+3=8 bytes total
        decode_frame(bad_crc[:8])  # Truncate to expected length but with wrong CRC
        assert False, 'Should reject invalid CRC'
    except InvalidCRCError:
        pass

    try:
        decode_frame(b'\x5a\xa5')
        assert False, 'Should reject truncated'
    except TruncatedFrameError:
        pass

    try:
        decode_read_body(b'\x99\x00\x00\x00\x01')
        assert False, 'Should reject unsupported opcode'
    except UnsupportedOpcodeError:
        pass

    try:
        encode_write_frame(0x0600, [])
        assert False, 'Should reject empty write'
    except EmptyWritePayloadError:
        pass

    try:
        encode_read_frame(0x0600, 0)
        assert False, 'Should reject zero word count'
    except InvalidWordCountError:
        pass

    try:
        encode_read_frame(0x0600, 9)
        assert False, 'Should reject word count > 8'
    except InvalidWordCountError:
        pass

    try:
        encode_read_frame(0x10000, 1)
        assert False, 'Should reject address > 0xFFFF'
    except InvalidAddressError:
        pass

    print('Error case tests: PASS')
    print('All offline tests passed. No hardware accessed.')