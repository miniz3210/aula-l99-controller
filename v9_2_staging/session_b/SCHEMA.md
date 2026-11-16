# Session B Schema: V9.2 Bounded Shared-State and Callback-Slot Analysis

## Overview

This schema describes the deterministic JSON document produced by
`scripts/V92SharedStateCollector.java` (Ghidra 12.1.4) and consumed offline by
`python/validate_shared_state.py`. The collector is read-only.

Output path:
`v9_2_staging/session_b/outputs/collected_shared_state.json`

## Top-level document

| Key | Type | Description |
|-----|------|-------------|
| schema | string | Fixed value `V92SharedStateCollector.v1` |
| program_identity | object | Firmware/program identifying metadata |
| memory_range | object | Loaded firmware memory range and blocks |
| requested_states | array[object] | Exactly 7 requested-state rows |
| access_records | array[object] | Access records keyed by requested-state address |
| callback_chains | array[object] | Callback-chain records (notably 0x600450BC) |
| initializer_candidates | array[object] | Write/initializer candidates per requested state |
| shared_function_matrix | object | Matrix across the three primary functions |
| classification_summary | object | Aggregate classification counts |
| validation_summary | object | Fail-closed validation flags |

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

## requested_states

Exactly seven rows, one per requested address, sorted ascending by
`normalized_address`. Requested addresses:

`0x00821528, 0x600450A8, 0x600450B0, 0x600450B4, 0x600450BC,
0x0086CF28, 0x0086DF28`

| Key | Type | Description |
|-----|------|-------------|
| requested_address | string | normalized `0x`-prefixed hex address |
| normalized_address | string | normalized `0x`-prefixed hex address |
| address_space | string | Ghidra address space name |
| address_classification | string | `LOADED_FIRMWARE`, `RAM_OR_EXTERNAL_SPACE`, `OUTSIDE_LOADED_MEMORY`, `UNRESOLVED` |
| memory_block_name | string|null | containing memory block name |
| initialized_status | string | initialized / not_initialized / unmapped_or_outside_loaded_memory |
| block_readable | boolean|null | block read flag |
| block_writable | boolean|null | block write flag |
| block_executable | boolean|null | block execute flag |
| raw_bytes | string|null | uppercase hex bytes around the address |
| raw_byte_start_address | string|null | start address of raw-byte window |
| raw_byte_count | integer | number of readable bytes in window |
| raw_bytes_available | boolean | whether raw bytes could be read |
| incoming_references | array[object] | references to this address |
| outgoing_references | array[object] | references from this address |
| source_instruction | string|null | instruction text of the reference source |
| source_function | string|null | containing function name, nullable when unresolved |
| reference_type | string|null | ReferenceType string |
| inferred_access_direction | string | one of `READ`, `WRITE`, `READ_WRITE`, `ADDRESS_TAKEN`, `PARAMETER`, `COMPUTED_CALL`, `UNKNOWN` |
| inferred_access_width | string|null | `1`, `2`, `4`, or `UNKNOWN` |
| preceding_instruction | string|null | instruction before the source instruction |
| following_instruction | string|null | instruction after the source instruction |
| containing_function | string|null | function containing the source instruction |
| referenced_by_0x60049D98 | boolean | referenced by function 0x60049D98 |
| referenced_by_0x60049E5C | boolean | referenced by function 0x60049E5C |
| referenced_by_0x60044FEC | boolean | referenced by function 0x60044FEC |
| referenced_by_another_function | boolean | referenced by another function |
| write_or_initializer_candidates | array[object] | write/initializer candidate entries |
| initializer_candidate_addresses | array[string] | sorted candidate addresses |
| load_to_register_to_call_evidence | string|null | load-to-call chain evidence |
| bounded_decompiler_snippet | string|null | bounded disassembly snippet |
| evidence_backed_state_classification | string | one of `CALLBACK_POINTER`, `BUFFER_POINTER`, `DATA_POINTER`, `LENGTH_VALUE`, `MODE_OR_STATE`, `COMMAND_VALUE`, `QUEUE_OR_INDEX`, `UNKNOWN` |
| confidence | string | one of `CONFIRMED`, `PROBABLE`, `UNRESOLVED`, `INSUFFICIENT_EVIDENCE` |
| exact_supporting_evidence | array[string] | address-level evidence strings |

## access_records

One record per incoming reference per requested-state address.

| Key | Type | Description |
|-----|------|-------------|
| requested_state_address | string | normalized requested-state address |
| source_instruction | string | instruction text |
| source_function | string|null | containing function name |
| reference_type | string | ReferenceType string |
| access_direction | string | one of allowed directions |
| access_width_evidence | string | `1`, `2`, `4`, or `UNKNOWN` |

## callback_chains

Callback-chain analysis for `0x600450BC`.

| Key | Type | Description |
|-----|------|-------------|
| callback_slot_address | string | `0x600450BC` |
| memory_block_name | string|null | containing block name |
| in_loaded_memory | boolean | whether slot is in loaded memory |
| readers | array[object] | reader reference entries |
| writers | array[object] | writer reference entries |
| address_taking_references | array[object] | address-taking / computed-call references |
| callback_destination | object | resolved call destination |
| chain_classification | string | one of `CONFIRMED_CALLBACK_CHAIN`, `PROBABLE_CALLBACK_CHAIN`, `UNRESOLVED_COMPUTED_CALL`, `REFERENCE_ANALYSIS_ARTIFACT`, `INSUFFICIENT_EVIDENCE` |

## initializer_candidates

One entry per write reference to a requested-state address.

| Key | Type | Description |
|-----|------|-------------|
| candidate_initializer_address | string | write source address |
| candidate_function_entry | string|null | containing function name |
| target_state_address | string | requested-state address |
| instruction_text | string|null | write instruction text |
| write_value_recoverable | string|null | recovered written value |

## shared_function_matrix

| Key | Type | Description |
|-----|------|-------------|
| primary_functions | array[object] | one entry per primary function |
| all_three_present | boolean | whether all three relevant functions are present |

Primary function entry:
| Key | Type | Description |
|-----|------|-------------|
| function_entry | string | function entry address |
| function_name | string|null | function name |
| instruction_count | integer|null | instruction count |
| incoming_reference_count | integer|null | incoming reference count |
| references_requested_states | array[string] | requested states referenced |

## classification_summary

| Key | Type | Description |
|-----|------|-------------|
| total_requested_states | integer | 7 |
| classification_counts | object | count per allowed classification |
| confidence_counts | object | count per allowed confidence |

## validation_summary

| Key | Type | Description |
|-----|------|-------------|
| requested_state_count | integer | number of requested-state rows |
| expected_requested_state_count | integer | 7 |
| seven_requested_states_present | boolean | exactly seven present |
| no_duplicate_requested_address | boolean | no duplicates |
| rows_deterministically_sorted | boolean | rows sorted by address |
| program_identity_present | boolean | program identity present |
| memory_range_present | boolean | memory range present |
| stack_references_excluded | boolean | stack references excluded |
| code_addresses_not_ram_without_classification | boolean | code addresses not misclassified as RAM |
| callback_pointer_requires_load_to_call_evidence | boolean | callback pointer needs load-to-call evidence |
| no_display_specific_without_address_level_evidence | boolean | no display-specific claims without evidence |
| shared_function_matrix_includes_three_functions | boolean | matrix includes all three functions |
| missing_initializer_evidence_explicit | boolean | missing initializer evidence explicit |
| fail_closed_validation_required | boolean | fail-closed validation required |

## Address normalization

All addresses are `0x`-prefixed, zero-padded to 8 hex digits (uppercase). The
validator normalizes `int`, `0x`-prefixed string, and malformed inputs
fail-closed. A null address fails validation.

## JSON escaping

Strings are escaped per RFC 8259: `"`, `\`, control characters `< 0x20` as
`\uXXXX`, and `\b`, `\f`, `\n`, `\r`, `\t`. Non-ASCII printable UTF-8 is emitted
as-is. The collector hand-rolls serialization to avoid depending on a JSON
library inside the Ghidra scripting environment. Property names are produced
through a shared `property(key)` helper wrapping `escapeJson`, so no
over-escaped property names such as `\\"requested_address\\"` appear.

## Fail-closed validation rules

The validator fails if any of the following hold:

1. Exactly seven requested-state rows are required; missing or extra rows fail.
2. All seven required addresses must be present.
3. No duplicate requested-state address is allowed.
4. Addresses must be normalized and sorted deterministically.
5. Program identity must exist.
6. Memory range must exist.
7. Every access record must have: requested state address, source instruction,
   source function (nullable only when unresolved), reference type, access
   direction, access-width evidence or explicit unknown status.
8. Stack references are excluded from requested-state rows.
9. Code addresses are not represented as RAM state without an explicit
   mixed/code classification.
10. Callback-pointer classification includes load-to-call evidence.
11. Display-specific classification includes explicit address-level evidence.
12. Shared-function matrix includes all three relevant functions.
13. Rows are deterministically sorted.
14. Classification confidence is within the documented allowed values.
15. Missing initializer evidence is represented explicitly rather than inferred.

## Ghidra APIs used (12.1.4)

- `ghidra.app.script.GhidraScript`
- `currentProgram.getAddressFactory().getAddress(long)` (throws `AddressFormatException`)
- `currentProgram.getMemory()`, `Memory.contains(Address)`, `Memory.getByte(Address)`, `Memory.getBlocks()`, `Memory.getBlock(Address)`
- `MemoryBlock.getName()`, `getStart()`, `getEnd()`, `getSize()`, `isLoaded()`, `isExecute()`, `isRead()`, `isWrite()`
- `currentProgram.getListing()`, `Listing.getInstructionAt(Address)`, `Listing.getInstructions(Address, boolean)`
- `Instruction.getBytes()`, `toString()`, `getMnemonicString()`, `getNumOperands()`, `getOpObjects(int)`, `getFlows()`, `getLength()`
- `currentProgram.getReferenceManager()`, `ReferenceManager.getReferencesFrom(Address)`, `ReferenceManager.getReferencesTo(Address)`, `ReferenceIterator`
- `Reference.getReferenceType()`, `isRead()`, `isWrite()`, `isCall()`, `isComputedCall()`, `getFromAddress()`, `getToAddress()`
- `currentProgram.getFunctionManager()`, `FunctionManager.getFunctionAt(Address)`, `getFunctionContaining(Address)`
- `Function.getEntryPoint()`, `getName()`, `getBody()`
- `ghidra.program.model.scalar.Scalar.getUnsignedValue()`
- `ghidra.program.model.address.AddressFormatException`

## ReferenceIterator and Reference[] handling under Ghidra 12.1.4

Ghidra 12.1.4 exposes `ReferenceManager.getReferencesTo(Address)` returning a
`ReferenceIterator`, iterated with `hasNext()`/`next()`. It also exposes
`ReferenceManager.getReferencesFrom(Address)` returning `Reference[]`, iterated
with an enhanced for-loop. The collector uses the correct form for each: an
iterator for incoming references, a for-each loop for outgoing references. It
never treats `getReferencesFrom(Address)` as a `ReferenceIterator`.

## AddressFormatException handling

`currentProgram.getAddressFactory().getAddress(long)` throws
`AddressFormatException` for offsets outside the address space. The collector
wraps address conversion in `toAddr(long)` and allows the exception to propagate
through methods declared `throws Exception`, failing fast rather than producing
silently-wrong rows. Malformed addresses are never silently substituted.

## Access-direction rules

- `READ`: reference type is a read
- `WRITE`: reference type is a write
- `READ_WRITE`: reference type is both read and write
- `ADDRESS_TAKEN`: address is taken (computed call or data reference)
- `PARAMETER`: address passed as a parameter
- `COMPUTED_CALL`: reference is a computed call
- `UNKNOWN`: direction cannot be inferred

Direction is never inferred from reference type alone; instruction evidence is
required.

## Access-width rules

Width is inferred only when instruction evidence supports it:
- byte load/store → `1`
- halfword load/store → `2`
- word load/store → `4`
- unknown or ambiguous instruction → `UNKNOWN`

The instruction mnemonic used for every inferred width is recorded in
`exact_supporting_evidence`.

## Memory classification rules

The loaded firmware range is `0x60000000` through `0x6004C933`.
- Addresses inside that range are not automatically RAM state.
- Addresses in stack space must not appear as requested global-state records.
- Code addresses must not be classified as RAM state merely because a reference
  exists.
- For addresses outside the loaded firmware range: report memory-block status
  from Ghidra; distinguish RAM or external address space from a completely
  unmapped address; do not fabricate raw bytes if memory cannot be read; set
  raw-byte availability explicitly.

## Special analysis: 0x600450BC callback slot

Collectors preserve every reader, writer, address-taking reference, value
written, candidate initializer functions, load instruction, destination register,
subsequent instruction, indirect/computed call sites, null checks or conditional
use evidence, source function, call-site address, instruction text,
ReferenceManager call destination, destination-in-loaded-memory status,
recovered-function status, valid-instruction status, and chain classification.

A `CALLBACK_POINTER` classification requires load-to-call evidence. A
`COMPUTED_CALL` reference alone is insufficient. `0x60053524` is outside the
loaded firmware range and is not classified as a confirmed callback
implementation solely because Ghidra reports a computed-call reference.

## Special analysis: 0x00821528 shared state

Every reference from `0x60049D98` and `0x60049E5C` is preserved: read/write
direction, access width, source instruction, source function, pointer
arithmetic, base-plus-offset use, offsets used, associated loop conditions,
associated lengths or bounds, and whether the address behaves like
`BUFFER_POINTER`, `DESCRIPTOR_TABLE_POINTER`, `STATE_OBJECT`, or `UNKNOWN`.
References are not collapsed before preserving every source record. A
normalized summary may deduplicate by address, source function, source
instruction, access direction, access width.

## Special comparison: 0x0086CF28 versus 0x0086DF28

Determines whether the two addresses represent parallel structures, mode-specific
state, separate buffers, separate descriptors, unrelated state, or insufficient
evidence. Records source functions, read/write direction, access width,
surrounding instruction pattern, offset pattern, shared callees, branch
conditions, and exact comparison evidence.
