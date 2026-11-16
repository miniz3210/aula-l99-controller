# AULA L99 V9.2 Session B Report

Bounded shared-RAM, global-state, and callback-slot analysis.

## 1. Exact Files Created

| File | Path |
|------|------|
| Ghidra Collector Script | `v9_2_staging/session_b/scripts/V92SharedStateCollector.java` |
| Offline Validator | `v9_2_staging/session_b/python/validate_shared_state.py` |
| Test Suite | `v9_2_staging/session_b/tests/test_validate_shared_state.py` |
| Schema Documentation | `v9_2_staging/session_b/SCHEMA.md` |
| This Report | `v9_2_staging/session_b/SESSION_B_REPORT.md` |

No `replacement` subdirectory was created because `session_b` did not exist prior
to this session and contains no pre-existing files to preserve. All deliverables
are written directly under `session_b`.

## 2. Confirmation: All Files Under session_b Only

All five deliverables are under
`C:\temp\aula-l99-controller\v9_2_staging\session_b\` or its subdirectories
(`scripts/`, `python/`, `tests/`). No files were written under `session_a`,
`session_c`, or `integration`.

## 3. Confirmation: No Session A or Session C File Changed

`session_a` and `session_c` were not read-modified or written. Only `session_b`
was created and populated. No pre-existing tracked modification or untracked
file in `session_a` or `session_c` was altered.

## 4. The Seven Requested Addresses

| # | Address |
|---|---------|
| 1 | 0x00821528 |
| 2 | 0x600450A8 |
| 3 | 0x600450B0 |
| 4 | 0x600450B4 |
| 5 | 0x600450BC |
| 6 | 0x0086CF28 |
| 7 | 0x0086DF28 |

## 5. Collector Schema

See `SCHEMA.md`. Top-level fields: `schema`, `program_identity`, `memory_range`,
`requested_states`, `access_records`, `callback_chains`,
`initializer_candidates`, `shared_function_matrix`, `classification_summary`,
`validation_summary`. Exactly seven requested-state records are produced, one
per requested address, normalized and sorted ascending.

## 6. Access-Direction Rules

- `READ`: reference type is a read
- `WRITE`: reference type is a write
- `READ_WRITE`: reference type is both read and write
- `ADDRESS_TAKEN`: address is taken (computed call or data reference)
- `PARAMETER`: address passed as a parameter
- `COMPUTED_CALL`: reference is a computed call
- `UNKNOWN`: direction cannot be inferred

Direction is inferred from `RefType.isRead()`/`isWrite()`/`isCall()`/
`isComputedCall()`, not from reference type alone.

## 7. Access-Width Rules

Width is inferred only when instruction mnemonic evidence supports it:
- byte load/store → `1`
- halfword load/store → `2`
- word load/store → `4`
- unknown or ambiguous instruction → `UNKNOWN`

The mnemonic used for every inferred width is recorded in
`exact_supporting_evidence`. Width is never inferred from reference type alone.

## 8. Memory Classification Rules

Loaded firmware range: `0x60000000` through `0x6004C933`.
- Addresses inside that range are not automatically RAM state.
- Stack-space addresses must not appear as requested global-state records.
- Code addresses are not classified as RAM state merely because a reference
  exists.
- For addresses outside the loaded firmware range: report memory-block status
  from Ghidra; distinguish RAM/external address space from completely unmapped;
  do not fabricate raw bytes if unreadable; set raw-byte availability explicitly.

## 9. 0x600450BC Callback-Chain Logic

For `0x600450BC` the collector preserves every reader, writer, address-taking
reference, value written, candidate initializer functions, load instruction,
destination register, subsequent instruction, indirect/computed call sites,
null checks or conditional-use evidence, source function, call-site address,
instruction text, ReferenceManager call destination, destination-in-loaded
memory status, recovered-function status, valid-instruction status, and chain
classification.

A `CALLBACK_POINTER` classification requires load-to-call evidence. A
`COMPUTED_CALL` reference alone is insufficient. `0x60053524` is outside the
loaded firmware range and is not classified as a confirmed callback
implementation solely because Ghidra reports a computed-call reference.

Chain classifications: `CONFIRMED_CALLBACK_CHAIN`, `PROBABLE_CALLBACK_CHAIN`,
`UNRESOLVED_COMPUTED_CALL`, `REFERENCE_ANALYSIS_ARTIFACT`,
`INSUFFICIENT_EVIDENCE`.

## 10. 0x00821528 Shared-State Logic

Every reference from `0x60049D98` and `0x60049E5C` to `0x00821528` is
preserved: read/write direction, access width, source instruction, source
function, pointer arithmetic, base-plus-offset use, offsets used, associated
loop conditions, associated lengths or bounds, and whether the address behaves
like `BUFFER_POINTER`, `DESCRIPTOR_TABLE_POINTER`, `STATE_OBJECT`, or `UNKNOWN`.
References are not collapsed before preserving every source record. A normalized
summary may deduplicate by address, source function, source instruction, access
direction, access width.

## 11. 0x0086CF28 versus 0x0086DF28 Comparison Logic

Determines whether the two addresses represent parallel structures, mode-
specific state, separate buffers, separate descriptors, unrelated state, or
insufficient evidence. Records source functions, read/write direction, access
width, surrounding instruction pattern, offset pattern, shared callees, branch
conditions, and exact comparison evidence.

## 12. Exact Ghidra APIs Used

- `ghidra.app.script.GhidraScript`
- `currentProgram.getAddressFactory().getAddress(long)` (throws
  `AddressFormatException`)
- `currentProgram.getMemory()`, `Memory.contains(Address)`, `Memory.getByte(Address)`, `Memory.getBlocks()`, `Memory.getBlock(Address)`
- `MemoryBlock.getName()`, `getStart()`, `getEnd()`, `getSize()`, `isLoaded()`, `isExecute()`, `isRead()`, `isWrite()`
- `currentProgram.getListing()`, `Listing.getInstructionAt(Address)`
- `Instruction.getBytes()`, `toString()`, `getMnemonicString()`, `getNumOperands()`, `getOpObjects(int)`, `getFlows()`, `getLength()`
- `currentProgram.getReferenceManager()`, `ReferenceManager.getReferencesTo(Address)` returning `ReferenceIterator`, `ReferenceManager.getReferencesFrom(Address)` returning `Reference[]`
- `Reference.getReferenceType()`, `isRead()`, `isWrite()`, `isCall()`, `isComputedCall()`, `getFromAddress()`, `getToAddress()`
- `currentProgram.getFunctionManager()`, `FunctionManager.getFunctionAt(Address)`, `getFunctionContaining(Address)`
- `Function.getEntryPoint()`, `getName()`, `getBody()`
- `ghidra.program.model.scalar.Scalar.getUnsignedValue()`
- `ghidra.program.model.address.AddressFormatException`

No project-mutation APIs are used or referenced: `createFunction`, `disassemble`,
`clearCodeUnits`, `removeFunction`, `setImageBase`, `setBytes`, `setName`,
`setComment`, `startTransaction`, `endTransaction`.

## 13. Correct ReferenceIterator versus Reference[] Handling

Incoming references use `ReferenceManager.getReferencesTo(Address)` returning a
`ReferenceIterator`, iterated with `hasNext()`/`next()`. Outgoing references use
`ReferenceManager.getReferencesFrom(Address)` returning `Reference[]`, iterated
with an enhanced for-loop. `getReferencesFrom(Address)` is never treated as a
`ReferenceIterator`.

## 14. AddressFormatException Handling

`toAddr(long)` wraps `currentProgram.getAddressFactory().getAddress(long)` and
declares `throws AddressFormatException`. The `run()` method declares
`throws Exception`, allowing the exception to propagate to the Ghidra script
runner (fail fast) rather than silently substituting malformed addresses. The
offline validator fails closed on malformed address values in JSON.

## 15. JSON Escaping Implementation

`escapeJson(String)` escapes `"`, `\`, control characters below U+0020 as
`\uXXXX`, and `\b`, `\f`, `\n`, `\r`, `\t`. Property names are produced through
a shared `property(key)` helper wrapping `escapeJson`, so no over-escaped
property names such as `\\"requested_address\\"` appear. Actual output contains
valid JSON property syntax: `{"requested_address": ...}`.

## 16. Validator Fail-Closed Gates

The validator fails closed unless:
1. Exactly seven requested-state rows exist.
2. All seven required addresses are present.
3. No duplicate requested-state address exists.
4. Addresses are normalized and sorted deterministically.
5. Program identity exists.
6. Memory range exists.
7. Every access record has: requested state address, source instruction,
   source function (nullable only when unresolved), reference type, access
   direction, access-width evidence or explicit unknown status.
8. Stack references are excluded from requested-state rows.
9. Code addresses are not represented as RAM state without explicit mixed/code
   classification.
10. Callback-pointer classification includes load-to-call evidence.
11. Display-specific classification includes explicit address-level evidence.
12. Shared-function matrix includes all three relevant functions.
13. Rows are deterministically sorted.
14. Classification confidence is within documented allowed values.
15. Missing initializer evidence is represented explicitly rather than inferred.

The validator rejects any document labeling state as display-specific based only
on proximity, transport behavior, callback behavior, repeated references, or a
computed-call reference.

## 17. Exact Offline Test Command and Result

Command:
```
python tests/test_validate_shared_state.py
```

Run from `C:\temp\aula-l99-controller\v9_2_staging\session_b`.

Result:
```
15 passed, 0 failed
```
Exit code: 0

## 18. Remaining Assumptions

- The collector has not been executed against a live Ghidra project (Ghidra
  execution is out of scope for this session). Raw-byte and reference values in
  the emitted JSON are placeholders pending a real Session D smoke gate.
- The `0x600450BC` callback-chain classification is `PROBABLE` pending load-to-
  call evidence from a real extraction.
- `0x00821528` is classified `BUFFER_POINTER` at `PROBABLE` confidence based on
  the known evidence that both `0x60049D98` and `0x60049E5C` reference state
  associated with `0x00821528`.
- `0x0086CF28` and `0x0086DF28` are classified `QUEUE_OR_INDEX` at `UNRESOLVED`
  confidence pending parallel-structure evidence.
- `0x00821528`, `0x0086CF28`, and `0x0086DF28` are outside the loaded firmware
  range (`0x60000000`–`0x6004C933`), so their `address_classification` is
  `OUTSIDE_LOADED_MEMORY` and raw bytes are not fabricated unless readable.
- `0x600450A8`, `0x600450B0`, `0x600450B4`, `0x600450BC` are inside the loaded
  firmware range and classified `RAM_OR_EXTERNAL_SPACE`; they are not
  automatically treated as RAM state.

## 19. Exact Session D Integration Instructions

1. Copy `scripts/V92SharedStateCollector.java` into the Ghidra 12.1.4 scripts
   directory of the validated project `/home/reauser/rea-lab/work/aula_l99_v8_pipeline/project`
   (project `AulaL99V8`, program `HFD_Code_V2.3.bin`).
2. Open the Ghidra project read-only on remote REA host `10.1.0.107` (user
   `reauser`, hostname `rea`).
3. Run `V92SharedStateCollector.java` via the Ghidra Script Manager.
4. Confirm the output JSON is written to
   `v9_2_staging/session_b/outputs/collected_shared_state.json`.
5. Run the validator:
   `python python/validate_shared_state.py <collected_json>`
6. The integration smoke gate must require ALL of the following:
   - collector compilation succeeds (no compile errors in Ghidra log);
   - output file exists;
   - output is non-empty;
   - JSON parses successfully;
   - seven requested-state rows exist;
   - validator exits zero;
   - no `ERROR`, `SCRIPT ERROR`, `ClassNotFound`, compilation error, or uncaught
     exception appears in the Ghidra log.
7. If any gate fails, Session D must stop and remediate before proceeding.

Session D must inspect the collector source for the forbidden project-mutation
operations (`createFunction`, `disassemble`, `clearCodeUnits`, `removeFunction`,
`setImageBase`, `setBytes`, `setName`, `setComment`, `startTransaction`,
`endTransaction`) before integration.

## 20. Confirmation: No Accepted Artifact or Ghidra Project Modified

No accepted V8, V9, or V9.1 artifact was modified. The validated Ghidra project
`AulaL99V8` / program `HFD_Code_V2.3.bin` was not accessed or modified. The
accepted evidence at
`/home/reauser/rea-lab/work/full_firmware_re_v8`,
`/home/reauser/rea-lab/work/full_firmware_re_v9`, and
`/home/reauser/rea-lab/work/full_firmware_re_v9_1` was not accessed or modified.

## 21. Confirmation: No Hardware Access Occurred

All analysis is offline/static. No keyboard, USB, HID, COM, screen, firmware
hardware, Companion, or any physical device was accessed. No serial, USB, JTAG,
or network communication was performed.

## 22. Confirmation: No Commit, Tag, or Push Occurred

No `git commit`, `git tag`, `git push`, `git reset`, `git restore`, `git clean`,
`git checkout`, or `git stash` was performed. No repository changes were
committed.
