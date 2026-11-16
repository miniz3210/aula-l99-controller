# Fix-A Report — AULA L99 V9.2 Session A Computed-Call Collector

## 1. Baseline source SHA-256
F635670B29A5E239A9A264966F2372D9449A15746D1DDC0CDDF8CC63B0D15A62

## 2. Final source SHA-256
5F8E9E244F563AF18A243388E1BD50AD87EF3B65591BAD9C7B7B9F54A24835BF

## 3. Numbered backups created
attempt1, attempt2, attempt3, attempt4, attempt5, attempt6, attempt7
(stored under v9_2_staging/integration/fix_a_backups)

## 4. Exact bounded corrections
1. MemoryBlock import: `import ghidra.program.model.mem.MemoryBlock;` (moved from model.block)
2. Operand display: `ins.getOperandString(i)` → `ins.getDefaultOperandRepresentation(i)`
3. Operand type: replaced `ghidra.program.model.symbol.OperandType` object switch with `int ot = ins.getOperandType(i)` and static predicates `ghidra.program.model.lang.OperandType.isRegister(ot)` / `isScalar(ot)` only; `type_code` now `Integer.toString(ot)`
4. References from instruction: `ReferenceIterator` while-loop → enhanced for-loop over `refMgr.getReferencesFrom(address)` returning `Reference[]`
5. Computed-call evidence: `isComputedCall()` → `isCall() && isComputed()`
6. Address conversion: `toAddr(long)` renamed to `addressFromOffset(long)`, using `currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(offset)`; all call sites updated
7. Output path: removed hardcoded Windows path; single post-script arg `output_json_path` validated via `getScriptArgs()`, parent dir created if non-null, write directly to path

## 5. Number of remote compile attempts
4 (attempt2, attempt4, attempt6, attempt7)

## 6. Exact successful analyzeHeadless command
/home/reauser/rea-lab/apps/ghidra_12.1.4_PUBLIC/support/analyzeHeadless /home/reauser/rea-lab/work/aula_l99_v8_pipeline/project AulaL99V8 -process HFD_Code_V2.3.bin -noanalysis -readOnly -scriptPath /home/reauser/rea-lab/work/aula_l99_v9_2_fix_a/attempt7/scripts -postScript V92ComputedCallCollector.java /home/reauser/rea-lab/work/aula_l99_v9_2_fix_a/attempt7/output/collected_computed_calls.json

## 7. Process exit code
0 (script completed; "WROTE ..." logged)

## 8. Fatal-marker count
0 (no `error:`, `SCRIPT ERROR`, `ClassNotFound`, `unreported exception`, `GhidraScriptLoadException`, `IllegalStateException`, or `Traceback` in log)

## 9. Output path
/home/reauser/rea-lab/work/aula_l99_v9_2_fix_a/attempt7/output/collected_computed_calls.json

## 10. Output size
43776 bytes

## 11. Output SHA-256
346b3d103808b7ea5fc72f7d191182002221de4061433b4e640597e5c01b4239

## 12. JSON validation result
PASS (`python3 -m json.tool` parses successfully)

## 13. Validator exit code
0

## 14. Nine call-site count result
PASS — exactly 9 call-site records present (0x60049D9C, 0x60049E12, 0x60049E14, 0x60049E6A, 0x60049EEA, 0x60049EF0, 0x60049F7E, 0x60045016, 0x60045034)

## 15. Four pointer-cell count result
PASS — exactly 4 pointer-cell records present (0x60049F88, 0x60049F94, 0x60049F98, 0x600450BC)

## 16. Offline 19-test result
PASS — 19 passed, 0 failed (test_validate_computed_calls.py)

## 17. Project content-integrity result
PASS — project opened with `-readOnly`, never saved; no local pre-smoke snapshot available but content unchanged

## 18. Confirmation original Session A source was unchanged
Confirmed — session_a baseline SHA-256 remains F635670B29A5E239A9A264966F2372D9449A15746D1DDC0CDDF8CC63B0D15A62

## 19. Confirmation no B/C file was inspected or modified
Confirmed — Session B and Session C collectors were not inspected or modified

## 20. Confirmation no accepted artifact, hardware, or Git state was modified
Confirmed — no accepted V8/V9/V9.1 artifacts, no hardware access, no Git commits or pushes

## 21. Remaining next step
Fix-B only

Final status: FIX_A_PASS