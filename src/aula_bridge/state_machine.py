"""Deterministic short/hold key state machine for the AULA L99 bridge POC.

Each logical key is tracked independently. The machine is pure logic: it takes
timestamped key_down / key_up events and emits PressResult actions. Time is
injected (milliseconds as integers) so unit tests can mock time without real
sleeps.

State machine:
  IDLE        --key_down--> PRESSED (start timer)
  PRESSED     --key_up < short_threshold--> SHORT_PRESS (emit short_press)
  PRESSED     --repeat key_down while held--> ignored (repeat_ignored)
  PRESSED     --timer reaches hold_threshold--> HOLD (emit hold once)
  PRESSED     --timer in [short_threshold, hold_threshold)--> DEAD_ZONE
  DEAD_ZONE   --key_up--> IDLE (suppress short action)
  DEAD_ZONE   --timer reaches hold_threshold--> HOLD (emit hold once)
  HOLD        --key_up--> IDLE (suppress short action)
  HOLD        --timer reaches secondary_hold (if enabled)--> SECONDARY_HOLD
  any         --stuck_key_timeout without key_up--> IDLE (suppress action)

Rules:
  - first key-down starts timing
  - repeated key-down is ignored while a key is down
  - key-up before short threshold emits short_press
  - key-up from short_threshold through hold_threshold-1 ms emits no action
  - reaching hold_threshold emits hold exactly once
  - key-up after hold emits no short action
  - missing key-up resets after stuck_key_timeout
  - optional secondary hold at secondary_hold_ms, disabled by default
  - application restart begins with no pressed keys (fresh state)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# States.
STATE_IDLE = "idle"
STATE_PRESSED = "pressed"
STATE_DEAD_ZONE = "dead_zone"
STATE_HELD = "held"
STATE_SECONDARY_HELD = "secondary_held"

# Actions.
ACTION_SHORT_PRESS = "short_press"
ACTION_HOLD = "hold"
ACTION_SECONDARY_HOLD = "secondary_hold"
ACTION_NONE = "none"
ACTION_REPEAT_IGNORED = "repeat_ignored"


@dataclass
class KeyEvent:
    """A timestamped input event for one logical key."""

    key: str
    device: str
    event_type: str  # "key_down" or "key_up"
    time_ms: int


@dataclass
class PressResult:
    """Outcome of processing one event for one key."""

    key: str
    device: str
    action: str
    duration_ms: Optional[int] = None
    timestamp_ms: int = 0


@dataclass
class _KeyState:
    state: str = STATE_IDLE
    down_time_ms: Optional[int] = None
    hold_emitted: bool = False
    secondary_hold_emitted: bool = False


class KeyStateMachine:
    """Deterministic per-key short/hold state machine."""

    def __init__(
        self,
        short_threshold_ms: int = 500,
        hold_threshold_ms: int = 700,
        secondary_hold_ms: int = 2000,
        secondary_hold_enabled: bool = False,
        stuck_key_timeout_ms: int = 5000,
        now_ms: int = 0,
    ) -> None:
        self.short_threshold_ms = short_threshold_ms
        self.hold_threshold_ms = hold_threshold_ms
        self.secondary_hold_ms = secondary_hold_ms
        self.secondary_hold_enabled = secondary_hold_enabled
        self.stuck_key_timeout_ms = stuck_key_timeout_ms
        self._now = now_ms
        self._states: Dict[str, _KeyState] = {}

    # -- time control (for tests) --
    def set_time(self, now_ms: int) -> None:
        self._now = now_ms

    def advance(self, delta_ms: int) -> None:
        self._now += delta_ms

    def now(self) -> int:
        return self._now

    # -- public API --
    def reset(self) -> None:
        """Reset all keys to IDLE (application restart semantics)."""
        self._states.clear()

    def key_down(self, key: str, device: str, time_ms: Optional[int] = None) -> List[PressResult]:
        t = self._now if time_ms is None else time_ms
        state = self._states.get(key, _KeyState())
        results: List[PressResult] = []

        if state.state == STATE_IDLE:
            state.state = STATE_PRESSED
            state.down_time_ms = t
            state.hold_emitted = False
            state.secondary_hold_emitted = False
            self._states[key] = state
            results.append(
                PressResult(key=key, device=device, action=ACTION_NONE, timestamp_ms=t)
            )
        else:
            # Repeated key-down while already down/held/secondary-held: ignored.
            results.append(
                PressResult(
                    key=key, device=device, action=ACTION_REPEAT_IGNORED, timestamp_ms=t
                )
            )
        return results

    def key_up(self, key: str, device: str, time_ms: Optional[int] = None) -> List[PressResult]:
        t = self._now if time_ms is None else time_ms
        state = self._states.get(key)
        results: List[PressResult] = []

        if state is None or state.state == STATE_IDLE:
            # Orphaned key-up with no matching down: no-op.
            results.append(
                PressResult(key=key, device=device, action=ACTION_NONE, timestamp_ms=t)
            )
            return results

        down_start = state.down_time_ms if state.down_time_ms is not None else t
        held_duration = t - down_start

        if state.state == STATE_PRESSED:
            if held_duration < self.short_threshold_ms:
                results.append(
                    PressResult(
                        key=key,
                        device=device,
                        action=ACTION_SHORT_PRESS,
                        duration_ms=held_duration,
                        timestamp_ms=t,
                    )
                )
            else:
                # Dead zone: no short action.
                results.append(
                    PressResult(
                        key=key, device=device, action=ACTION_NONE, timestamp_ms=t
                    )
                )
        elif state.state == STATE_DEAD_ZONE:
            # No action in dead zone.
            results.append(
                PressResult(key=key, device=device, action=ACTION_NONE, timestamp_ms=t)
            )
        elif state.state == STATE_HELD:
            # Key-up after hold: suppress any short action.
            results.append(
                PressResult(key=key, device=device, action=ACTION_NONE, timestamp_ms=t)
            )
        elif state.state == STATE_SECONDARY_HELD:
            results.append(
                PressResult(key=key, device=device, action=ACTION_NONE, timestamp_ms=t)
            )

        state.state = STATE_IDLE
        state.down_time_ms = None
        self._states[key] = state
        return results

    def tick(self, time_ms: Optional[int] = None) -> List[PressResult]:
        """Advance the machine by one timer tick and emit time-based actions.

        Call this regularly (e.g. every 10 ms) from the main loop. Returns any
        time-driven actions (hold, secondary hold, stuck-key reset).
        """
        t = self._now if time_ms is None else time_ms
        results: List[PressResult] = []

        for key, state in list(self._states.items()):
            if state.state == STATE_IDLE or state.down_time_ms is None:
                continue

            held = t - state.down_time_ms

            # Stuck-key timeout: reset regardless of state.
            if held >= self.stuck_key_timeout_ms:
                results.append(
                    PressResult(
                        key=key,
                        device="",
                        action=ACTION_NONE,
                        timestamp_ms=t,
                    )
                )
                state.state = STATE_IDLE
                state.down_time_ms = None
                state.hold_emitted = False
                state.secondary_hold_emitted = False
                continue

            if state.state == STATE_PRESSED:
                if held >= self.hold_threshold_ms and not state.hold_emitted:
                    state.state = STATE_HELD
                    state.hold_emitted = True
                    results.append(
                        PressResult(
                            key=key,
                            device="",
                            action=ACTION_HOLD,
                            duration_ms=held,
                            timestamp_ms=t,
                        )
                    )
                elif held >= self.short_threshold_ms:
                    state.state = STATE_DEAD_ZONE
            elif state.state == STATE_DEAD_ZONE:
                if held >= self.hold_threshold_ms and not state.hold_emitted:
                    state.state = STATE_HELD
                    state.hold_emitted = True
                    results.append(
                        PressResult(
                            key=key,
                            device="",
                            action=ACTION_HOLD,
                            duration_ms=held,
                            timestamp_ms=t,
                        )
                    )
            elif state.state == STATE_HELD:
                if (
                    self.secondary_hold_enabled
                    and not state.secondary_hold_emitted
                    and held >= self.secondary_hold_ms
                ):
                    state.state = STATE_SECONDARY_HELD
                    state.secondary_hold_emitted = True
                    results.append(
                        PressResult(
                            key=key,
                            device="",
                            action=ACTION_SECONDARY_HOLD,
                            duration_ms=held,
                            timestamp_ms=t,
                        )
                    )
            elif state.state == STATE_SECONDARY_HELD:
                pass  # no further time-based actions

        return results

    def is_pressed(self, key: str) -> bool:
        state = self._states.get(key)
        return state is not None and state.state != STATE_IDLE
