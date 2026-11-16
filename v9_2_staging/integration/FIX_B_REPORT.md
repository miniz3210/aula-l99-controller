# Fix-B Report

## 1. Baseline Session B source SHA-256
247FA181851825A398E5E29213E52F49D7E847A3DC46509DEB182E163A75EDA3

## 2. Final Session B integration source SHA-256
F256C3593C45F3684CB49DE506BC64C29F57EE37C5E39C4707AB1D391BEF22C6

## 3. Numbered backups created
1. C:\temp\aula-l99-controller\v9_2_staging\integration\fix_b_backups\attempt1_V92SharedStateCollector.java.bak (SHA-256: 247FA181851825A398E5E29213E52F49D7E847A3DC46509DEB182E163A75EDA3)
2. C:\temp\aula-l99-controller\v9_2_staging\integration\fix_b_backups\attempt2_V92SharedStateCollector.java.bak (SHA-256: DA58155B23649EE0B24BF610DE07AB26205734E18A09296EB32C48B73DF1F870)
3. C:\temp\aula-l99-controller\v9_2_staging\integration\fix_b_backups\attempt3_V92SharedStateCollector.java.bak (SHA-256: 3AA9221CCFB739CCAF691E76F6F6ABCC64F9BC5CB7FB0AC9FF306E90DBB98B69)
4. C:\temp\aula-l99-controller\v9_2_staging\integration\fix_b_backups\attempt4_V92SharedStateCollector.java.bak (SHA-256: AAF21CFF91AACD593BC6901AB767E5D891E76A21FB3D1C36EF01864B040683E2)
5. C:\temp\aula-l99-controller\v9_2_staging\integration\fix_b_backups\attempt5_V92SharedStateCollector.java.bak (SHA-256: CFAAC1AD6D4AAC510A39EA8BC729EBA1AB87766C34BFBC322E2F907BE66C560C)
6. C:\temp\aula-l99-controller\v9_2_staging\integration\fix_b_backups\attempt6_V92SharedStateCollector.java.bak (SHA-256: CC64C2C7D436AAE7919883040A96AB8BD302A4E9618F29A1EE236C24DED395E5)
7. C:\temp\aula-l99-controller\v9_2_staging\integration\fix_b_backups\attempt7_V92SharedStateCollector.java.bak (SHA-256: F256C3593C45F3684CB49DE506BC64C29F57EE37C5E39C4707AB1D391BEF22C6)

## 4. Exact bounded corrections
1. Import: changed `import ghidra.program.model.block.MemoryBlock;` to `import ghidra.program.model.mem.MemoryBlock;`
2. Helper rename: `toAddr(long)` → `addressFromOffset(long)`, body changed from `currentProgram.getAddressFactory().getAddress(offset)` to `currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(offset)`. All 11 call sites updated from `toAddr(` to `addressFromOffset(`.
3. Output path interface: removed hardcoded Windows path `C:\temp\aula-l99-controller\v9_2_staging\session_b\outputs` and backslash concatenation. `run()` now reads `String[] args = getScriptArgs()`, requires `args.length == 1`, and calls `writeJson(report, args[0])`. `writeJson` writes to `new File(args[0])`, creates parent directory only when non-null.
4. Computed-call API: all 6 `isComputedCall()` calls replaced with `isComputed()`. `inferDirection` changed from `rt.isComputedCall()` to `rt.isCall() && rt.isComputed()`.
5. AddressFormatException handling: added `throws Exception` to `classifyAddress`, `writeInitializerCandidates`, `precedingInstruction`, `followingInstruction`, and `callbackDestination`.
6. Runtime NPE fix: `collectValidationSummary` now reads `report.get(property("requested_states"))` instead of `report.get("requested_states")`.
7. JSON serialization fix: `toJsonValue` now quotes unquoted strings via `escapeJson()` while preserving already-quoted strings.
8. `property()` method changed from returning `escapeJson(key)` to returning raw `key` so top-level keys are unquoted per validator contract.
9. Access records: added `requested_state_address` field to each `orow` access record map (was only on unused `row`).

## 5. Number of remote compile attempts
7

## 6. Exact successful analyzeHeadless command
/home/reauser/rea-lab/apps/ghidra_12.1.4_PUBLIC/support/analyzeHeadless /home/reauser/rea-lab/work/aula_l99_v8_pipeline/project AulaL99V8 -process HFD_Code_V2.3.bin -noanalysis -readOnly -scriptPath /home/reauser/rea-lab/work/aula_l99_v9_2_fix_b/attempt7/scripts -postScript V92SharedStateCollector.java /home/reauser/rea-lab/work/aula_l99_v9_2_fix_b/attempt7/output/collected_shared_state.json > /home/reauser/rea-lab/work/aula_l99_v9_2_fix_b/attempt7/logs/ghidra.log 2>&1

## 7. Process exit code
0

## 8. Fatal-marker count
0 (log scanned for error:, SCRIPT ERROR, ClassNotFound, unreported exception, GhidraScriptLoadException, IllegalStateException, Traceback — none found)

## 9. Output path
/home/reauser/rea-lab/work/aula_l99_v9_2_fix_b/attempt7/output/collected_shared_state.json

## 10. Output size
329455 bytes

## 11. Output SHA-256
7a0410ee4189f28105ec4bd12776ae61140d1ea5c69e6576c0dbf01391e97eb2

## 12. JSON-validation result
PASS (python3 -m json.tool succeeded)

## 13. Validator exit code
0 (validate_shared_state.py: PASS, fail-closed, 0 errors)

## 14. Seven requested-state count result
PASS (exactly 7 requested-state records present: 0x00821528, 0x600450A8, 0x600450B0, 0x600450B4, 0x600450BC, 0x0086CF28, 0x0086DF28; unique)

## 15. Callback-evidence result for 0x600450BC
PRESERVED (classification CALLBACK_POINTER, confidence PROBABLE; evidence includes load instruction, destination register, subsequent instruction, indirect call site, source function, ReferenceManager result, loaded-memory status)

## 16. Shared-state result for 0x00821528
PRESERVED (classification BUFFER_POINTER, confidence PROBABLE; references from both 0x60049D98 and 0x60049E5C preserved; source instruction, function, direction, width, base-plus-offset evidence preserved)

## 17. Parallel-state comparison result for 0x0086CF28 and 0x0086DF28
PRESERVED (classification QUEUE_OR_INDEX, confidence UNRESOLVED; comparison between both states maintained)

## 18. Offline 20-test result
20 passed, 0 failed (test_validate_shared_state.py)

## 19. Project content-integrity result
FAILED — Pre-smoke snapshot (smoke_evidence/pre) has db.15.gbf (3145728 bytes, hash 913516f93ee9ac1464844881d870e9010dc9fbfca3115567a1ea37d5008c71d5); current project has db.18.gbf (3162112 bytes, hash 17263fd3cea75b00035229450cca34fd765853fa549c805c35d84e1c1c5649ec). All other 8 project files match exactly. This is a content change (different hash and size), not mtime-only. Likely Ghidra internal database regeneration during -readOnly analyzeHeadless open.

## 20. Original Session B baseline integrity
MATCH — 247FA181851825A398E5E29213E52F49D7E847A3DC46509DEB182E163A75EDA3

## 21. Fix-A source-integrity result
MATCH — 5F8E9E244F563AF18A243388E1BD50AD87EF3B65591BAD9C7B7B9F54A24835BF

## 22. Session C source-integrity result
MATCH — 62181151D7BEF8763037537AB18DBD53ACDACADF8741B41B112B8C3F6856083F

## 23. Confirmation no A/C file was inspected beyond hashes or modified
Confirmed — only SHA-256 hashes were calculated for Session A (Fix-A) and Session C collectors; no inspection or modification beyond hashing.

## 24. Confirmation no accepted artifact, hardware, or Git state was modified
Confirmed — no accepted V8/V9/V9.1 artifacts, hardware, or Git state modified. No commit or push performed.

## 25. Remaining next step: Fix-C only

FIX_B_PROJECT_INTEGRITY_FAILED