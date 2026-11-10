#!/usr/bin/env python3
"""Deterministic unit tests for the AULA L99 bridge state machine.

All time is mocked; no real sleeps, no Windows hardware, no Raw Input.
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from aula_bridge.state_machine import (
    KeyStateMachine,
    KeyEvent,
    PressResult,
    STATE_IDLE,
    STATE_PRESSED,
    STATE_DEAD_ZONE,
    STATE_HELD,
    ACTION_SHORT_PRESS,
    ACTION_HOLD,
    ACTION_NONE,
    ACTION_REPEAT_IGNORED,
)
from aula_bridge.provider import DryRunProvider, ProviderEvent
from aula_bridge.keymap import LogicalKeyMap, RETURN_VALUE_TO_KEY, SCREEN_MAKE_CODE_TO_KEY


class StateMachineTests(unittest.TestCase):
    def test_short_press_100ms(self):
        m = KeyStateMachine(now_ms=0)
        m.key_down("numpad_1", "0C45:800A", 0)
        m.set_time(100)
        results = m.key_up("numpad_1", "0C45:800A", 100)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, ACTION_SHORT_PRESS)
        self.assertEqual(results[0].duration_ms, 100)

    def test_short_press_499ms(self):
        m = KeyStateMachine(now_ms=0)
        m.key_down("numpad_1", "0C45:800A", 0)
        m.set_time(499)
        results = m.key_up("numpad_1", "0C45:800A", 499)
        self.assertEqual(results[0].action, ACTION_SHORT_PRESS)
        self.assertEqual(results[0].duration_ms, 499)

    def test_dead_zone_500ms(self):
        m = KeyStateMachine(now_ms=0)
        m.key_down("numpad_1", "0C45:800A", 0)
        m.set_time(500)
        results = m.key_up("numpad_1", "0C45:800A", 500)
        self.assertEqual(results[0].action, ACTION_NONE)

    def test_dead_zone_699ms(self):
        m = KeyStateMachine(now_ms=0)
        m.key_down("numpad_1", "0C45:800A", 0)
        m.set_time(699)
        results = m.key_up("numpad_1", "0C45:800A", 699)
        self.assertEqual(results[0].action, ACTION_NONE)

    def test_hold_fires_exactly_once_at_700ms(self):
        m = KeyStateMachine(now_ms=0)
        m.key_down("numpad_1", "0C45:800A", 0)
        m.set_time(700)
        results = m.tick(700)
        holds = [r for r in results if r.action == ACTION_HOLD]
        self.assertEqual(len(holds), 1)
        self.assertEqual(holds[0].duration_ms, 700)
        # A second tick must not emit another hold.
        m.set_time(800)
        results2 = m.tick(800)
        self.assertEqual([r for r in results2 if r.action == ACTION_HOLD], [])

    def test_key_up_after_hold_no_short(self):
        m = KeyStateMachine(now_ms=0)
        m.key_down("numpad_1", "0C45:800A", 0)
        m.set_time(700)
        m.tick(700)  # emit hold
        m.set_time(800)
        results = m.key_up("numpad_1", "0C45:800A", 800)
        self.assertEqual(results[0].action, ACTION_NONE)

    def test_repeated_key_down_ignored(self):
        m = KeyStateMachine(now_ms=0)
        m.key_down("numpad_1", "0C45:800A", 0)
        m.set_time(100)
        results = m.key_down("numpad_1", "0C45:800A", 100)
        self.assertEqual(results[0].action, ACTION_REPEAT_IGNORED)

    def test_missing_key_up_timeout_recovery(self):
        m = KeyStateMachine(now_ms=0, stuck_key_timeout_ms=1000)
        m.key_down("numpad_1", "0C45:800A", 0)
        m.set_time(1500)
        results = m.tick(1500)
        # After timeout, key returns to IDLE; subsequent key_up is a no-op.
        self.assertFalse(m.is_pressed("numpad_1"))
        results2 = m.key_up("numpad_1", "0C45:800A", 1600)
        self.assertEqual(results2[0].action, ACTION_NONE)

    def test_two_keys_held_simultaneously(self):
        m = KeyStateMachine(now_ms=0)
        m.key_down("numpad_1", "0C45:800A", 0)
        m.key_down("numpad_2", "0C45:800A", 50)
        self.assertTrue(m.is_pressed("numpad_1"))
        self.assertTrue(m.is_pressed("numpad_2"))
        m.set_time(700)
        results = m.tick(700)
        holds = [r for r in results if r.action == ACTION_HOLD]
        self.assertEqual(len(holds), 1)
        self.assertEqual(holds[0].key, "numpad_1")
        # numpad_2 still pressed, no hold yet.
        self.assertTrue(m.is_pressed("numpad_2"))

    def test_secondary_hold_disabled(self):
        m = KeyStateMachine(now_ms=0, secondary_hold_enabled=False)
        m.key_down("numpad_1", "0C45:800A", 0)
        m.set_time(2500)
        results = m.tick(2500)
        self.assertEqual([r for r in results if r.action == "secondary_hold"], [])
        self.assertTrue(m.is_pressed("numpad_1"))

    def test_secondary_hold_enabled_at_2000ms(self):
        m = KeyStateMachine(now_ms=0, secondary_hold_enabled=True, secondary_hold_ms=2000)
        m.key_down("numpad_1", "0C45:800A", 0)
        m.set_time(700)
        m.tick(700)  # primary hold
        m.set_time(2000)
        results = m.tick(2000)
        secondary = [r for r in results if r.action == "secondary_hold"]
        self.assertEqual(len(secondary), 1)
        self.assertEqual(secondary[0].duration_ms, 2000)

    def test_non_target_device_ignored(self):
        # The state machine itself is device-agnostic; device filtering happens
        # in the Raw Input layer. Verify two keys on different devices are
        # tracked independently.
        m = KeyStateMachine(now_ms=0)
        m.key_down("numpad_1", "0C45:800A", 0)
        m.key_down("numpad_2", "0000:0000", 0)
        self.assertTrue(m.is_pressed("numpad_1"))
        self.assertTrue(m.is_pressed("numpad_2"))

    def test_restart_begins_with_no_pressed_keys(self):
        m = KeyStateMachine(now_ms=0)
        m.key_down("numpad_1", "0C45:800A", 0)
        m.set_time(100)
        m.key_up("numpad_1", "0C45:800A", 100)
        m.reset()
        self.assertFalse(m.is_pressed("numpad_1"))


class LogicalKeyMapTests(unittest.TestCase):
    def setUp(self):
        self.keymap = LogicalKeyMap()

    def test_physical_return_values_map_to_17_logical_keys(self):
        self.assertEqual(len(self.keymap.all_keys()), 17)
        self.assertEqual(len(RETURN_VALUE_TO_KEY), 17)

    def test_home_absent_from_pc_map(self):
        self.assertNotIn("home", self.keymap.all_keys())
        self.assertNotIn(0x0020, RETURN_VALUE_TO_KEY)
        self.assertIsNone(self.keymap.key_for_return_value(0x0020))

    def test_screen_num1_vkey_97_and_35_map_identically(self):
        # Num Lock ON (VKey 97) and OFF (VKey 35), same make_code 79.
        self.assertEqual(
            self.keymap.key_for_make_code(79, flags=0, vkey=97),
            "numpad_1",
        )
        self.assertEqual(
            self.keymap.key_for_make_code(79, flags=0, vkey=35),
            "numpad_1",
        )
        self.assertEqual(
            self.keymap.key_for_make_code(79, flags=0, vkey=97),
            self.keymap.key_for_make_code(79, flags=0, vkey=35),
        )

    def test_screen_num2_vkey_98_and_40_map_identically(self):
        # Num Lock ON (VKey 98) and OFF (VKey 40), same make_code 80.
        self.assertEqual(
            self.keymap.key_for_make_code(80, flags=0, vkey=98),
            "numpad_2",
        )
        self.assertEqual(
            self.keymap.key_for_make_code(80, flags=0, vkey=40),
            "numpad_2",
        )
        self.assertEqual(
            self.keymap.key_for_make_code(80, flags=0, vkey=98),
            self.keymap.key_for_make_code(80, flags=0, vkey=40),
        )


class DryRunProviderTests(unittest.TestCase):
    def test_emits_deterministic_jsonl(self):
        provider = DryRunProvider(log_file="test_events.jsonl", log_dir="logs")
        provider.emit(ProviderEvent(event="key_down", key="numpad_1", device="0C45:800A"))
        provider.emit(
            ProviderEvent(
                event="short_press", key="numpad_1", device="0C45:800A", duration_ms=183
            )
        )
        provider.close()
        with open(provider.path, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        self.assertEqual(len(lines), 2)
        first = json.loads(lines[0])
        self.assertEqual(first["event"], "key_down")
        self.assertEqual(first["key"], "numpad_1")
        self.assertEqual(first["device"], "0C45:800A")
        second = json.loads(lines[1])
        self.assertEqual(second["event"], "short_press")
        self.assertEqual(second["duration_ms"], 183)
        self.assertEqual(second["seq"], 2)


if __name__ == "__main__":
    import json

    unittest.main()
