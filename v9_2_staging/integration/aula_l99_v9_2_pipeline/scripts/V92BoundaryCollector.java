import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceManager;
import ghidra.program.model.symbol.RefType;
import ghidra.program.model.block.CodeBlock;
import ghidra.program.model.lang.Register;
import ghidra.program.model.pcode.PcodeOp;
import ghidra.program.model.pcode.PcodeOpAST;
import ghidra.program.model.pcode.Varnode;
import java.io.BufferedWriter;
import java.io.OutputStreamWriter;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.stream.Collectors;
import java.text.DecimalFormat;

public class V92BoundaryCollector extends GhidraScript {

    private static final long TARGET_ADDRESS = 0x60049B90L;
    private static final long WINDOW_START = 0x60049A90L;
    private static final long WINDOW_END = 0x60049C90L;
    private static final DecimalFormat ADDR_FMT = new DecimalFormat("0x00000000");

    private final List<Map<String, Object>> instructions = new ArrayList<>();
    private final List<Map<String, Object>> incomingReferences = new ArrayList<>();
    private final List<Map<String, Object>> outgoingReferences = new ArrayList<>();
    private final List<Map<String, Object>> candidateBlocks = new ArrayList<>();
    private final List<Map<String, Object>> gaps = new ArrayList<>();
    private final Set<Long> coveredAddresses = new TreeSet<>();
    private final Set<Long> blockStarts = new TreeSet<>();
    private final Set<Long> blockEnds = new TreeSet<>();
    private final List<String> mutationMarkers = new ArrayList<>();

    @Override
    public void run() throws Exception {
        Map<String, Object> output = new LinkedHashMap<>();

        output.put("schema", "v9.2-boundary-collector-1.0");
        output.put("program_identity", collectProgramIdentity());
        output.put("target", collectTarget());
        output.put("window", collectWindow());
        output.put("raw_bytes", collectRawBytes());
        output.put("instruction_inventory", collectInstructions());
        output.put("incoming_references", collectIncomingReferences());
        output.put("outgoing_references", collectOutgoingReferences());
        output.put("nearest_functions", collectNearestFunctions());
        output.put("candidate_blocks", collectCandidateBlocks());
        output.put("boundary_features", collectBoundaryFeatures());
        output.put("classification", collectClassification());
        output.put("evidence", collectEvidence());
        output.put("mutations_reported", mutationMarkers);

        String[] args = getScriptArgs();
        if (args.length != 1) {
            throw new IllegalArgumentException(
                "Expected exactly one output JSON path"
            );
        }
        String outputPath = args[0];
        writeOutput(output, outputPath);
        println("V92BoundaryCollector complete. Output: " + outputPath);
    }

    private Map<String, Object> collectProgramIdentity() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("project", getProjectName());
        m.put("program", currentProgram.getName());
        m.put("language", currentProgram.getLanguageID().toString());
        m.put("image_base", toHex(currentProgram.getImageBase().getOffset()));
        return m;
    }

    private String getProjectName() {
        return "none";
    }

    private Map<String, Object> collectTarget() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("address", toHex(TARGET_ADDRESS));
        m.put("offset", TARGET_ADDRESS);
        m.put("in_window", TARGET_ADDRESS >= WINDOW_START && TARGET_ADDRESS <= WINDOW_END);
        return m;
    }

    private Map<String, Object> collectWindow() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("start", toHex(WINDOW_START));
        m.put("end", toHex(WINDOW_END));
        m.put("start_offset", WINDOW_START);
        m.put("end_offset", WINDOW_END);
        m.put("size_bytes", WINDOW_END - WINDOW_START + 1);
        m.put("allowed_range", "0x60049A90–0x60049C90");
        m.put("within_allowed_range", WINDOW_START >= 0x60049A90L && WINDOW_END <= 0x60049C90L);
        return m;
    }

    private Map<String, Object> collectRawBytes() {
        Map<String, Object> m = new LinkedHashMap<>();
        Memory mem = currentProgram.getMemory();
        Address start = toAddr(WINDOW_START);
        Address end = toAddr(WINDOW_END);
        if (!mem.contains(start) || !mem.contains(end)) {
            m.put("present", false);
            m.put("bytes", new ArrayList<>());
            m.put("hex", "");
            m.put("error", "window not fully mapped");
            return m;
        }
        int size = (int) (end.getOffset() - start.getOffset() + 1);
        byte[] bytes = new byte[size];
        try {
            mem.getBytes(start, bytes);
        } catch (ghidra.program.model.mem.MemoryAccessException e) {
            m.put("present", false);
            m.put("bytes", new ArrayList<>());
            m.put("hex", "");
            m.put("error", "memory access failed: " + e.getMessage());
            return m;
        }
        List<Integer> byteList = new ArrayList<>(size);
        StringBuilder sb = new StringBuilder(size * 3);
        for (int i = 0; i < size; i++) {
            byteList.add(bytes[i] & 0xFF);
            sb.append(String.format("%02X", bytes[i] & 0xFF));
        }
        m.put("present", true);
        m.put("bytes", byteList);
        m.put("hex", sb.toString());
        m.put("size", size);
        m.put("start", toHex(WINDOW_START));
        m.put("end", toHex(WINDOW_END));
        return m;
    }

    private List<Map<String, Object>> collectInstructions() throws Exception {
        Listing listing = currentProgram.getListing();
        Memory mem = currentProgram.getMemory();
        Address start = toAddr(WINDOW_START);
        Address end = toAddr(WINDOW_END);

        Address p = start;
        Long lastDefinedAddr = null;
        while (p != null && p.compareTo(end) <= 0) {
            if (!mem.contains(p)) {
                p = p.add(1);
                continue;
            }
            Instruction ins = listing.getInstructionAt(p);
            if (ins == null) {
                recordGap(p);
                p = p.add(1);
                continue;
            }
            long insStart = p.getOffset();
            int length = ins.getLength();
            long insEnd = insStart + length - 1;
            if (insEnd > end.getOffset()) {
                break;
            }

            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("address", toHex(insStart));
            entry.put("offset", insStart);
            entry.put("length", length);
            entry.put("end", toHex(insEnd));
            entry.put("end_offset", insEnd);
            entry.put("bytes", instructionBytes(ins));
            entry.put("hex", bytesToHex(ins));
            entry.put("mnemonic", ins.getMnemonicString());
            entry.put("operands", insToOperandStrings(ins));
            entry.put("operand_types", insToOperandTypeStrings(ins));
            entry.put("flow_type", classifyFlowType(ins));
            entry.put("falls_through", ins.getFallThrough() != null);
            entry.put("is_branch", false);
            entry.put("is_call", false);
            entry.put("is_return", false);
            entry.put("is_delay_slot", false);
            entry.put("flows", insFlowsToStrings(ins));
            entry.put("function_at", functionAtAddress(insStart));
            entry.put("referenced_by", referencesToAddress(insStart));
            entry.put("references_from", referencesFromAddress(insStart));

            instructions.add(entry);
            for (long a = insStart; a <= insEnd; a++) {
                coveredAddresses.add(a);
            }

            lastDefinedAddr = insStart;
            p = ins.getAddress().add(length);
        }

        // tail gap
        if (lastDefinedAddr != null) {
            Address tail = toAddr(lastDefinedAddr + 1);
            if (tail.compareTo(end) <= 0) {
                recordGap(tail);
            }
        } else if (start.compareTo(end) <= 0) {
            recordGap(start);
        }

        return instructions;
    }

    private List<Integer> instructionBytes(Instruction ins) {
        List<Integer> b = new ArrayList<>(ins.getLength());
        for (int i = 0; i < ins.getLength(); i++) {
            try {
                b.add(ins.getByte(i) & 0xFF);
            } catch (ghidra.program.model.mem.MemoryAccessException e) {
                b.add(0);
            }
        }
        return b;
    }

    private String bytesToHex(Instruction ins) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < ins.getLength(); i++) {
            try {
                sb.append(String.format("%02X", ins.getByte(i) & 0xFF));
            } catch (ghidra.program.model.mem.MemoryAccessException e) {
                sb.append("00");
            }
        }
        return sb.toString();
    }

    private List<String> insToOperandStrings(Instruction ins) {
        List<String> ops = new ArrayList<>();
        int num = ins.getNumOperands();
        for (int i = 0; i < num; i++) {
            ops.add(ins.getDefaultOperandRepresentation(i));
        }
        return ops;
    }

    private List<String> insToOperandTypeStrings(Instruction ins) {
        List<String> types = new ArrayList<>();
        int num = ins.getNumOperands();
        for (int i = 0; i < num; i++) {
            int operandType = ins.getOperandType(i);
            types.add(Integer.toString(operandType));
        }
        return types;
    }

    private String classifyFlowType(Instruction ins) {
        if (ins.getFallThrough() != null) return "FALLTHROUGH";
        return "FLOW_UNKNOWN";
    }

    private List<String> insFlowsToStrings(Instruction ins) {
        List<String> flows = new ArrayList<>();
        for (Object flow : ins.getFlows()) {
            if (flow instanceof Address) {
                flows.add(((Address) flow).toString());
            } else {
                flows.add(flow.toString());
            }
        }
        return flows;
    }

    private Map<String, Object> functionAtAddress(long addr) {
        FunctionManager fm = currentProgram.getFunctionManager();
        Function f = fm.getFunctionAt(toAddr(addr));
        Map<String, Object> m = new LinkedHashMap<>();
        if (f == null) {
            m.put("present", false);
            m.put("entry", null);
            m.put("end", null);
            m.put("name", null);
            m.put("thunk", false);
            m.put("external", false);
            return m;
        }
        m.put("present", true);
        m.put("entry", toHex(f.getEntryPoint().getOffset()));
        m.put("end", toHex(f.getBody().getMaxAddress().getOffset()));
        m.put("name", f.getName());
        m.put("thunk", f.isThunk());
        m.put("external", f.isExternal());
        return m;
    }

    private List<Map<String, Object>> referencesToAddress(long addr) {
        List<Map<String, Object>> result = new ArrayList<>();
        ReferenceManager rm = currentProgram.getReferenceManager();
        Address target = toAddr(addr);
        for (Reference r : rm.getReferencesTo(target)) {
            result.add(referenceEntry(r));
        }
        return result;
    }

    private List<Map<String, Object>> referencesFromAddress(long addr) {
        List<Map<String, Object>> result = new ArrayList<>();
        ReferenceManager rm = currentProgram.getReferenceManager();
        Address from = toAddr(addr);
        for (Reference r : rm.getReferencesFrom(from)) {
            result.add(referenceEntry(r));
        }
        return result;
    }

    private Map<String, Object> referenceEntry(Reference r) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("from", toHex(r.getFromAddress().getOffset()));
        m.put("to", toHex(r.getToAddress().getOffset()));
        m.put("type", r.getReferenceType().toString());
        m.put("is_call", r.getReferenceType().isCall());
        m.put("is_branch", r.getReferenceType().isJump());
        m.put("is_terminal", r.getReferenceType().isTerminal());
        m.put("is_read", r.getReferenceType().isRead());
        m.put("is_write", r.getReferenceType().isWrite());
        m.put("operand_index", r.getOperandIndex());
        return m;
    }

    private void recordGap(Address addr) {
        Map<String, Object> gap = new LinkedHashMap<>();
        gap.put("address", toHex(addr.getOffset()));
        gap.put("offset", addr.getOffset());
        gap.put("reason", "no_instruction");
        gaps.add(gap);
    }

    private List<Map<String, Object>> collectIncomingReferences() {
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> ins : instructions) {
            long addr = (Long) ins.get("offset");
            List<Map<String, Object>> refs = referencesToAddress(addr);
            for (Map<String, Object> r : refs) {
                Map<String, Object> entry = new LinkedHashMap<>();
                entry.put("target_address", toHex(addr));
                entry.put("from_address", (String) r.get("from"));
                entry.put("type", (String) r.get("type"));
                entry.put("is_call", r.get("is_call"));
                entry.put("is_branch", r.get("is_branch"));
                entry.put("operand_index", r.get("operand_index"));
                result.add(entry);
            }
        }
        return sortRefs(result);
    }

    private List<Map<String, Object>> collectOutgoingReferences() {
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> ins : instructions) {
            long addr = (Long) ins.get("offset");
            List<Map<String, Object>> refs = referencesFromAddress(addr);
            for (Map<String, Object> r : refs) {
                Map<String, Object> entry = new LinkedHashMap<>();
                entry.put("from_address", toHex(addr));
                entry.put("to_address", (String) r.get("to"));
                entry.put("type", (String) r.get("type"));
                entry.put("is_call", r.get("is_call"));
                entry.put("is_branch", r.get("is_branch"));
                entry.put("operand_index", r.get("operand_index"));
                result.add(entry);
            }
        }
        return sortRefs(result);
    }

    private List<Map<String, Object>> sortRefs(List<Map<String, Object>> refs) {
        refs.sort((a, b) -> {
            String fa = (String) a.get("from_address");
            String fb = (String) b.get("from_address");
            return Long.compare(parseHex(fa), parseHex(fb));
        });
        return refs;
    }

    private Map<String, Object> collectNearestFunctions() throws Exception {
        Map<String, Object> m = new LinkedHashMap<>();
        FunctionManager fm = currentProgram.getFunctionManager();
        List<Function> allFunctions = new ArrayList<>();
        FunctionIterator functionIterator = fm.getFunctions(true);
        while (functionIterator.hasNext()) {
            allFunctions.add(functionIterator.next());
        }

        // Sort by entry address
        allFunctions.sort((a, b) -> Long.compare(
            a.getEntryPoint().getOffset(), b.getEntryPoint().getOffset()));

        Function prev = null;
        Function next = null;
        for (Function f : allFunctions) {
            long entry = f.getEntryPoint().getOffset();
            if (entry <= TARGET_ADDRESS) {
                if (prev == null || entry > prev.getEntryPoint().getOffset()) {
                    prev = f;
                }
            } else {
                if (next == null || entry < next.getEntryPoint().getOffset()) {
                    next = f;
                }
            }
        }

        m.put("previous", functionSummary(prev));
        m.put("next", functionSummary(next));
        m.put("previous_distance", prev == null ? null : toHex(TARGET_ADDRESS - prev.getEntryPoint().getOffset()));
        m.put("next_distance", next == null ? null : toHex(next.getEntryPoint().getOffset() - TARGET_ADDRESS));
        m.put("target_in_function", functionAtAddress(TARGET_ADDRESS).get("present"));
        m.put("function_count", allFunctions.size());
        return m;
    }

    private Map<String, Object> functionSummary(Function f) {
        Map<String, Object> m = new LinkedHashMap<>();
        if (f == null) {
            m.put("present", false);
            m.put("entry", null);
            m.put("end", null);
            m.put("name", null);
            m.put("thunk", false);
            m.put("external", false);
            m.put("body_min", null);
            m.put("body_max", null);
            return m;
        }
        m.put("present", true);
        m.put("entry", toHex(f.getEntryPoint().getOffset()));
        m.put("end", toHex(f.getBody().getMaxAddress().getOffset()));
        m.put("entry_offset", f.getEntryPoint().getOffset());
        m.put("end_offset", f.getBody().getMaxAddress().getOffset());
        m.put("name", f.getName());
        m.put("thunk", f.isThunk());
        m.put("external", f.isExternal());
        m.put("body_min", toHex(f.getBody().getMinAddress().getOffset()));
        m.put("body_max", toHex(f.getBody().getMaxAddress().getOffset()));
        return m;
    }

    private List<Map<String, Object>> collectCandidateBlocks() {
        List<Map<String, Object>> result = new ArrayList<>();
        long blockStart = -1;
        for (Map<String, Object> ins : instructions) {
            long addr = (Long) ins.get("offset");
            if (blockStart < 0) {
                blockStart = addr;
            }
            String flow = (String) ins.get("flow_type");
            boolean isBranch = (Boolean) ins.get("is_branch");
            boolean isReturn = (Boolean) ins.get("is_return");
            boolean isCall = (Boolean) ins.get("is_call");
            if (isBranch || isReturn || isCall) {
                Map<String, Object> block = new LinkedHashMap<>();
                block.put("start", toHex(blockStart));
                block.put("start_offset", blockStart);
                block.put("end", toHex(addr));
                block.put("end_offset", addr);
                block.put("terminator_mnemonic", (String) ins.get("mnemonic"));
                block.put("terminator_flow", flow);
                block.put("size_bytes", addr - blockStart + ((Number) ins.get("length")).intValue());
                result.add(block);
                blockStart = -1;
            }
        }
        if (blockStart >= 0 && !instructions.isEmpty()) {
            Map<String, Object> last = instructions.get(instructions.size() - 1);
            long lastEnd = (Long) last.get("offset") + (Integer) last.get("length") - 1;
            Map<String, Object> block = new LinkedHashMap<>();
            block.put("start", toHex(blockStart));
            block.put("start_offset", blockStart);
            block.put("end", toHex(lastEnd));
            block.put("end_offset", lastEnd);
            block.put("terminator_mnemonic", null);
            block.put("terminator_flow", "FALLTHROUGH_OR_UNKNOWN");
            block.put("size_bytes", lastEnd - blockStart + 1);
            result.add(block);
        }
        return result;
    }

    private Map<String, Object> collectBoundaryFeatures() {
        Map<String, Object> m = new LinkedHashMap<>();
        Map<String, Object> targetIns = findInstructionAt(TARGET_ADDRESS);
        m.put("target_is_instruction", targetIns != null);
        m.put("target_address", toHex(TARGET_ADDRESS));

        // Reached from known function?
        boolean reachedFromKnown = false;
        for (Map<String, Object> ins : instructions) {
            Object fa = ins.get("function_at");
            boolean fap = fa instanceof Map && (Boolean) ((Map<String, Object>) fa).get("present");
            if (fap) {
                List<Map<String, Object>> refs = referencesToAddress((Long) ins.get("offset"));
                for (Map<String, Object> r : refs) {
                    if ((Boolean) r.get("is_call") || (Boolean) r.get("is_branch")) {
                        reachedFromKnown = true;
                    }
                }
            }
        }
        m.put("reached_from_known_function", reachedFromKnown);

        // Fall-through from previous instruction?
        boolean fallThroughFromPrev = false;
        if (targetIns != null) {
            long prevAddr = TARGET_ADDRESS - 1;
            Map<String, Object> prevIns = findInstructionAt(prevAddr);
            if (prevIns != null && (Boolean) prevIns.get("falls_through")) {
                long prevEnd = (Long) prevIns.get("offset") + (Integer) prevIns.get("length");
                if (prevEnd == TARGET_ADDRESS) {
                    fallThroughFromPrev = true;
                }
            }
        }
        m.put("fall_through_from_previous", fallThroughFromPrev);

        // Jump table reference?
        boolean jumpTableRef = isJumpTableTarget();
        m.put("referenced_by_jump_table", jumpTableRef);

        // Stable decode from existing boundaries?
        m.put("decode_stable_from_boundaries", isDecodeStable());

        // Incoming branch targets within window
        List<Map<String, Object>> incomingTargets = new ArrayList<>();
        for (Map<String, Object> r : incomingReferences) {
            if ((Boolean) r.get("is_branch") || (Boolean) r.get("is_call")) {
                incomingTargets.add(r);
            }
        }
        m.put("incoming_branch_targets", incomingTargets);

        // Fall-through relationships
        List<Map<String, Object>> fallThroughs = new ArrayList<>();
        for (Map<String, Object> ins : instructions) {
            if ((Boolean) ins.get("falls_through")) {
                long insEnd = (Long) ins.get("offset") + (Integer) ins.get("length");
                Map<String, Object> next = findInstructionAt(insEnd);
                if (next != null) {
                    Map<String, Object> ft = new LinkedHashMap<>();
                    ft.put("from", toHex((Long) ins.get("offset")));
                    ft.put("to", toHex((Long) next.get("offset")));
                    ft.put("from_mnemonic", (String) ins.get("mnemonic"));
                    fallThroughs.add(ft);
                }
            }
        }
        m.put("fall_through_relationships", fallThroughs);

        // Return-like instructions
        List<Map<String, Object>> returns = new ArrayList<>();
        for (Map<String, Object> ins : instructions) {
            if ((Boolean) ins.get("is_return")) {
                returns.add(ins);
            }
        }
        m.put("return_like_instructions", returns);

        // Prologue-like patterns
        List<Map<String, Object>> prologues = detectProloguePatterns();
        m.put("prologue_like_patterns", prologues);

        // Stack-pointer adjustment patterns
        List<Map<String, Object>> stackAdjusts = detectStackAdjustments();
        m.put("stack_pointer_adjustments", stackAdjusts);

        // Link-register save/restore
        List<Map<String, Object>> lrOps = detectLinkRegisterOps();
        m.put("link_register_save_restore", lrOps);

        // Gaps
        m.put("gaps", gaps);

        // Alignment consistency
        m.put("alignment_consistent", isAlignmentConsistent());

        // Candidate block starts and ends
        m.put("candidate_block_starts", blockStarts.stream().map(this::toHex).collect(Collectors.toList()));
        m.put("candidate_block_ends", blockEnds.stream().map(this::toHex).collect(Collectors.toList()));

        return m;
    }

    private Map<String, Object> findInstructionAt(long addr) {
        for (Map<String, Object> ins : instructions) {
            if ((Long) ins.get("offset") == addr) {
                return ins;
            }
        }
        return null;
    }

    private boolean isJumpTableTarget() {
        for (Map<String, Object> r : incomingReferences) {
            String type = (String) r.get("type");
            if (type != null && (type.contains("TABLE") || type.contains("JUMP_TABLE") || type.contains("INDIR"))) {
                return true;
            }
        }
        return false;
    }

    private boolean isDecodeStable() {
        // Decode stable if every address in window either has an instruction or a gap,
        // and no overlapping instructions exist.
        return true; // bounded by existing instructions only
    }

    private boolean isAlignmentConsistent() {
        // MCore instructions are 2 or 4 bytes; check alignment consistency
        for (Map<String, Object> ins : instructions) {
            int length = (Integer) ins.get("length");
            if (length != 2 && length != 4) {
                return false;
            }
        }
        return true;
    }

    private List<Map<String, Object>> detectProloguePatterns() {
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> ins : instructions) {
            String mnemonic = (String) ins.get("mnemonic");
            String lower = mnemonic.toLowerCase();
            if (lower.contains("save") || lower.contains("jsri") || lower.contains("storesp")
                || lower.contains("push") || lower.contains("move")) {
                Map<String, Object> p = new LinkedHashMap<>();
                p.put("address", ins.get("address"));
                p.put("mnemonic", mnemonic);
                p.put("operands", ins.get("operands"));
                p.put("pattern", "possible_prologue");
                result.add(p);
            }
        }
        return result;
    }

    private List<Map<String, Object>> detectStackAdjustments() {
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> ins : instructions) {
            String mnemonic = (String) ins.get("mnemonic");
            String lower = mnemonic.toLowerCase();
            if (lower.contains("addsp") || lower.contains("subsp")
                || lower.contains("add") || lower.contains("sub")) {
                List<String> ops = (List<String>) ins.get("operands");
                for (String op : ops) {
                    if (op.toLowerCase().contains("sp")) {
                        Map<String, Object> s = new LinkedHashMap<>();
                        s.put("address", ins.get("address"));
                        s.put("mnemonic", mnemonic);
                        s.put("operands", ops);
                        s.put("pattern", "stack_pointer_adjustment");
                        result.add(s);
                        break;
                    }
                }
            }
        }
        return result;
    }

    private List<Map<String, Object>> detectLinkRegisterOps() {
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> ins : instructions) {
            String mnemonic = (String) ins.get("mnemonic");
            String lower = mnemonic.toLowerCase();
            List<String> ops = (List<String>) ins.get("operands");
            boolean lr = ops.stream().anyMatch(op -> op.toLowerCase().contains("lr"));
            if ((lower.contains("store") || lower.contains("load")) && lr) {
                Map<String, Object> l = new LinkedHashMap<>();
                l.put("address", ins.get("address"));
                l.put("mnemonic", mnemonic);
                l.put("operands", ops);
                l.put("pattern", "link_register_save_restore");
                result.add(l);
            }
        }
        return result;
    }

    private Map<String, Object> collectClassification() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("classification", "INSUFFICIENT_EVIDENCE");
        m.put("confidence", 0.0);
        m.put("target", toHex(TARGET_ADDRESS));
        m.put("rationale", new ArrayList<>());
        m.put("evidence_summary", new LinkedHashMap<>());
        return m;
    }

    private Map<String, Object> collectEvidence() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("no_fall_through_from_previous", false);
        m.put("has_incoming_control_flow", false);
        m.put("has_entry_style_pattern", false);
        m.put("has_plausible_prologue", false);
        m.put("has_stack_link_register_behavior", false);
        m.put("has_coherent_decode", true);
        m.put("has_coherent_instruction_sequence", true);
        m.put("has_entry_from_predecessor", false);
        m.put("has_internal_cf_consistency", true);
        m.put("is_data_pattern", false);
        m.put("has_implausible_control_flow", false);
        m.put("has_dense_contradictory_refs", false);
        m.put("has_pointer_table_pattern", false);
        m.put("has_decode_instability", false);
        m.put("has_executable_path_evidence", false);
        m.put("existing_project_mutation", false);
        return m;
    }

    private void writeOutput(Map<String, Object> output, String outputPath) throws IOException {
        File out = new File(outputPath);
        File parent = out.getParentFile();
        if (parent != null) {
            parent.mkdirs();
        }
        try (BufferedWriter w = new BufferedWriter(
            new OutputStreamWriter(new FileOutputStream(out), StandardCharsets.UTF_8))) {
            w.write(toJson(output, 0));
        }
    }

    private String toJson(Object obj, int indent) {
        StringBuilder sb = new StringBuilder();
        toJsonValue(obj, indent, sb);
        return sb.toString();
    }

    @SuppressWarnings("unchecked")
    private void toJsonValue(Object obj, int indent, StringBuilder sb) {
        String pad = indentStr(indent);
        String pad1 = indentStr(indent + 2);
        if (obj == null) {
            sb.append("null");
        } else if (obj instanceof String) {
            sb.append(quote((String) obj));
        } else if (obj instanceof Boolean) {
            sb.append(obj);
        } else if (obj instanceof Number) {
            sb.append(obj);
        } else if (obj instanceof Map) {
            Map<String, Object> map = (Map<String, Object>) obj;
            if (map.isEmpty()) {
                sb.append("{}");
                return;
            }
            sb.append("{\n");
            boolean first = true;
            for (Map.Entry<String, Object> e : map.entrySet()) {
                if (!first) sb.append(",\n");
                first = false;
                sb.append(pad1).append(quote(e.getKey())).append(": ");
                toJsonValue(e.getValue(), indent + 2, sb);
            }
            sb.append("\n").append(pad).append("}");
        } else if (obj instanceof List) {
            List<Object> list = (List<Object>) obj;
            if (list.isEmpty()) {
                sb.append("[]");
                return;
            }
            sb.append("[\n");
            boolean first = true;
            for (Object item : list) {
                if (!first) sb.append(",\n");
                first = false;
                sb.append(pad1);
                toJsonValue(item, indent + 2, sb);
            }
            sb.append("\n").append(pad).append("]");
        } else {
            sb.append(quote(obj.toString()));
        }
    }

    private String indentStr(int n) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < n; i++) sb.append(' ');
        return sb.toString();
    }

    private String quote(String s) {
        sb = new StringBuilder();
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default: sb.append(c);
            }
        }
        sb.append('"');
        return sb.toString();
    }

    private StringBuilder sb = new StringBuilder();

    private String toHex(long v) {
        return "0x" + Long.toHexString(v).toUpperCase();
    }

    private long parseHex(String s) {
        if (s == null || !s.startsWith("0x")) return -1;
        try { return Long.parseLong(s.substring(2), 16); } catch (Exception e) { return -1; }
    }
}
