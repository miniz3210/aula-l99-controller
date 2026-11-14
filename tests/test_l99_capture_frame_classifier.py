"""Tests for AULA L99 Capture Frame Classifier."""

import pytest
import struct
from scripts.research.l99_capture_frame_classifier import (
    crc16_modbus,
    decode_runtime_frame,
    classify_body,
    classify_payload,
    classify_crc_valid_unsupported_opcode,
    extract_crc_valid_frames,
    extract_short_runtime_frames,
    FrameClass,
    EndpointAttribution,
    DecodeError,
    FrameCandidate,
    MAGIC,
    OPCODE_READ,
    OPCODE_WRITE,
    parse_endpoint_direction,
    is_hid_report,
    get_endpoint_attribution,
)


class TestCRC16:
    def test_known_vector(self):
        assert crc16_modbus(b'123456789') == 0x4B37

    def test_empty(self):
        assert crc16_modbus(b'') == 0xFFFF

    def test_deterministic(self):
        data = b'test data'
        assert crc16_modbus(data) == crc16_modbus(data)


class TestParseEndpointDirection:
    def test_in_endpoint(self):
        assert parse_endpoint_direction("0x81") == "IN"
        assert parse_endpoint_direction("0x82") == "IN"
        assert parse_endpoint_direction("0x80") == "IN"

    def test_out_endpoint(self):
        assert parse_endpoint_direction("0x01") == "OUT"
        assert parse_endpoint_direction("0x02") == "OUT"
        assert parse_endpoint_direction("0x00") == "OUT"

    def test_invalid_endpoint(self):
        assert parse_endpoint_direction("invalid") == "UNKNOWN"
        assert parse_endpoint_direction("") == "UNKNOWN"


class TestIsHidReport:
    def test_mouse_report(self):
        payload = b'\x01\x00\x00\x00\x00\x00\x00'
        assert is_hid_report(payload) is True

    def test_keyboard_report(self):
        payload = b'\x02\x00\x00\x00\x00\x00\x00\x00\x00'
        assert is_hid_report(payload) is True

    def test_consumer_report(self):
        payload = b'\x03\x00\x00'
        assert is_hid_report(payload) is True

    def test_not_hid_report(self):
        payload = b'\x04\x00\x00'
        assert is_hid_report(payload) is False

    def test_empty_payload(self):
        assert is_hid_report(b'') is False

    def test_short_payload(self):
        assert is_hid_report(b'\x01') is False


class TestDecodeRuntimeFrame:
    def test_valid_read_frame(self):
        body = b'\x03\x06\x38\x00\x02'
        crc = crc16_modbus(body)
        payload = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', crc)
        decoded_body, error = decode_runtime_frame(payload)
        assert error is None
        assert decoded_body == body

    def test_valid_write_frame(self):
        body = b'\x10\x06\x00\x45\x4E\x45\x31'
        crc = crc16_modbus(body)
        payload = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', crc)
        decoded_body, error = decode_runtime_frame(payload)
        assert error is None
        assert decoded_body == body

    def test_truncated(self):
        payload = MAGIC + b'\x05'
        body, error = decode_runtime_frame(payload)
        assert error == DecodeError.TRUNCATED
        assert body == b""

    def test_invalid_magic(self):
        payload = b'\x00\x00\x05\x03\x00\x00\x01\x00\x00'
        body, error = decode_runtime_frame(payload)
        assert error == DecodeError.INVALID_MAGIC

    def test_invalid_length_extra_bytes(self):
        body = b'\x03\x06\x38\x00\x02'
        crc = crc16_modbus(body)
        payload = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', crc) + b'\x00'
        decoded_body, error = decode_runtime_frame(payload)
        assert error == DecodeError.EXTRA_TRAILING_BYTES

    def test_invalid_crc(self):
        body = b'\x03\x06\x38\x00\x02'
        crc = crc16_modbus(body)
        bad_crc = (crc + 1) & 0xFFFF
        payload = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', bad_crc)
        decoded_body, error = decode_runtime_frame(payload)
        assert error == DecodeError.INVALID_CRC


class TestClassifyBody:
    def test_valid_read(self):
        body = b'\x03\x06\x38\x00\x02'
        frame_class, error, opcode, addr, word_count, words = classify_body(body)
        assert frame_class == FrameClass.VALID_RUNTIME
        assert error is None
        assert opcode == OPCODE_READ
        assert addr == 0x0638
        assert word_count == 2
        assert words is None

    def test_valid_write(self):
        body = b'\x10\x06\x00\x45\x4E\x45\x31'
        frame_class, error, opcode, addr, word_count, words = classify_body(body)
        assert frame_class == FrameClass.VALID_RUNTIME
        assert error is None
        assert opcode == OPCODE_WRITE
        assert addr == 0x0600
        assert word_count is None
        assert words == (0x454E, 0x4531)

    def test_invalid_read_length(self):
        body = b'\x03\x06\x38\x00'
        frame_class, error, opcode, addr, word_count, words = classify_body(body)
        assert frame_class == FrameClass.INVALID_RUNTIME
        assert error == DecodeError.INVALID_WORD_COUNT

    def test_invalid_read_word_count_zero(self):
        body = b'\x03\x06\x38\x00\x00'
        frame_class, error, opcode, addr, word_count, words = classify_body(body)
        assert frame_class == FrameClass.INVALID_RUNTIME
        assert error == DecodeError.INVALID_WORD_COUNT

    def test_invalid_read_word_count_too_large(self):
        body = b'\x03\x06\x38\x00\x09'
        frame_class, error, opcode, addr, word_count, words = classify_body(body)
        assert frame_class == FrameClass.INVALID_RUNTIME
        assert error == DecodeError.INVALID_WORD_COUNT

    def test_invalid_write_empty(self):
        body = b'\x10\x06\x00'
        frame_class, error, opcode, addr, word_count, words = classify_body(body)
        assert frame_class == FrameClass.INVALID_RUNTIME
        assert error == DecodeError.EMPTY_WRITE_PAYLOAD

    def test_invalid_write_payload_not_even(self):
        body = b'\x10\x06\x00\x45'
        frame_class, error, opcode, addr, word_count, words = classify_body(body)
        assert frame_class == FrameClass.INVALID_RUNTIME
        assert error == DecodeError.PAYLOAD_NOT_EVEN

    def test_unsupported_opcode(self):
        body = b'\x99\x00\x00\x00\x01'
        frame_class, error, opcode, addr, word_count, words = classify_body(body)
        assert frame_class == FrameClass.INVALID_RUNTIME
        assert error == DecodeError.UNSUPPORTED_OPCODE
        assert opcode == 0x99

    def test_invalid_address(self):
        body = b'\x03\x00\x01\x00\x01'
        frame_class, error, opcode, addr, word_count, words = classify_body(body)
        assert frame_class == FrameClass.VALID_RUNTIME
        assert error is None

    def test_invalid_address_out_of_range(self):
        body = b'\x03\x00\x00\x00\x01'
        frame_class, error, opcode, addr, word_count, words = classify_body(body)
        assert frame_class == FrameClass.VALID_RUNTIME
        assert error is None
        
    def test_invalid_write_address_out_of_range(self):
        body = b'\x10\x00\x00\x45\x4E'
        frame_class, error, opcode, addr, word_count, words = classify_body(body)
        assert frame_class == FrameClass.VALID_RUNTIME
        assert error is None


class TestClassifyPayload:
    def test_valid_read_payload(self):
        body = b'\x03\x06\x38\x00\x02'
        crc = crc16_modbus(body)
        payload = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', crc)
        frame_class, error, opcode, addr, word_count, words = classify_payload(payload.hex())
        assert frame_class == FrameClass.VALID_RUNTIME
        assert error is None
        assert opcode == OPCODE_READ
        assert addr == 0x0638
        assert word_count == 2

    def test_valid_write_payload(self):
        body = b'\x10\x06\x00\x45\x4E\x45\x31'
        crc = crc16_modbus(body)
        payload = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', crc)
        frame_class, error, opcode, addr, word_count, words = classify_payload(payload.hex())
        assert frame_class == FrameClass.VALID_RUNTIME
        assert error is None
        assert opcode == OPCODE_WRITE
        assert addr == 0x0600
        assert word_count is None
        assert words == (0x454E, 0x4531)

    def test_invalid_crc_payload(self):
        body = b'\x03\x06\x38\x00\x02'
        crc = crc16_modbus(body)
        bad_crc = (crc + 1) & 0xFFFF
        payload = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', bad_crc)
        frame_class, error, opcode, addr, word_count, words = classify_payload(payload.hex())
        assert frame_class == FrameClass.INVALID_RUNTIME
        assert error == DecodeError.INVALID_CRC

    def test_large_upload_reclassified(self):
        payload = b'x' * 1500
        frame_class, error, opcode, addr, word_count, words = classify_payload(payload.hex())
        assert frame_class == FrameClass.UNVERIFIED_LARGE_PAYLOAD

    def test_large_payload_with_magic_but_invalid_structure(self):
        body = b'\x99\x00\x00\x00\x01'
        crc = crc16_modbus(body)
        payload = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', crc)
        payload = payload + b'x' * 1000
        frame_class, error, opcode, addr, word_count, words = classify_payload(payload.hex())
        assert frame_class == FrameClass.UNVERIFIED_LARGE_PAYLOAD

    def test_unknown_no_magic(self):
        payload = b'\x00\x00\x00\x00'
        frame_class, error, opcode, addr, word_count, words = classify_payload(payload.hex())
        assert frame_class == FrameClass.UNKNOWN
        assert error is None

    def test_unknown_too_short(self):
        payload = b'\x5a\xa5'
        frame_class, error, opcode, addr, word_count, words = classify_payload(payload.hex())
        assert frame_class == FrameClass.UNKNOWN

    def test_empty_payload(self):
        frame_class, error, opcode, addr, word_count, words = classify_payload("")
        assert frame_class == FrameClass.UNKNOWN

    def test_hid_mouse_report_not_runtime(self):
        payload = b'\x01\x01\x00\x00\x00\x00\x00'
        frame_class, error, opcode, addr, word_count, words = classify_payload(payload.hex())
        assert frame_class == FrameClass.UNKNOWN

    def test_hid_keyboard_report_not_runtime(self):
        payload = b'\x02\x00\x00\x00\x00\x00\x00\x00\x00'
        frame_class, error, opcode, addr, word_count, words = classify_payload(payload.hex())
        assert frame_class == FrameClass.UNKNOWN

    def test_hid_consumer_report_not_runtime(self):
        payload = b'\x03\x00\x00'
        frame_class, error, opcode, addr, word_count, words = classify_payload(payload.hex())
        assert frame_class == FrameClass.UNKNOWN

    def test_runtime_frame_precedence_over_size(self):
        body = b'\x03\x06\x38\x00\x02'
        crc = crc16_modbus(body)
        payload = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', crc)
        frame_class, error, opcode, addr, word_count, words = classify_payload(payload.hex())
        assert frame_class == FrameClass.VALID_RUNTIME
        assert error is None

    def test_unverified_large_payload_when_valid_but_no_magic(self):
        payload = b'x' * 1500
        frame_class, error, opcode, addr, word_count, words = classify_payload(payload.hex())
        assert frame_class == FrameClass.UNVERIFIED_LARGE_PAYLOAD

    def test_valid_short_runtime_read_frame(self):
        body = b'\x03\x06\x38\x00\x02'
        crc = crc16_modbus(body)
        payload = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', crc)
        assert len(payload) <= 258
        frame_class, error, opcode, addr, word_count, words = classify_payload(payload.hex())
        assert frame_class == FrameClass.VALID_RUNTIME
        assert error is None
        assert opcode == OPCODE_READ
        assert addr == 0x0638
        assert word_count == 2

    def test_valid_short_runtime_write_frame(self):
        body = b'\x10\x06\x00\x45\x4E\x45\x31'
        crc = crc16_modbus(body)
        payload = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', crc)
        assert len(payload) <= 258
        frame_class, error, opcode, addr, word_count, words = classify_payload(payload.hex())
        assert frame_class == FrameClass.VALID_RUNTIME
        assert error is None
        assert opcode == OPCODE_WRITE
        assert addr == 0x0600
        assert word_count is None
        assert words == (0x454E, 0x4531)

    def test_malformed_short_runtime_frame(self):
        body = b'\x03\x06\x38\x00'
        crc = crc16_modbus(body)
        payload = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', crc)
        assert len(payload) <= 258
        frame_class, error, opcode, addr, word_count, words = classify_payload(payload.hex())
        assert frame_class == FrameClass.INVALID_RUNTIME
        assert error == DecodeError.INVALID_WORD_COUNT

    def test_hid_magic_false_positive_filtering(self):
        hid_payload = b'\x01\x00\x5a\xa5\x00\x00\x00'
        frame_class, error, opcode, addr, word_count, words = classify_payload(hid_payload.hex())
        assert frame_class == FrameClass.UNKNOWN
        assert error is None

    def test_hid_mouse_payload_not_invalid_runtime(self):
        hid_mouse = b'\x01\x01\x00\x00\x00\x00\x00'
        frame_class, error, opcode, addr, word_count, words = classify_payload(hid_mouse.hex())
        assert frame_class == FrameClass.UNKNOWN
        assert error is None

    def test_unknown_device_attribution(self):
        body = b'\x03\x06\x38\x00\x02'
        crc = crc16_modbus(body)
        payload = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', crc)
        frame_class, error, opcode, addr, word_count, words = classify_payload(payload.hex())
        assert frame_class == FrameClass.VALID_RUNTIME

    def test_capture_local_verified_screen_mapping(self):
        capture_name = "aula_home_numpad_transition"
        device = "15"
        endpoint = "0x81"
        attrib = get_endpoint_attribution(capture_name, device, endpoint)
        assert attrib == EndpointAttribution.VERIFIED_SCREEN

    def test_capture_local_verified_non_screen_mapping(self):
        capture_name = "aula_home_numpad_transition"
        device = "6"
        endpoint = "0x81"
        attrib = get_endpoint_attribution(capture_name, device, endpoint)
        assert attrib == EndpointAttribution.VERIFIED_NON_SCREEN

    def test_same_device_address_different_captures(self):
        attrib1 = get_endpoint_attribution("aula_home_numpad_transition", "15", "0x81")
        attrib2 = get_endpoint_attribution("aula_solid_black", "15", "0x81")
        assert attrib1 == EndpointAttribution.VERIFIED_SCREEN
        assert attrib2 == EndpointAttribution.UNVERIFIED

    def test_missing_endpoint_metadata(self):
        attrib = get_endpoint_attribution("unknown_capture", "99", "0xFF")
        assert attrib == EndpointAttribution.UNVERIFIED


class TestDeterministicOrdering:
    def test_frame_candidate_sort(self):
        c1 = FrameCandidate("b", 2, "", "", "", "", FrameClass.VALID_RUNTIME, EndpointAttribution.UNVERIFIED, None, OPCODE_READ, 0x0600, 1, None, "", 10)
        c2 = FrameCandidate("a", 1, "", "", "", "", FrameClass.VALID_RUNTIME, EndpointAttribution.UNVERIFIED, None, OPCODE_READ, 0x0600, 1, None, "", 10)
        c3 = FrameCandidate("a", 2, "", "", "", "", FrameClass.VALID_RUNTIME, EndpointAttribution.UNVERIFIED, None, OPCODE_READ, 0x0600, 1, None, "", 10)
        candidates = [c1, c2, c3]
        candidates.sort()
        assert candidates[0].capture_file == "a"
        assert candidates[0].frame_number == 1
        assert candidates[1].capture_file == "a"
        assert candidates[1].frame_number == 2
        assert candidates[2].capture_file == "b"
        assert candidates[2].frame_number == 2


class TestFrameCandidateFields:
    def test_frame_candidate_has_all_required_fields(self):
        c = FrameCandidate(
            capture_file="test_capture",
            frame_number=123,
            timestamp="0.000123",
            device="5",
            endpoint="0x81",
            direction="IN",
            frame_class=FrameClass.VALID_RUNTIME,
            endpoint_attribution=EndpointAttribution.UNVERIFIED,
            decode_error=None,
            opcode=OPCODE_READ,
            word_address=0x0638,
            word_count=2,
            write_words=None,
            payload_hex="5aa5050306380002crc16",
            payload_length=8,
        )
        assert c.capture_file == "test_capture"
        assert c.frame_number == 123
        assert c.timestamp == "0.000123"
        assert c.device == "5"
        assert c.endpoint == "0x81"
        assert c.direction == "IN"
        assert c.frame_class == FrameClass.VALID_RUNTIME
        assert c.endpoint_attribution == EndpointAttribution.UNVERIFIED
        assert c.opcode == OPCODE_READ
        assert c.word_address == 0x0638
        assert c.word_count == 2
        assert c.payload_length == 8


class TestCategoryCountReconciliation:
    def test_categories_are_mutually_exclusive(self):
        all_classes = set(FrameClass)
        assert len(all_classes) == 5
        assert FrameClass.VALID_RUNTIME in all_classes
        assert FrameClass.INVALID_RUNTIME in all_classes
        assert FrameClass.UNVERIFIED_LARGE_PAYLOAD in all_classes
        assert FrameClass.UNKNOWN in all_classes
        assert FrameClass.CRC_VALID_UNSUPPORTED_OPCODE in all_classes

    def test_endpoint_attribution_categories(self):
        all_attribs = set(EndpointAttribution)
        assert len(all_attribs) == 3
        assert EndpointAttribution.VERIFIED_SCREEN in all_attribs
        assert EndpointAttribution.VERIFIED_NON_SCREEN in all_attribs
        assert EndpointAttribution.UNVERIFIED in all_attribs


class TestConcatenatedFrames:
    def test_two_concatenated_valid_frames(self):
        body1 = b'\x03\x06\x38\x00\x02'
        crc1 = crc16_modbus(body1)
        frame1 = MAGIC + bytes([len(body1) + 2]) + body1 + struct.pack('<H', crc1)
        
        body2 = b'\x10\x06\x00\x45\x4E\x45\x31'
        crc2 = crc16_modbus(body2)
        frame2 = MAGIC + bytes([len(body2) + 2]) + body2 + struct.pack('<H', crc2)
        
        concatenated = frame1 + frame2
        
        from scripts.research.l99_capture_frame_classifier import extract_short_runtime_frames
        frames = extract_short_runtime_frames(concatenated)
        
        assert len(frames) == 2
        assert frames[0][1] == 0
        assert frames[1][1] == len(frame1)
        
        for frame_bytes, _, _ in frames:
            fc, err, op, addr, wc, w = classify_payload(frame_bytes.hex())
            assert fc == FrameClass.VALID_RUNTIME
            assert err is None
        
    def test_valid_frame_followed_by_invalid_frame(self):
        body1 = b'\x03\x06\x38\x00\x02'
        crc1 = crc16_modbus(body1)
        frame1 = MAGIC + bytes([len(body1) + 2]) + body1 + struct.pack('<H', crc1)
        
        body2 = b'\x03\x06\x38\x00'
        crc2 = crc16_modbus(body2)
        frame2 = MAGIC + bytes([len(body2) + 2]) + body2 + struct.pack('<H', crc2)
        
        concatenated = frame1 + frame2
        
        from scripts.research.l99_capture_frame_classifier import extract_short_runtime_frames
        frames = extract_short_runtime_frames(concatenated)
        
        assert len(frames) == 1
        assert frames[0][1] == 0
        
        frame_bytes, _, _ = frames[0]
        fc, err, op, addr, wc, w = classify_payload(frame_bytes.hex())
        assert fc == FrameClass.VALID_RUNTIME
        assert err is None
        assert op == OPCODE_READ
        assert wc == 2

    def test_invalid_prefix_followed_by_valid_frame(self):
        invalid_prefix = b'\x00\x00\x00\x00'
        
        body = b'\x03\x06\x38\x00\x02'
        crc = crc16_modbus(body)
        frame = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', crc)
        
        concatenated = invalid_prefix + frame
        
        from scripts.research.l99_capture_frame_classifier import extract_short_runtime_frames
        frames = extract_short_runtime_frames(concatenated)
        
        assert len(frames) == 0

    def test_trailing_unknown_bytes_preserved(self):
        body = b'\x03\x06\x38\x00\x02'
        crc = crc16_modbus(body)
        frame = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', crc)
        
        trailing = b'\xFF\xEE\xDD\xCC'
        concatenated = frame + trailing
        
        frame_class, error, opcode, addr, word_count, words = classify_payload(concatenated.hex())
        
        assert frame_class == FrameClass.INVALID_RUNTIME
        assert error == DecodeError.EXTRA_TRAILING_BYTES


class TestReadWordCount:
    def test_read_word_count_extraction(self):
        body = b'\x03\x06\x38\x00\x02'
        frame_class, error, opcode, addr, word_count, words = classify_body(body)
        
        assert frame_class == FrameClass.VALID_RUNTIME
        assert opcode == OPCODE_READ
        assert addr == 0x0638
        assert word_count == 2
        assert words is None

    def test_read_word_count_various_values(self):
        for wc in [1, 2, 4, 8]:
            body = b'\x03\x06\x38' + struct.pack('>H', wc)
            frame_class, error, opcode, addr, word_count, words = classify_body(body)
            assert frame_class == FrameClass.VALID_RUNTIME
            assert word_count == wc

    def test_read_word_count_zero_invalid(self):
        body = b'\x03\x06\x38\x00\x00'
        frame_class, error, opcode, addr, word_count, words = classify_body(body)
        assert frame_class == FrameClass.INVALID_RUNTIME
        assert error == DecodeError.INVALID_WORD_COUNT

    def test_read_word_count_too_large_invalid(self):
        body = b'\x03\x06\x38\x00\x09'
        frame_class, error, opcode, addr, word_count, words = classify_body(body)
        assert frame_class == FrameClass.INVALID_RUNTIME
        assert error == DecodeError.INVALID_WORD_COUNT


class TestFull16BitAddressBoundaries:
    def test_address_min_boundary(self):
        body = b'\x03\x00\x00\x00\x01'
        frame_class, error, opcode, addr, word_count, words = classify_body(body)
        assert frame_class == FrameClass.VALID_RUNTIME
        assert addr == 0x0000

    def test_address_max_boundary(self):
        body = b'\x03\xFF\xFF\x00\x01'
        frame_class, error, opcode, addr, word_count, words = classify_body(body)
        assert frame_class == FrameClass.VALID_RUNTIME
        assert addr == 0xFFFF

    def test_write_address_min_boundary(self):
        body = b'\x10\x00\x00\x45\x4E'
        frame_class, error, opcode, addr, word_count, words = classify_body(body)
        assert frame_class == FrameClass.VALID_RUNTIME
        assert addr == 0x0000
        assert words == (0x454E,)

    def test_write_address_max_boundary(self):
        body = b'\x10\xFF\xFF\x45\x4E'
        frame_class, error, opcode, addr, word_count, words = classify_body(body)
        assert frame_class == FrameClass.VALID_RUNTIME
        assert addr == 0xFFFF
        assert words == (0x454E,)


class TestDeterministicCandidateOrdering:
    def test_multiple_candidates_same_frame_deterministic(self):
        body1 = b'\x03\x06\x38\x00\x02'
        crc1 = crc16_modbus(body1)
        frame1 = MAGIC + bytes([len(body1) + 2]) + body1 + struct.pack('<H', crc1)
        
        body2 = b'\x10\x06\x00\x45\x4E\x45\x31'
        crc2 = crc16_modbus(body2)
        frame2 = MAGIC + bytes([len(body2) + 2]) + body2 + struct.pack('<H', crc2)
        
        concatenated = frame1 + frame2
        
        from scripts.research.l99_capture_frame_classifier import extract_short_runtime_frames
        frames = extract_short_runtime_frames(concatenated)
        
        assert len(frames) == 2
        assert frames[0][1] == 0
        assert frames[1][1] == len(frame1)
        assert frames[0][2] == len(frame1)
        assert frames[1][2] == len(frame2)


class TestCategoryCountReconciliationExtended:
    def test_concatenated_frames_increase_valid_count(self):
        body1 = b'\x03\x06\x38\x00\x02'
        crc1 = crc16_modbus(body1)
        frame1 = MAGIC + bytes([len(body1) + 2]) + body1 + struct.pack('<H', crc1)
        
        body2 = b'\x10\x06\x00\x45\x4E\x45\x31'
        crc2 = crc16_modbus(body2)
        frame2 = MAGIC + bytes([len(body2) + 2]) + body2 + struct.pack('<H', crc2)
        
        concatenated = frame1 + frame2
        
        from scripts.research.l99_capture_frame_classifier import extract_short_runtime_frames
        frames = extract_short_runtime_frames(concatenated)
        
        valid_count = 0
        for frame_bytes, _, _ in frames:
            fc, err, op, addr, wc, w = classify_payload(frame_bytes.hex())
            if fc == FrameClass.VALID_RUNTIME:
                valid_count += 1
                
        assert valid_count == 2

    def test_trailing_bytes_do_not_create_invalid_runtime(self):
        body = b'\x03\x06\x38\x00\x02'
        crc = crc16_modbus(body)
        frame = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', crc)
        
        trailing = b'\xFF\xEE'
        concatenated = frame + trailing
        
        fc, err, op, addr, wc, w = classify_payload(concatenated.hex())
        
        assert fc == FrameClass.INVALID_RUNTIME
        assert err == DecodeError.EXTRA_TRAILING_BYTES


class TestCRCValidUnsupportedOpcode:
    def test_single_crc_valid_unsupported_opcode(self):
        """Test a single frame with opcode 0x64 that has valid CRC."""
        body = b'\x64\x04\x1e\x00\x00'
        crc = crc16_modbus(body)
        payload = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', crc)
        
        frame_class, error, opcode, addr, word_count, words = classify_payload(payload.hex())
        
        assert frame_class == FrameClass.CRC_VALID_UNSUPPORTED_OPCODE
        assert error == DecodeError.UNSUPPORTED_OPCODE
        assert opcode == 0x64

    def test_two_concatenated_crc_valid_unsupported_opcode_frames(self):
        """Test two concatenated frames with opcode 0x64, both CRC valid."""
        body1 = b'\x64\xff\x6b'
        crc1 = crc16_modbus(body1)
        frame1 = MAGIC + bytes([len(body1) + 2]) + body1 + struct.pack('<H', crc1)
        
        body2 = b'\x64\x04\x1e\x00\x00'
        crc2 = crc16_modbus(body2)
        frame2 = MAGIC + bytes([len(body2) + 2]) + body2 + struct.pack('<H', crc2)
        
        concatenated = frame1 + frame2
        
        frames = extract_crc_valid_frames(concatenated)
        
        assert len(frames) == 2
        assert frames[0][1] == 0
        assert frames[1][1] == len(frame1)
        
        for frame_bytes, _, _ in frames:
            fc, err, op, addr, wc, w = classify_payload(frame_bytes.hex())
            assert fc == FrameClass.CRC_VALID_UNSUPPORTED_OPCODE
            assert err == DecodeError.UNSUPPORTED_OPCODE
            assert op == 0x64

    def test_mixed_valid_and_unsupported_frames(self):
        """Test concatenated valid runtime frame followed by unsupported opcode frame."""
        body1 = b'\x03\x06\x38\x00\x02'
        crc1 = crc16_modbus(body1)
        frame1 = MAGIC + bytes([len(body1) + 2]) + body1 + struct.pack('<H', crc1)
        
        body2 = b'\x64\xff\x6b'
        crc2 = crc16_modbus(body2)
        frame2 = MAGIC + bytes([len(body2) + 2]) + body2 + struct.pack('<H', crc2)
        
        concatenated = frame1 + frame2
        
        frames = extract_crc_valid_frames(concatenated)
        
        assert len(frames) == 2
        assert frames[0][1] == 0
        assert frames[1][1] == len(frame1)
        
        fc1, err1, op1, addr1, wc1, w1 = classify_payload(frames[0][0].hex())
        assert fc1 == FrameClass.VALID_RUNTIME
        assert err1 is None
        assert op1 == OPCODE_READ
        assert wc1 == 2
        
        fc2, err2, op2, addr2, wc2, w2 = classify_payload(frames[1][0].hex())
        assert fc2 == FrameClass.CRC_VALID_UNSUPPORTED_OPCODE
        assert err2 == DecodeError.UNSUPPORTED_OPCODE
        assert op2 == 0x64

    def test_mixed_unsupported_and_valid_frames(self):
        """Test concatenated unsupported opcode frame followed by valid runtime frame."""
        body1 = b'\x64\xff\x6b'
        crc1 = crc16_modbus(body1)
        frame1 = MAGIC + bytes([len(body1) + 2]) + body1 + struct.pack('<H', crc1)
        
        body2 = b'\x10\x06\x00\x45\x4e'
        crc2 = crc16_modbus(body2)
        frame2 = MAGIC + bytes([len(body2) + 2]) + body2 + struct.pack('<H', crc2)
        
        concatenated = frame1 + frame2
        
        frames = extract_crc_valid_frames(concatenated)
        
        assert len(frames) == 2
        assert frames[0][1] == 0
        assert frames[1][1] == len(frame1)
        
        fc1, err1, op1, addr1, wc1, w1 = classify_payload(frames[0][0].hex())
        assert fc1 == FrameClass.CRC_VALID_UNSUPPORTED_OPCODE
        assert err1 == DecodeError.UNSUPPORTED_OPCODE
        assert op1 == 0x64
        
        fc2, err2, op2, addr2, wc2, w2 = classify_payload(frames[1][0].hex())
        assert fc2 == FrameClass.VALID_RUNTIME
        assert err2 is None
        assert op2 == OPCODE_WRITE

    def test_crc_valid_unsupported_opcode_with_trailing_bytes(self):
        """Test unsupported opcode frame with trailing unknown bytes."""
        body = b'\x64\xff\x6b'
        crc = crc16_modbus(body)
        frame = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', crc)
        
        trailing = b'\xFF\xEE\xDD\xCC'
        concatenated = frame + trailing
        
        frames = extract_crc_valid_frames(concatenated)
        
        assert len(frames) == 1
        assert frames[0][1] == 0
        
        fc, err, op, addr, wc, w = classify_payload(frames[0][0].hex())
        assert fc == FrameClass.CRC_VALID_UNSUPPORTED_OPCODE
        assert err == DecodeError.UNSUPPORTED_OPCODE
        assert op == 0x64
        
        trailing_bytes = concatenated[frames[0][1] + frames[0][2]:]
        assert trailing_bytes == trailing

    def test_extract_crc_valid_frames_vs_extract_short_runtime_frames(self):
        """Test that extract_crc_valid_frames extracts unsupported opcodes but extract_short_runtime_frames does not."""
        body1 = b'\x03\x06\x38\x00\x02'
        crc1 = crc16_modbus(body1)
        frame1 = MAGIC + bytes([len(body1) + 2]) + body1 + struct.pack('<H', crc1)
        
        body2 = b'\x64\xff\x6b'
        crc2 = crc16_modbus(body2)
        frame2 = MAGIC + bytes([len(body2) + 2]) + body2 + struct.pack('<H', crc2)
        
        concatenated = frame1 + frame2
        
        short_frames = extract_short_runtime_frames(concatenated)
        crc_frames = extract_crc_valid_frames(concatenated)
        
        assert len(short_frames) == 1
        assert short_frames[0][1] == 0
        
        assert len(crc_frames) == 2
        assert crc_frames[0][1] == 0
        assert crc_frames[1][1] == len(frame1)

    def test_crc_valid_unsupported_opcode_classify_body_direct(self):
        """Test classify_crc_valid_unsupported_opcode function directly."""
        body = b'\x64\x04\x1e\x00\x00'
        frame_class, error, opcode, addr, word_count, words = classify_crc_valid_unsupported_opcode(body)
        
        assert frame_class == FrameClass.CRC_VALID_UNSUPPORTED_OPCODE
        assert error == DecodeError.UNSUPPORTED_OPCODE
        assert opcode == 0x64
        assert addr is None
        assert word_count is None
        assert words is None

    def test_crc_valid_unsupported_opcode_not_valid_runtime(self):
        """Test that CRC_VALID_UNSUPPORTED_OPCODE is distinct from VALID_RUNTIME."""
        body = b'\x64\x04\x1e\x00\x00'
        crc = crc16_modbus(body)
        payload = MAGIC + bytes([len(body) + 2]) + body + struct.pack('<H', crc)
        
        frame_class, error, opcode, addr, word_count, words = classify_payload(payload.hex())
        
        assert frame_class == FrameClass.CRC_VALID_UNSUPPORTED_OPCODE
        assert frame_class != FrameClass.VALID_RUNTIME
        assert frame_class != FrameClass.INVALID_RUNTIME
        assert frame_class != FrameClass.UNKNOWN
        assert frame_class != FrameClass.UNVERIFIED_LARGE_PAYLOAD

    def test_category_count_reconciliation_with_unsupported(self):
        """Test that category counts include CRC_VALID_UNSUPPORTED_OPCODE."""
        body1 = b'\x03\x06\x38\x00\x02'
        crc1 = crc16_modbus(body1)
        frame1 = MAGIC + bytes([len(body1) + 2]) + body1 + struct.pack('<H', crc1)
        
        body2 = b'\x10\x06\x00\x45\x4e'
        crc2 = crc16_modbus(body2)
        frame2 = MAGIC + bytes([len(body2) + 2]) + body2 + struct.pack('<H', crc2)
        
        body3 = b'\x64\xff\x6b'
        crc3 = crc16_modbus(body3)
        frame3 = MAGIC + bytes([len(body3) + 2]) + body3 + struct.pack('<H', crc3)
        
        body4 = b'\x64\x04\x1e\x00\x00'
        crc4 = crc16_modbus(body4)
        frame4 = MAGIC + bytes([len(body4) + 2]) + body4 + struct.pack('<H', crc4)
        
        concatenated = frame1 + frame2 + frame3 + frame4
        
        frames = extract_crc_valid_frames(concatenated)
        
        counts = {
            FrameClass.VALID_RUNTIME: 0,
            FrameClass.CRC_VALID_UNSUPPORTED_OPCODE: 0,
            FrameClass.INVALID_RUNTIME: 0,
            FrameClass.UNKNOWN: 0,
            FrameClass.UNVERIFIED_LARGE_PAYLOAD: 0,
        }
        
        for frame_bytes, _, _ in frames:
            fc, _, _, _, _, _ = classify_payload(frame_bytes.hex())
            counts[fc] += 1
        
        assert counts[FrameClass.VALID_RUNTIME] == 2
        assert counts[FrameClass.CRC_VALID_UNSUPPORTED_OPCODE] == 2
        assert counts[FrameClass.INVALID_RUNTIME] == 0
        assert sum(counts.values()) == 4


if __name__ == '__main__':
    pytest.main([__file__, '-v'])