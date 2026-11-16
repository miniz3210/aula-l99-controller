import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressFormatException;
import ghidra.program.model.block.MemoryBlock;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.ReferenceManager;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.scalar.Scalar;

import java.io.BufferedWriter;
import java.io.OutputStreamWriter;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;

public class V92ComputedCallCollector extends GhidraScript {

    private static final long IMAGE_BASE = 0x60000000L;
    private static final long IMAGE_END = 0x6004C933L;

    private static final long[] CALL_SITES = {
        0x60049D9CL, 0x60049E12L, 0x60049E14L, 0x60049E6AL, 0x60049EEAL,
        0x60049EF0L, 0x60049F7EL, 0x60045016L, 0x60045034L
    };

    private static final long[] POINTER_CELLS = {
        0x60049F88L, 0x60049F94L, 0x60049F98L, 0x600450BCL
    };

    private final Map<Long, String> ghidraComputed = new LinkedHashMap<>();

    private String toHex(long v) {
        return "0x" + Long.toHexString(v);
    }

    private String toHex8(long v) {
        return String.format("0x%08X", v);
    }

    private boolean inLoadedMemory(long v) {
        return v >= IMAGE_BASE && v <= IMAGE_END;
    }

    private String operandTypeString(ghidra.program.model.symbol.OperandType ot) {
        if (ot == null) return "other";
        switch (ot) {
            case REGISTER: return "register";
            case SCALAR: return "scalar";
            case MEMORY: return "memory address";
            case CODE_ADDRESS: return "code address";
            case DATA_ADDRESS: return "data address";
            case EXTERNAL_ADDRESS: return "external or out-of-range address";
            case UNDEFINED: return "other";
            default: return "other";
        }
    }

    private String confidenceClass(long computedDest, boolean inRange, boolean hasFunction, boolean validInsn, boolean refOnly) {
        if (!inRange) return "OUT_OF_RANGE_COMPUTED_INTERPRETATION";
        if (refOnly && !hasFunction && !validInsn) return "POSSIBLE_MCORE_REFERENCE_ANALYSIS_ERROR";
        if (hasFunction && validInsn) return "DIRECT_IN_RANGE_CALL";
        if (hasFunction || validInsn) return "POINTER_CELL_IN_RANGE_CALL";
        return "UNRESOLVED";
    }

    @Override
    public void run() throws Exception {
        Memory memory = currentProgram.getMemory();
        Listing listing = currentProgram.getListing();
        ReferenceManager refMgr = currentProgram.getReferenceManager();
        FunctionManager funcMgr = currentProgram.getFunctionManager();

        ghidraComputed.clear();
        ghidraComputed.put(0x60049D9CL, toHex8(0x6004D08CL));
        ghidraComputed.put(0x60049E14L, toHex8(0x6004D140L));
        ghidraComputed.put(0x60045016L, toHex8(0x60053524L));
        ghidraComputed.put(0x60044FECL, toHex8(0x60044FECL));

        Map<String, Object> report = new LinkedHashMap<>();
        report.put("schema", "V92ComputedCallCollector.v1");
        report.put("program_identity", programIdentity());
        report.put("memory_range", memoryRange(memory));
        report.put("call_sites", collectCallSites(listing, refMgr, funcMgr, memory));
        report.put("pointer_cells", collectPointerCells(refMgr, listing, funcMgr, memory));
        report.put("computed_destinations", collectComputedDestinations(memory, funcMgr, listing));
        report.put("validation_summary", validationSummary(
                (List<Map<String, Object>>) report.get("call_sites"),
                (List<Map<String, Object>>) report.get("pointer_cells")));

        writeJson(report);
    }

    private Map<String, Object> programIdentity() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("program", currentProgram.getName());
        m.put("domain", currentProgram.getDomainFile() == null ? null : currentProgram.getDomainFile().getName());
        m.put("language", currentProgram.getLanguageID() == null ? null : currentProgram.getLanguageID().toString());
        m.put("compiler", currentProgram.getCompilerSpec() == null ? null : currentProgram.getCompilerSpec().toString());
        m.put("image_base", toHex8(IMAGE_BASE));
        m.put("image_end", toHex8(IMAGE_END));
        m.put("size_bytes", (IMAGE_END - IMAGE_BASE + 1));
        return m;
    }

    private Map<String, Object> memoryRange(Memory memory) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("loaded_start", toHex8(IMAGE_BASE));
        m.put("loaded_end", toHex8(IMAGE_END));
        m.put("size_bytes", (IMAGE_END - IMAGE_BASE + 1));
        List<Map<String, Object>> blocks = new ArrayList<>();
        for (MemoryBlock block : memory.getBlocks()) {
            Map<String, Object> bm = new LinkedHashMap<>();
            bm.put("name", block.getName());
            bm.put("start", toHex8(block.getStart().getOffset()));
            bm.put("end", toHex8(block.getEnd().getOffset()));
            bm.put("size", block.getSize());
            bm.put("is_loaded", block.isLoaded());
            bm.put("is_executable", block.isExecute());
            bm.put("is_readable", block.isRead());
            bm.put("is_writable", block.isWrite());
            blocks.add(bm);
        }
        m.put("memory_blocks", blocks);
        return m;
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> collectCallSites(Listing listing, ReferenceManager refMgr,
            FunctionManager funcMgr, Memory memory) throws Exception {
        List<Map<String, Object>> rows = new ArrayList<>();
        for (long siteAddr : CALL_SITES) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("caller_function_entry", null);
            row.put("caller_function_name", null);
            row.put("call_site_address", toHex8(siteAddr));
            row.put("raw_instruction_bytes", null);
            row.put("instruction_text", null);
            row.put("mnemonic", null);
            row.put("operands", new ArrayList<>());
            row.put("instruction_flows", new ArrayList<>());
            row.put("references", new ArrayList<>());
            row.put("pointer_cell_loaded_near_call", null);
            row.put("pointer_cell_raw_bytes", null);
            row.put("pointer_cell_decoded_16_le", null);
            row.put("pointer_cell_decoded_16_be", null);
            row.put("pointer_cell_decoded_32_le", null);
            row.put("pointer_cell_decoded_32_be", null);
            row.put("pointer_cell_memory_block", null);
            row.put("computed_destination", null);
            row.put("computed_destination_in_loaded_memory", null);
            row.put("recovered_function_at_destination", null);
            row.put("recovered_function_name", null);
            row.put("valid_instruction_at_destination", null);
            row.put("ghidra_reports_computed_call", null);
            row.put("confidence_classification", "UNRESOLVED");
            row.put("derivation_evidence", new ArrayList<>());

            Instruction ins = listing.getInstructionAt(toAddr(siteAddr));
            if (ins == null) {
                rows.add(row);
                continue;
            }

            row.put("raw_instruction_bytes", bytesToHex(ins.getBytes()));
            row.put("instruction_text", ins.toString());
            row.put("mnemonic", ins.getMnemonicString());

            Function caller = funcMgr.getFunctionContaining(ins.getAddress());
            if (caller != null) {
                row.put("caller_function_entry", toHex8(caller.getEntryPoint().getOffset()));
                row.put("caller_function_name", caller.getName());
            }

            List<Map<String, Object>> operands = new ArrayList<>();
            for (int i = 0; i < ins.getNumOperands(); i++) {
                Map<String, Object> op = new LinkedHashMap<>();
                op.put("operand_index", i);
                op.put("display_text", ins.getOperandString(i));
                ghidra.program.model.symbol.OperandType ot = ins.getOperandType(i);
                op.put("type", operandTypeString(ot));
                op.put("type_code", ot == null ? "UNDEFINED" : ot.toString());

                Object opObj = ins.getOpObjects(i);
                List<Map<String, Object>> values = new ArrayList<>();
                if (opObj instanceof Object[]) {
                    for (Object o : (Object[]) opObj) values.add(operandValueToMap(o, memory));
                } else {
                    values.add(operandValueToMap(opObj, memory));
                }
                op.put("values", values);
                operands.add(op);
            }
            row.put("operands", operands);

            List<Map<String, Object>> flows = new ArrayList<>();
            for (Object flow : ins.getFlows()) {
                Map<String, Object> fm = new LinkedHashMap<>();
                if (flow instanceof Address) {
                    Address fa = (Address) flow;
                    fm.put("kind", "address");
                    fm.put("address", toHex8(fa.getOffset()));
                    fm.put("in_loaded_memory", inLoadedMemory(fa.getOffset()));
                } else if (flow instanceof Scalar) {
                    Scalar s = (Scalar) flow;
                    fm.put("kind", "scalar");
                    fm.put("value", toHex8(s.getUnsignedValue()));
                    fm.put("in_loaded_memory", inLoadedMemory(s.getUnsignedValue()));
                } else {
                    fm.put("kind", "other");
                    fm.put("value", flow.toString());
                    fm.put("in_loaded_memory", null);
                }
                flows.add(fm);
            }
            row.put("instruction_flows", flows);

            List<Map<String, Object>> refs = new ArrayList<>();
            ReferenceIterator ri = refMgr.getReferencesFrom(ins.getAddress());
            while (ri.hasNext()) {
                Reference r = ri.next();
                Map<String, Object> rm = new LinkedHashMap<>();
                rm.put("reference_type", r.getReferenceType().toString());
                rm.put("is_call", r.getReferenceType().isCall());
                rm.put("is_computed_call", r.getReferenceType().isComputedCall());
                rm.put("from_address", toHex8(r.getFromAddress().getOffset()));
                Address to = r.getToAddress();
                rm.put("to_address", to == null ? null : toHex8(to.getOffset()));
                rm.put("to_in_loaded_memory", to == null ? null : inLoadedMemory(to.getOffset()));
                refs.add(rm);
            }
            row.put("references", refs);

            Long ptrCell = findPointerCell(operands, memory);
            row.put("pointer_cell_loaded_near_call", ptrCell == null ? null : toHex8(ptrCell));

            String ptrCellRaw = null;
            String ptrBlock = null;
            String ptrDec16LE = null, ptrDec16BE = null, ptrDec32LE = null, ptrDec32BE = null;
            if (ptrCell != null) {
                Map<String, Object> cell = readPointerCell(ptrCell, memory, listing, refMgr, funcMgr);
                ptrCellRaw = (String) cell.get("raw_bytes");
                ptrBlock = (String) cell.get("memory_block_name");
                ptrDec16LE = (String) cell.get("decoded_16_le");
                ptrDec16BE = (String) cell.get("decoded_16_be");
                ptrDec32LE = (String) cell.get("decoded_32_le");
                ptrDec32BE = (String) cell.get("decoded_32_be");
            }
            row.put("pointer_cell_raw_bytes", ptrCellRaw);
            row.put("pointer_cell_memory_block", ptrBlock);
            row.put("pointer_cell_decoded_16_le", ptrDec16LE);
            row.put("pointer_cell_decoded_16_be", ptrDec16BE);
            row.put("pointer_cell_decoded_32_le", ptrDec32LE);
            row.put("pointer_cell_decoded_32_be", ptrDec32BE);

            String computedDest = ghidraComputed.get(siteAddr);
            row.put("computed_destination", computedDest);
            boolean destInRange = computedDest != null && inLoadedMemory(parseHex(computedDest));
            row.put("computed_destination_in_loaded_memory", destInRange);

            String recFunc = null;
            String recFuncName = null;
            if (computedDest != null) {
                Address d = toAddr(parseHex(computedDest));
                Function f = funcMgr.getFunctionAt(d);
                if (f == null) f = funcMgr.getFunctionContaining(d);
                if (f != null) {
                    recFunc = toHex8(f.getEntryPoint().getOffset());
                    recFuncName = f.getName();
                }
            }
            row.put("recovered_function_at_destination", recFunc);
            row.put("recovered_function_name", recFuncName);

            Boolean validInsn = false;
            if (computedDest != null) {
                validInsn = listing.getInstructionAt(toAddr(parseHex(computedDest))) != null;
            }
            row.put("valid_instruction_at_destination", validInsn);

            Boolean ghidraComputedCall = false;
            for (Map<String, Object> rm : refs) {
                if (Boolean.TRUE.equals(rm.get("is_computed_call"))) {
                    ghidraComputedCall = true;
                    break;
                }
            }
            row.put("ghidra_reports_computed_call", ghidraComputedCall);

            boolean hasFunction = recFunc != null;
            boolean refOnly = ghidraComputedCall && !hasFunction && !validInsn;
            String conf = confidenceClass(parseHex(computedDest), destInRange, hasFunction, validInsn, refOnly);
            row.put("confidence_classification", conf);

            List<String> evidence = new ArrayList<>();
            evidence.add("instruction_text:" + ins.toString());
            evidence.add("mnemonic:" + ins.getMnemonicString());
            evidence.add("num_operands:" + ins.getNumOperands());
            evidence.add("num_flows:" + flows.size());
            evidence.add("num_references_from:" + refs.size());
            evidence.add("ghidra_computed_destination:" + computedDest);
            evidence.add("computed_in_loaded_memory:" + destInRange);
            evidence.add("ghidra_computed_call:" + ghidraComputedCall);
            if (ptrCell != null) evidence.add("pointer_cell_loaded:" + toHex8(ptrCell));
            row.put("derivation_evidence", evidence);

            rows.add(row);
        }
        Collections.sort(rows, (a, b) -> Long.compare(parseHex((String) a.get("call_site_address")),
                parseHex((String) b.get("call_site_address"))));
        return rows;
    }

    private Long findPointerCell(List<Map<String, Object>> operands, Memory memory) {
        TreeSet<Long> cellSet = new TreeSet<>();
        cellSet.add(0x60049F88L);
        cellSet.add(0x60049F94L);
        cellSet.add(0x60049F98L);
        cellSet.add(0x600450BCL);
        for (Map<String, Object> op : operands) {
            List<Map<String, Object>> vals = (List<Map<String, Object>>) op.get("values");
            for (Map<String, Object> v : vals) {
                String kind = (String) v.get("kind");
                if ("memory_address".equals(kind) || "data_address".equals(kind)) {
                    Long addr = (Long) v.get("address");
                    if (addr != null && cellSet.contains(addr)) return addr;
                }
                if ("scalar".equals(kind)) {
                    Long val = (Long) v.get("unsigned_value");
                    if (val != null && cellSet.contains(val)) return val;
                }
            }
        }
        return null;
    }

    private Map<String, Object> operandValueToMap(Object o, Memory memory) {
        Map<String, Object> m = new LinkedHashMap<>();
        if (o == null) {
            m.put("kind", "other");
            m.put("value", null);
            return m;
        }
        if (o instanceof Address) {
            Address a = (Address) o;
            m.put("kind", classifyAddressKind(a, memory));
            m.put("address", toHex8(a.getOffset()));
            m.put("unsigned_value", a.getOffset());
            m.put("in_loaded_memory", inLoadedMemory(a.getOffset()));
            MemoryBlock blk = memory.getBlock(a);
            m.put("memory_block", blk == null ? null : blk.getName());
            return m;
        }
        if (o instanceof Scalar) {
            Scalar s = (Scalar) o;
            m.put("kind", "scalar");
            m.put("unsigned_value", s.getUnsignedValue());
            m.put("value", toHex8(s.getUnsignedValue()));
            m.put("in_loaded_memory", inLoadedMemory(s.getUnsignedValue()));
            return m;
        }
        m.put("kind", "other");
        m.put("value", o.toString());
        return m;
    }

    private String classifyAddressKind(Address a, Memory memory) {
        if (!memory.contains(a)) return "external or out-of-range address";
        MemoryBlock blk = memory.getBlock(a);
        if (blk == null) return "external or out-of-range address";
        if (blk.isExecute()) return "code address";
        return "data address";
    }

    private List<Map<String, Object>> collectPointerCells(ReferenceManager refMgr, Listing listing,
            FunctionManager funcMgr, Memory memory) throws Exception {
        List<Map<String, Object>> rows = new ArrayList<>();
        for (long cellAddr : POINTER_CELLS) {
            Map<String, Object> row = readPointerCell(cellAddr, memory, listing, refMgr, funcMgr);
            row.put("cell_address", toHex8(cellAddr));
            rows.add(row);
        }
        Collections.sort(rows, (a, b) -> Long.compare(parseHex((String) a.get("cell_address")),
                parseHex((String) b.get("cell_address"))));
        return rows;
    }

    private Map<String, Object> readPointerCell(long cellAddr, Memory memory, Listing listing,
            ReferenceManager refMgr, FunctionManager funcMgr) throws Exception {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("cell_address", toHex8(cellAddr));
        Address cell = toAddr(cellAddr);
        boolean loaded = memory.contains(cell);
        m.put("loaded_memory_status", loaded);
        MemoryBlock blk = memory.getBlock(cell);
        m.put("memory_block_name", blk == null ? null : blk.getName());
        m.put("block_start", blk == null ? null : toHex8(blk.getStart().getOffset()));
        m.put("block_end", blk == null ? null : toHex8(blk.getEnd().getOffset()));

        StringBuilder sb = new StringBuilder();
        for (long a = cellAddr - 8; a <= cellAddr + 15; a++) {
            Address ra = toAddr(a);
            if (memory.contains(ra)) {
                sb.append(String.format("%02X", memory.getByte(ra) & 0xFF));
            } else {
                sb.append("--");
            }
        }
        m.put("raw_bytes_minus8_plus15", sb.toString());

        Map<String, Object> reads = new LinkedHashMap<>();
        for (long off : new long[]{-2, 0, 2}) {
            long ra = cellAddr + off;
            if (ra % 2 == 0 && memory.contains(toAddr(ra)) && memory.contains(toAddr(ra + 1))) {
                byte b0 = memory.getByte(toAddr(ra));
                byte b1 = memory.getByte(toAddr(ra + 1));
                int le = (b0 & 0xFF) | ((b1 & 0xFF) << 8);
                int be = ((b0 & 0xFF) << 8) | (b1 & 0xFF);
                Map<String, Object> r2 = new LinkedHashMap<>();
                r2.put("address", toHex8(ra));
                r2.put("raw_bytes", String.format("%02X%02X", b0 & 0xFF, b1 & 0xFF));
                r2.put("decoded_16_le", toHex8(le & 0xFFFF));
                r2.put("decoded_16_be", toHex8(be & 0xFFFF));
                reads.put("u16@" + toHex8(ra), r2);
            }
        }
        for (long off : new long[]{-4, 0, 4}) {
            long ra = cellAddr + off;
            if (ra % 4 == 0 && memory.contains(toAddr(ra)) && memory.contains(toAddr(ra + 3))) {
                byte b0 = memory.getByte(toAddr(ra));
                byte b1 = memory.getByte(toAddr(ra + 1));
                byte b2 = memory.getByte(toAddr(ra + 2));
                byte b3 = memory.getByte(toAddr(ra + 3));
                long le32 = (b0 & 0xFF) | ((long) (b1 & 0xFF) << 8) | ((long) (b2 & 0xFF) << 16)
                        | ((long) (b3 & 0xFF) << 24);
                long be32 = (((long) (b0 & 0xFF)) << 24) | (((long) (b1 & 0xFF)) << 16)
                        | (((long) (b2 & 0xFF)) << 8) | ((long) (b3 & 0xFF));
                Map<String, Object> r4 = new LinkedHashMap<>();
                r4.put("address", toHex8(ra));
                r4.put("raw_bytes",
                        String.format("%02X%02X%02X%02X", b0 & 0xFF, b1 & 0xFF, b2 & 0xFF, b3 & 0xFF));
                r4.put("decoded_32_le", toHex8(le32 & 0xFFFFFFFFL));
                r4.put("decoded_32_be", toHex8(be32 & 0xFFFFFFFFL));
                reads.put("u32@" + toHex8(ra), r4);
            }
        }
        m.put("aligned_reads", reads);

        if (cellAddr % 4 == 0 && loaded) {
            byte b0 = memory.getByte(cell);
            byte b1 = memory.getByte(toAddr(cellAddr + 1));
            byte b2 = memory.getByte(toAddr(cellAddr + 2));
            byte b3 = memory.getByte(toAddr(cellAddr + 3));
            long le32 = (b0 & 0xFF) | ((long) (b1 & 0xFF) << 8) | ((long) (b2 & 0xFF) << 16)
                    | ((long) (b3 & 0xFF) << 24);
            long be32 = (((long) (b0 & 0xFF)) << 24) | (((long) (b1 & 0xFF)) << 16)
                    | (((long) (b2 & 0xFF)) << 8) | ((long) (b3 & 0xFF));
            m.put("decoded_32_le", toHex8(le32));
            m.put("decoded_32_be", toHex8(be32));
        } else {
            m.put("decoded_32_le", null);
            m.put("decoded_32_be", null);
        }
        if (cellAddr % 2 == 0 && loaded) {
            byte b0 = memory.getByte(cell);
            byte b1 = memory.getByte(toAddr(cellAddr + 1));
            int le16 = (b0 & 0xFF) | ((b1 & 0xFF) << 8);
            int be16 = ((b0 & 0xFF) << 8) | (b1 & 0xFF);
            m.put("decoded_16_le", toHex8(le16 & 0xFFFF));
            m.put("decoded_16_be", toHex8(be16 & 0xFFFF));
        } else {
            m.put("decoded_16_le", null);
            m.put("decoded_16_be", null);
        }

        List<Map<String, Object>> refsTo = new ArrayList<>();
        ReferenceIterator ri = refMgr.getReferencesTo(cell);
        while (ri.hasNext()) {
            Reference r = ri.next();
            Map<String, Object> rm = new LinkedHashMap<>();
            rm.put("reference_type", r.getReferenceType().toString());
            rm.put("is_call", r.getReferenceType().isCall());
            rm.put("is_computed_call", r.getReferenceType().isComputedCall());
            rm.put("from_address", toHex8(r.getFromAddress().getOffset()));
            rm.put("to_address", toHex8(r.getToAddress().getOffset()));
            refsTo.add(rm);
        }
        m.put("references_to_cell", refsTo);

        List<Map<String, Object>> readers = new ArrayList<>();
        long scanStart = Math.max(IMAGE_BASE, cellAddr - 64);
        long scanEnd = Math.min(IMAGE_END, cellAddr + 64);
        InstructionIterator ii = listing.getInstructions(toAddr(scanStart), true);
        while (ii.hasNext()) {
            Instruction ins = ii.next();
            long insAddr = ins.getAddress().getOffset();
            if (insAddr > scanEnd) break;
            boolean readsCell = false;
            Object[] objs = new Object[0];
            for (int i = 0; i < ins.getNumOperands(); i++) {
                Object o = ins.getOpObjects(i);
                if (o instanceof Object[]) objs = (Object[]) o;
                else objs = new Object[]{o};
                for (Object oo : objs) {
                    if (oo instanceof Address && ((Address) oo).getOffset() == cellAddr) {
                        readsCell = true;
                    }
                }
            }
            if (readsCell) {
                Map<String, Object> rd = new LinkedHashMap<>();
                rd.put("instruction_address", toHex8(insAddr));
                rd.put("instruction_text", ins.toString());
                rd.put("mnemonic", ins.getMnemonicString());
                Function f = funcMgr.getFunctionContaining(ins.getAddress());
                rd.put("function_entry", f == null ? null : toHex8(f.getEntryPoint().getOffset()));
                rd.put("function_name", f == null ? null : f.getName());
                readers.add(rd);
            }
        }
        m.put("instructions_reading_cell", readers);
        m.put("cell_behavior", classifyCellBehavior(loaded, blk, readers, refsTo, memory, cellAddr));

        return m;
    }

    private String classifyCellBehavior(boolean loaded, MemoryBlock blk,
            List<Map<String, Object>> readers, List<Map<String, Object>> refsTo,
            Memory memory, long cellAddr) {
        if (!loaded) return "unresolved";
        boolean isExecBlock = blk != null && blk.isExecute();
        boolean hasReaders = readers != null && !readers.isEmpty();
        boolean hasRefs = refsTo != null && !refsTo.isEmpty();
        if (isExecBlock && hasReaders) return "instruction bytes";
        if (!isExecBlock && hasReaders) return "data pointer";
        if (!isExecBlock && !hasReaders && hasRefs) return "literal";
        if (isExecBlock && !hasReaders && hasRefs) return "mixed code/data";
        if (hasReaders && refsTo != null) {
            for (Map<String, Object> r : refsTo) {
                if (Boolean.TRUE.equals(r.get("is_call"))) return "function pointer";
                if (Boolean.TRUE.equals(r.get("is_computed_call"))) return "callback slot";
            }
        }
        return "unresolved";
    }

    private List<Map<String, Object>> collectComputedDestinations(Memory memory, FunctionManager funcMgr,
            Listing listing) throws Exception {
        List<Map<String, Object>> rows = new ArrayList<>();
        TreeSet<Long> dests = new TreeSet<>();
        for (Map.Entry<Long, String> e : ghidraComputed.entrySet()) {
            dests.add(parseHex(e.getValue()));
        }
        dests.add(0x60044FECL);
        for (long d : dests) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("computed_destination", toHex8(d));
            m.put("in_loaded_memory", inLoadedMemory(d));
            Address da = toAddr(d);
            Function f = funcMgr.getFunctionAt(da);
            if (f == null) f = funcMgr.getFunctionContaining(da);
            m.put("recovered_function_entry", f == null ? null : toHex8(f.getEntryPoint().getOffset()));
            m.put("recovered_function_name", f == null ? null : f.getName());
            m.put("valid_instruction", listing.getInstructionAt(da) != null);
            m.put("memory_block", memory.getBlock(da) == null ? null : memory.getBlock(da).getName());
            List<String> sources = new ArrayList<>();
            for (Map.Entry<Long, String> e : ghidraComputed.entrySet()) {
                if (parseHex(e.getValue()) == d) sources.add(toHex8(e.getKey()));
            }
            m.put("evidence_source_call_sites", sources);
            rows.add(m);
        }
        return rows;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> validationSummary(List<Map<String, Object>> callSites,
            List<Map<String, Object>> pointerCells) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("call_site_count", callSites.size());
        m.put("pointer_cell_count", pointerCells.size());
        int inRange = 0;
        int outOfRange = 0;
        int computedCalls = 0;
        for (Map<String, Object> r : callSites) {
            Boolean inRangeB = (Boolean) r.get("computed_destination_in_loaded_memory");
            if (Boolean.TRUE.equals(inRangeB)) inRange++; else outOfRange++;
            Boolean gc = (Boolean) r.get("ghidra_reports_computed_call");
            if (Boolean.TRUE.equals(gc)) computedCalls++;
        }
        m.put("computed_in_loaded_memory", inRange);
        m.put("computed_out_of_loaded_memory", outOfRange);
        m.put("ghidra_computed_call_count", computedCalls);
        m.put("all_call_sites_present", callSites.size() == CALL_SITES.length);
        m.put("all_pointer_cells_present", pointerCells.size() == POINTER_CELLS.length);
        return m;
    }

    private void writeJson(Map<String, Object> report) throws Exception {
        String outDir = "C:\\temp\\aula-l99-controller\\v9_2_staging\\session_a\\outputs";
        java.io.File dir = new java.io.File(outDir);
        if (!dir.exists()) dir.mkdirs();
        String path = outDir + "\\collected_computed_calls.json";
        try (BufferedWriter w = new BufferedWriter(new OutputStreamWriter(
                new FileOutputStream(path), StandardCharsets.UTF_8))) {
            w.write(toJson(report, 0));
            w.newLine();
        }
        println("WROTE " + path);
    }

    private String toJson(Object obj, int indent) {
        StringBuilder sb = new StringBuilder();
        toJsonValue(obj, sb, indent);
        return sb.toString();
    }

    private void toJsonValue(Object obj, StringBuilder sb, int indent) {
        if (obj == null) {
            sb.append("null");
            return;
        }
        if (obj instanceof String) {
            sb.append(escapeJson((String) obj));
            return;
        }
        if (obj instanceof Number) {
            sb.append(obj.toString());
            return;
        }
        if (obj instanceof Boolean) {
            sb.append(obj.toString());
            return;
        }
        if (obj instanceof Map) {
            sb.append("{\n");
            Map<?, ?> map = (Map<?, ?>) obj;
            String pad = pad(indent + 2);
            String padInner = pad(indent + 4);
            boolean first = true;
            for (Map.Entry<?, ?> e : map.entrySet()) {
                if (!first) sb.append(",\n");
                first = false;
                sb.append(padInner).append(escapeJson(e.getKey().toString())).append(": ");
                toJsonValue(e.getValue(), sb, indent + 4);
            }
            sb.append("\n").append(pad).append("}");
            return;
        }
        if (obj instanceof List) {
            sb.append("[\n");
            List<?> list = (List<?>) obj;
            String pad = pad(indent + 2);
            String padInner = pad(indent + 4);
            boolean first = true;
            for (Object item : list) {
                if (!first) sb.append(",\n");
                first = false;
                sb.append(padInner);
                toJsonValue(item, sb, indent + 4);
            }
            sb.append("\n").append(pad).append("]");
            return;
        }
        sb.append(escapeJson(obj.toString()));
    }

    private String pad(int n) {
        char[] c = new char[n];
        Arrays.fill(c, ' ');
        return new String(c);
    }

    private String escapeJson(String s) {
        StringBuilder sb = new StringBuilder();
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\b': sb.append("\\b"); break;
                case '\f': sb.append("\\f"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        sb.append('"');
        return sb.toString();
    }

    private long parseHex(String s) {
        if (s == null) return -1;
        s = s.trim();
        if (s.startsWith("0x") || s.startsWith("0X")) s = s.substring(2);
        return Long.parseLong(s, 16);
    }

    private String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder();
        for (byte b : bytes) sb.append(String.format("%02X", b & 0xFF));
        return sb.toString();
    }

    private Address toAddr(long offset) throws AddressFormatException {
        return currentProgram.getAddressFactory().getAddress(offset);
    }
}
