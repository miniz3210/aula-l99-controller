# V9.2 Boundary Collector Schema

Bounded read-only Ghidra collector and offline validator for the AULA L99 V9.2
Session C analysis around `0x60049B90`.

## Output document structure

The collector emits a single deterministic JSON document with the following
top-level keys (in order):

| Key | Type | Description |
|-----|------|-------------|
| `schema` | string | Schema identifier: `v9.2-boundary-collector-1.0` |
| `program_identity` | object | Ghidra project/program/language identity |
| `target` | object | Target address `0x60049B90` |
| `window` | object | Bounded analysis window start/end |
| `raw_bytes` | object | Raw bytes for the entire bounded window |
| `instruction_inventory` | array | Every existing Ghidra instruction in the window |
| `incoming_references` | array | Every incoming reference to any instruction in the window |
| `outgoing_references` | array | Every outgoing reference from instructions in the window |
| `nearest_functions` | object | Nearest previous/next recovered function |
| `candidate_blocks` | array | Candidate basic blocks in the window |
| `boundary_features` | object | Boundary detection features |
| `classification` | object | Final classification and evidence summary |
| `evidence` | object | Evidence flags used by classification rules |
| `mutations_reported` | array | Must be empty (read-only guarantee) |

## program_identity

| Field | Type | Description |
|-------|------|-------------|
| `project` | string | Ghidra project name or `none`/`unknown` |
| `program` | string | Program name |
| `language` | string | Language ID, e.g. `MCORE:LE:32:default` |
| `compiler` | string | Compiler spec ID |
| `image_base` | string | Image base address hex |

## target

| Field | Type | Description |
|-------|------|-------------|
| `address` | string | `0x60049B90` |
| `offset` | integer | Numeric offset |
| `in_window` | boolean | Whether target is inside the window |

## window

| Field | Type | Description |
|-------|------|-------------|
| `start` | string | Window start hex |
| `end` | string | Window end hex |
| `start_offset` | integer | Window start offset |
| `end_offset` | integer | Window end offset |
| `size_bytes` | integer | Window size in bytes |
| `allowed_range` | string | `0x60049A90–0x60049C90` |
| `within_allowed_range` | boolean | Whether window respects hard limits |

## raw_bytes

| Field | Type | Description |
|-------|------|-------------|
| `present` | boolean | Whether bytes were read |
| `bytes` | array of integer | Byte values 0–255 |
| `hex` | string | Uppercase hex string |
| `size` | integer | Number of bytes |
| `start` | string | Window start hex |
| `end` | string | Window end hex |

## instruction_inventory

Array of instruction objects, sorted by address ascending.

| Field | Type | Description |
|-------|------|-------------|
| `address` | string | Instruction address hex |
| `offset` | integer | Instruction address offset |
| `length` | integer | Instruction length in bytes |
| `end` | string | Instruction end address hex |
| `end_offset` | integer | Instruction end offset |
| `bytes` | array of integer | Instruction bytes |
| `hex` | string | Instruction bytes hex |
| `mnemonic` | string | Instruction mnemonic |
| `operands` | array of string | Operand text strings |
| `operand_types` | array of string | Operand type strings |
| `flow_type` | string | `CALL`, `RETURN`, `BRANCH`, `FALLTHROUGH`, `FLOW_UNKNOWN` |
| `falls_through` | boolean | Whether instruction falls through |
| `is_branch` | boolean | Whether instruction is a branch |
| `is_call` | boolean | Whether instruction is a call |
| `is_return` | boolean | Whether instruction is a return |
| `is_delay_slot` | boolean | Whether instruction is a delay slot |
| `flows` | array of string | Flow target address strings |
| `function_at` | object | Function at or containing this instruction |
| `referenced_by` | array | Incoming references to this instruction |
| `references_from` | array | Outgoing references from this instruction |

### function_at

| Field | Type | Description |
|-------|------|-------------|
| `present` | boolean | Whether a function exists |
| `entry` | string | Function entry hex |
| `end` | string | Function end hex |
| `name` | string | Function name |
| `thunk` | boolean | Whether function is a thunk |
| `external` | boolean | Whether function is external |

### reference object

| Field | Type | Description |
|-------|------|-------------|
| `from` / `from_address` | string | Source address hex |
| `to` / `to_address` | string | Target address hex |
| `type` | string | Reference type string |
| `is_call` | boolean | Whether reference is a call |
| `is_branch` | boolean | Whether reference is a branch |
| `is_read` | boolean | Whether reference is a read |
| `is_write` | boolean | Whether reference is a write |
| `operand_index` | integer | Operand index |

## incoming_references / outgoing_references

Arrays of reference objects, sorted by `from_address` ascending.

## nearest_functions

| Field | Type | Description |
|-------|------|-------------|
| `previous` | object | Function summary or null |
| `next` | object | Function summary or null |
| `previous_distance` | string or null | Distance from previous entry to target |
| `next_distance` | string or null | Distance from target to next entry |
| `target_in_function` | boolean | Whether target is inside a function |
| `function_count` | integer | Total function count |

## candidate_blocks

| Field | Type | Description |
|-------|------|-------------|
| `start` | string | Block start hex |
| `start_offset` | integer | Block start offset |
| `end` | string | Block end hex |
| `end_offset` | integer | Block end offset |
| `terminator_mnemonic` | string or null | Terminator instruction mnemonic |
| `terminator_flow` | string | Terminator flow type |
| `size_bytes` | integer | Block size in bytes |

## boundary_features

| Field | Type | Description |
|-------|------|-------------|
| `target_is_instruction` | boolean | Whether target decodes as an instruction |
| `target_address` | string | Target address hex |
| `reached_from_known_function` | boolean | Whether target is reached from a known function |
| `fall_through_from_previous` | boolean | Whether target falls through from previous instruction |
| `referenced_by_jump_table` | boolean | Whether target is referenced by a jump table |
| `decode_stable_from_boundaries` | boolean | Whether decoding remains stable from existing boundaries |
| `incoming_branch_targets` | array | Incoming branch/call targets |
| `fall_through_relationships` | array | Fall-through relationships |
| `return_like_instructions` | array | Return-like instructions |
| `prologue_like_patterns` | array | Prologue-like patterns |
| `stack_pointer_adjustments` | array | Stack-pointer adjustment patterns |
| `link_register_save_restore` | array | Link-register save/restore patterns |
| `gaps` | array | Gaps in instruction coverage |
| `alignment_consistent` | boolean | Whether instruction alignment is consistent |
| `candidate_block_starts` | array of string | Candidate block start addresses |
| `candidate_block_ends` | array of string | Candidate block end addresses |

## classification

| Field | Type | Description |
|-------|------|-------------|
| `classification` | string | One of the valid classifications |
| `confidence` | number | Confidence score 0.0–1.0 |
| `target` | string | Target address hex |
| `rationale` | array of string | Classification rationale |
| `evidence_summary` | object | Evidence summary |

## evidence

| Field | Type | Description |
|-------|------|-------------|
| `no_fall_through_from_previous` | boolean | No fall-through from previous instruction |
| `has_incoming_control_flow` | boolean | At least one incoming control-flow reference |
| `has_entry_style_pattern` | boolean | Entry-style pattern present |
| `has_plausible_prologue` | boolean | Plausible prologue present |
| `has_stack_link_register_behavior` | boolean | Stack/link-register behavior present |
| `has_coherent_decode` | boolean | Coherent bounded decode |
| `has_coherent_instruction_sequence` | boolean | Coherent instruction sequence |
| `has_entry_from_predecessor` | boolean | Entry from existing/unresolved predecessor |
| `has_internal_cf_consistency` | boolean | Internal control-flow consistency |
| `is_data_pattern` | boolean | Region looks like data |
| `has_implausible_control_flow` | boolean | Implausible control flow |
| `has_dense_contradictory_refs` | boolean | Dense contradictory references |
| `has_pointer_table_pattern` | boolean | Pointer-table pattern |
| `has_decode_instability` | boolean | Decode instability |
| `has_executable_path_evidence` | boolean | Executable path evidence |
| `existing_project_mutation` | boolean | Whether project mutation was reported |

## Valid classifications

| Classification | Meaning |
|----------------|---------|
| `RECOVERABLE_FUNCTION_BODY` | Coherent function body with entry evidence |
| `PROBABLE_FUNCTION_ENTRY` | Probable function entry point |
| `FALL_THROUGH_REGION` | Region reached by fall-through only |
| `JUMP_TABLE_TARGET` | Target of a jump table |
| `SHARED_BASIC_BLOCK` | Shared basic block |
| `MISALIGNED_DECODE` | Misaligned decode region |
| `DATA_AS_CODE` | Data being interpreted as code |
| `UNRESOLVED_CODE_REGION` | Unresolved code region |
| `INSUFFICIENT_EVIDENCE` | Not enough evidence to classify |

## Classification rules

### PROBABLE_FUNCTION_ENTRY requires

- No valid fall-through from a previous instruction
- At least one incoming control-flow reference or entry-style pattern
- Plausible prologue or stack/link-register behavior
- Coherent bounded decode

### RECOVERABLE_FUNCTION_BODY requires

- Coherent instruction sequence
- Evidence of entry from an existing or unresolved predecessor
- Internal control-flow consistency
- No evidence that the region is data

### FALL_THROUGH_REGION requires

- Valid preceding instruction whose fall-through reaches the region
- No independent entry evidence

### DATA_AS_CODE requires strong evidence such as

- Implausible control flow
- Dense invalid or contradictory references
- Pointer-table pattern
- Decode instability
- No executable path evidence

If evidence is mixed, use `INSUFFICIENT_EVIDENCE`.

## Validator gates

The validator (`validate_boundary.py`) fails if:

1. Target differs from `0x60049B90`
2. Analysis window exceeds `0x60049A90`–`0x60049C90`
3. Raw bytes are absent
4. Instruction inventory is empty
5. Classification lacks supporting evidence
6. A probable-function classification is made without control-flow evidence
7. An existing project mutation is reported
8. Addresses are malformed or unsorted
9. Output is not deterministic

## MCore limitations

- MCore instructions are 2 or 4 bytes; alignment is 2-byte.
- The collector does not disassemble new bytes and does not create code units.
- All analysis is bounded to the existing Ghidra instruction inventory within the window.
- No Ghidra project or accepted artifact is modified.
