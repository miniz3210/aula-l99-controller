# AULA L99 Windows Input Bridge POC

Firmware-free Windows bridge that translates verified AULA L99 Mini Numpad HID
events into logical key actions using Raw Input device attribution.

## What this POC does

- Uses the Windows Raw Input API to attribute keyboard events to the physical
  device `VID 0C45 / PID 800A` (AULA L99 wired HID).
- Maps the 17 verified Mini Numpad return values to logical key IDs
  (`numpad_0`..`numpad_9`, `numpad_add`/plus, etc., plus `home`).
- Runs a deterministic per-key short/hold state machine:
  - key-down starts timing
  - key-up before 500 ms emits `short_press`
  - key-up from 500 ms through 699 ms emits nothing (dead zone)
  - reaching 700 ms emits `hold` exactly once
  - key-up after hold emits no short action
  - missing key-up resets after a configurable stuck-key timeout
  - optional secondary hold at 2000 ms (disabled by default)
- Writes deterministic structured JSON lines through a dry-run provider.

## What this POC does NOT do

- No Bitfocus Companion requests (integration deferred to a later task).
- No global keyboard suppression (keys still reach other applications).
- No USB, HID, COM, or screen commands.
- No firmware modification or flashing.
- No updater execution.

## Raw Input limitation

Raw Input identifies the physical device that produced an input event, but it
does not provide `WH_KEYBOARD_LL`-style global suppression. Device attribution
and global key suppression are separate concerns and are not combined in this
POC. The L99 key is still delivered to the foreground application.

## Configuration

Configuration lives in `src/aula_bridge/config/bridge_config.json`:

| Field | Meaning | Default |
|---|---|---|
| vid | Target vendor ID | `0x0C45` |
| pid | Target product ID | `0x800A` |
| short_threshold_ms | Short-press threshold | `500` |
| hold_threshold_ms | Hold threshold | `700` |
| secondary_hold_ms | Secondary hold threshold | `2000` |
| secondary_hold_enabled | Enable secondary hold | `false` |
| stuck_key_timeout_ms | Missing key-up reset timeout | `5000` |
| provider | Output provider | `dry_run` |
| log_file | JSONL log filename | `bridge_events.jsonl` |
| log_dir | Log directory | `logs` |
| key_mappings | Return value -> logical key | verified Mini Numpad map |

## Running

From the repository root:

```
py aula_input_bridge.py --list-devices
py aula_input_bridge.py
```

`--list-devices` enumerates Raw Input devices so you can confirm the L99
(`0C45:800A`) is present and in wired HID mode. The bridge writes events to
`logs/bridge_events.jsonl`.

Example log lines:

```
{"event":"key_down","key":"numpad_1","device":"0C45:800A"}
{"event":"short_press","key":"numpad_1","duration_ms":183,"device":"0C45:800A"}
{"event":"hold","key":"numpad_1","duration_ms":700,"device":"0C45:800A"}
{"event":"key_up","key":"numpad_1","held":true,"device":"0C45:800A"}
```

## Tests

Run the deterministic state-machine tests (no Windows hardware, no real sleeps):

```
py -m unittest discover -s tests -v
```

## Next task

Implement a Bitfocus Companion provider against the tested provider interface
(`BridgeProvider.emit`), reusing the existing device, state-machine, keymap, and
dry-run provider layers.
