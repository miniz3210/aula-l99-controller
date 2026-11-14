#!/usr/bin/env python3
"""
Tests for AULA L99 Touch Event Normalizer
"""

import csv
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'research'))

from l99_touch_event_normalizer import (
    normalize_touch_event,
    normalize_keyboard_event,
    normalize_unknown_event,
    process_touch_csv,
    process_keyboard_csv,
    normalize_capture,
    TOUCH_STATE_MAP,
)


class TestTouchEventNormalization(unittest.TestCase):
    def setUp(self):
        self.capture_name = 'test_capture'

    def test_touch_press(self):
        row = {
            'frame': '100',
            'time': '1.234567000',
            'device': '13',
            'endpoint': '0x83',
            'prefix': '03 12 01 00 00',
            'state_byte': '1',
            'payload': '031201000001000000000000000000000000000000',
        }
        event = normalize_touch_event(row, self.capture_name)

        self.assertEqual(event['source_capture'], self.capture_name)
        self.assertEqual(event['usb_frame_number'], 100)
        self.assertEqual(event['timestamp'], 1.234567000)
        self.assertEqual(event['device_identity']['capture_local_device_id'], '13')
        self.assertEqual(event['device_identity']['endpoint'], '0x83')
        self.assertEqual(event['event_type'], 'touch')
        self.assertEqual(event['press_release_state'], 'press')
        self.assertEqual(event['known_return_code'], '1')
        self.assertEqual(event['raw_source']['state_byte'], '1')
        self.assertEqual(event['raw_source']['payload'], '031201000001000000000000000000000000000000')
        self.assertIn('source_hash', event)

    def test_touch_release(self):
        row = {
            'frame': '101',
            'time': '1.334567000',
            'device': '13',
            'endpoint': '0x83',
            'prefix': '03 12 01 00 00',
            'state_byte': '0',
            'payload': '031201000000000000000000000000000000000000',
        }
        event = normalize_touch_event(row, self.capture_name)

        self.assertEqual(event['press_release_state'], 'release')
        self.assertEqual(event['known_return_code'], '0')

    def test_unknown_touch_state(self):
        row = {
            'frame': '102',
            'time': '1.434567000',
            'device': '13',
            'endpoint': '0x83',
            'prefix': '03 12 01 00 00',
            'state_byte': '2',
            'payload': '031201000002000000000000000000000000000000',
        }
        event = normalize_touch_event(row, self.capture_name)

        self.assertEqual(event['press_release_state'], 'unknown')
        self.assertEqual(event['known_return_code'], '2')

    def test_keyboard_hid_event(self):
        row = {
            'frame': '200',
            'time': '2.000000000',
            'device': '16',
            'endpoint': '0x81',
            'state': 'press',
            'modifier': '0x00',
            'usage_ids': '0x53',
            'names': 'Num Lock',
            'payload': '0000530000000000',
        }
        event = normalize_keyboard_event(row, self.capture_name)

        self.assertEqual(event['source_capture'], self.capture_name)
        self.assertEqual(event['usb_frame_number'], 200)
        self.assertEqual(event['timestamp'], 2.0)
        self.assertEqual(event['device_identity']['capture_local_device_id'], '16')
        self.assertEqual(event['device_identity']['endpoint'], '0x81')
        self.assertEqual(event['event_type'], 'keyboard_hid')
        self.assertEqual(event['press_release_state'], 'press')
        self.assertIsNotNone(event['known_return_code'])
        self.assertEqual(event['known_return_code']['usage_id'], '0x53')
        self.assertEqual(event['known_return_code']['key_name'], 'Num Lock')
        self.assertEqual(event['raw_source']['state'], 'press')
        self.assertIn('source_hash', event)

    def test_keyboard_release_event(self):
        row = {
            'frame': '201',
            'time': '2.100000000',
            'device': '16',
            'endpoint': '0x81',
            'state': 'release',
            'modifier': '0x00',
            'usage_ids': '',
            'names': '',
            'payload': '0000000000000000',
        }
        event = normalize_keyboard_event(row, self.capture_name)

        self.assertEqual(event['press_release_state'], 'release')
        self.assertIsNone(event['known_return_code'])

    def test_missing_fields(self):
        row = {
            'frame': '300',
            'time': '3.000000000',
        }
        event = normalize_touch_event(row, self.capture_name)

        self.assertEqual(event['usb_frame_number'], 300)
        self.assertEqual(event['timestamp'], 3.0)
        self.assertEqual(event['device_identity']['capture_local_device_id'], '')
        self.assertEqual(event['press_release_state'], 'unknown')
        self.assertIsNone(event['known_return_code'])

    def test_malformed_csv_handling(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            capture_dir = Path(tmpdir) / 'malformed_capture'
            capture_dir.mkdir()

            touch_file = capture_dir / 'touch_reports.csv'
            with touch_file.open('w', newline='') as f:
                f.write('frame,time,device,endpoint,prefix,state_byte,payload\n')
                f.write('not_a_number,1.0,13,0x83,03 12 01 00 00,1,031201000001000000000000000000000000000000\n')

            events = normalize_capture(capture_dir)
            self.assertEqual(len(events), 0)

    def test_empty_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            capture_dir = Path(tmpdir) / 'empty_capture'
            capture_dir.mkdir()

            touch_file = capture_dir / 'touch_reports.csv'
            with touch_file.open('w', newline='') as f:
                f.write('frame,time,device,endpoint,prefix,state_byte,payload\n')

            keyboard_file = capture_dir / 'keyboard_reports.csv'
            with keyboard_file.open('w', newline='') as f:
                f.write('frame,time,device,endpoint,state,modifier,usage_ids,names,payload\n')

            events = normalize_capture(capture_dir)
            self.assertEqual(len(events), 0)

    def test_deterministic_ordering(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            capture_dir = Path(tmpdir) / 'order_capture'
            capture_dir.mkdir()

            touch_file = capture_dir / 'touch_reports.csv'
            with touch_file.open('w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['frame', 'time', 'device', 'endpoint', 'prefix', 'state_byte', 'payload'])
                writer.writerow(['10', '2.0', '13', '0x83', '03 12 01 00 00', '1', 'payload1'])
                writer.writerow(['5', '1.0', '13', '0x83', '03 12 01 00 00', '0', 'payload2'])
                writer.writerow(['10', '1.5', '13', '0x83', '03 12 01 00 00', '1', 'payload3'])

            events = normalize_capture(capture_dir)
            self.assertEqual(len(events), 3)
            self.assertEqual(events[0]['usb_frame_number'], 5)
            self.assertEqual(events[1]['usb_frame_number'], 10)
            self.assertEqual(events[1]['timestamp'], 1.5)
            self.assertEqual(events[2]['usb_frame_number'], 10)
            self.assertEqual(events[2]['timestamp'], 2.0)

    def test_capture_local_device_attribution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            capture_dir = Path(tmpdir) / 'device_capture'
            capture_dir.mkdir()

            touch_file = capture_dir / 'touch_reports.csv'
            with touch_file.open('w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['frame', 'time', 'device', 'endpoint', 'prefix', 'state_byte', 'payload'])
                writer.writerow(['100', '1.0', '13', '0x83', '03 12 01 00 00', '1', 'payload'])

            keyboard_file = capture_dir / 'keyboard_reports.csv'
            with keyboard_file.open('w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['frame', 'time', 'device', 'endpoint', 'state', 'modifier', 'usage_ids', 'names', 'payload'])
                writer.writerow(['200', '2.0', '16', '0x81', 'press', '0x00', '0x53', 'Num Lock', 'payload'])

            events = normalize_capture(capture_dir)
            self.assertEqual(len(events), 2)

            touch_event = next(e for e in events if e['event_type'] == 'touch')
            self.assertEqual(touch_event['device_identity']['capture_local_device_id'], '13')
            self.assertEqual(touch_event['device_identity']['endpoint'], '0x83')

            kb_event = next(e for e in events if e['event_type'] == 'keyboard_hid')
            self.assertEqual(kb_event['device_identity']['capture_local_device_id'], '16')
            self.assertEqual(kb_event['device_identity']['endpoint'], '0x81')

    def test_no_invented_coordinates(self):
        row = {
            'frame': '100',
            'time': '1.0',
            'device': '13',
            'endpoint': '0x83',
            'prefix': '03 12 01 00 00',
            'state_byte': '1',
            'payload': '031201000001000000000000000000000000000000',
        }
        event = normalize_touch_event(row, self.capture_name)

        self.assertNotIn('x', event)
        self.assertNotIn('y', event)
        self.assertNotIn('coordinates', event)
        self.assertNotIn('position', event)
        self.assertEqual(event['raw_source']['payload'], '031201000001000000000000000000000000000000')

    def test_source_record_preservation(self):
        row = {
            'frame': '100',
            'time': '1.234567000',
            'device': '13',
            'endpoint': '0x83',
            'prefix': '03 12 01 00 00',
            'state_byte': '1',
            'payload': '031201000001000000000000000000000000000000',
        }
        event = normalize_touch_event(row, self.capture_name)

        self.assertEqual(event['raw_source']['frame'], '100')
        self.assertEqual(event['raw_source']['time'], '1.234567000')
        self.assertEqual(event['raw_source']['device'], '13')
        self.assertEqual(event['raw_source']['endpoint'], '0x83')
        self.assertEqual(event['raw_source']['prefix'], '03 12 01 00 00')
        self.assertEqual(event['raw_source']['state_byte'], '1')
        self.assertEqual(event['raw_source']['payload'], '031201000001000000000000000000000000000000')

    def test_unknown_report_type(self):
        row = {
            'frame': '400',
            'time': '4.0',
            'device': '14',
            'endpoint': '0x82',
            'extra_field': 'some_value',
        }
        event = normalize_unknown_event(row, self.capture_name, 'other')

        self.assertEqual(event['event_type'], 'unknown')
        self.assertEqual(event['press_release_state'], 'unknown')
        self.assertIsNone(event['known_return_code'])
        self.assertEqual(event['raw_source']['extra_field'], 'some_value')

    def test_deterministic_json_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            capture_dir = Path(tmpdir) / 'json_capture'
            capture_dir.mkdir()

            touch_file = capture_dir / 'touch_reports.csv'
            with touch_file.open('w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['frame', 'time', 'device', 'endpoint', 'prefix', 'state_byte', 'payload'])
                writer.writerow(['100', '1.0', '13', '0x83', '03 12 01 00 00', '1', 'payload1'])

            events1 = normalize_capture(capture_dir)
            events2 = normalize_capture(capture_dir)

            output1 = json.dumps({'events': events1}, separators=(',', ':'), ensure_ascii=False)
            output2 = json.dumps({'events': events2}, separators=(',', ':'), ensure_ascii=False)

            self.assertEqual(output1, output2)

    def test_streaming_processing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            capture_dir = Path(tmpdir) / 'stream_capture'
            capture_dir.mkdir()

            touch_file = capture_dir / 'touch_reports.csv'
            with touch_file.open('w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['frame', 'time', 'device', 'endpoint', 'prefix', 'state_byte', 'payload'])
                for i in range(100):
                    writer.writerow([str(i), f'{i}.0', '13', '0x83', '03 12 01 00 00', '1', f'payload{i}'])

            events = list(process_touch_csv(touch_file, 'stream_capture'))
            self.assertEqual(len(events), 100)

    def test_keyboard_unknown_state(self):
        row = {
            'frame': '200',
            'time': '2.0',
            'device': '16',
            'endpoint': '0x81',
            'state': 'hold',
            'modifier': '0x00',
            'usage_ids': '0x53',
            'names': 'Num Lock',
            'payload': '0000530000000000',
        }
        event = normalize_keyboard_event(row, self.capture_name)

        self.assertEqual(event['press_release_state'], 'unknown')


class TestIntegration(unittest.TestCase):
    def test_real_capture_normalization(self):
        capture_dir = Path(__file__).parent.parent / 'capture_analysis' / 'aula_calculator_all_keys'
        if capture_dir.exists():
            events = normalize_capture(capture_dir)
            self.assertGreater(len(events), 0)

            for event in events:
                self.assertIn('source_capture', event)
                self.assertIn('usb_frame_number', event)
                self.assertIn('timestamp', event)
                self.assertIn('device_identity', event)
                self.assertIn('event_type', event)
                self.assertIn('press_release_state', event)
                self.assertIn('source_hash', event)
                self.assertIn(event['event_type'], ['touch', 'keyboard_hid', 'unknown'])
                self.assertIn(event['press_release_state'], ['press', 'release', 'unknown'])


if __name__ == '__main__':
    unittest.main()