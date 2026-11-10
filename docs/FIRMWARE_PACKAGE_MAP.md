# AULA L99 Firmware Package Map

This document maps the relationships and verified identity of the firmware and tool components discovered in the AULA L99 project.

## Relationship Diagram

```mermaid
graph TD
    ResetZip[Official Reset ZIP 2026.5.25]
    ResetZip -->|Contains| ScreenExe[Screen Reset EXE 194MB]
    ResetZip -->|Contains| KeyboardExe[Keyboard Reset EXE 2.2MB]

    ScreenExe -->|Extracts| UartTFT[UartTFT-II_Flash.bin]
    ScreenExe -->|Extracts| HFD22[HFD_Code_V2.2.bin]
    ScreenExe -->|Extracts| HFD23[HFD_Code_V2.3.bin (Official)]

    ISP123[L99 ISP V1.23.exe]
    HFD131[HFD_ISP_TOOL_V1.31.exe]
```

## Hash and Size Table

| File | Size (Bytes) | SHA-256 |
|---|---|---|
| Reset ZIP | 45,080,624 | `e854bebb87a592eaa8553dacff103a7ae62007318592cba2159685fbdb3615e3` |
| Screen Reset EXE | 194,946,048 | `8d52849afefeadf3a5d28a5e226f2c7a372a9376e1286f35c286d9b820d1ae84` |
| UartTFT-II_Flash.bin | 127,599,044 | `4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4` |
| HFD_Code_V2.2.bin | 305,800 | `432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf` |
| HFD_Code_V2.3.bin (Official) | 313,652 | `a76806ada9648d2672bbebead8a9bb396c0bc6f3a0a071e22e99001ac3359d03` |
| HFD_Code_V2.3.bin (Earlier) | 313,504 | `b277823234fcab7137963896493bcb6896fd985fc972354166fcfc584534e37f` |

## Verified Facts and Inferences

- **Official Reset Package**: A comprehensive recovery archive containing the necessary binaries to restore the keyboard and screen MCU to a factory-defined state.
- **Not a NAND Dump**: The extracted `UartTFT-II_Flash.bin` is a resource image for the UI engine; it lacks OOB, ECC, and per-device calibration data required for a raw NAND recovery.
- **Version Ambiguity**: HFD V2.3 files with identical names but different hashes have been identified. The version contained in the reset package is the verified latest reference.
- **ISP Tools**: `L99 ISP V1.23.exe` and `HFD_ISP_TOOL_V1.31.exe` are distinct tools; their roles should not be conflated with the MCU firmware itself.

## Unresolved Questions

- Functional differences between the two HFD V2.3 builds remain unproven without deep disassembly.
- The precise mechanism of the official ISP tools in verifying flash after write is known, but raw read-back capability is not established.

## Safest Next Step

Continue with offline-only analysis, such as descriptor resolution, using the verified official assets as the primary reference. Do not attempt hardware interaction until these analyses have fully validated the intended firmware structure.
