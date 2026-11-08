# AULA L99 Controller Research

Windows-oriented research and tooling for the AULA L99 keyboard touchscreen.

## Verified findings

- Screen controller: `EEEF:268A`
- Keyboard HID controller: `0C45:800A`
- Touch and pointer controller: `1A86:8091`
- Screen resolution: 320 x 480
- The built-in numpad page exposes 17 distinct HID touch actions
- Real-time telemetry uses a 64-byte HID Feature Report
- CPU and GPU usage fields were verified with controlled load tests
- Runtime photo framebuffer uploads do not replace built-in numpad UI resources

## Repository contents

- `scripts/`: independently written protocol-analysis and replay tools
- `docs/`: verified notes and protocol mappings
- `examples/`: non-sensitive example configurations

## Excluded material

This repository does not redistribute:

- Official AULA applications or firmware
- Extracted vendor executables, DLLs, or drivers
- USB packet captures
- Process or memory dumps
- Third-party repository copies
- Local virtual environments

See `docs/THIRD_PARTY_REFERENCES.md`.

## Status

Current research is focused on locating the built-in page, resource, and action
tables required to reskin the numpad page or add a custom Stream Deck-style page.

## Safety

Firmware modification and flashing can permanently disable the display
controller. Do not write modified firmware without a verified backup and
recovery procedure.
