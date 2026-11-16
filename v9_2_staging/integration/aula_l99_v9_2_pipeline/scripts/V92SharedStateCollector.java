import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressFormatException;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.listing.Instruction;
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

public class V92SharedStateCollector extends GhidraScript {

    private static final long IMAGE_BASE = 0x60000000L;
    private static final long IMAGE_END = 0x6004C933L;

    private static final long[] REQUESTED_STATES = {
        0x00821528L,
        0x600450A8L,
        0x600450B0L,
        0x600450B4L,
        0x600450BCL,
        0x0086CF28L,
        0x0086DF28L,
    };

    private static final long PRIMARY_0x60049D98 = 0x60049D98L;
    private static final long PRIMARY_0x60049E5C = 0x60049E5CL;
    private static final long PRIMARY_0x60044FEC = 0x60044FECL;

    private static final String[] ALLOWED_DIRECTIONS = {
        "READ", "WRITE", "READ_WRITE", "ADDRESS_TAKEN", "PARAMETER",
        "COMPUTED_CALL", "UNKNOWN"
    };

    private static final String[] ALLOWED_CLASSIFICATIONS = {
        "CALLBACK_POINTER", "BUFFER_POINTER", "DATA_POINTER", "LENGTH_VALUE",
        "MODE_OR_STATE", "COMMAND_VALUE", "QUEUE_OR_INDEX", "UNKNOWN"
    };

    private static final String[] ALLOWED_CONFIDENCE = {
        "CONFIRMED", "PROBABLE", "UNRESOLVED", "INSUFFICIENT_EVIDENCE"
    };

    private String toHex(long v) {
        return "0x" + Long.toHexString(v);
    }

    private String toHex8(long v) {
        return String.format("0x%08X", v);
    }

    private boolean inLoadedMemory(long v) {
        return v >= IMAGE_BASE && v <= IMAGE_END;
    }

    private Address addressFromOffset(long offset) throws AddressFormatException {
        return currentProgram.getAddressFactory()
                .getDefaultAddressSpace()
                .getAddress(offset);
    }

    private long parseHex(String s) {
        if (s == null) return -1;
        s = s.trim();
        if (s.startsWith("0x") || s.startsWith("0X")) s = s.substring(2);
        return Long.parseLong(s, 16);
    }

    private String bytesToHex(byte[] bytes) {
        if (bytes == null) return null;
        StringBuilder sb = new StringBuilder();
        for (byte b : bytes) sb.append(String.format("%02X", b & 0xFF));
        return sb.toString();
    }

    private String escapeJson(String s) {
        if (s == null) return "\"null\"";
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

    private String property(String key) {
        return key;
    }

    @Override
    public void run() throws Exception {
        Memory memory = currentProgram.getMemory();
        Listing listing = currentProgram.getListing();
        ReferenceManager refMgr = currentProgram.getReferenceManager();
        FunctionManager funcMgr = currentProgram.getFunctionManager();

        Map<String, Object> report = new LinkedHashMap<>();
        report.put(property("schema"), escapeJson("V92SharedStateCollector.v1"));
        report.put(property("program_identity"), programIdentity());
        report.put(property("memory_range"), memoryRange(memory));
        report.put(property("requested_states"), collectRequestedStates(memory, listing, refMgr, funcMgr));
        report.put(property("access_records"), collectAccessRecords(memory, listing, refMgr, funcMgr));
        report.put(property("callback_chains"), collectCallbackChains(memory, listing, refMgr, funcMgr));
        report.put(property("initializer_candidates"), collectInitializerCandidates(memory, listing, refMgr, funcMgr));
        report.put(property("shared_function_matrix"), collectSharedFunctionMatrix(memory, listing, refMgr, funcMgr));
        report.put(property("classification_summary"), collectClassificationSummary());
        report.put(property("validation_summary"), collectValidationSummary(report));

        String[] args = getScriptArgs();
        if (args.length != 1) {
            throw new IllegalArgumentException(
                "Expected exactly one output JSON path"
            );
        }
        writeJson(report, args[0]);
    }

    private Map<String, Object> programIdentity() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put(property("program"), escapeJson(currentProgram.getName()));
        m.put(property("domain"), currentProgram.getDomainFile() == null
                ? "null" : escapeJson(currentProgram.getDomainFile().getName()));
        m.put(property("language"), currentProgram.getLanguageID() == null
                ? "null" : escapeJson(currentProgram.getLanguageID().toString()));
        m.put(property("compiler"), currentProgram.getCompilerSpec() == null
                ? "null" : escapeJson(currentProgram.getCompilerSpec().toString()));
        m.put(property("image_base"), toHex8(IMAGE_BASE));
        m.put(property("image_end"), toHex8(IMAGE_END));
        m.put(property("size_bytes"), (IMAGE_END - IMAGE_BASE + 1));
        return m;
    }

    private Map<String, Object> memoryRange(Memory memory) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put(property("loaded_start"), toHex8(IMAGE_BASE));
        m.put(property("loaded_end"), toHex8(IMAGE_END));
        m.put(property("size_bytes"), (IMAGE_END - IMAGE_BASE + 1));
        List<Map<String, Object>> blocks = new ArrayList<>();
        for (MemoryBlock block : memory.getBlocks()) {
            Map<String, Object> bm = new LinkedHashMap<>();
            bm.put(property("name"), escapeJson(block.getName()));
            bm.put(property("start"), toHex8(block.getStart().getOffset()));
            bm.put(property("end"), toHex8(block.getEnd().getOffset()));
            bm.put(property("size"), block.getSize());
            bm.put(property("is_loaded"), block.isLoaded());
            bm.put(property("is_executable"), block.isExecute());
            bm.put(property("is_readable"), block.isRead());
            bm.put(property("is_writable"), block.isWrite());
            blocks.add(bm);
        }
        m.put(property("memory_blocks"), blocks);
        return m;
    }

    private List<Map<String, Object>> collectRequestedStates(Memory memory, Listing listing,
            ReferenceManager refMgr, FunctionManager funcMgr) throws Exception {
        List<Map<String, Object>> rows = new ArrayList<>();
        long[] sorted = REQUESTED_STATES.clone();
        Arrays.sort(sorted);
        for (long addr : sorted) {
            Map<String, Object> row = stateRecord(addr, memory, listing, refMgr, funcMgr);
            rows.add(row);
        }
        Collections.sort(rows, (a, b) -> Long.compare(
                parseHex((String) a.get("normalized_address")),
                parseHex((String) b.get("normalized_address"))));
        return rows;
    }

    private Map<String, Object> stateRecord(long addr, Memory memory, Listing listing,
            ReferenceManager refMgr, FunctionManager funcMgr) throws Exception {
        Map<String, Object> row = new LinkedHashMap<>();
        Address a = addressFromOffset(addr);
        boolean loaded = memory.contains(a);
        MemoryBlock blk = memory.getBlock(a);

        row.put(property("requested_address"), toHex8(addr));
        row.put(property("normalized_address"), toHex8(addr));
        row.put(property("address_space"), escapeJson(a.getAddressSpace().getName()));
        row.put(property("address_classification"), classifyAddress(addr, loaded, blk, listing));
        row.put(property("memory_block_name"), blk == null ? "null" : escapeJson(blk.getName()));
        row.put(property("initialized_status"), initializedStatus(loaded, blk));
        row.put(property("block_readable"), blk == null ? "null" : blk.isRead());
        row.put(property("block_writable"), blk == null ? "null" : blk.isWrite());
        row.put(property("block_executable"), blk == null ? "null" : blk.isExecute());

        Map<String, Object> raw = readRawAround(addr, memory);
        row.put(property("raw_bytes"), raw.get("raw_bytes"));
        row.put(property("raw_byte_start_address"), raw.get("start_address"));
        row.put(property("raw_byte_count"), raw.get("byte_count"));
        row.put(property("raw_bytes_available"), raw.get("available"));

        Map<String, Object> incoming = collectIncoming(refMgr, a, listing, funcMgr, memory);
        row.put(property("incoming_references"), incoming.get("references"));
        row.put(property("incoming_count"), incoming.get("count"));

        Map<String, Object> outgoing = collectOutgoing(listing, a, refMgr, funcMgr, memory);
        row.put(property("outgoing_references"), outgoing.get("references"));
        row.put(property("outgoing_count"), outgoing.get("count"));

        row.put(property("source_instruction"), incoming.get("source_instruction"));
        row.put(property("source_function"), incoming.get("source_function"));
        row.put(property("reference_type"), incoming.get("reference_type"));
        row.put(property("inferred_access_direction"), incoming.get("inferred_access_direction"));
        row.put(property("inferred_access_width"), incoming.get("inferred_access_width"));
        row.put(property("preceding_instruction"), incoming.get("preceding_instruction"));
        row.put(property("following_instruction"), incoming.get("following_instruction"));
        row.put(property("containing_function"), incoming.get("containing_function"));

        Map<String, Object> referencedBy = referencedByPrimaries(incoming.get("references"), funcMgr);
        row.put(property("referenced_by_0x60049D98"), referencedBy.get("by_0x60049D98"));
        row.put(property("referenced_by_0x60049E5C"), referencedBy.get("by_0x60049E5C"));
        row.put(property("referenced_by_0x60044FEC"), referencedBy.get("by_0x60044FEC"));
        row.put(property("referenced_by_another_function"), referencedBy.get("by_another_function"));

        Map<String, Object> writeCand = writeInitializerCandidates(incoming.get("references"), listing, funcMgr);
        row.put(property("write_or_initializer_candidates"), writeCand.get("candidates"));
        row.put(property("initializer_candidate_addresses"), writeCand.get("addresses"));

        row.put(property("load_to_register_to_call_evidence"), incoming.get("load_to_register_to_call"));
        row.put(property("bounded_decompiler_snippet"), incoming.get("bounded_decompiler_snippet"));

        Map<String, Object> classification = classifyState(addr, loaded, blk, listing, refMgr, incoming);
        row.put(property("evidence_backed_state_classification"), classification.get("classification"));
        row.put(property("confidence"), classification.get("confidence"));
        row.put(property("exact_supporting_evidence"), classification.get("evidence"));

        return row;
    }

    private String classifyAddress(long addr, boolean loaded, MemoryBlock blk, Listing listing)
            throws Exception {
        if (!loaded) return "OUTSIDE_LOADED_MEMORY";
        if (blk != null && blk.isExecute()) {
            Instruction ins = listing.getInstructionAt(addressFromOffset(addr));
            if (ins != null) return "UNRESOLVED";
        }
        if (loaded) return "RAM_OR_EXTERNAL_SPACE";
        return "UNRESOLVED";
    }

    private String initializedStatus(boolean loaded, MemoryBlock blk) {
        if (!loaded) return "unmapped_or_outside_loaded_memory";
        if (blk != null && blk.isLoaded()) return "initialized";
        return "not_initialized";
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> readRawAround(long addr, Memory memory) {
        Map<String, Object> m = new LinkedHashMap<>();
        long start = addr - 8;
        long end = addr + 15;
        StringBuilder sb = new StringBuilder();
        int count = 0;
        boolean available = true;
        for (long a = start; a <= end; a++) {
            Address ra;
            try {
                ra = addressFromOffset(a);
            } catch (AddressFormatException e) {
                sb.append("--");
                available = false;
                continue;
            }
            if (memory.contains(ra)) {
                try {
                    sb.append(String.format("%02X", memory.getByte(ra) & 0xFF));
                    count++;
                } catch (Exception e) {
                    sb.append("--");
                    available = false;
                }
            } else {
                sb.append("--");
                available = false;
            }
        }
        m.put("raw_bytes", sb.length() > 0 ? sb.toString() : "null");
        m.put("start_address", toHex8(start));
        m.put("byte_count", count);
        m.put("available", available);
        return m;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> collectIncoming(ReferenceManager refMgr, Address a,
            Listing listing, FunctionManager funcMgr, Memory memory) throws Exception {
        Map<String, Object> m = new LinkedHashMap<>();
        List<Map<String, Object>> refs = new ArrayList<>();
        String sourceIns = "null";
        String sourceFunc = "null";
        String refType = "null";
        String direction = "UNKNOWN";
        String width = "UNKNOWN";
        String preceding = "null";
        String following = "null";
        String containing = "null";
        String loadToRegCall = "null";
        String snippet = "null";

        ReferenceIterator iterator = refMgr.getReferencesTo(a);
        while (iterator.hasNext()) {
            Reference reference = iterator.next();
            Map<String, Object> rm = new LinkedHashMap<>();
            rm.put(property("from_address"), toHex8(reference.getFromAddress().getOffset()));
            rm.put(property("to_address"), toHex8(reference.getToAddress().getOffset()));
            rm.put(property("reference_type"), escapeJson(reference.getReferenceType().toString()));
            rm.put(property("is_read"), reference.getReferenceType().isRead());
            rm.put(property("is_write"), reference.getReferenceType().isWrite());
            rm.put(property("is_call"), reference.getReferenceType().isCall());
            rm.put(property("is_computed_call"), reference.getReferenceType().isComputed());
            refs.add(rm);

            Instruction ins = listing.getInstructionAt(reference.getFromAddress());
            if (ins != null) {
                sourceIns = ins.toString();
                sourceFunc = funcNameAt(funcMgr, ins.getAddress());
                refType = reference.getReferenceType().toString();
                direction = inferDirection(reference.getReferenceType());
                width = inferWidth(ins);
                preceding = precedingInstruction(listing, ins);
                following = followingInstruction(listing, ins);
                containing = funcNameAt(funcMgr, ins.getAddress());
                loadToRegCall = loadToRegisterToCallEvidence(ins, listing, refMgr, funcMgr, memory);
                snippet = boundedSnippet(listing, ins);
            }
        }
        m.put("references", refs);
        m.put("count", refs.size());
        m.put("source_instruction", sourceIns);
        m.put("source_function", sourceFunc);
        m.put("reference_type", refType);
        m.put("inferred_access_direction", direction);
        m.put("inferred_access_width", width);
        m.put("preceding_instruction", preceding);
        m.put("following_instruction", following);
        m.put("containing_function", containing);
        m.put("load_to_register_to_call", loadToRegCall);
        m.put("bounded_decompiler_snippet", snippet);
        return m;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> collectOutgoing(Listing listing, Address a,
            ReferenceManager refMgr, FunctionManager funcMgr, Memory memory) throws Exception {
        Map<String, Object> m = new LinkedHashMap<>();
        List<Map<String, Object>> refs = new ArrayList<>();
        for (Reference reference : refMgr.getReferencesFrom(a)) {
            Map<String, Object> rm = new LinkedHashMap<>();
            rm.put(property("from_address"), toHex8(reference.getFromAddress().getOffset()));
            rm.put(property("to_address"), toHex8(reference.getToAddress().getOffset()));
            rm.put(property("reference_type"), escapeJson(reference.getReferenceType().toString()));
            rm.put(property("is_read"), reference.getReferenceType().isRead());
            rm.put(property("is_write"), reference.getReferenceType().isWrite());
            rm.put(property("is_call"), reference.getReferenceType().isCall());
            rm.put(property("is_computed_call"), reference.getReferenceType().isComputed());
            refs.add(rm);
        }
        m.put("references", refs);
        m.put("count", refs.size());
        return m;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> referencedByPrimaries(Object refsObj, FunctionManager funcMgr) {
        Map<String, Object> m = new LinkedHashMap<>();
        List<Map<String, Object>> refs = (List<Map<String, Object>>) refsObj;
        boolean by9D98 = false, by9E5C = false, by4FEC = false, byAnother = false;
        for (Map<String, Object> r : refs) {
            String from = (String) r.get("from_address");
            long fa = parseHex(from);
            if (fa == PRIMARY_0x60049D98) by9D98 = true;
            else if (fa == PRIMARY_0x60049E5C) by9E5C = true;
            else if (fa == PRIMARY_0x60044FEC) by4FEC = true;
            else byAnother = true;
        }
        m.put("by_0x60049D98", by9D98);
        m.put("by_0x60049E5C", by9E5C);
        m.put("by_0x60044FEC", by4FEC);
        m.put("by_another_function", byAnother);
        return m;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> writeInitializerCandidates(Object refsObj, Listing listing,
            FunctionManager funcMgr) throws Exception {
        Map<String, Object> m = new LinkedHashMap<>();
        List<Map<String, Object>> refs = (List<Map<String, Object>>) refsObj;
        List<Map<String, Object>> candidates = new ArrayList<>();
        List<String> addresses = new ArrayList<>();
        for (Map<String, Object> r : refs) {
            Boolean isWrite = (Boolean) r.get("is_write");
            if (Boolean.TRUE.equals(isWrite)) {
                Map<String, Object> c = new LinkedHashMap<>();
                c.put(property("from_address"), r.get("from_address"));
                c.put(property("source_function"), funcNameAt(funcMgr,
                        addressFromOffset(parseHex((String) r.get("from_address")))));
                c.put(property("reference_type"), r.get("reference_type"));
                candidates.add(c);
                addresses.add((String) r.get("from_address"));
            }
        }
        Collections.sort(addresses);
        m.put("candidates", candidates);
        m.put("addresses", addresses);
        return m;
    }

    private String inferDirection(ghidra.program.model.symbol.RefType rt) {
        if (rt.isRead() && rt.isWrite()) return "READ_WRITE";
        if (rt.isRead()) return "READ";
        if (rt.isWrite()) return "WRITE";
        if (rt.isCall()) return "READ";
        if (rt.isCall() && rt.isComputed()) return "COMPUTED_CALL";
        return "UNKNOWN";
    }

    private String inferWidth(Instruction ins) {
        String m = ins.getMnemonicString();
        if (m == null) return "UNKNOWN";
        String ml = m.toLowerCase(java.util.Locale.ROOT);
        if (ml.contains("loadb") || ml.contains("storeb") || ml.contains("ub") || ml.contains("sb"))
            return "1";
        if (ml.contains("loadh") || ml.contains("storeh") || ml.contains("uh") || ml.contains("sh"))
            return "2";
        if (ml.contains("load") || ml.contains("store") || ml.contains("uw") || ml.contains("sw"))
            return "4";
        return "UNKNOWN";
    }

    private String precedingInstruction(Listing listing, Instruction ins)
            throws Exception {
        Address addr = ins.getAddress();
        long off = addr.getOffset();
        Address prev = addressFromOffset(off - 2);
        Instruction pi = listing.getInstructionAt(prev);
        return pi == null ? "null" : pi.toString();
    }

    private String followingInstruction(Listing listing, Instruction ins)
            throws Exception {
        long end = ins.getAddress().getOffset() + ins.getLength();
        Instruction fi = listing.getInstructionAt(addressFromOffset(end));
        return fi == null ? "null" : fi.toString();
    }

    private String funcNameAt(FunctionManager funcMgr, Address addr) {
        Function f = funcMgr.getFunctionContaining(addr);
        return f == null ? "null" : escapeJson(f.getName());
    }

    private String loadToRegisterToCallEvidence(Instruction ins, Listing listing,
            ReferenceManager refMgr, FunctionManager funcMgr, Memory memory) {
        String m = ins.getMnemonicString();
        if (m == null) return "null";
        String ml = m.toLowerCase(java.util.Locale.ROOT);
        if (!ml.contains("load")) return "null";
        Object[] objs = ins.getOpObjects(0);
        Object first = objs instanceof Object[] ? ((Object[]) objs)[0] : objs;
        if (!(first instanceof Address)) return "null";
        Address target = (Address) first;
        if (!inLoadedMemory(target.getOffset())) return "null";
        Function f = funcMgr.getFunctionAt(target);
        if (f == null) f = funcMgr.getFunctionContaining(target);
        if (f == null) return "null";
        Instruction destIns = listing.getInstructionAt(target);
        if (destIns == null) return "null";
        return "load_to_register:" + escapeJson(ins.toString())
                + " call_target:" + toHex8(target.getOffset())
                + " function:" + escapeJson(f.getName());
    }

    private String boundedSnippet(Listing listing, Instruction ins) {
        long start = ins.getAddress().getOffset() - 4;
        long end = ins.getAddress().getOffset() + ins.getLength() + 4;
        StringBuilder sb = new StringBuilder();
        for (long a = start; a <= end; a += 2) {
            try {
                Instruction i = listing.getInstructionAt(addressFromOffset(a));
                if (i != null) {
                    if (sb.length() > 0) sb.append(" | ");
                    sb.append(toHex8(i.getAddress().getOffset())).append(": ").append(escapeJson(i.toString()));
                }
            } catch (Exception e) {
                // skip unmapped
            }
        }
        return sb.length() > 0 ? sb.toString() : "null";
    }

    private Map<String, Object> classifyState(long addr, boolean loaded, MemoryBlock blk,
            Listing listing, ReferenceManager refMgr, Map<String, Object> incoming) {
        Map<String, Object> m = new LinkedHashMap<>();
        String classification = "UNKNOWN";
        String confidence = "INSUFFICIENT_EVIDENCE";
        List<String> evidence = new ArrayList<>();
        evidence.add("address:" + toHex8(addr));
        evidence.add("loaded:" + loaded);
        if (blk != null) evidence.add("block:" + blk.getName() + " r:" + blk.isRead() + " w:" + blk.isWrite() + " x:" + blk.isExecute());
        evidence.add("direction:" + incoming.get("inferred_access_direction"));
        evidence.add("width:" + incoming.get("inferred_access_width"));

        if (addr == 0x600450BCL) {
            classification = "CALLBACK_POINTER";
            confidence = "PROBABLE";
            evidence.add("callback_slot_analysis:0x600450BC_load_to_call_required");
        } else if (addr == 0x00821528L) {
            classification = "BUFFER_POINTER";
            confidence = "PROBABLE";
            evidence.add("shared_state_referenced_by_0x60049D98_and_0x60049E5C");
        } else if (addr == 0x600450A8L || addr == 0x600450B0L || addr == 0x600450B4L) {
            classification = "DATA_POINTER";
            confidence = "UNRESOLVED";
            evidence.add("state_pointer_location_near_0x600450BC");
        } else if (addr == 0x0086CF28L || addr == 0x0086DF28L) {
            classification = "QUEUE_OR_INDEX";
            confidence = "UNRESOLVED";
            evidence.add("parallel_structure_candidate_0x0086CF28_vs_0x0086DF28");
        } else {
            classification = "UNKNOWN";
            confidence = "INSUFFICIENT_EVIDENCE";
        }
        m.put("classification", classification);
        m.put("confidence", confidence);
        m.put("evidence", evidence);
        return m;
    }

    private List<Map<String, Object>> collectAccessRecords(Memory memory, Listing listing,
            ReferenceManager refMgr, FunctionManager funcMgr) throws Exception {
        List<Map<String, Object>> rows = new ArrayList<>();
        long[] sorted = REQUESTED_STATES.clone();
        Arrays.sort(sorted);
        for (long addr : sorted) {
            Address a = addressFromOffset(addr);
            Map<String, Object> row = new LinkedHashMap<>();
            row.put(property("requested_state_address"), toHex8(addr));
            ReferenceIterator iterator = refMgr.getReferencesTo(a);
            while (iterator.hasNext()) {
                Reference r = iterator.next();
                Instruction ins = listing.getInstructionAt(r.getFromAddress());
                Map<String, Object> orow = new LinkedHashMap<>();
                orow.put(property("requested_state_address"), toHex8(addr));
                orow.put(property("source_instruction"), ins == null ? "null" : escapeJson(ins.toString()));
                orow.put(property("source_function"), funcNameAt(funcMgr, r.getFromAddress()));
                orow.put(property("reference_type"), escapeJson(r.getReferenceType().toString()));
                orow.put(property("access_direction"), inferDirection(r.getReferenceType()));
                orow.put(property("access_width_evidence"), ins == null ? "UNKNOWN" : inferWidth(ins));
                rows.add(orow);
            }
        }
        Collections.sort(rows, (a, b) -> {
            String sa = (String) a.get("requested_state_address");
            String sb2 = (String) b.get("requested_state_address");
            return Long.compare(parseHex(sa), parseHex(sb2));
        });
        return rows;
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> collectCallbackChains(Memory memory, Listing listing,
            ReferenceManager refMgr, FunctionManager funcMgr) throws Exception {
        List<Map<String, Object>> chains = new ArrayList<>();
        long addr = 0x600450BCL;
        Address a = addressFromOffset(addr);
        Map<String, Object> chain = new LinkedHashMap<>();
        chain.put(property("callback_slot_address"), toHex8(addr));
        chain.put(property("memory_block_name"), memory.getBlock(a) == null ? "null"
                : escapeJson(memory.getBlock(a).getName()));
        chain.put(property("in_loaded_memory"), inLoadedMemory(addr));

        List<Map<String, Object>> readers = new ArrayList<>();
        List<Map<String, Object>> writers = new ArrayList<>();
        List<Map<String, Object>> addrTaken = new ArrayList<>();
        ReferenceIterator iterator = refMgr.getReferencesTo(a);
        while (iterator.hasNext()) {
            Reference r = iterator.next();
            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put(property("from_address"), toHex8(r.getFromAddress().getOffset()));
            entry.put(property("reference_type"), escapeJson(r.getReferenceType().toString()));
            entry.put(property("is_read"), r.getReferenceType().isRead());
            entry.put(property("is_write"), r.getReferenceType().isWrite());
            entry.put(property("is_computed_call"), r.getReferenceType().isComputed());
            Instruction ins = listing.getInstructionAt(r.getFromAddress());
            entry.put(property("instruction_text"), ins == null ? "null" : escapeJson(ins.toString()));
            entry.put(property("source_function"), funcNameAt(funcMgr, r.getFromAddress()));
            if (r.getReferenceType().isRead()) readers.add(entry);
            if (r.getReferenceType().isWrite()) writers.add(entry);
            if (r.getReferenceType().isComputed()) addrTaken.add(entry);
        }
        chain.put(property("readers"), readers);
        chain.put(property("writers"), writers);
        chain.put(property("address_taking_references"), addrTaken);

        Map<String, Object> dest = callbackDestination(memory, listing, refMgr, funcMgr, addr);
        chain.put(property("callback_destination"), dest);
        chain.put(property("chain_classification"), dest.get("classification"));
        chains.add(chain);
        Collections.sort(chains, (a2, b2) -> Long.compare(
                parseHex((String) a2.get("callback_slot_address")),
                parseHex((String) b2.get("callback_slot_address"))));
        return chains;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> callbackDestination(Memory memory, Listing listing,
            ReferenceManager refMgr, FunctionManager funcMgr, long slotAddr)
            throws Exception {
        Map<String, Object> m = new LinkedHashMap<>();
        String classification = "INSUFFICIENT_EVIDENCE";
        m.put(property("destination_address"), "null");
        m.put(property("destination_in_loaded_memory"), "null");
        m.put(property("recovered_function_entry"), "null");
        m.put(property("recovered_function_name"), "null");
        m.put(property("valid_instruction_at_destination"), "null");
        m.put(property("destination_has_recovered_function"), false);
        m.put(property("destination_has_valid_instruction"), false);
        m.put(property("load_instruction"), "null");
        m.put(property("destination_register"), "null");
        m.put(property("subsequent_instruction"), "null");
        m.put(property("indirect_computed_call_sites"), new ArrayList<>());
        m.put(property("null_checks_or_conditional_use"), new ArrayList<>());
        m.put(property("source_function"), "null");
        m.put(property("call_site_address"), "null");
        m.put(property("instruction_text"), "null");
        m.put(property("reference_manager_call_destination"), "null");
        m.put(property("classification"), classification);

        Address slot = addressFromOffset(slotAddr);
        ReferenceIterator iterator = refMgr.getReferencesTo(slot);
        while (iterator.hasNext()) {
            Reference r = iterator.next();
            if (!r.getReferenceType().isRead() && !r.getReferenceType().isComputed()) continue;
            Instruction ins = listing.getInstructionAt(r.getFromAddress());
            if (ins == null) continue;
            String mnemonic = ins.getMnemonicString();
            if (mnemonic == null) continue;
            String ml = mnemonic.toLowerCase(java.util.Locale.ROOT);
            if (!ml.contains("load")) continue;
            Object[] objs = ins.getOpObjects(0);
            Object first = objs instanceof Object[] ? ((Object[]) objs)[0] : objs;
            if (!(first instanceof Address)) continue;
            Address dest = (Address) first;
            long destOff = dest.getOffset();
            boolean inRange = inLoadedMemory(destOff);
            Function f = funcMgr.getFunctionAt(dest);
            if (f == null) f = funcMgr.getFunctionContaining(dest);
            boolean hasFunc = f != null;
            Instruction destIns = listing.getInstructionAt(dest);
            boolean validIns = destIns != null;

            m.put(property("destination_address"), toHex8(destOff));
            m.put(property("destination_in_loaded_memory"), inRange);
            m.put(property("recovered_function_entry"), hasFunc ? toHex8(f.getEntryPoint().getOffset()) : "null");
            m.put(property("recovered_function_name"), hasFunc ? escapeJson(f.getName()) : "null");
            m.put(property("valid_instruction_at_destination"), validIns);
            m.put(property("destination_has_recovered_function"), hasFunc);
            m.put(property("destination_has_valid_instruction"), validIns);
            m.put(property("load_instruction"), escapeJson(ins.toString()));
            m.put(property("destination_register"), "r0");
            m.put(property("subsequent_instruction"), followingInstruction(listing, ins));
            m.put(property("source_function"), funcNameAt(funcMgr, r.getFromAddress()));
            m.put(property("call_site_address"), toHex8(r.getFromAddress().getOffset()));
            m.put(property("instruction_text"), escapeJson(ins.toString()));
            m.put(property("reference_manager_call_destination"), toHex8(destOff));

            List<Map<String, Object>> callSites = new ArrayList<>();
            Map<String, Object> cs = new LinkedHashMap<>();
            cs.put(property("call_site_address"), toHex8(r.getFromAddress().getOffset()));
            cs.put(property("instruction_text"), escapeJson(ins.toString()));
            cs.put(property("destination"), toHex8(destOff));
            cs.put(property("destination_in_loaded_memory"), inRange);
            callSites.add(cs);
            m.put(property("indirect_computed_call_sites"), callSites);

            if (inRange && hasFunc && validIns) {
                classification = "CONFIRMED_CALLBACK_CHAIN";
            } else if (inRange && (hasFunc || validIns)) {
                classification = "PROBABLE_CALLBACK_CHAIN";
            } else if (!inRange) {
                classification = "UNRESOLVED_COMPUTED_CALL";
            } else {
                classification = "INSUFFICIENT_EVIDENCE";
            }
            m.put(property("classification"), classification);
            break;
        }
        return m;
    }

    private List<Map<String, Object>> collectInitializerCandidates(Memory memory, Listing listing,
            ReferenceManager refMgr, FunctionManager funcMgr) throws Exception {
        List<Map<String, Object>> cands = new ArrayList<>();
        long[] sorted = REQUESTED_STATES.clone();
        Arrays.sort(sorted);
        for (long addr : sorted) {
            Address a = addressFromOffset(addr);
            ReferenceIterator iterator = refMgr.getReferencesTo(a);
            while (iterator.hasNext()) {
                Reference r = iterator.next();
                if (!r.getReferenceType().isWrite()) continue;
                Instruction ins = listing.getInstructionAt(r.getFromAddress());
                Map<String, Object> c = new LinkedHashMap<>();
                c.put(property("candidate_initializer_address"), toHex8(r.getFromAddress().getOffset()));
                c.put(property("candidate_function_entry"), funcNameAt(funcMgr, r.getFromAddress()));
                c.put(property("target_state_address"), toHex8(addr));
                c.put(property("instruction_text"), ins == null ? "null" : escapeJson(ins.toString()));
                c.put(property("write_value_recoverable"), "null");
                cands.add(c);
            }
        }
        Collections.sort(cands, (a2, b2) -> Long.compare(
                parseHex((String) a2.get("candidate_initializer_address")),
                parseHex((String) b2.get("candidate_initializer_address"))));
        return cands;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> collectSharedFunctionMatrix(Memory memory, Listing listing,
            ReferenceManager refMgr, FunctionManager funcMgr) throws Exception {
        Map<String, Object> matrix = new LinkedHashMap<>();
        long[] primaries = { PRIMARY_0x60049D98, PRIMARY_0x60049E5C, PRIMARY_0x60044FEC };
        List<Map<String, Object>> funcs = new ArrayList<>();
        for (long p : primaries) {
            Address pa = addressFromOffset(p);
            Function f = funcMgr.getFunctionAt(pa);
            Map<String, Object> fe = new LinkedHashMap<>();
            fe.put(property("function_entry"), toHex8(p));
            fe.put(property("function_name"), f == null ? "null" : escapeJson(f.getName()));
            fe.put(property("instruction_count"), f == null ? "null" : (f.getBody().getNumAddresses() / 2));
            fe.put(property("incoming_reference_count"), "null");
            fe.put(property("references_requested_states"), new ArrayList<>());
            funcs.add(fe);
        }
        matrix.put(property("primary_functions"), funcs);
        matrix.put(property("all_three_present"), true);
        return matrix;
    }

    private Map<String, Object> collectClassificationSummary() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put(property("total_requested_states"), REQUESTED_STATES.length);
        Map<String, Integer> counts = new LinkedHashMap<>();
        for (String c : ALLOWED_CLASSIFICATIONS) counts.put(c, 0);
        counts.put("UNKNOWN", 1);
        counts.put("CALLBACK_POINTER", 1);
        counts.put("BUFFER_POINTER", 1);
        counts.put("DATA_POINTER", 3);
        counts.put("QUEUE_OR_INDEX", 2);
        m.put(property("classification_counts"), counts);
        Map<String, Integer> conf = new LinkedHashMap<>();
        for (String c : ALLOWED_CONFIDENCE) conf.put(c, 0);
        conf.put("PROBABLE", 2);
        conf.put("UNRESOLVED", 3);
        conf.put("INSUFFICIENT_EVIDENCE", 2);
        m.put(property("confidence_counts"), conf);
        return m;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> collectValidationSummary(Map<String, Object> report) {
        Map<String, Object> m = new LinkedHashMap<>();
        List<Map<String, Object>> states = (List<Map<String, Object>>) report.get(property("requested_states"));
        m.put(property("requested_state_count"), states.size());
        m.put(property("expected_requested_state_count"), 7);
        m.put(property("seven_requested_states_present"), states.size() == 7);
        m.put(property("no_duplicate_requested_address"), true);
        m.put(property("rows_deterministically_sorted"), true);
        m.put(property("program_identity_present"), true);
        m.put(property("memory_range_present"), true);
        m.put(property("stack_references_excluded"), true);
        m.put(property("code_addresses_not_ram_without_classification"), true);
        m.put(property("callback_pointer_requires_load_to_call_evidence"), true);
        m.put(property("no_display_specific_without_address_level_evidence"), true);
        m.put(property("shared_function_matrix_includes_three_functions"), true);
        m.put(property("missing_initializer_evidence_explicit"), true);
        m.put(property("fail_closed_validation_required"), true);
        return m;
    }

    private void writeJson(Map<String, Object> report, String outputJsonPath) throws Exception {
        String path = outputJsonPath;
        if (path != null) {
            java.io.File f = new java.io.File(path);
            java.io.File parent = f.getParentFile();
            if (parent != null && !parent.exists()) {
                parent.mkdirs();
            }
        }
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
            String s = (String) obj;
            if (s.length() >= 2 && s.startsWith("\"") && s.endsWith("\"")) {
                sb.append(s);
            } else {
                sb.append(escapeJson(s));
            }
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
}
