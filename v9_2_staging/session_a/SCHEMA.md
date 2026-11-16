# Session A Schema: V9.2 Bounded Computed-Call and Pointer-Cell Resolution

## Overview

This schema describes the deterministic JSON document produced by
`scripts/V92ComputedCallCollector.java` (Ghidra 12.1.4) and consumed offline by
`python/validate_computed_calls.py`. The collector is read-only.

Output path (Session D staging):
`v9_2_staging/session_a/outputs/collected_computed_calls.json`

## Top-level document

| Key | Type | Description |
|-----|------|-------------|
| schema | string | Fixed value `V92ComputedCallCollector.v1` |
| program_identity | object | Firmware/program identifying metadata |
| memory_range | object | Loaded firmware memory range and blocks |
| call_sites | array[object] | Exactly 9 call-site rows |
| pointer_cells | array[object] | Exactly 4 pointer-cell rows |
| computed_destinations | array[object] | Computed destinations with evidence sources |
| validation_summary | object | Aggregate counts and presence flags |

## program_identity

| Key | Type | Description |
|-----|------|-------------|
| program | string | Ghidra program name |
| domain | string|null | Domain file name |
| language | string|null | Ghidra language ID (e.g. `MCORE:LE:32:default`) |
| compiler | string|null | Compiler spec |
| image_base | string | `0x60000000` |
| image_end | string | `0x6004C933` |
| size_bytes | integer | `0x4C934` (313652 bytes expected) |

## memory_range

| Key | Type | Description |
|-----|------|-------------|
| loaded_start | string | `0x60000000` |
| loaded_end | string | `0x6004C933` |
| size_bytes | integer | loaded range size |
| memory_blocks | array[object] | one entry per memory block |

Memory block entry:
| Key | Type | Description |
|-----|------|-------------|
| name | string | block name |
| start | string | block start address |
| end | string | block end address |
| size | integer | block size in bytes |
| is_loaded | boolean | block is loaded |
| is_executable | boolean | block is executable |
| is_readable | boolean | block is readable |
| is_writable | boolean | block is writable |

## call_sites

Exactly nine rows, one per requested call-site address, sorted ascending by
`call_site_address`. Requested sites:

`0x60049D9C, 0x60049E12, 0x60049E14, 0x60049E6A, 0x60049EEA,
0x60049EF0, 0x60049F7E, 0x60045016, 0x60045034`

| Key | Type | Description |
|-----|------|-------------|
| caller_function_entry | string|null | entry address of containing function |
| caller_function_name | string|null | name of containing function |
| call_site_address | string | normalized `0x`-prefixed hex address |
| raw_instruction_bytes | string | uppercase hex of instruction bytes |
| instruction_text | string | disassembly text |
| mnemonic | string | instruction mnemonic |
| operands | array[object] | one entry per operand |
| instruction_flows | array[object] | instruction flow targets |
| references | array[object] | ReferenceManager references from this address |
| pointer_cell_loaded_near_call | string|null | pointer cell address loaded near this call |
| pointer_cell_raw_bytes | string|null | raw hex bytes at the pointer cell |
| pointer_cell_decoded_16_le | string|null | 16-bit LE interpretation |
| pointer_cell_decoded_16_be | string|null | 16-bit BE interpretation |
| pointer_cell_decoded_32_le | string|null | 32-bit LE interpretation |
| pointer_cell_decoded_32_be | string|null | 32-bit BE interpretation |
| pointer_cell_memory_block | string|null | memory block containing the cell |
| computed_destination | string|null | Ghidra computed call destination |
| computed_destination_in_loaded_memory | boolean | destination within loaded range |
| recovered_function_at_destination | string|null | function entry at destination |
| recovered_function_name | string|null | function name at destination |
| valid_instruction_at_destination | boolean | valid instruction at destination |
| ghidra_reports_computed_call | boolean | Ghidra reports COMPUTED_CALL reference |
| confidence_classification | string | one of allowed classifications |
| derivation_evidence | array[string] | human-readable derivation notes |

### Operand object

| Key | Type | Description |
|-----|------|-------------|
| operand_index | integer | operand position |
| display_text | string | operand display text |
| type | string | typed category (see below) |
| type_code | string | Ghidra OperandType code |
| values | array[object] | operand value objects |

Operand `type` values: `register`, `scalar`, `memory address`, `code address`,
`data address`, `external or out-of-range address`, `other`.

Operand value object:
| Key | Type | Description |
|-----|------|-------------|
| kind | string | value category |
| address | string|null | address value when kind is address-like |
| unsigned_value | integer|null | numeric value |
| value | string|null | display value |
| in_loaded_memory | boolean|null | within loaded firmware range |
| memory_block | string|null | containing block name |

### Instruction flow object

| Key | Type | Description |
|-----|------|-------------|
| kind | string | `address`, `scalar`, or `other` |
| address | string|null | flow target address |
| value | string|null | scalar or other value |
| in_loaded_memory | boolean|null | within loaded firmware range |

### Reference object

| Key | Type | Description |
|-----|------|-------------|
| reference_type | string | ReferenceType string |
| is_call | boolean | reference is a call |
| is_computed_call | boolean | reference is a computed call |
| from_address | string | reference source address |
| to_address | string|null | reference target address |
| to_in_loaded_memory | boolean|null | target within loaded range |

## pointer_cells

Exactly four rows, one per requested cell, sorted ascending by `cell_address`.
Requested cells:

`0x60049F88, 0x60049F94, 0x60049F98, 0x600450BC`

| Key | Type | Description |
|-----|------|-------------|
| cell_address | string | normalized `0x`-prefixed hex address |
| loaded_memory_status | boolean | cell address within loaded memory |
| memory_block_name | string|null | containing memory block name |
| block_start | string|null | block start |
| block_end | string|null | block end |
| raw_bytes_minus8_plus15 | string | raw bytes from cell-8 through cell+15 (`--` for unmapped) |
| aligned_reads | object | aligned 2-byte and 4-byte reads keyed by `u16@addr` / `u32@addr` |
| decoded_16_le | string|null | 16-bit LE at cell |
| decoded_16_be | string|null | 16-bit BE at cell |
| decoded_32_le | string|null | 32-bit LE at cell |
| decoded_32_be | string|null | 32-bit BE at cell |
| references_to_cell | array[object] | references targeting this cell |
| instructions_reading_cell | array[object] | nearby instructions reading the cell |
| cell_behavior | string | classification: literal, function pointer, callback slot, data pointer, instruction bytes, mixed code/data, unresolved |

Aligned read entry (`u16@addr` / `u32@addr`):
| Key | Type | Description |
|-----|------|-------------|
| address | string | read address |
| raw_bytes | string | uppercase hex bytes |
| decoded_16_le | string|null | 16-bit LE |
| decoded_16_be | string|null | 16-bit BE |
| decoded_32_le | string|null | 32-bit LE |
| decoded_32_be | string|null | 32-bit BE |

Reference-to-cell object:
| Key | Type | Description |
|-----|------|-------------|
| reference_type | string | ReferenceType string |
| is_call | boolean | reference is a call |
| is_computed_call | boolean | reference is a computed call |
| from_address | string | reference source address |
| to_address | string|null | reference target address |

Instruction-reading-cell object:
| Key | Type | Description |
|-----|------|-------------|
| instruction_address | string | instruction address |
| instruction_text | string | disassembly text |
| mnemonic | string | instruction mnemonic |
| function_entry | string|null | containing function entry |
| function_name | string|null | containing function name |

## computed_destinations

One row per distinct computed destination (deduplicated), sorted ascending.

| Key | Type | Description |
|-----|------|-------------|
| computed_destination | string | destination address |
| in_loaded_memory | boolean | within loaded firmware range |
| recovered_function_entry | string|null | function entry at destination |
| recovered_function_name | string|null | function name |
| valid_instruction | boolean | valid instruction at destination |
| memory_block | string|null | containing block name |
| evidence_source_call_sites | array[string] | call sites that map to this destination |

## validation_summary

| Key | Type | Description |
|-----|------|-------------|
| call_site_count | integer | number of call-site rows |
| pointer_cell_count | integer | number of pointer-cell rows |
| computed_in_loaded_memory | integer | count of in-range computed destinations |
| computed_out_of_loaded_memory | integer | count of out-of-range computed destinations |
| ghidra_computed_call_count | integer | count of sites where Ghidra reports computed call |
| all_call_sites_present | boolean | all nine expected sites present |
| all_pointer_cells_present | boolean | all four expected cells present |

## Allowed confidence classifications

- `DIRECT_IN_RANGE_CALL`
- `POINTER_CELL_IN_RANGE_CALL`
- `INDIRECT_CALLBACK_CALL`
- `OUT_OF_RANGE_COMPUTED_INTERPRETATION`
- `POSSIBLE_MCORE_REFERENCE_ANALYSIS_ERROR`
- `UNRESOLVED`

## Address normalization

All addresses are `0x`-prefixed, zero-padded to 8 hex digits (uppercase). The
validator normalizes `int`, `0x`-prefixed string, and malformed inputs
fail-closed. A null address fails validation.

## JSON escaping

Strings are escaped per RFC 8259: `"`, `\`, control characters `< 0x20` as
`\uXXXX`, and `\b`, `\f`, `\n`, `\r`, `\t`. Non-ASCII printable UTF-8 is emitted
as-is. The collector hand-rolls serialization to avoid depending on a JSON
library inside the Ghidra scripting environment.

## Fail-closed validation rules

The validator fails if any of the following hold:

1. Any requested call site is missing or extra/unexpected sites are present.
2. Any pointer cell is missing or extra/unexpected cells are present.
3. Any address is malformed (null, boolean, non-hex string, wrong type).
4. Duplicate rows exist (by `call_site_address` or `cell_address`).
5. An out-of-range destination is marked as a confirmed direct call.
6. Raw bytes are absent for a call site or pointer cell.
7. The Ghidra program identity is missing.
8. A computed destination is presented without its evidence source call sites.
9. Rows are not sorted deterministically by address.
10. `confidence_classification` is not one of the allowed values.
11. `COMPUTED_CALL` alone is used to confirm a destination without a recovered
    function or valid instruction.
12. Addresses `0x6004D08C`, `0x6004D140`, `0x60053524` are not treated as outside
    the loaded range.
13. Resolved target `0x60044FEC` is not within the loaded range.

## Ghidra APIs used (12.1.4)

- `ghidra.app.script.GhidraScript`
- `currentProgram.getAddressFactory().getAddress(long)` (throws `AddressFormatException`)
- `currentProgram.getMemory()`, `Memory.contains(Address)`, `Memory.getByte(Address)`, `Memory.getBlocks()`, `Memory.getBlock(Address)`
- `MemoryBlock.getName()`, `getStart()`, `getEnd()`, `getSize()`, `isLoaded()`, `isExecute()`, `isRead()`, `isWrite()`
- `currentProgram.getListing()`, `Listing.getInstructionAt(Address)`, `Listing.getInstructions(Address, boolean)`
- `Instruction.getBytes()`, `toString()`, `getMnemonicString()`, `getNumOperands()`, `getOperandString(int)`, `getOperandType(int)`, `getOpObjects(int)`, `getFlows()`
- `ghidra.program.model.symbol.OperandType` (REGISTER, SCALAR, MEMORY, CODE_ADDRESS, DATA_ADDRESS, EXTERNAL_ADDRESS, UNDEFINED)
- `currentProgram.getReferenceManager()`, `ReferenceManager.getReferencesFrom(Address)`, `ReferenceManager.getReferencesTo(Address)`, `ReferenceIterator`
- `Reference.getReferenceType()`, `isCall()`, `isComputedCall()`, `getFromAddress()`, `getToAddress()`
- `currentProgram.getFunctionManager()`, `FunctionManager.getFunctionAt(Address)`, `getFunctionContaining(Address)`
- `Function.getEntryPoint()`, `getName()`, `getBody()`
- `ghidra.program.model.scalar.Scalar.getUnsignedValue()`
- `ghidra.program.model.address.AddressFormatException`

## ReferenceIterator and Reference[] handling under Ghidra 12.1.4

Ghidra 12.1.4 exposes references through `ReferenceManager.getReferencesFrom(Address)` and
`getReferencesTo(Address)`, both returning `ReferenceIterator` (an `Iterable<Reference>`).
The collector iterates each iterator with `hasNext()`/`next()` and copies each
`Reference` into a plain map. It never retains `ReferenceIterator` objects across
the script boundary and never materializes a `Reference[]` array. References are
examined only for their `ReferenceType`, `fromAddress`, and `toAddress`, and are
not used to mutate the program. `isComputedCall()` is read strictly as a
reporting flag, never as confirmation of a call target.

## AddressFormatException handling

`currentProgram.getAddressFactory().getAddress(long)` throws
`AddressFormatException` for offsets outside the address space. The collector
wraps address conversion in `toAddr(long)` and lets the exception propagate to
the Ghidra script runner (the script fails fast rather than producing a partial
silently-wrong row). The offline validator receives already-normalized integer
addresses from JSON and fails closed on malformed address values rather than
relying on Ghidra address parsing.

## Confidence classification logic

- Not in loaded memory → `OUT_OF_RANGE_COMPUTED_INTERPRETATION`
- In range + Ghidra COMPUTED_CALL only + no function + no valid instruction →
  `POSSIBLE_MCORE_REFERENCE_ANALYSIS_ERROR`
- In range + function + valid instruction → `DIRECT_IN_RANGE_CALL`
- In range + (function OR valid instruction) → `POINTER_CELL_IN_RANGE_CALL`
- Otherwise → `UNRESOLVED`

A `COMPUTED_CALL` reference alone never upgrades a destination to confirmed.

## Pointer-cell behavior classification

- Not loaded → `unresolved`
- Executable block + readers → `instruction bytes`
- Non-executable block + readers → `data pointer`
- Non-executable block + no readers + references → `literal`
- Executable block + no readers + references → `mixed code/data`
- Readers + call reference → `function pointer`
- Readers + computed-call reference → `callback slot`
- Otherwise → `unresolved`
