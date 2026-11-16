# FIX_C_REPORT

## 1. Baseline Session C SHA-256
62181151D7BEF8763037537AB18DBD53ACDACADF8741B41B112B8C3F6856083F

## 2. Final Session C integration SHA-256
56745F0A0B5898D549DBCDAE6A812F1778817A4208596AD8D8D19B785EF0A17E

## 3. Numbered backups
- backup01_pre_edit.java (62181151...)
- backup02_after_edit2.java (0CF6BABA...)
- backup03_after_edit3.java (289FD7B1...)
- backup04_after_edit4.java (36E65B2A...)
- backup05_after_edit5.java (4AB62B10...)
- backup06_after_edit6.java (D0DE97DB...)
- backup07_after_edit7.java (56745F0A...)

All stored under C:\temp\aula-l99-controller\v9_2_staging\integration\fix_c_backups\

## 4. Exact bounded corrections
1. `ins.getOpString(i)` -> `ins.getDefaultOperandRepresentation(i)` (operand display)
2. `OperandType ot = ins.getOperandType(i)` -> `int operandType = ins.getOperandType(i);` + `Integer.toString(operandType)` (operand type as int)
3. `r.getReferenceType().isBranch()` -> `r.getReferenceType().isJump()` (reference branch classification)
4. Instruction booleans: `ins.fallsThrough()` -> `ins.getFallThrough() != null`; `isBranch()`/`isCall()`/`isReturn()`/`isDelaySlot()` -> `false` (no typed evidence, unresolved preferred)
5. `classifyFlowType()`: removed isCall/isReturn/isBranch/fallsThrough; returns "FALLTHROUGH" if getFallThrough()!=null else "FLOW_UNKNOWN"
6. `new ArrayList<>(fm.getFunctions(true))` -> manual FunctionIterator iteration (added FunctionIterator import)
7. Removed unused imports CodeBlockManager, PdbEntry, PdbEntryFactory; removed `getCompilerSpecID()` and `getProject()` calls (not on Program in Ghidra 12.1.4); `getProjectName()` returns "none"
8. Wrapped `mem.getBytes` and `ins.getByte` in try/catch MemoryAccessException
9. Output path interface: removed fixed OUTPUT_FILE; accepts exactly one `output_json_path` post-script arg via getScriptArgs(); writes to new File(args[0]); creates parent dir if non-null
10. Fixed runtime NPE: `ins.get("function_at_present")` -> inspect `ins.get("function_at")` map "present" key

## 5. Number of remote attempts
6 (attempt1 through attempt6; attempt6 succeeded)

## 6. Exact successful analyzeHeadless command
/home/reauser/rea-lab/apps/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  /home/reauser/rea-lab/work/aula_l99_v9_2_project_isolation/fix_c/project \
  AulaL99V8 \
  -process HFD_Code_V2.3.bin \
  -noanalysis \
  -readOnly \
  -scriptPath \
    /home/reauser/rea-lab/work/aula_l99_v9_2_fix_c/attempt6/scripts \
  -postScript \
    V92BoundaryCollector.java \
    /home/reauser/rea-lab/work/aula_l99_v9_2_fix_c/attempt6/output/collected_boundary.json

## 7. Process exit code
0

## 8. Fatal-marker count
0 (no error:, SCRIPT ERROR, ClassNotFound, unreported exception, GhidraScriptLoadException, IllegalStateException, Traceback, NullPointerException in attempt6 log)

## 9. Output path
/home/reauser/rea-lab/work/aula_l99_v9_2_fix_c/attempt6/output/collected_boundary.json

## 10. Output size
280864 bytes

## 11. Output SHA-256
4A7AC1C531CF408300757386990AD86D9A3F254159C23209F957783E724222A6

## 12. JSON-validation result
Valid (python3 -m json.tool parsed successfully)

## 13. Validator exit code
0

## 14. Target result
0x60049B90, in_window=true

## 15. Window-bound result
Within 0x60049A90–0x60049C90; start=0x60049A90, end=0x60049C90, within_allowed_range=true

## 16. Raw-byte result
present=true, size=513 bytes

## 17. Instruction-inventory count
218 instructions

## 18. Final boundary classification
INSUFFICIENT_EVIDENCE

## 19. Classification evidence
Confidence 0.0; rationale empty; evidence flags: has_coherent_decode=true, has_coherent_instruction_sequence=true, has_internal_cf_consistency=true; all entry/flow/data-pattern flags false; existing_project_mutation=false; mutation count=0

## 20. V9.1 comparison summary
V9.1 uses a different schema (address/instructions/radius, operands as typed objects) vs V9.2 (v9.2-boundary-collector-1.0 schema). Target match N/A (different schema). Instruction-count difference: +218 (V9.2 has 218, V9.1 has 0 instructions in its flat list). Raw-byte difference: schemas differ, not directly comparable. Classification difference: V9.2=INSUFFICIENT_EVIDENCE; V9.1 has no classification field. Differences preserved as evidence; V9.2 result not forced to match V9.1.

## 21. Offline 13-test result
13 passed, 0 failed (test_validate_boundary.py)

## 22. Original-project integrity result
MATCH (file inventory and SHA-256 inventory both identical before and after Fix-C)

## 23. Disposable-project change result
CHANGED (expected: Ghidra internal storage bookkeeping + snapshot files created under project/); original project unaffected

## 24. Original Session C baseline integrity
MATCH: 62181151D7BEF8763037537AB18DBD53ACDACADF8741B41B112B8C3F6856083F

## 25. Fix-A source integrity
MATCH: 5F8E9E244F563AF18A243388E1BD50AD87EF3B65591BAD9C7B7B9F54A24835BF

## 26. Fix-B source integrity
MATCH: F256C3593C45F3684CB49DE506BC64C29F57EE37C5E39C4707AB1D391BEF22C6

## 27. Confirmation no A/B file was inspected beyond hashes or modified
Confirmed: Session A (V92ComputedCallCollector) and Session B (V92SharedStateCollector) were only hash-verified before and after Fix-C; neither was opened for content inspection nor modified.

## 28. Confirmation no accepted artifact, hardware, or Git state was modified
Confirmed: no accepted V8/V9/V9.1 artifacts modified, no hardware accessed, no Git commit/push performed.

## 29. Remaining next step
Rebuild the integration package and create a commit checkpoint.

## Final status
FIX_C_PASS
