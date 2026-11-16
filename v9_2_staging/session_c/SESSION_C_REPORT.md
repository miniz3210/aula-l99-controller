# AULA L99 V9.2 Session C Report

## 1. Exact Files Created

| File | Path |
|------|------|
| Ghidra Collector Script | `v9_2_staging/session_c/scripts/V92BoundaryCollector.java` |
| Offline Validator | `v9_2_staging/session_c/python/validate_boundary.py` |
| Schema Documentation | `v9_2_staging/session_c/SCHEMA.md` |
| Test Suite | `v9_2_staging/session_c/tests/test_validate_boundary.py` |
| This Report | `v9_2_staging/session_c/SESSION_C_REPORT.md` |

## 2. Boundary Classification Model

The collector classifies the target address `0x60049B90` into one of nine categories:

| Classification | Requirements |
|----------------|--------------|
| `RECOVERABLE_FUNCTION_BODY` | Coherent instruction sequence; evidence of entry from existing/unresolved predecessor; internal CF consistency; no data evidence |
| `PROBABLE_FUNCTION_ENTRY` | No valid fall-through from previous; ≥1 incoming CF reference or entry-style pattern; plausible prologue/stack-LR behavior; coherent bounded decode |
| `FALL_THROUGH_REGION` | Valid preceding instruction whose fall-through reaches region; no independent entry evidence |
| `JUMP_TABLE_TARGET` | Referenced by jump table pattern |
| `SHARED_BASIC_BLOCK` | Shared basic block structure |
| `MISALIGNED_DECODE` | Alignment inconsistency detected |
| `DATA_AS_CODE` | Strong evidence: implausible CF, dense contradictory refs, pointer-table pattern, decode instability, no executable path |
| `UNRESOLVED_CODE_REGION` | Code region without clear boundaries |
| `INSUFFICIENT_EVIDENCE` | Mixed or insufficient evidence (default) |

## 3. Ghidra APIs Used

| API | Purpose |
|-----|---------|
| `currentProgram.getListing()` | Instruction enumeration |
| `currentProgram.getMemory()` | Raw byte reading |
| `currentProgram.getFunctionManager()` | Function queries |
| `currentProgram.getReferenceManager()` | Reference traversal |
| `Instruction.getFlows()` | Control-flow targets |
| `Instruction.fallsThrough()` | Fall-through detection |
| `Instruction.isBranch()`, `isCall()`, `isReturn()` | Flow type classification |
| `Function.getEntryPoint()`, `getBody()` | Function boundaries |
| `Reference.getReferenceType()` | Reference type inspection |

## 4. Evidence Rules

### Prologue-like Patterns
- Mnemonics containing: `save`, `jsri`, `storesp`, `push`, `move`
- Detected at any instruction in window

### Return-like Instructions
- `ins.isReturn()` == true

### Stack-Pointer Adjustments
- Mnemonics: `addsp`, `subsp`, `add`, `sub` with operand containing `sp`

### Link-Register Save/Restore
- Mnemonics: `store`, `load` with operand containing `lr`

### Fall-Through Detection
- `ins.fallsThrough()` == true and next instruction starts at `insEnd + 1`

### Alignment Consistency
- All instructions must be 2 or 4 bytes (MCore requirement)

## 5. Validator Gates

The validator fails if any of these conditions are met:

1. ✅ Target differs from `0x60049B90`
2. ✅ Window exceeds `0x60049A90`–`0x60049C90`
3. ✅ Raw bytes absent
4. ✅ Instruction inventory empty
5. ✅ Classification lacks `evidence_summary`
6. ✅ `PROBABLE_FUNCTION_ENTRY` without `has_incoming_control_flow` evidence
7. ✅ Mutation markers present in `mutations_reported` or `boundary_features.existing_project_mutation`
8. ✅ Addresses malformed or unsorted
9. ✅ Output not deterministic under re-serialization

## 6. Tests Run and Exact Results

```
PASS: test_correct_target_required
PASS: test_window_bounded
PASS: test_raw_bytes_required
PASS: test_instruction_inventory_required
PASS: test_address_sorting
PASS: test_fall_through_classification
PASS: test_probable_entry_requires_incoming_flow
PASS: test_data_as_code_requires_strong_evidence
PASS: test_missing_evidence_causes_rejection
PASS: test_deterministic_output
PASS: test_no_mutation_markers_permitted
PASS: test_empty_nearest_function_handled
PASS: test_valid_document_passes

13 passed, 0 failed
```

All 13 required test cases pass.

## 7. Known MCore Limitations

- MCore instructions are 2 or 4 bytes with 2-byte alignment
- Collector does not disassemble new bytes
- Collector does not create code units
- All analysis bounded to existing Ghidra instruction inventory within window
- Delay slots not explicitly modeled beyond `isDelaySlot()` check
- Jump table detection limited to reference type string matching

## 8. Integration Instructions for Session D

1. Copy `V92BoundaryCollector.java` to Ghidra scripts directory
2. Open Ghidra project `AulaL99V8` with program `HFD_Code_V2.3.bin`
3. Run script via Script Manager (Window → Script Manager)
4. Output JSON written to `V92BoundaryCollector_output.json` in project directory
5. Run validator: `python validate_boundary.py V92BoundaryCollector_output.json`
6. Validator returns exit code 0 on success, 1 on failure with stderr details

## 9. Confirmation: No Function or Instruction Created

The collector is **read-only**. It:
- Does not call `createFunction()`, `disassemble()`, `setCodeUnit()`
- Does not modify `Listing`, `FunctionManager`, or `CodeUnit` state
- Only queries existing instructions, functions, and references

## 10. Confirmation: No Ghidra Project or Accepted Artifact Modified

- The collector runs as a GhidraScript with no write operations
- The V9.1 boundary artifact at `/home/reauser/rea-lab/work/full_firmware_re_v9_1/boundary_0x60049b90.json` was not accessed or modified
- The Ghidra project `AulaL99V8` is opened read-only

## 11. Confirmation: No Hardware Access Occurred

- All analysis is offline/static using Ghidra's program database
- No serial, USB, JTAG, or network communication performed
- No external process execution beyond Ghidra script runtime