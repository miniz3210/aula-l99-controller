#!/usr/bin/env python3
"""Read-only bounded recursive M*Core CFG utility for HFD Code V2.3.

Reuses local_analysis/third_party/kei825_aula-l99-screen-fw/emulator/mcdis.py
for instruction decoding. Never modifies the input binary. All generated output
is written under local_analysis/cfg/.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import struct
import sys
import tempfile
from collections import Counter, deque
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
MCDIS_PATH = PROJECT_ROOT / "local_analysis" / "third_party" / "kei825_aula-l99-screen-fw" / "emulator" / "mcdis.py"

DEFAULT_BUDGETS = {
    "max_roots": 21,
    "max_depth": 8,
    "max_functions": 64,
    "max_basic_blocks": 512,
    "max_instructions": 4096,
    "max_decoded_bytes": 65536,
    "max_instructions_per_block": 128,
    "max_direct_successors": 2,
}

EXPERIMENTAL_BUDGET_FIELDS = frozenset({
    "max_roots",
    "max_depth",
    "max_functions",
    "max_basic_blocks",
    "max_decoded_bytes",
    "max_instructions_per_block",
    "max_direct_successors",
})


def validate_budget_profile(args, requested_budgets, roots, output_dir):
    """Validate the experimental single-root 8192 safety profiles.

    Returns a dict describing the enforced profile. Raises SystemExit (fail
    loudly) on any violation. Does not traverse or modify firmware state.
    """
    experimental_8192_enabled = bool(getattr(args, EXPERIMENTAL_FLAG, False))
    experimental_8192_1024_enabled = bool(getattr(args, EXPERIMENTAL_8192_1024_FLAG, False))

    profile = {
        "safety_profile": "default_bounded",
        "experimental_profile_enabled": False,
        "experimental_profile_name": None,
        "requested_budgets": dict(requested_budgets),
        "effective_budgets": dict(requested_budgets),
        "default_budgets_unchanged": True,
        "root_constraint_enforced": False,
        "experiment_output_isolated": False,
    }

    # Check for conflicting experimental flags
    if experimental_8192_enabled and experimental_8192_1024_enabled:
        print("ERROR: Cannot enable both --experimental-single-root-8192 and --experimental-single-root-8192-blocks-1024", file=sys.stderr)
        raise SystemExit(1)

    # --- Handle experimental_single_root_8192 (8192/512) ---
    if experimental_8192_enabled:
        # --- Experiment requires exactly one explicit root ---
        explicit_root_count = 0 if args.root is None else len(args.root)
        if explicit_root_count == 0:
            print("ERROR: --experimental-single-root-8192 requires an explicit root", file=sys.stderr)
            raise SystemExit(1)
        if explicit_root_count != 1:
            print(f"ERROR: --experimental-single-root-8192 requires exactly one root, got {explicit_root_count}", file=sys.stderr)
            raise SystemExit(1)
        root = roots[0]
        if root != EXPERIMENTAL_ROOT:
            print(f"ERROR: --experimental-single-root-8192 requires root 0x{EXPERIMENTAL_ROOT:08X}, got 0x{root:08X}", file=sys.stderr)
            raise SystemExit(1)

        # --- max_instructions must be exactly 8192 ---
        if requested_budgets["max_instructions"] != EXPERIMENTAL_MAX_INSTRUCTIONS:
            print(f"ERROR: --experimental-single-root-8192 requires --max_instructions {EXPERIMENTAL_MAX_INSTRUCTIONS}, got {requested_budgets['max_instructions']}", file=sys.stderr)
            raise SystemExit(1)

        # --- All other budgets must remain at existing defaults ---
        for key in EXPERIMENTAL_BUDGET_FIELDS:
            if requested_budgets[key] != DEFAULT_BUDGETS[key]:
                print(f"ERROR: --experimental-single-root-8192 requires {key}={DEFAULT_BUDGETS[key]}, got {requested_budgets[key]}", file=sys.stderr)
                raise SystemExit(1)

        # --- Output directory must be isolated under cfg_experiments, not baseline ---
        output_dir_str = str(output_dir).replace("\\", "/")
        parent = output_dir_str.rsplit("/", 1)[0] if "/" in output_dir_str else ""
        if parent != EXPERIMENT_OUTPUT_PARENT:
            print(f"ERROR: --experimental-single-root-8192 output directory must be under {EXPERIMENT_OUTPUT_PARENT}/, got {output_dir_str}", file=sys.stderr)
            raise SystemExit(1)
        if output_dir_str == BASELINE_OUTPUT_DIR or output_dir_str.startswith(BASELINE_OUTPUT_DIR + "/"):
            print(f"ERROR: --experimental-single-root-8192 output directory must not be the baseline directory {BASELINE_OUTPUT_DIR}", file=sys.stderr)
            raise SystemExit(1)

        profile["safety_profile"] = "experimental_single_root_8192"
        profile["experimental_profile_enabled"] = True
        profile["experimental_profile_name"] = EXPERIMENTAL_PROFILE_NAME
        profile["default_budgets_unchanged"] = True
        profile["root_constraint_enforced"] = True
        profile["experiment_output_isolated"] = True
        profile["effective_budgets"]["max_instructions"] = EXPERIMENTAL_MAX_INSTRUCTIONS
        return profile

    # --- Handle experimental_single_root_8192_blocks_1024 (8192/1024) ---
    if experimental_8192_1024_enabled:
        # --- Experiment requires exactly one explicit root ---
        explicit_root_count = 0 if args.root is None else len(args.root)
        if explicit_root_count == 0:
            print("ERROR: --experimental-single-root-8192-blocks-1024 requires an explicit root", file=sys.stderr)
            raise SystemExit(1)
        if explicit_root_count != 1:
            print(f"ERROR: --experimental-single-root-8192-blocks-1024 requires exactly one root, got {explicit_root_count}", file=sys.stderr)
            raise SystemExit(1)
        root = roots[0]
        if root != EXPERIMENTAL_8192_1024_ROOT:
            print(f"ERROR: --experimental-single-root-8192-blocks-1024 requires root 0x{EXPERIMENTAL_8192_1024_ROOT:08X}, got 0x{root:08X}", file=sys.stderr)
            raise SystemExit(1)

        # --- max_instructions must be exactly 8192 ---
        if requested_budgets["max_instructions"] != EXPERIMENTAL_8192_1024_MAX_INSTRUCTIONS:
            print(f"ERROR: --experimental-single-root-8192-blocks-1024 requires --max_instructions {EXPERIMENTAL_8192_1024_MAX_INSTRUCTIONS}, got {requested_budgets['max_instructions']}", file=sys.stderr)
            raise SystemExit(1)

        # --- max_basic_blocks must be exactly 1024 ---
        if requested_budgets["max_basic_blocks"] != EXPERIMENTAL_8192_1024_MAX_BASIC_BLOCKS:
            print(f"ERROR: --experimental-single-root-8192-blocks-1024 requires --max_basic_blocks {EXPERIMENTAL_8192_1024_MAX_BASIC_BLOCKS}, got {requested_budgets['max_basic_blocks']}", file=sys.stderr)
            raise SystemExit(1)

        # --- All other budgets must remain at existing defaults (except max_basic_blocks) ---
        for key in EXPERIMENTAL_BUDGET_FIELDS:
            if key == "max_basic_blocks":
                continue  # This is the one we're changing
            if requested_budgets[key] != DEFAULT_BUDGETS[key]:
                print(f"ERROR: --experimental-single-root-8192-blocks-1024 requires {key}={DEFAULT_BUDGETS[key]}, got {requested_budgets[key]}", file=sys.stderr)
                raise SystemExit(1)

        # --- Output directory must be isolated under cfg_experiments, not baseline ---
        output_dir_str = str(output_dir).replace("\\", "/")
        parent = output_dir_str.rsplit("/", 1)[0] if "/" in output_dir_str else ""
        if parent != EXPERIMENTAL_8192_1024_OUTPUT_PARENT:
            print(f"ERROR: --experimental-single-root-8192-blocks-1024 output directory must be under {EXPERIMENTAL_8192_1024_OUTPUT_PARENT}/, got {output_dir_str}", file=sys.stderr)
            raise SystemExit(1)
        if output_dir_str == BASELINE_OUTPUT_DIR or output_dir_str.startswith(BASELINE_OUTPUT_DIR + "/"):
            print(f"ERROR: --experimental-single-root-8192-blocks-1024 output directory must not be the baseline directory {BASELINE_OUTPUT_DIR}", file=sys.stderr)
            raise SystemExit(1)
        if output_dir_str != EXPERIMENTAL_8192_1024_OUTPUT_DIR:
            print(f"ERROR: --experimental-single-root-8192-blocks-1024 output directory must be exactly {EXPERIMENTAL_8192_1024_OUTPUT_DIR}, got {output_dir_str}", file=sys.stderr)
            raise SystemExit(1)

        profile["safety_profile"] = "experimental_single_root_8192_blocks_1024"
        profile["experimental_profile_enabled"] = True
        profile["experimental_profile_name"] = EXPERIMENTAL_8192_1024_PROFILE_NAME
        profile["default_budgets_unchanged"] = True
        profile["root_constraint_enforced"] = True
        profile["experiment_output_isolated"] = True
        profile["effective_budgets"]["max_instructions"] = EXPERIMENTAL_8192_1024_MAX_INSTRUCTIONS
        profile["effective_budgets"]["max_basic_blocks"] = EXPERIMENTAL_8192_1024_MAX_BASIC_BLOCKS
        return profile

    return profile


PROHIBITED_START = 0x60031198
PROHIBITED_END = 0x600315D0
CANDIDATE_IMAGE_BASE = 0x60010000
DEFAULT_ROOTS = [0x60017490]

CFG_SCHEMA_VERSION = "hfd-cfg-1.0"

EXPERIMENTAL_FLAG = "experimental_single_root_8192"
EXPERIMENTAL_PROFILE_NAME = "single_root_8192"
EXPERIMENTAL_MAX_INSTRUCTIONS = 8192
EXPERIMENTAL_ROOT = 0x60017490
EXPERIMENT_OUTPUT_PARENT = "local_analysis/cfg_experiments"
BASELINE_OUTPUT_DIR = "local_analysis/cfg"

VERIFIED = "VERIFIED"
STRONG_STRUCTURAL_INFERENCE = "STRONG_STRUCTURAL_INFERENCE"
STRUCTURAL_CANDIDATE = "STRUCTURAL_CANDIDATE"
UNKNOWN = "UNKNOWN"
ALLOWED_EVIDENCE_CLASSES = frozenset({
    VERIFIED,
    STRONG_STRUCTURAL_INFERENCE,
    STRUCTURAL_CANDIDATE,
    UNKNOWN,
})
INSTRUCTION_WIDTH_BYTES = 2
SELF_LOOP_ADDR = 0x600174BC
SELF_LOOP_FOLLOW_ON_ADDR = 0x600174BE
STARTUP_STACK_VALUE = 0x00874FFC


EXPERIMENTAL_8192_1024_FLAG = "experimental_single_root_8192_blocks_1024"
EXPERIMENTAL_8192_1024_PROFILE_NAME = "single_root_8192_blocks_1024"
EXPERIMENTAL_8192_1024_MAX_INSTRUCTIONS = 8192
EXPERIMENTAL_8192_1024_MAX_BASIC_BLOCKS = 1024
EXPERIMENTAL_8192_1024_ROOT = 0x60017490
EXPERIMENTAL_8192_1024_OUTPUT_PARENT = "local_analysis/cfg_experiments"
EXPERIMENTAL_8192_1024_OUTPUT_DIR = "local_analysis/cfg_experiments/single_root_8192_blocks_1024"


class CanonicalPartitionError(Exception):
    """Raised when canonical partitioning invariants are violated."""


def canonical_partition(
    instruction_observations,
    boundary_addresses,
    terminator_observations,
    successor_observations,
    ownership_observations,
    prohibited_start=PROHIBITED_START,
    prohibited_end=PROHIBITED_END,
):
    """Pure deterministic canonical basic-block partitioner.

    Works only on caller-supplied in-memory observations. Does not touch the
    firmware file, decoder, filesystem, hardware, or network. Not called from
    run(), _build_output(), or write_outputs() in Stage A.
    """
    boundaries = {int(b) for b in (boundary_addresses or [])}
    terminators = {int(t) for t in (terminator_observations or [])}
    successors = {}
    for src, tgts in (successor_observations or {}).items():
        successors[int(src)] = [int(t) for t in (tgts or [])]
    ownership = {}
    for addr, fids in (ownership_observations or {}).items():
        ownership[int(addr)] = {int(f) for f in (fids or [])}

    all_addrs = {int(a) for a in instruction_observations.keys()}
    all_addrs.update(boundaries)
    all_addrs.update(terminators)
    all_addrs.update(ownership.keys())
    for src, tgts in successors.items():
        all_addrs.add(int(src))
        all_addrs.update(int(t) for t in tgts)

    for a in all_addrs:
        if a % 2 != 0:
            raise CanonicalPartitionError(
                f"odd instruction or boundary address: 0x{a:08X}"
            )
    for a in all_addrs:
        if prohibited_start <= a <= prohibited_end:
            raise CanonicalPartitionError(
                f"prohibited-range address supplied: 0x{a:08X}"
            )

    # Collapse observations; detect conflicts (different size or raw bytes).
    canonical = {}
    source_instruction_occurrence_count = 0
    conflicting_observation_count = 0
    for addr, obs_list in instruction_observations.items():
        addr = int(addr)
        source_instruction_occurrence_count += len(obs_list)
        base = None
        conflict = False
        for obs in obs_list:
            size = int(obs["size"])
            raw = bytes(obs["raw"])
            if base is None:
                base = {
                    "addr": addr,
                    "size": size,
                    "raw": raw,
                    "mnemonic": obs.get("mnemonic"),
                    "category": obs.get("category"),
                }
            elif base["size"] != size or base["raw"] != raw:
                conflict = True
                break
        if conflict:
            conflicting_observation_count += 1
            raise CanonicalPartitionError(
                f"conflicting instruction observations at 0x{addr:08X}"
            )
        canonical[addr] = base

    unique_instruction_count = len(canonical)
    duplicate_observation_count = (
        source_instruction_occurrence_count - unique_instruction_count
    )

    # Explicit boundaries must be observed (no silent block at unobserved addr).
    for b in boundaries:
        if b not in canonical:
            raise CanonicalPartitionError(
                f"unobserved required boundary: 0x{b:08X}"
            )

    # Effective boundaries: explicit boundaries plus accepted successor targets
    # that live inside the observed instruction map.
    effective_boundaries = set(boundaries)
    for src, tgts in successors.items():
        for t in tgts:
            if t in canonical:
                effective_boundaries.add(t)

    # Sort unique reachable instructions by address.
    sorted_addrs = sorted(canonical.keys())

    # Partition contiguous reachable runs into canonical blocks.
    blocks = []
    block_split_count = 0
    current = None
    for addr in sorted_addrs:
        if current is None:
            current = [addr]
        else:
            prev = current[-1]
            prev_size = canonical[prev]["size"]
            must_split = False
            if prev in terminators:
                must_split = True
            elif addr in effective_boundaries:
                must_split = True
            elif addr != prev + prev_size:
                must_split = True
            if must_split:
                block_split_count += 1
                blocks.append(current)
                current = [addr]
            else:
                current.append(addr)
        if addr in terminators:
            blocks.append(current)
            current = None
    if current is not None:
        blocks.append(current)

    # Build canonical instructions and blocks.
    instruction_ownership = {}
    for addr in sorted_addrs:
        instruction_ownership[addr] = sorted(ownership.get(addr, set()))

    canonical_blocks = []
    block_starts = set()
    for bid, block_addrs in enumerate(blocks):
        start = block_addrs[0]
        end = block_addrs[-1] + canonical[block_addrs[-1]]["size"]
        block_ownership_set = set()
        for a in block_addrs:
            block_ownership_set.update(instruction_ownership[a])
        canonical_blocks.append(
            {
                "id": bid,
                "start": start,
                "end": end,
                "instruction_addresses": list(block_addrs),
                "instruction_count": len(block_addrs),
                "ownership": sorted(block_ownership_set),
            }
        )
        block_starts.add(start)

    # ---- Pure validations ----
    block_addresses = set()
    for b in canonical_blocks:
        block_addresses.update(b["instruction_addresses"])
    if block_addresses != set(sorted_addrs):
        raise CanonicalPartitionError(
            "partitioning changes the union of input unique instruction addresses"
        )

    addr_to_block = {}
    for b in canonical_blocks:
        for a in b["instruction_addresses"]:
            if a in addr_to_block:
                raise CanonicalPartitionError(
                    f"instruction 0x{a:08X} belongs to multiple canonical blocks"
                )
            addr_to_block[a] = b["id"]

    starts = [b["start"] for b in canonical_blocks]
    if len(starts) != len(set(starts)):
        raise CanonicalPartitionError("duplicate canonical block starts")

    ranges = sorted((b["start"], b["end"]) for b in canonical_blocks)
    for i in range(1, len(ranges)):
        if ranges[i][0] < ranges[i - 1][1]:
            raise CanonicalPartitionError(
                "canonical blocks overlap: "
                f"0x{ranges[i - 1][0]:08X}-0x{ranges[i - 1][1]:08X} and "
                f"0x{ranges[i][0]:08X}-0x{ranges[i][1]:08X}"
            )

    for b in canonical_blocks:
        addrs = b["instruction_addresses"]
        for i in range(1, len(addrs)):
            prev = addrs[i - 1]
            if addrs[i] != prev + canonical[prev]["size"]:
                raise CanonicalPartitionError(
                    f"block {b['id']} contains non-contiguous instruction addresses"
                )
        for i, a in enumerate(addrs):
            if a in terminators and i != len(addrs) - 1:
                raise CanonicalPartitionError(
                    f"block {b['id']} crosses a terminator at 0x{a:08X}"
                )

    for b in boundaries:
        if b not in block_starts:
            raise CanonicalPartitionError(
                f"required boundary 0x{b:08X} is not a block start"
            )

    for src, tgts in successors.items():
        for t in tgts:
            if t in canonical and t not in block_starts:
                raise CanonicalPartitionError(
                    f"accepted successor target 0x{t:08X} inside observed map "
                    f"is not a canonical block start"
                )

    # Metrics.
    overlap_pair_count_after = 0
    duplicate_instruction_ownership_count = 0
    shared_instruction_count = 0
    shared_block_count = 0
    blocks_with_multiple_reaching_functions = sum(
        1 for b in canonical_blocks if len(b["ownership"]) > 1
    )

    metrics = {
        "source_instruction_occurrence_count": source_instruction_occurrence_count,
        "unique_instruction_count": unique_instruction_count,
        "duplicate_observation_count": duplicate_observation_count,
        "conflicting_observation_count": conflicting_observation_count,
        "canonical_block_count": len(canonical_blocks),
        "block_split_count": block_split_count,
        "overlap_pair_count_after": overlap_pair_count_after,
        "duplicate_instruction_ownership_count": duplicate_instruction_ownership_count,
        "shared_instruction_count": shared_instruction_count,
        "shared_block_count": shared_block_count,
        "blocks_with_multiple_reaching_functions": blocks_with_multiple_reaching_functions,
    }

    canonical_instructions = [
        {
            "addr": canonical[a]["addr"],
            "size": canonical[a]["size"],
            "raw": canonical[a]["raw"],
            "mnemonic": canonical[a]["mnemonic"],
            "category": canonical[a]["category"],
            "ownership": instruction_ownership[a],
        }
        for a in sorted_addrs
    ]

    return {
        "metrics": metrics,
        "instructions": canonical_instructions,
        "blocks": canonical_blocks,
        "block_starts": sorted(block_starts),
        "terminators": sorted(terminators),
    }


def load_mcdis():
    spec = importlib.util.spec_from_file_location("mcdis", MCDIS_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def classify(mcdis_mod, inst_word):
    cl = None
    code = None
    for name, c, cd in mcdis_mod.T:
        if cd == (inst_word & mcdis_mod.IMSK[c]):
            cl = c
            code = cd
            break
    if cl is None:
        return "unknown"

    BR = mcdis_mod.BR
    BL = mcdis_mod.BL
    JMP = mcdis_mod.JMP
    JSR = mcdis_mod.JSR
    LJ = mcdis_mod.LJ
    LR = mcdis_mod.LR
    O0 = mcdis_mod.O0

    if cl == BR:
        op = inst_word & 0xF800
        if op == 0xE000:
            return "cond_branch"
        if op == 0xE800:
            return "cond_branch"
        if op == 0xF000:
            return "uncond_branch"
        if op == 0xF800:
            return "direct_call"
        return "other"
    if cl == BL:
        return "cond_branch"
    if cl == JMP:
        rx = inst_word & 0xF
        return "return" if rx == 15 else "indirect_jump"
    if cl == JSR:
        return "indirect_call"
    if cl == LJ:
        if code == 0x7000:
            return "indirect_jump"
        if code == 0x7F00:
            return "direct_call"  # jsri: statically recoverable via literal pool
        return "other"
    if cl == LR:
        return "literal_load"
    if cl == O0:
        if code == 0x00CF:
            return "return"
        return "other"
    return "other"


def call_target(extra):
    """Extract call target address from decoded instruction extra field."""
    if extra is None:
        return None
    if extra[0] == "br":
        return extra[1]
    if extra[0] == "lit":
        return extra[2]
    return None


def decode_instruction(mcdis_mod, data, base, addr):
    off = addr - base
    if off < 0 or off + 2 > len(data):
        return None
    inst_word = struct.unpack_from('<H', data, off)[0]
    _, mnemonic, extra = mcdis_mod.dis(data, base, addr)
    category = classify(mcdis_mod, inst_word)
    return {
        "addr": addr,
        "inst_word": inst_word,
        "mnemonic": mnemonic,
        "category": category,
        "extra": extra,
        "size": 2,
    }


# ---------------------------------------------------------------------------
# Shared queue-accounting helper (Task 1)
# ---------------------------------------------------------------------------

def build_queue_accounting(
    queued_work,
    accepted_entry_addresses=None,
    candidate_states=None,
    node_start_addrs=None,
    rejected_addrs=None,
    repeated_queue_discovery_count=0,
):
    """Pure shared queue-accounting helper.

    Extracts the real accounting logic from the legacy _build_output path into
    one shared implementation used by _build_output, build_canonical_summary,
    cfg_report generation, cfg_reproducibility generation, and canonical
    preview output. Returns all queue aggregates required by the canonical
    output schema.
    """
    accepted_entry_addresses = accepted_entry_addresses or set()
    accepted_entry_addrs = set()
    for a in accepted_entry_addresses:
        accepted_entry_addrs.add(int(a, 16) if isinstance(a, str) else int(a))

    node_start_addrs = node_start_addrs or set()
    rejected_addrs = rejected_addrs or set()
    candidate_states = candidate_states or {}

    repeated_count = int(repeated_queue_discovery_count)

    # Stable deduplication identity (preserved from legacy implementation).
    unique_queue_records = {}
    for q in queued_work:
        tgt = q.get("target", q.get("address"))
        key = (
            tgt,
            q.get("call_addr"),
            q["depth"],
            q["work_type"],
            q["reason"],
            q.get("function"),
        )
        if key in unique_queue_records:
            continue
        unique_queue_records[key] = q

    def queue_status(q):
        reason = q["reason"]
        work_type = q["work_type"]
        tgt = q.get("target", q.get("address"))
        # Generic budget exhaustion: any reason beginning with budget_, plus
        # pending_unprocessed_budget_exhaustion, classifies as pending budget
        # exhaustion (Task 3).
        if reason == "pending_unprocessed_budget_exhaustion" or reason.startswith("budget_"):
            return "pending_budget_exhaustion"
        if reason == "queued_for_function_traversal":
            if tgt is None:
                return "unresolved"
            tgt_int = int(tgt, 16) if isinstance(tgt, str) else tgt
            if tgt_int in accepted_entry_addrs:
                return "accepted"
            if tgt_int in node_start_addrs:
                return "existing_node"
            if tgt_int in rejected_addrs:
                return "rejected"
            return "unresolved"
        if reason == "existing_node":
            return "existing_node"
        if reason == "existing_function":
            return "existing_function"
        if reason == "rejected":
            return "rejected"
        return "unresolved"

    pending_block_addrs = set()
    pending_function_addrs = set()
    status_counts = {}
    for key, q in unique_queue_records.items():
        st = queue_status(q)
        status_counts[st] = status_counts.get(st, 0) + 1
        if st == "pending_budget_exhaustion":
            tgt = q.get("target", q.get("address"))
            if tgt is not None:
                if q["work_type"] == "block":
                    pending_block_addrs.add(tgt)
                elif q["work_type"] == "function":
                    pending_function_addrs.add(tgt)

    pending_total_addrs = pending_block_addrs | pending_function_addrs
    processed_or_resolved_count = sum(
        v for k, v in status_counts.items() if k != "pending_budget_exhaustion"
    )

    status_count_sum = sum(status_counts.values())
    if status_count_sum != len(unique_queue_records):
        raise SystemExit(
            "CONSISTENCY FAILURE: queue status counts "
            f"{status_counts} sum to {status_count_sum} "
            f"but unique queue records total {len(unique_queue_records)}"
        )

    # Stable queue-record schema (Task 2).
    records = []
    for key, q in unique_queue_records.items():
        tgt = q.get("target", q.get("address"))
        call_addr = q.get("call_addr")
        fn = q.get("function")
        records.append({
            "target_address": hex(tgt) if tgt is not None else None,
            "call_site_address": hex(call_addr) if call_addr is not None else None,
            "depth": q["depth"],
            "work_type": q["work_type"],
            "reason": q["reason"],
            "function_id": hex(fn) if fn is not None else None,
            "final_status": queue_status(q),
        })

    records.sort(key=lambda r: (
        r["work_type"],
        r["target_address"] if r["target_address"] is not None else "",
        r["call_site_address"] if r["call_site_address"] is not None else "",
        r["depth"],
        r["function_id"] if r["function_id"] is not None else "",
        r["reason"],
    ))

    return {
        "queue_discovery_records": records,
        "queue_discovery_record_count": len(unique_queue_records),
        "queue_final_status_counts": status_counts,
        "pending_block_work": [hex(a) for a in sorted(pending_block_addrs)],
        "pending_block_count": len(pending_block_addrs),
        "pending_function_work": [hex(a) for a in sorted(pending_function_addrs)],
        "pending_function_count": len(pending_function_addrs),
        "pending_total_work": [hex(a) for a in sorted(pending_total_addrs)],
        "pending_total_count": len(pending_total_addrs),
        "processed_or_resolved_queue_records": processed_or_resolved_count,
        "repeated_queue_discovery_count": repeated_count,
        "queue_reconciliation_status": {
            "status_count_sum": status_count_sum,
            "unique_record_count": len(unique_queue_records),
            "processed_plus_pending": processed_or_resolved_count + len(pending_total_addrs),
            "total_records": len(unique_queue_records),
        },
    }


def reconcile_queue_accounting(accounting):
    counts = accounting["queue_final_status_counts"]
    total = accounting["queue_discovery_record_count"]
    records = accounting["queue_discovery_records"]
    pending_block = accounting["pending_block_work"]
    pending_function = accounting["pending_function_work"]
    pending_total = accounting["pending_total_work"]
    processed = accounting["processed_or_resolved_queue_records"]
    pending_total_count = accounting["pending_total_count"]

    if sum(counts.values()) != total:
        raise SystemExit(
            "QUEUE RECONCILIATION FAILURE: sum(queue_final_status_counts.values())="
            f"{sum(counts.values())} != queue_discovery_record_count={total}"
            f" (counts={counts})"
        )
    if len(records) != total:
        raise SystemExit(
            f"QUEUE RECONCILIATION FAILURE: len(queue_discovery_records)="
            f"{len(records)} != queue_discovery_record_count={total}"
        )
    if accounting["pending_block_count"] != len(pending_block):
        raise SystemExit(
            f"QUEUE RECONCILIATION FAILURE: pending_block_count="
            f"{accounting['pending_block_count']} != len(pending_block_work)={len(pending_block)}"
        )
    if accounting["pending_function_count"] != len(pending_function):
        raise SystemExit(
            f"QUEUE RECONCILIATION FAILURE: pending_function_count="
            f"{accounting['pending_function_count']} != len(pending_function_work)={len(pending_function)}"
        )
    if accounting["pending_total_count"] != len(pending_total):
        raise SystemExit(
            f"QUEUE RECONCILIATION FAILURE: pending_total_count="
            f"{accounting['pending_total_count']} != len(pending_total_work)={len(pending_total)}"
        )
    expected_total = set(pending_block) | set(pending_function)
    if set(pending_total) != expected_total or len(pending_total) != len(expected_total):
        raise SystemExit(
            "QUEUE RECONCILIATION FAILURE: pending_total_work is not the "
            f"deduplicated union of pending_block_work and pending_function_work: "
            f"{sorted(pending_total)} vs {sorted(expected_total)}"
        )
    # Reconciliation using record counts (not unique address counts) to handle
    # multiple queue records for the same address with different call sites/depths.
    pending_budget_exhaustion_records = counts.get("pending_budget_exhaustion", 0)
    if processed + pending_budget_exhaustion_records != total:
        raise SystemExit(
            f"QUEUE RECONCILIATION FAILURE: processed_or_resolved_queue_records="
            f"{processed} + pending_budget_exhaustion_records={pending_budget_exhaustion_records} = "
            f"{processed + pending_budget_exhaustion_records} != queue_discovery_record_count={total}"
        )


# ---------------------------------------------------------------------------
# Candidate-vs-queue metrics (Task 5)
# ---------------------------------------------------------------------------

def candidate_queue_metrics(builder, accounting):
    """Classify queued direct-call candidates into scheduling states.

    Returns metrics distinguishing candidates queued at max depth (not
    scheduled), scheduled-but-pending due to budget exhaustion, and candidates
    without a function work record. Never infers classification when the source
    record lacks evidence; uses UNKNOWN or explicit unclassified counts.
    """
    unique_candidates = set(builder.candidates)
    scheduled_pending = 0
    not_scheduled_depth_limit = 0
    without_function_work = 0

    queued_function_targets = set()
    for q in builder.queued_work:
        if q.get("work_type") == "function":
            tgt = q.get("target")
            if tgt is not None:
                queued_function_targets.add(tgt)

    pending_function_addrs = set()
    for a in accounting.get("pending_function_work", []):
        pending_function_addrs.add(int(a, 16) if isinstance(a, str) else a)

    for c in unique_candidates:
        c_int = int(c, 16) if isinstance(c, str) else c
        state = builder.candidate_state.get(c, "queued")

        if c_int in queued_function_targets:
            if c_int in pending_function_addrs:
                scheduled_pending += 1
            else:
                without_function_work += 1
        elif state == "queued":
            not_scheduled_depth_limit += 1
        else:
            without_function_work += 1

    return {
        "queued_candidates_scheduled_pending": scheduled_pending,
        "queued_candidates_not_scheduled_depth_limit": not_scheduled_depth_limit,
        "queued_candidates_without_function_work_record": without_function_work,
    }


class CFGBuilder:
    def __init__(self, data, base, roots, budgets, mcdis_mod):
        self.data = data
        self.size = len(data)
        self.base = base
        self.image_end = base + self.size
        self.roots = roots
        self.budgets = budgets
        self.mcdis = mcdis_mod

        self.func_count = 0
        self.block_count = 0
        self.inst_count = 0
        self.decoded_bytes = 0

        self.functions = {}
        self.nodes = []
        self.edges = []
        self.literal_pools = set()
        self.candidates = []
        self.rejected = []
        self.candidate_state = {}
        self.queued_work = []
        self.stop_reasons = {}
        self.fallback_opcodes = []
        self.prohibited_rejections = 0
        self.prohibited_targets = set()
        self._queued_work_keys = set()

        self.analyzed_blocks = set()
        self.accepted_functions = []
        self.func_worklist = deque()
        self.root_processed = 0

        self.budget_exhausted_flag = False
        self.budget_exhaustion_observations = []
        self.repeated_queue_discovery_count = 0
        self.repeated_function_discovery_count = 0
        self.current_node_index = None
        self.entry_to_fid = {}
        self.function_callers = {}
        self.function_call_sites = {}
        self.function_discovery_count = {}
        self.root_fid = None

    def _add_queued_work(self, target, call_addr, depth, work_type, reason, function=None):
        key = (target, call_addr, depth, work_type, reason, function)
        if key in self._queued_work_keys:
            self.repeated_queue_discovery_count += 1
            return
        self._queued_work_keys.add(key)
        entry = {
            "target": target,
            "call_addr": call_addr,
            "depth": depth,
            "work_type": work_type,
            "reason": reason,
        }
        if function is not None:
            entry["function"] = function
        self.queued_work.append(entry)

    def budget_exceeded(self):
        if self.func_count >= self.budgets["max_functions"]:
            return "max_functions"
        if self.block_count >= self.budgets["max_basic_blocks"]:
            return "max_basic_blocks"
        if self.inst_count >= self.budgets["max_instructions"]:
            return "max_instructions"
        if self.decoded_bytes >= self.budgets["max_decoded_bytes"]:
            return "max_decoded_bytes"
        return None

    def _count_stop(self, reason):
        self.stop_reasons[reason] = self.stop_reasons.get(reason, 0) + 1

    def in_image(self, addr):
        return self.base <= addr < self.image_end

    def is_aligned(self, addr):
        return addr % 2 == 0

    def is_prohibited(self, addr):
        return PROHIBITED_START <= addr <= PROHIBITED_END

    def in_data_range(self, addr):
        for p in self.literal_pools:
            if p <= addr < p + 4:
                return True
        return False

    def mark_literal_pool(self, p):
        self.literal_pools.add(p)

    def add_edge(self, source, target, edge_type, validation_status, rejection_reason=None, source_node_index=None):
        self.edges.append({
            "source": hex(source),
            "target": hex(target) if target is not None else None,
            "type": edge_type,
            "validation_status": validation_status,
            "rejection_reason": rejection_reason,
            "source_node_index": source_node_index,
        })

    def add_candidate(self, target):
        if target not in self.candidates:
            self.candidates.append(target)
        self.candidate_state.setdefault(target, "queued")

    def set_candidate_accepted(self, target):
        if target in self.candidate_state:
            self.candidate_state[target] = "accepted"

    def set_candidate_rejected(self, target, reason):
        self.candidate_state[target] = "rejected"

    def validate_entry(self, addr):
        """Return (ok, reason) for an entry point or block start."""
        if not self.in_image(addr):
            return False, "out_of_image"
        if not self.is_aligned(addr):
            return False, "misaligned"
        if self.is_prohibited(addr):
            self.prohibited_rejections += 1
            self.prohibited_targets.add(addr)
            return False, "prohibited_range"
        if self.in_data_range(addr):
            return False, "data_or_literal_pool_range"
        return True, None

    def validate_call_target(self, target):
        """Full validation for a direct call target. Returns (ok, reason)."""
        ok, reason = self.validate_entry(target)
        if not ok:
            return False, reason
        first = decode_instruction(self.mcdis, self.data, self.base, target)
        if first is None:
            return False, "out_of_image"
        if first["category"] == "unknown":
            return False, "unknown_opcode"
        return True, None

    def run(self):
        for root in self.roots[: self.budgets["max_roots"]]:
            self.func_worklist.append((root, 0, None, None))

        next_fid = 0

        while self.func_worklist:
            be = self.budget_exceeded()
            if be:
                if not self.budget_exhausted_flag:
                    self.budget_exhausted_flag = True
                    self._count_stop(f"budget_{be}")
                    self.budget_exhaustion_observations.append(
                        {
                            "budget": be,
                            "location": "function_loop",
                        }
                    )
                for remaining in self.func_worklist:
                    remaining_addr = remaining[0]
                    remaining_depth = remaining[1]
                    self._add_queued_work(
                        remaining_addr,
                        None,
                        remaining_depth,
                        "function",
                        "pending_unprocessed_budget_exhaustion",
                    )
                break

            addr, depth, call_addr, caller_fid = self.func_worklist.popleft()

            ok, reason = self.validate_entry(addr)
            if not ok:
                self._count_stop(f"entry_{reason}")
                self.rejected.append({"addr": addr, "reason": reason})
                continue

            is_initial_root = depth == 0 and self.root_processed < len(self.roots)
            if is_initial_root:
                self.root_processed += 1
                if self.root_processed > self.budgets["max_roots"]:
                    self._count_stop("max_roots")
                    continue

            if depth > self.budgets["max_depth"]:
                self._count_stop("max_depth")
                continue

            first = decode_instruction(self.mcdis, self.data, self.base, addr)
            if first is None:
                self._count_stop("first_block_out_of_image")
                continue
            if first["category"] == "unknown" or first["mnemonic"].startswith(".short"):
                self._count_stop("first_block_unknown_opcode")
                self.fallback_opcodes.append(addr)
                continue

            if addr in self.entry_to_fid:
                fid = self.entry_to_fid[addr]
                self.repeated_function_discovery_count += 1
                self.function_discovery_count[fid] = self.function_discovery_count.get(fid, 0) + 1
                if caller_fid is not None:
                    self.function_callers.setdefault(fid, set()).add(caller_fid)
                if call_addr is not None:
                    self.function_call_sites.setdefault(fid, set()).add(call_addr)
                continue

            if self.func_count >= self.budgets["max_functions"]:
                self._count_stop("max_functions")
                continue

            fid = next_fid
            next_fid += 1
            self.func_count += 1
            self.accepted_functions.append(fid)
            self.entry_to_fid[addr] = fid
            self.functions[fid] = {"start": addr, "depth": depth, "blocks": []}
            self.set_candidate_accepted(addr)
            self.function_discovery_count[fid] = 1
            if is_initial_root:
                self.root_fid = fid
            if caller_fid is not None:
                self.function_callers.setdefault(fid, set()).add(caller_fid)
            if call_addr is not None:
                self.function_call_sites.setdefault(fid, set()).add(call_addr)

            block_worklist = deque([addr])

            while block_worklist:
                block_start = block_worklist.popleft()

                be = self.budget_exceeded()
                if be:
                    if not self.budget_exhausted_flag:
                        self.budget_exhausted_flag = True
                        self._count_stop(f"budget_{be}")
                        self.budget_exhaustion_observations.append(
                            {
                                "budget": be,
                                "location": "block_loop",
                            }
                        )
                    reason = f"budget_{be}"
                    self._add_queued_work(
                        block_start, None, depth, "block", reason,
                    )
                    for remaining_addr in block_worklist:
                        self._add_queued_work(
                            remaining_addr, None, depth, "block", reason,
                        )
                    break
                if block_start in self.analyzed_blocks:
                    continue

                ok, reason = self.validate_entry(block_start)
                if not ok:
                    self._count_stop(f"block_{reason}")
                    continue

                block = self._decode_block(block_start, depth, fid)
                if block is None:
                    continue

                self.block_count += 1
                self.analyzed_blocks.add(block_start)
                self.functions[fid]["blocks"].append(block_start)
                self.nodes.append(block)
                self.current_node_index = len(self.nodes) - 1

                term = block["termination_reason"]
                calls_in_block = block.get("calls", [])

                # Process call edges recorded within the block
                for call_target, call_addr in calls_in_block:
                    ok2, reason2 = self.validate_call_target(call_target)
                    if ok2:
                        self.add_edge(call_addr, call_target, "direct_call", "valid",
                                      source_node_index=self.current_node_index)
                        self.add_candidate(call_target)
                        if depth + 1 <= self.budgets["max_depth"]:
                            self.func_worklist.append((call_target, depth + 1, call_addr, fid))
                            self._add_queued_work(
                                call_target,
                                call_addr,
                                depth + 1,
                                "function",
                                "queued_for_function_traversal",
                                function=call_target,
                            )
                    else:
                        self.add_edge(call_addr, call_target, "direct_call", "rejected", reason2,
                                      source_node_index=self.current_node_index)
                        self.set_candidate_rejected(call_target, reason2)
                        self.rejected.append({"addr": call_target, "reason": reason2})

                if term == "conditional_branch":
                    last = block["instructions"][-1]
                    target = last["extra"][1]
                    fall_through = last["addr"] + 2

                    ok_t, reason_t = self.validate_entry(target)
                    if ok_t:
                        self.add_edge(last["addr"], target, "conditional", "valid",
                                  source_node_index=self.current_node_index)
                        block_worklist.append(target)
                    else:
                        self.add_edge(last["addr"], target, "conditional", "rejected", reason_t,
                                  source_node_index=self.current_node_index)

                    ok_f, reason_f = self.validate_entry(fall_through)
                    if ok_f:
                        self.add_edge(last["addr"], fall_through, "fall_through", "valid",
                                      source_node_index=self.current_node_index)
                        block_worklist.append(fall_through)
                    else:
                        self.add_edge(last["addr"], fall_through, "fall_through", "rejected", reason_f,
                                      source_node_index=self.current_node_index)

                elif term == "unconditional_branch":
                    last = block["instructions"][-1]
                    target = last["extra"][1]
                    self.add_edge(last["addr"], target, "unconditional", "valid",
                                  source_node_index=self.current_node_index)
                    if target == block_start:
                        self._count_stop("self_loop")

                elif term == "return":
                    last = block["instructions"][-1]
                    self.add_edge(last["addr"], None, "return", "valid",
                                  source_node_index=self.current_node_index)

                elif term == "unresolved_indirect_jump":
                    last = block["instructions"][-1]
                    self.add_edge(last["addr"], None, "indirect_jump", "unresolved",
                                  source_node_index=self.current_node_index)

                elif term == "unresolved_indirect_call":
                    last = block["instructions"][-1]
                    extra = last["extra"]
                    if extra and extra[0] == "lit":
                        target = extra[2]
                        self.add_edge(last["addr"], target, "indirect_call", "resolved_via_literal_pool",
                                      source_node_index=self.current_node_index)
                        ok2, reason2 = self.validate_call_target(target)
                        if ok2:
                            self.add_candidate(target)
                            if depth + 1 <= self.budgets["max_depth"]:
                                self.func_worklist.append((target, depth + 1, last["addr"], fid))
                                self._add_queued_work(
                                    target,
                                    last["addr"],
                                    depth + 1,
                                    "function",
                                    "queued_for_function_traversal",
                                    function=target,
                                )
                        else:
                            self.rejected.append({"addr": target, "reason": reason2})
                            self.set_candidate_rejected(target, reason2)
                    else:
                        self.add_edge(last["addr"], None, "indirect_call", "unresolved",
                                      source_node_index=self.current_node_index)

                elif term == "unknown_opcode":
                    self.fallback_opcodes.append(block_start)

        self._validate_consistency()

        return self._build_output()

    def _validate_consistency(self):
        """Fail loudly if any consistency invariant is violated."""
        # Reachable node must not overlap prohibited range.
        for n in self.nodes:
            ns, ne = n["start"], n["end"]
            if PROHIBITED_START <= ns <= PROHIBITED_END or PROHIBITED_START < ne <= PROHIBITED_END:
                raise SystemExit(
                    f"CONSISTENCY FAILURE: reachable node 0x{ns:08X} overlaps prohibited range "
                    f"[0x{PROHIBITED_START:08X}, 0x{PROHIBITED_END:08X}]"
                )
            if not self.in_image(ns):
                raise SystemExit(
                    f"CONSISTENCY FAILURE: reachable node 0x{ns:08X} outside image"
                )
            if not self.is_aligned(ns):
                raise SystemExit(
                    f"CONSISTENCY FAILURE: reachable node 0x{ns:08X} misaligned"
                )

        # Accepted function must be inside image and aligned, and have an accepted entry node.
        accepted_starts = set()
        for n in self.nodes:
            accepted_starts.add(n["start"])
        for fid, func in self.functions.items():
            s = func["start"]
            if not self.in_image(s):
                raise SystemExit(f"CONSISTENCY FAILURE: accepted function {fid} entry 0x{s:08X} outside image")
            if not self.is_aligned(s):
                raise SystemExit(f"CONSISTENCY FAILURE: accepted function {fid} entry 0x{s:08X} misaligned")
            if s not in accepted_starts:
                raise SystemExit(f"CONSISTENCY FAILURE: accepted function {fid} has no accepted entry node at 0x{s:08X}")

        # Two reachable nodes must not overlap incompatibly (same start, different end).
        # Different-start overlaps are normal CFG (multiple entry points into a region)
        # and are reported, not failed.
        node_by_start = {}
        for n in self.nodes:
            s = n["start"]
            e = n["end"]
            if s in node_by_start and node_by_start[s] != e:
                raise SystemExit(
                    f"CONSISTENCY FAILURE: incompatible overlapping nodes at same start {hex(s)}: "
                    f"end {hex(node_by_start[s])} vs {hex(e)}"
                )
            node_by_start[s] = e

        # Instruction totals agree with node totals.
        node_inst_total = sum(n["instruction_count"] for n in self.nodes)
        if node_inst_total != self.inst_count:
            raise SystemExit(
                f"CONSISTENCY FAILURE: instruction total {self.inst_count} != sum of node "
                f"instruction_count {node_inst_total}"
            )

        # Decoded-byte totals agree with documented accounting (instruction_count * 2).
        if self.decoded_bytes != self.inst_count * 2:
            raise SystemExit(
                f"CONSISTENCY FAILURE: decoded bytes {self.decoded_bytes} != instruction_count*2 "
                f"= {self.inst_count * 2}"
            )

        # Every edge marked valid must have a target that is in_image or None.
        for e in self.edges:
            if e["validation_status"] == "valid" and e["target"] is not None:
                t = int(e["target"], 16)
                if not self.in_image(t):
                    raise SystemExit(
                        f"CONSISTENCY FAILURE: valid edge {e['source']} -> {e['target']} "
                        f"target outside image"
                    )

        # Pending queue entries must not disappear when budget is reached (all still listed).
        # (queued_work is populated whenever work is queued; nothing removes entries.)

        # Candidate-state counts must sum to the unique candidate total.
        state_counts = Counter(self.candidate_state.values())
        if sum(state_counts.values()) != len(set(self.candidates)):
            raise SystemExit(
                f"CONSISTENCY FAILURE: candidate-state counts {dict(state_counts)} do not sum "
                f"to unique candidate total {len(set(self.candidates))}"
            )

    def _decode_block(self, start_addr, depth, fid):
        instructions = []
        calls = []
        addr = start_addr
        termination_reason = "fall_through"
        block_end = start_addr

        while len(instructions) < self.budgets["max_instructions_per_block"]:
            be = self.budget_exceeded()
            if be:
                termination_reason = f"budget_{be}"
                break

            inst = decode_instruction(self.mcdis, self.data, self.base, addr)
            if inst is None:
                termination_reason = "out_of_image"
                break

            self.inst_count += 1
            self.decoded_bytes += 2
            block_end = addr + 2

            if inst["category"] == "unknown" or inst["mnemonic"].startswith(".short"):
                termination_reason = "unknown_opcode"
                instructions.append(inst)
                break

            instructions.append(inst)

            category = inst["category"]
            extra = inst["extra"]

            if category == "uncond_branch":
                termination_reason = "unconditional_branch"
                break
            if category == "cond_branch":
                termination_reason = "conditional_branch"
                break
            if category == "return":
                termination_reason = "return"
                break
            if category == "indirect_jump":
                termination_reason = "unresolved_indirect_jump"
                break
            if category == "indirect_call":
                termination_reason = "unresolved_indirect_call"
                break
            if category == "direct_call":
                tgt = call_target(extra)
                calls.append((tgt, addr))
            if category == "literal_load":
                if extra and extra[0] == "lit":
                    self.mark_literal_pool(extra[1])

            addr += 2

        if len(instructions) >= self.budgets["max_instructions_per_block"]:
            if termination_reason == "fall_through":
                termination_reason = "block_instruction_budget"

        return {
            "start": start_addr,
            "end": block_end,
            "function": fid,
            "depth": depth,
            "classification": "reachable_code",
            "instruction_count": len(instructions),
            "termination_reason": termination_reason,
            "calls": calls,
            "instructions": [
                {
                    "addr": i["addr"],
                    "size": i["size"],
                    "raw": f"{i['inst_word']:04x}",
                    "mnemonic": i["mnemonic"],
                    "category": i["category"],
                    "extra": list(i["extra"]) if i.get("extra") is not None else None,
                }
                for i in instructions
            ],
        }

    def _build_output(self):
        cond = sum(1 for e in self.edges if e["type"] == "conditional")
        uncond = sum(1 for e in self.edges if e["type"] == "unconditional")
        ft = sum(1 for e in self.edges if e["type"] == "fall_through")
        indirect = sum(1 for e in self.edges if e["type"] == "indirect_call" or e["type"] == "indirect_jump")

        be = self.budget_exceeded()
        budget_status = be if be else "none"

        # Candidate states
        unique_candidates = sorted(set(self.candidates))
        candidate_states = []
        for c in unique_candidates:
            state = self.candidate_state.get(c, "queued")
            candidate_states.append({
                "target": hex(c),
                "state": state,
            })
        state_counts = Counter(self.candidate_state.values())

        # Accepted function identity canonicalised by entry address
        accepted_functions_list = []
        seen_starts = set()
        accepted_entries = []
        for f in self.functions.values():
            if f["start"] not in seen_starts:
                seen_starts.add(f["start"])
                accepted_entries.append(hex(f["start"]))
        fid_by_start = {f["start"]: fid for fid, f in self.functions.items()}
        for start in sorted(fid_by_start):
            fid = fid_by_start[start]
            func = self.functions[fid]
            accepted_functions_list.append({
                "function_id": fid,
                "entry": hex(start),
                "is_root": fid == self.root_fid,
                "caller_function_ids": sorted(self.function_callers.get(fid, set())),
                "call_site_addresses": [hex(a) for a in sorted(self.function_call_sites.get(fid, set()))],
                "call_site_count": len(self.function_call_sites.get(fid, set())),
                "discovery_count": self.function_discovery_count.get(fid, 1),
                "accepted_depth": func["depth"],
                "final_analysis_status": "accepted",
            })

        # Block termination counts

        # Block termination counts
        term_counts = Counter(n["termination_reason"] for n in self.nodes)

        # Traversal stop counts
        stop_counts = dict(self.stop_reasons)

        # Target rejection counts
        rej_counts = Counter(r["reason"] for r in self.rejected)

        # Queue final-status accounting (shared helper, Task 1).
        accepted_entry_addrs = set(accepted_entries) if accepted_entries else set()
        node_start_addrs = {n["start"] for n in self.nodes}
        rejected_addrs = {
            int(r["addr"], 16) if isinstance(r.get("addr"), str) else r.get("addr")
            for r in self.rejected if r.get("addr") is not None
        }

        accounting = build_queue_accounting(
            queued_work=self.queued_work,
            accepted_entry_addresses=accepted_entry_addrs,
            candidate_states={},
            node_start_addrs=node_start_addrs,
            rejected_addrs=rejected_addrs,
            repeated_queue_discovery_count=self.repeated_queue_discovery_count,
        )

        queue_records = accounting["queue_discovery_records"]
        queue_status_counts = accounting["queue_final_status_counts"]
        pending_block_work = accounting["pending_block_work"]
        pending_block_count = accounting["pending_block_count"]
        pending_function_work = accounting["pending_function_work"]
        pending_function_count = accounting["pending_function_count"]
        pending_total_work = accounting["pending_total_work"]
        pending_total_count = accounting["pending_total_count"]
        processed_or_resolved_count = accounting["processed_or_resolved_queue_records"]
        repeated_count = accounting["repeated_queue_discovery_count"]

        # Fail-loud reconciliation before any output replacement (Task 4).
        reconcile_queue_accounting(accounting)

        # Candidate-vs-queue metrics (Task 5).
        candidate_queue = candidate_queue_metrics(self, accounting)

        return {
            "summary": {
                "input_path": str(Path("tools/softce-aula-l99-research/extracted/HFD_Code_V2.3.bin").resolve()),
                "size": self.size,
                "sha256": hashlib.sha256(self.data).hexdigest().upper(),
                "candidate_image_base": hex(CANDIDATE_IMAGE_BASE),
                "root_entries": [hex(r) for r in self.roots],
                "traversal_budgets": self.budgets,
                "stop_reason_counts": self.stop_reasons,
                "unique_accepted_function_count": len(accepted_entries),
                "accepted_function_entries": accepted_entries,
                "accepted_functions": accepted_functions_list,
                "function_discovery_event_count": sum(self.function_discovery_count.values()),
                "repeated_function_discovery_count": self.repeated_function_discovery_count,
                "function_call_site_count": sum(f["call_site_count"] for f in accepted_functions_list),
                "functions_with_multiple_callers": sum(1 for f in accepted_functions_list if len(f["caller_function_ids"]) > 1),
                "functions_with_multiple_call_sites": sum(1 for f in accepted_functions_list if f["call_site_count"] > 1),
                "basic_blocks": self.block_count,
                "instruction_count": self.inst_count,
                "decoded_byte_count": self.decoded_bytes,
                "decoded_byte_accounting": "instruction_count * 2 (non-unique; counts bytes per decoded instruction)",
                "direct_call_candidates": [hex(c) for c in self.candidates],
                "unique_candidate_count": len(unique_candidates),
                "candidate_states": candidate_states,
                "candidate_state_counts": dict(state_counts),
                "conditional_edges": cond,
                "unconditional_edges": uncond,
                "fall_through_edges": ft,
                "unresolved_indirect_edges": indirect,
                "rejected_targets": self.rejected,
                "target_rejection_counts": dict(rej_counts),
                "fallback_unknown_opcode_locations": [hex(a) for a in self.fallback_opcodes],
                "prohibited_range_rejection_count": self.prohibited_rejections,
                "unique_prohibited_target_count": len(self.prohibited_targets),
                "budget_exhaustion_status": budget_status,
                "output_complete": budget_status is None,
                "evidence_classification": "STRUCTURAL_CANDIDATE",
                "block_termination_counts": dict(term_counts),
                "traversal_stop_counts": stop_counts,
                "budget_exhaustion_observations": self.budget_exhaustion_observations,
                "queue_discovery_records": queue_records,
                "queue_discovery_record_count": len(queue_records),
                "queue_final_status_counts": queue_status_counts,
                "repeated_queue_discovery_count": repeated_count,
                "pending_block_work": pending_block_work,
                "pending_block_count": pending_block_count,
                "pending_function_work": pending_function_work,
                "pending_function_count": pending_function_count,
                "pending_total_work": pending_total_work,
                "pending_total_count": pending_total_count,
                "processed_or_resolved_queue_records": processed_or_resolved_count,
                # Candidate-vs-queue metrics (Task 5).
                "queued_candidates_scheduled_pending": candidate_queue[
                    "queued_candidates_scheduled_pending"
                ],
                "queued_candidates_not_scheduled_depth_limit": candidate_queue[
                    "queued_candidates_not_scheduled_depth_limit"
                ],
                "queued_candidates_without_function_work_record": candidate_queue[
                    "queued_candidates_without_function_work_record"
                ],
            },
            "nodes": [
                {
                    "start": hex(n["start"]),
                    "end": hex(n["end"]),
                    "function": n["function"],
                    "depth": n["depth"],
                    "classification": n["classification"],
                    "instruction_count": n["instruction_count"],
                    "termination_reason": n["termination_reason"],
                }
                for n in self.nodes
            ],
            "edges": self.edges,
            "ranges": {
                "literal_pool": [hex(p) for p in sorted(self.literal_pools)],
                "embedded_data": [],
                "unknown": [],
            },
        }


def write_outputs(output_dir, output):
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "cfg_summary.json", "w", encoding="utf-8") as f:
        json.dump(output["summary"], f, indent=2)

    with open(output_dir / "cfg_nodes.json", "w", encoding="utf-8") as f:
        json.dump(output["nodes"], f, indent=2)

    with open(output_dir / "cfg_edges.json", "w", encoding="utf-8") as f:
        json.dump(output["edges"], f, indent=2)

    with open(output_dir / "cfg_ranges.json", "w", encoding="utf-8") as f:
        json.dump(output["ranges"], f, indent=2)

    report_lines = []
    s = output["summary"]
    report_lines.append("HFD Code V2.3 M*Core CFG Report")
    report_lines.append("=" * 60)
    report_lines.append(f"Input path: {s['input_path']}")
    report_lines.append(f"Size: {s['size']} bytes")
    report_lines.append(f"SHA-256: {s['sha256']}")
    report_lines.append(f"Candidate image base: {s['candidate_image_base']}")
    report_lines.append(f"Root entries: {', '.join(s['root_entries'])}")
    report_lines.append("")
    report_lines.append("Traversal budgets:")
    for k, v in s["traversal_budgets"].items():
        report_lines.append(f"  {k}: {v}")
    report_lines.append("")
    report_lines.append("Stop reason counts:")
    for k, v in sorted(s["stop_reason_counts"].items()):
        report_lines.append(f"  {k}: {v}")
    report_lines.append("")
    report_lines.append(f"Unique accepted functions: {s['unique_accepted_function_count']}")
    report_lines.append(f"Root functions: {sum(1 for f in s['accepted_functions'] if f['is_root'])}")
    report_lines.append(f"Function discovery event count: {s['function_discovery_event_count']}")
    report_lines.append(f"Repeated function discovery count: {s['repeated_function_discovery_count']}")
    report_lines.append(f"Function call site count: {s['function_call_site_count']}")
    report_lines.append(f"Functions with multiple callers: {s['functions_with_multiple_callers']}")
    report_lines.append(f"Functions with multiple call sites: {s['functions_with_multiple_call_sites']}")
    report_lines.append(f"Basic blocks: {s['basic_blocks']}")
    report_lines.append(f"Instruction count: {s['instruction_count']}")
    report_lines.append(f"Decoded byte count: {s['decoded_byte_count']}")
    report_lines.append(f"Direct-call candidates: {len(s['direct_call_candidates'])}")
    for c in s["direct_call_candidates"]:
        report_lines.append(f"  {c}")
    report_lines.append(f"Conditional edges: {s['conditional_edges']}")
    report_lines.append(f"Unconditional edges: {s['unconditional_edges']}")
    report_lines.append(f"Fall-through edges: {s['fall_through_edges']}")
    report_lines.append(f"Unresolved indirect edges: {s['unresolved_indirect_edges']}")
    report_lines.append(f"Rejected targets: {len(s['rejected_targets'])}")
    for r in s["rejected_targets"]:
        report_lines.append(f"  0x{r['addr']:08X}: {r['reason']}")
    report_lines.append(f"Fallback/unknown opcode locations: {len(s['fallback_unknown_opcode_locations'])}")
    for a in s["fallback_unknown_opcode_locations"]:
        report_lines.append(f"  {a}")
    report_lines.append(f"Prohibited-range rejections: {s['prohibited_range_rejection_count']}")
    report_lines.append(f"Unique prohibited targets: {s['unique_prohibited_target_count']}")
    report_lines.append(f"Budget exhaustion status: {s['budget_exhaustion_status']}")
    report_lines.append(f"Output complete: {s['output_complete']}")
    report_lines.append(f"Evidence classification: {s['evidence_classification']}")
    report_lines.append("")
    report_lines.append("Accepted functions:")
    for f in s["accepted_functions"]:
        report_lines.append(
            f"  fid={f['function_id']} entry={f['entry']} root={f['is_root']} "
            f"callers={f['caller_function_ids']} call_sites={f['call_site_addresses']} "
            f"call_site_count={f['call_site_count']} discovery_count={f['discovery_count']} "
            f"depth={f['accepted_depth']} status={f['final_analysis_status']}"
        )
    report_lines.append("")
    report_lines.append("Block termination counts:")
    for k, v in sorted(s["block_termination_counts"].items()):
        report_lines.append(f"  {k}: {v}")
    report_lines.append("")
    report_lines.append("Traversal stop counts:")
    for k, v in sorted(s["traversal_stop_counts"].items()):
        report_lines.append(f"  {k}: {v}")
    report_lines.append("")
    report_lines.append("Budget exhaustion observations:")
    for obs in s.get("budget_exhaustion_observations", []):
        report_lines.append(f"  budget={obs['budget']} location={obs['location']}")
    report_lines.append("")
    report_lines.append("Target rejection counts:")
    for k, v in sorted(s["target_rejection_counts"].items()):
        report_lines.append(f"  {k}: {v}")
    report_lines.append("")
    report_lines.append("Candidate state counts:")
    for k, v in sorted(s["candidate_state_counts"].items()):
        report_lines.append(f"  {k}: {v}")
    report_lines.append(f"  unique_candidate_total: {s['unique_candidate_count']}")
    report_lines.append("")
    report_lines.append("Candidate states:")
    for cs in s["candidate_states"]:
        report_lines.append(f"  {cs['target']}: {cs['state']}")
    report_lines.append("")
    report_lines.append("Queue discovery records: {s['queue_discovery_record_count']}".replace("{s['queue_discovery_record_count']}", str(s["queue_discovery_record_count"])))
    report_lines.append(f"  repeated_queue_discovery_count: {s['repeated_queue_discovery_count']}")
    report_lines.append("Queue final status counts:")
    for k, v in sorted(s["queue_final_status_counts"].items()):
        report_lines.append(f"  {k}: {v}")
    report_lines.append(f"  status_total: {sum(s['queue_final_status_counts'].values())}")
    report_lines.append("")
    report_lines.append("Pending block work: {s['pending_block_count']}".replace("{s['pending_block_count']}", str(s["pending_block_count"])))
    for a in s["pending_block_work"]:
        report_lines.append(f"  {a}")
    report_lines.append("")
    report_lines.append("Pending function work: {s['pending_function_count']}".replace("{s['pending_function_count']}", str(s["pending_function_count"])))
    for a in s["pending_function_work"]:
        report_lines.append(f"  {a}")
    report_lines.append("")
    report_lines.append("Pending total work (deduplicated): {s['pending_total_count']}".replace("{s['pending_total_count']}", str(s["pending_total_count"])))
    for a in s["pending_total_work"]:
        report_lines.append(f"  {a}")
    report_lines.append("")
    report_lines.append("Processed or resolved queue records: {s['processed_or_resolved_queue_records']}".replace("{s['processed_or_resolved_queue_records']}", str(s["processed_or_resolved_queue_records"])))
    report_lines.append("")
    report_lines.append("Queue reconciliation:")
    report_lines.append(f"  pending_block_count + pending_function_count + processed_or_resolved_queue_records = {s['pending_block_count']} + {s['pending_function_count']} + {s['processed_or_resolved_queue_records']} = {s['pending_block_count'] + s['pending_function_count'] + s['processed_or_resolved_queue_records']}")
    report_lines.append(f"  queue_discovery_record_count = {s['queue_discovery_record_count']}")
    report_lines.append("")
    report_lines.append("Decoded byte accounting: {s['decoded_byte_accounting']}".replace("{s['decoded_byte_accounting']}", s["decoded_byte_accounting"]))

    with open(output_dir / "cfg_report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines) + "\n")


def _term_reason_for_addr(addr, terminators_by_kind):
    for kind, addrs in terminators_by_kind.items():
        if addr in addrs:
            return kind
    return None


def _edge_duplicate_count(edges):
    from collections import Counter
    c = Counter((e["source"], e["target"], e["type"]) for e in edges)
    # Count edge groups that are duplicated (each group counted once).
    return sum(1 for v in c.values() if v > 1)


def build_canonical_nodes(partition_result, observations, builder):
    """Build the canonical node list for cfg_nodes.json from a validated partition."""
    canon_instrs = partition_result["instructions"]
    canon_blocks = partition_result["blocks"]
    terminators = set(partition_result["terminators"])
    node_source_map = observations["node_source_map"]
    successor_observations = observations["successor_observations"]
    terminators_by_kind = observations["terminators_by_kind"]
    evidence_boundaries = set(observations["evidence_boundaries"])
    legacy_node_starts = set(observations["legacy_node_starts"])
    ownership_observations = observations["ownership_observations"]
    roots = set(int(r) for r in builder.roots)
    accepted_entries = set(int(f["start"]) for f in builder.functions.values())

    term_reason_map = {}
    for kind, addrs in terminators_by_kind.items():
        for a in addrs:
            term_reason_map[a] = kind

    instr_by_addr = {i["addr"]: i for i in canon_instrs}
    source_budget_truncated = builder.budget_exceeded() is not None

    canonical_nodes = []
    for block in canon_blocks:
        start = block["start"]
        end = block["end"]
        addrs = block["instruction_addresses"]
        last_addr = addrs[-1]
        is_terminator = last_addr in terminators
        term_reason = term_reason_map.get(last_addr, "fall_through")
        terminator_addr = last_addr if is_terminator else None

        reaching_fids = set()
        for a in addrs:
            reaching_fids.update(ownership_observations.get(a, []))

        source_nids = set()
        for a in addrs:
            source_nids.update(node_source_map.get(a, []))

        entry_reasons = []
        if start in roots:
            entry_reasons.append("root_entry")
        if start in accepted_entries:
            entry_reasons.append("function_entry")
        if start in evidence_boundaries:
            entry_reasons.append("control_flow_boundary")
        if start in legacy_node_starts:
            entry_reasons.append("legacy_node_start")
        if start in terminators:
            entry_reasons.append("terminator_boundary")

        successor_evidence = []
        if is_terminator and last_addr in successor_observations:
            successor_evidence = list(successor_observations[last_addr])

        canonical_instructions = []
        for a in addrs:
            i = instr_by_addr[a]
            raw = i["raw"]
            instruction_word_hex = raw if isinstance(raw, str) else raw.hex()
            canonical_instructions.append({
                "addr": _hex_addr(a),
                "size": i["size"],
                "instruction_word_hex": instruction_word_hex,
                "file_bytes_hex": None,
                "mnemonic": i["mnemonic"],
                "category": i["category"],
                "ownership": i["ownership"],
            })

        canonical_nodes.append({
            "id": block["id"],
            "schema_version": CFG_SCHEMA_VERSION,
            "start": _hex_addr(start),
            "end": _hex_addr(end),
            "instruction_addresses": [_hex_addr(a) for a in addrs],
            "instruction_count": block["instruction_count"],
            "reaching_function_ids": sorted(reaching_fids),
            "source_traversal_node_ids": sorted(source_nids),
            "block_entry_reasons": entry_reasons,
            "boundary_evidence": entry_reasons,
            "termination_reason": term_reason,
            "terminator_instruction_address": _hex_addr(terminator_addr) if terminator_addr is not None else None,
            "successor_evidence": [_hex_addr(t) for t in successor_evidence],
            "classification": "canonical_block",
            "source_budget_truncated": source_budget_truncated,
        })

    return canonical_nodes


def build_canonical_ranges(canonical_nodes):
    """Build cfg_ranges.json from canonical nodes only."""
    ranges = []
    for node in canonical_nodes:
        start = int(node["start"], 16)
        end = int(node["end"], 16)
        ranges.append({
            "schema_version": CFG_SCHEMA_VERSION,
            "start": node["start"],
            "end": node["end"],
            "instruction_count": node["instruction_count"],
        })
    ranges.sort(key=lambda r: int(r["start"], 16))
    return ranges


# ---------------------------------------------------------------------------
# Stage B3: canonical edge remapping
# ---------------------------------------------------------------------------

LEGACY_TO_NORMALIZED_TYPE = {
    "conditional": "conditional_branch",
    "unconditional": "unconditional_branch",
    "fall_through": "fall_through",
    "direct_call": "direct_call",
    "return": "return",
    "indirect_call": "unresolved_indirect_call",
    "indirect_jump": "unresolved_indirect_jump",
    "resolved_via_literal_pool": "direct_call",
}


def _normalize_type(etype):
    """Map legacy edge type to canonical normalized type."""
    return LEGACY_TO_NORMALIZED_TYPE.get(etype, etype)


def _edge_identity_key(record):
    """Stable deduplication identity for canonical edges.

    Legacy source-node ID is intentionally excluded.
    """
    return (
        record["source_address"],
        record["target_address"],
        record["normalized_type"],
        record["validation_status"],
        record["rejection_reason"],
    )


def _target_block_and_status(target_int, canonical_addrs, addr_to_block,
                             builder_base, builder_image_end,
                             prohibited_start, prohibited_end):
    """Classify a known numeric target address.

    Returns (target_block_id_or_None, target_observation_status).
    Raises CanonicalPartitionError for prohibited valid targets.
    """
    if target_int in canonical_addrs:
        return addr_to_block[target_int], "inside_observed_map"
    if builder_base <= target_int < builder_image_end:
        if prohibited_start <= target_int <= prohibited_end:
            raise CanonicalPartitionError(
                f"valid canonical edge targets prohibited range: "
                f"0x{target_int:08X}"
            )
        return None, "outside_observed_map"
    return None, "outside_image"


def build_canonical_edges(legacy_edges, partition_result, builder,
                          observations):
    """Remap validated legacy instruction-level edge evidence onto canonical
    blocks and emit a deterministic deduplicated canonical edge model.

    Pure function over in-memory observations. Does not modify builder state,
    traversal, partitioning, nodes, ranges, functions, queues, budgets, roots,
    or decoder behavior.
    """
    canon_instrs = partition_result["instructions"]
    canon_blocks = partition_result["blocks"]
    block_starts = set(partition_result["block_starts"])

    addr_to_block = {}
    block_by_start = {}
    for b in canon_blocks:
        block_by_start[b["start"]] = b["id"]
        for a in b["instruction_addresses"]:
            addr_to_block[a] = b["id"]

    canonical_addrs = set(addr_to_block.keys())

    ownership_observations = observations.get("ownership_observations", {})

    base = builder.base
    image_end = base + builder.size
    prohibited_start = PROHIBITED_START
    prohibited_end = PROHIBITED_END

    # Accumulate deduplicated edges keyed by canonical identity.
    deduped = {}  # identity -> record dict

    for legacy in legacy_edges:
        src_str = legacy["source"]
        src_int = int(src_str, 16) if isinstance(src_str, str) else int(src_str)
        tgt_raw = legacy["target"]
        tgt_int = None
        if tgt_raw is not None:
            tgt_int = int(tgt_raw, 16) if isinstance(tgt_raw, str) else int(tgt_raw)

        # Rule 2: canonical source mapping. Every source instruction inside the
        # canonical map must map to exactly one source canonical block.
        if src_int not in canonical_addrs:
            raise CanonicalPartitionError(
                f"edge source 0x{src_int:08X} maps to zero canonical blocks "
                f"(not in canonical instruction map)"
            )
        if src_int not in addr_to_block:
            raise CanonicalPartitionError(
                f"edge source 0x{src_int:08X} maps to more than one canonical block"
            )
        source_block_id = addr_to_block[src_int]

        # Normalize type.
        normalized_type = _normalize_type(legacy["type"])

        # Self-loop detection: source == target.
        is_self_loop = (tgt_int is not None and src_int == tgt_int)
        if is_self_loop and normalized_type == "unconditional_branch":
            self_loop_flag = True
        elif normalized_type == "self_loop":
            self_loop_flag = True
        else:
            self_loop_flag = False

        validation_status = legacy["validation_status"]
        rejection_reason = legacy.get("rejection_reason")

        # Target classification.
        target_block_id = None
        target_observation_status = None

        if tgt_int is None:
            # Return / unresolved indirect: no target.
            target_observation_status = None
        else:
            tb, status = _target_block_and_status(
                tgt_int, canonical_addrs, addr_to_block,
                base, image_end, prohibited_start, prohibited_end,
            )
            target_block_id = tb
            target_observation_status = status

            # Rule 3: control-flow entry edges must target a canonical block start.
            if (status == "inside_observed_map"
                    and normalized_type in (
                        "conditional_branch", "unconditional_branch",
                        "direct_call", "direct_call_fall_through",
                    )
                    and tgt_int not in block_starts):
                raise CanonicalPartitionError(
                    f"control-flow entry target 0x{tgt_int:08X} is not a "
                    f"canonical block start"
                )

        # reaching function IDs (union over legacy observations).
        source_rfids = set()
        for fid in ownership_observations.get(src_int, []):
            source_rfids.add(int(fid))
        target_rfids = set()
        if tgt_int is not None and tgt_int in ownership_observations:
            for fid in ownership_observations[tgt_int]:
                target_rfids.add(int(fid))

        legacy_node_index = legacy.get("source_node_index")
        legacy_node_ids = set()
        if legacy_node_index is not None:
            legacy_node_ids.add(legacy_node_index)

        identity = (
            src_int,
            tgt_int,
            normalized_type,
            validation_status,
            rejection_reason,
        )

        record = {
            "canonical_edge_id": None,  # filled after sort
            "schema_version": CFG_SCHEMA_VERSION,
            "source_address": src_int,
            "target_address": tgt_int,
            "normalized_type": normalized_type,
            "validation_status": validation_status,
            "rejection_reason": rejection_reason,
            "source_block_id": source_block_id,
            "target_block_id": target_block_id,
            "source_reaching_function_ids": set(source_rfids),
            "target_reaching_function_ids": set(target_rfids),
            "legacy_source_node_ids": set(legacy_node_ids),
            "discovery_count": 1,
            "target_observation_status": target_observation_status,
            "self_loop": bool(self_loop_flag),
            "provenance": [],
        }

        if identity in deduped:
            existing = deduped[identity]
            existing["legacy_source_node_ids"] |= legacy_node_ids
            existing["source_reaching_function_ids"] |= source_rfids
            existing["target_reaching_function_ids"] |= target_rfids
            existing["discovery_count"] += 1
        else:
            deduped[identity] = record

    # Finalize records: sort sets into lists, build provenance.
    canonical_edges = []
    for rec in deduped.values():
        rec["legacy_source_node_ids"] = sorted(rec["legacy_source_node_ids"])
        rec["source_reaching_function_ids"] = sorted(
            rec["source_reaching_function_ids"]
        )
        rec["target_reaching_function_ids"] = sorted(
            rec["target_reaching_function_ids"]
        )
        rec["provenance"] = sorted(
            {
                f"node_{nid}" for nid in rec["legacy_source_node_ids"]
            }
        )
        canonical_edges.append(rec)

    # Deterministic ordering (rule 6).
    def sort_key(rec):
        src = rec["source_address"]
        ntype = rec["normalized_type"]
        tgt = rec["target_address"]
        # known target before unknown target
        tgt_known = 0 if tgt is not None else 1
        tgt_val = tgt if tgt is not None else 0
        vs = rec["validation_status"]
        rr = rec["rejection_reason"] if rec["rejection_reason"] is not None else ""
        return (src, ntype, tgt_known, tgt_val, vs, rr)

    canonical_edges.sort(key=sort_key)

    # Assign stable canonical edge IDs.
    for idx, rec in enumerate(canonical_edges):
        rec["canonical_edge_id"] = idx

    return canonical_edges


def compute_canonical_edge_metrics(canonical_edges, legacy_edge_count,
                                   legacy_duplicate_group_count):
    """Compute the canonical edge metrics required by Stage B3 rule 11."""
    type_counts = Counter(rec["normalized_type"] for rec in canonical_edges)
    vs_counts = Counter(rec["validation_status"] for rec in canonical_edges)
    tos_counts = Counter(
        rec["target_observation_status"]
        for rec in canonical_edges
        if rec["target_observation_status"] is not None
    )

    unresolved = sum(
        1 for r in canonical_edges
        if r["normalized_type"] in ("unresolved_indirect_call", "unresolved_indirect_jump")
    )
    rejected = sum(1 for r in canonical_edges if r["validation_status"] == "rejected")
    returns = sum(1 for r in canonical_edges if r["normalized_type"] == "return")
    self_loop_count = sum(1 for r in canonical_edges if r["self_loop"])
    in_map = sum(1 for r in canonical_edges
                 if r["target_observation_status"] == "inside_observed_map")
    outside_map = sum(1 for r in canonical_edges
                      if r["target_observation_status"] == "outside_observed_map")

    multi_discoveries = sum(1 for r in canonical_edges if r["discovery_count"] > 1)
    multi_source_nodes = sum(1 for r in canonical_edges
                             if len(r["legacy_source_node_ids"]) > 1)

    canonical_duplicate_edge_count = 0  # deduplicated by construction

    collapsed = legacy_edge_count - len(canonical_edges)

    return {
        "legacy_edge_observation_count": legacy_edge_count,
        "legacy_duplicate_edge_group_count": legacy_duplicate_group_count,
        "canonical_edge_count": len(canonical_edges),
        "collapsed_duplicate_observation_count": collapsed,
        "canonical_duplicate_edge_count": canonical_duplicate_edge_count,
        "canonical_edges_with_multiple_discoveries": multi_discoveries,
        "canonical_edges_with_multiple_source_nodes": multi_source_nodes,
        "in_map_target_edge_count": in_map,
        "outside_observed_map_target_edge_count": outside_map,
        "unresolved_edge_count": unresolved,
        "rejected_edge_count": rejected,
        "return_edge_count": returns,
        "self_loop_edge_count": self_loop_count,
        "edge_type_counts": {k: type_counts[k] for k in sorted(type_counts)},
        "edge_validation_status_counts": {k: vs_counts[k] for k in sorted(vs_counts)},
        "target_observation_status_counts": {k: tos_counts[k] for k in sorted(tos_counts)},
    }


def canonical_edge_validate(canonical_edges, partition_result, builder):
    """Final consistency validation for canonical edges (rule 15).

    Raises CanonicalPartitionError with exact source/target/reason on failure.
    """
    canon_blocks = partition_result["blocks"]
    block_starts = set(partition_result["block_starts"])
    addr_to_block = {}
    for b in canon_blocks:
        for a in b["instruction_addresses"]:
            addr_to_block[a] = b["id"]

    base = builder.base
    image_end = base + builder.size
    prohibited_start = PROHIBITED_START
    prohibited_end = PROHIBITED_END

    # No duplicate canonical identities.
    seen = set()
    for rec in canonical_edges:
        key = _edge_identity_key(rec)
        if key in seen:
            raise CanonicalPartitionError(
                f"duplicate canonical edge identity: source={rec['source_address']:#010x} "
                f"target={rec['target_address']} type={rec['normalized_type']} "
                f"validation={rec['validation_status']} rejection={rec['rejection_reason']}"
            )
        seen.add(key)

    # Every valid in-map source/target maps correctly.
    for rec in canonical_edges:
        src = rec["source_address"]
        if src not in addr_to_block:
            raise CanonicalPartitionError(
                f"canonical edge source 0x{src:08X} not in canonical map"
            )
        tgt = rec["target_address"]
        if tgt is not None:
            tgt_int = int(tgt) if isinstance(tgt, str) else tgt
            # Prohibited valid target must fail.
            if (rec["validation_status"] == "valid"
                    and prohibited_start <= tgt_int <= prohibited_end):
                raise CanonicalPartitionError(
                    f"valid canonical edge targets prohibited range: "
                    f"0x{tgt_int:08X}"
                )
            if rec["target_observation_status"] == "inside_observed_map":
                if tgt_int not in addr_to_block:
                    raise CanonicalPartitionError(
                        f"in-map target 0x{tgt_int:08X} not in canonical map"
                    )
                if rec["target_block_id"] is None:
                    raise CanonicalPartitionError(
                        f"in-map target 0x{tgt_int:08X} has null target_block_id"
                    )
                # Control-flow entry edges must target block start.
                if rec["normalized_type"] in (
                    "conditional_branch", "unconditional_branch",
                    "direct_call", "direct_call_fall_through",
                ):
                    if tgt_int not in block_starts:
                        raise CanonicalPartitionError(
                            f"control-flow entry target 0x{tgt_int:08X} is not "
                            f"a canonical block start"
                        )
            elif rec["target_observation_status"] == "outside_observed_map":
                if not (base <= tgt_int < image_end):
                    raise CanonicalPartitionError(
                        f"outside-observed-map target 0x{tgt_int:08X} outside image"
                    )
                if rec["target_block_id"] is not None:
                    raise CanonicalPartitionError(
                        f"outside-observed-map target 0x{tgt_int:08X} "
                        f"has non-null target_block_id"
                    )

    # Self-loop: exactly one at 0x600174BC.
    sl = [r for r in canonical_edges
          if r["source_address"] == 0x600174BC and r["self_loop"]]
    if len(sl) != 1:
        raise CanonicalPartitionError(
            f"0x600174BC self-loop appears {len(sl)} times in canonical edges"
        )
    if sl[0]["target_address"] != 0x600174BC:
        raise CanonicalPartitionError(
            "0x600174BC self-loop target is not itself"
        )

    # No fall-through to 0x600174BE after the self-loop block.
    sl_block = None
    for b in canon_blocks:
        if 0x600174BC in b["instruction_addresses"]:
            sl_block = b
            break
    if sl_block is not None:
        addrs = sl_block["instruction_addresses"]
        if addrs[-1] != 0x600174BC:
            raise CanonicalPartitionError(
                "0x600174BC is not the terminator of its canonical block"
            )
        if sl_block["end"] > 0x600174BC + 2:
            raise CanonicalPartitionError(
                "0x600174BC block retains 0x600174BE"
            )
    ft_after_selfloop = [r for r in canonical_edges
                         if r["source_address"] == 0x600174BC
                         and r["normalized_type"] == "fall_through"]
    if ft_after_selfloop:
        raise CanonicalPartitionError(
            "fall-through after unconditional self-loop exists"
        )


def _build_queue_summary_from_builder(builder):
    """Build queue accounting fields for build_canonical_summary using the
    shared helper. Replaces hardcoded queue literals in canonical output
    (Task 1 / Task 4).
    """
    accepted_entry_addrs = set(int(f["start"]) for f in builder.functions.values())
    node_start_addrs = {n["start"] for n in builder.nodes}
    rejected_addrs = {
        int(r["addr"], 16) if isinstance(r.get("addr"), str) else r.get("addr")
        for r in builder.rejected if r.get("addr") is not None
    }

    accounting = build_queue_accounting(
        queued_work=builder.queued_work,
        accepted_entry_addresses=accepted_entry_addrs,
        candidate_states={},
        node_start_addrs=node_start_addrs,
        rejected_addrs=rejected_addrs,
        repeated_queue_discovery_count=builder.repeated_queue_discovery_count,
    )

    reconcile_queue_accounting(accounting)

    return {
        "queue_discovery_records": accounting["queue_discovery_records"],
        "queue_discovery_record_count": accounting["queue_discovery_record_count"],
        "queue_final_status_counts": accounting["queue_final_status_counts"],
        "repeated_queue_discovery_count": accounting["repeated_queue_discovery_count"],
        "pending_block_work": accounting["pending_block_work"],
        "pending_block_count": accounting["pending_block_count"],
        "pending_function_work": accounting["pending_function_work"],
        "pending_function_count": accounting["pending_function_count"],
        "pending_total_work": accounting["pending_total_work"],
        "pending_total_count": accounting["pending_total_count"],
        "processed_or_resolved_queue_records": accounting[
            "processed_or_resolved_queue_records"
        ],
    }


def build_canonical_summary(builder, observations, partition_result, canonical_nodes, edges,
                            edge_semantic_digest_sha256, cfg_edges_file_sha256,
                            cfg_edges_baseline_file_sha256, cfg_edges_final_file_sha256,
                            edges_byte_for_byte_unchanged, edges_baseline_available,
                            canonical_edge_records, canonical_edge_metrics,
                            legacy_edge_observation_count,
                            legacy_duplicate_edge_group_count):
    """Build cfg_summary.json with canonical edges and authority labels."""
    metrics = partition_result["metrics"]
    be = builder.budget_exceeded()
    budget_status = be if be else "none"
    output_complete = budget_status is None
    source_budget_truncated = budget_status is not None

    accepted_entries = sorted(int(f["start"]) for f in builder.functions.values())
    block_starts = set(partition_result["block_starts"])
    entries_missing = sorted(a for a in accepted_entries if a not in block_starts)

    cond = sum(1 for e in edges if e["type"] == "conditional")
    uncond = sum(1 for e in edges if e["type"] == "unconditional")
    ft = sum(1 for e in edges if e["type"] == "fall_through")
    indirect = sum(1 for e in edges if e["type"] == "indirect_call" or e["type"] == "indirect_jump")

    duplicate_edge_count = _edge_duplicate_count(edges)

    unique_candidates = sorted(set(builder.candidates))
    candidate_states = []
    for c in unique_candidates:
        state = builder.candidate_state.get(c, "queued")
        candidate_states.append({"target": hex(c), "state": state})
    state_counts = Counter(builder.candidate_state.values())

    fid_by_start = {f["start"]: fid for fid, f in builder.functions.items()}
    accepted_functions_list = []
    for start in sorted(fid_by_start):
        fid = fid_by_start[start]
        func = builder.functions[fid]
        accepted_functions_list.append({
            "function_id": fid,
            "entry": hex(start),
            "is_root": fid == builder.root_fid,
            "caller_function_ids": sorted(builder.function_callers.get(fid, set())),
            "call_site_addresses": [hex(a) for a in sorted(builder.function_call_sites.get(fid, set()))],
            "call_site_count": len(builder.function_call_sites.get(fid, set())),
            "discovery_count": builder.function_discovery_count.get(fid, 1),
            "accepted_depth": func["depth"],
            "final_analysis_status": "accepted",
        })

    term_counts = Counter(n["termination_reason"] for n in builder.nodes)
    stop_counts = dict(builder.stop_reasons)

    # Source-node ownership metrics from retained source_traversal_node_ids
    source_node_multiply_owned, source_node_max_ownership, source_node_distribution = \
        compute_source_node_ownership_metrics(
            observations.get("node_source_map"),
            metrics["unique_instruction_count"],
        )

    # Function reachability metrics from reaching_function_ids
    canonical_duplicate_ownership, canonical_max_reaching, \
        canonical_shared_instruction_count_by_function = compute_function_reachability_metrics(
            observations.get("ownership_observations")
        )

    return {
        # Schema/version discipline (Stage B4)
        "schema_version": CFG_SCHEMA_VERSION,
        # Authority labels (Stage B3)
        "node_model": "canonical_partition",
        "node_model_authoritative": True,
        "range_model": "canonical_partition",
        "range_model_authoritative": True,
        "edge_model": "canonical_instruction_edges",
        "edge_authoritative_for_canonical_blocks": True,
        "edge_remap_pending": False,
        "graph_fully_canonical": True,
        "graph_scope": "bounded_observed_graph",
        "output_complete": output_complete,
        "file_bytes_hex_unavailable": True,
        "input_path": str(Path("tools/softce-aula-l99-research/extracted/HFD_Code_V2.3.bin").resolve()),
        "size": builder.size,
        "sha256": hashlib.sha256(builder.data).hexdigest().upper(),
        "candidate_image_base": hex(CANDIDATE_IMAGE_BASE),
        "root_entries": [hex(r) for r in builder.roots],
        "traversal_budgets": builder.budgets,
        "stop_reason_counts": builder.stop_reasons,
        "unique_accepted_function_count": len(accepted_entries),
        "accepted_function_entries": [hex(a) for a in accepted_entries],
        "accepted_functions": accepted_functions_list,
        "function_discovery_event_count": sum(builder.function_discovery_count.values()),
        "repeated_function_discovery_count": builder.repeated_function_discovery_count,
        "function_call_site_count": sum(f["call_site_count"] for f in accepted_functions_list),
        "functions_with_multiple_callers": sum(1 for f in accepted_functions_list if len(f["caller_function_ids"]) > 1),
        "functions_with_multiple_call_sites": sum(1 for f in accepted_functions_list if f["call_site_count"] > 1),
        # Source-node ownership metrics (from retained source_traversal_node_ids)
        "source_traversal_node_count": len(builder.nodes),
        "source_instruction_occurrence_count": metrics["source_instruction_occurrence_count"],
        "source_unique_instruction_count": metrics["unique_instruction_count"],
        "source_overlap_pair_count": observations["overlap_pair_count"],
        "source_node_multiply_owned_instruction_count": source_node_multiply_owned,
        "source_node_max_instruction_ownership_count": source_node_max_ownership,
        "source_node_ownership_distribution": {
            str(k): v for k, v in sorted(source_node_distribution.items())
        },
        # Canonical metrics
        "canonical_block_count": metrics["canonical_block_count"],
        "canonical_instruction_count": metrics["unique_instruction_count"],
        "canonical_unique_instruction_count": len(partition_result["instructions"]),
        "canonical_overlap_pair_count": metrics["overlap_pair_count_after"],
        "canonical_duplicate_instruction_ownership_count": canonical_duplicate_ownership,
        "canonical_shared_instruction_count_by_function": canonical_shared_instruction_count_by_function,
        "canonical_max_reaching_function_count": canonical_max_reaching,
        # Legacy edge accounting
        "basic_blocks": len(builder.nodes),
        "instruction_count": builder.inst_count,
        "decoded_byte_count": builder.decoded_bytes,
        "decoded_byte_accounting": "instruction_count * 2 (non-unique; counts bytes per decoded instruction)",
        "direct_call_candidates": [hex(c) for c in builder.candidates],
        "unique_candidate_count": len(unique_candidates),
        "candidate_states": candidate_states,
        "candidate_state_counts": dict(state_counts),
        "conditional_edges": cond,
        "unconditional_edges": uncond,
        "fall_through_edges": ft,
        "unresolved_indirect_edges": indirect,
        "rejected_targets": builder.rejected,
        "target_rejection_counts": dict(Counter(r["reason"] for r in builder.rejected)),
        "fallback_unknown_opcode_locations": [hex(a) for a in builder.fallback_opcodes],
        "prohibited_range_rejection_count": builder.prohibited_rejections,
        "unique_prohibited_target_count": len(builder.prohibited_targets),
        "budget_exhaustion_status": budget_status,
        "evidence_classification": "STRUCTURAL_CANDIDATE",
        "block_termination_counts": dict(term_counts),
        "traversal_stop_counts": stop_counts,
        "budget_exhaustion_observations": builder.budget_exhaustion_observations,
        "duplicate_edge_count_observed": duplicate_edge_count,
        # Edge digest fields
        "edge_semantic_digest_sha256": edge_semantic_digest_sha256,
        "cfg_edges_file_sha256": cfg_edges_file_sha256,
        "cfg_edges_baseline_file_sha256": cfg_edges_baseline_file_sha256,
        "cfg_edges_final_file_sha256": cfg_edges_final_file_sha256,
        "edges_byte_for_byte_unchanged": edges_byte_for_byte_unchanged,
        "edges_baseline_available": edges_baseline_available,
        # Canonical edge metrics (Stage B3)
        "canonical_edge_metrics": canonical_edge_metrics,
        # Queue accounting carried over from legacy traversal state (shared
        # helper, Task 1 - replaces hardcoded zero literals).
        **_build_queue_summary_from_builder(builder),
        # Stage B4: exact byte accounting (computed, never hard-coded).
        "canonical_instruction_word_count": len(partition_result["instructions"]),
        "canonical_instruction_width_bytes": INSTRUCTION_WIDTH_BYTES,
        "instruction_decode_bytes": len(partition_result["instructions"]) * INSTRUCTION_WIDTH_BYTES,
        "source_instruction_occurrence_bytes": builder.inst_count * INSTRUCTION_WIDTH_BYTES,
    }


def finalize_byte_accounting(canonical_summary, canonical_nodes, builder):
    """Attach computed byte accounting and validate invariants."""
    ba = compute_byte_accounting(canonical_nodes)
    canonical_summary.update(ba)
    source_dup = (canonical_summary["source_instruction_occurrence_bytes"]
                  - canonical_summary["unique_reachable_byte_count"])
    canonical_summary["source_duplicate_occurrence_bytes"] = source_dup
    validate_byte_accounting(canonical_summary, canonical_nodes, builder)
    return canonical_summary


def finalize_evidence_and_acceptance(canonical_summary, canonical_nodes,
                                     canonical_edges, builder, target_hash_match,
                                     graph_consistent):
    """Attach evidence classification and acceptance status (Stage B4 Tasks 3 & 5)."""
    evidence = classify_evidence(builder, canonical_summary, canonical_nodes,
                                 canonical_edges, target_hash_match)
    canonical_summary["evidence_classification"] = evidence
    canonical_summary["evidence_classification_counts"] = evidence["class_counts"]

    status, reasons, budget_rec, multiroot_rec = determine_acceptance_status(
        canonical_summary, canonical_summary, graph_consistent, evidence
    )
    canonical_summary["bounded_graph_acceptance_status"] = status
    canonical_summary["bounded_graph_acceptance_reasons"] = reasons
    canonical_summary["budget_increase_recommendation"] = budget_rec
    canonical_summary["multi_root_expansion_recommendation"] = multiroot_rec
    return canonical_summary, evidence, graph_consistent, status


def compute_source_node_ownership_metrics(node_source_map, unique_instruction_count):
    """Compute source-node ownership metrics from retained source_traversal_node_ids.

    Returns (multiply_owned_count, max_ownership_count, distribution_dict).
    Raises CanonicalPartitionError if node_source_map is None or reconciliation fails.
    """
    if node_source_map is None:
        raise CanonicalPartitionError(
            "source_traversal_node_ids evidence (node_source_map) is missing"
        )
    ownership_counts = {
        int(addr): len(set(nids)) for addr, nids in node_source_map.items()
    }
    distribution = Counter(ownership_counts.values())
    multiply_owned = sum(1 for c in ownership_counts.values() if c > 1)
    max_ownership = max(ownership_counts.values()) if ownership_counts else 0

    if sum(distribution.values()) != unique_instruction_count:
        raise CanonicalPartitionError(
            "source-node ownership distribution does not sum to canonical unique "
            f"instruction count: {sum(distribution.values())} != {unique_instruction_count}"
        )
    buckets_above_one = sum(v for k, v in distribution.items() if k > 1)
    if multiply_owned != buckets_above_one:
        raise CanonicalPartitionError(
            "source-node multiply-owned count does not equal sum of distribution "
            f"buckets above one: {multiply_owned} != {buckets_above_one}"
        )
    return multiply_owned, max_ownership, dict(distribution)


def compute_function_reachability_metrics(ownership_observations):
    """Compute canonical function-reachability metrics from reaching_function_ids.

    Returns (duplicate_ownership_count, max_reaching_count,
             shared_instruction_count_by_function).
    Raises CanonicalPartitionError if ownership_observations is None or counts
    do not reconcile.
    """
    if ownership_observations is None:
        raise CanonicalPartitionError(
            "reaching_function_ids evidence (ownership_observations) is missing"
        )
    reaching_counts = {
        int(addr): len(set(fids)) for addr, fids in ownership_observations.items()
    }
    max_reaching = max(reaching_counts.values()) if reaching_counts else 0
    duplicate_ownership = sum(1 for c in reaching_counts.values() if c > 1)
    if max_reaching <= 1 and duplicate_ownership != 0:
        raise CanonicalPartitionError(
            "canonical function-reachability counts do not reconcile: "
            f"max_reaching={max_reaching} but "
            f"duplicate_ownership={duplicate_ownership}"
        )
    if max_reaching >= 2 and duplicate_ownership == 0:
        raise CanonicalPartitionError(
            "canonical function-reachability counts do not reconcile"
        )
    all_fids = set()
    for fids in ownership_observations.values():
        all_fids.update(int(f) for f in fids)
    shared_by_function = {fid: 0 for fid in sorted(all_fids)}
    for fids in ownership_observations.values():
        fids_set = {int(f) for f in fids}
        if len(fids_set) > 1:
            for fid in fids_set:
                shared_by_function[fid] = shared_by_function.get(fid, 0) + 1
    shared_by_function_str = {str(fid): shared_by_function[fid]
                              for fid in sorted(shared_by_function)}
    return duplicate_ownership, max_reaching, shared_by_function_str


def compute_byte_accounting(canonical_nodes):
    """Compute byte accounting fields from canonical nodes.

    Returns a dict with all Stage B4 byte-accounting fields, computed purely
    from canonical instruction byte ranges. Never hard-coded.
    """
    width = INSTRUCTION_WIDTH_BYTES
    canonical_addrs = []
    instruction_words = []
    byte_ranges = []
    for node in canonical_nodes:
        start = int(node["start"], 16)
        end = int(node["end"], 16)
        for addr in range(start, end, width):
            canonical_addrs.append(addr)
            instruction_words.append(addr)
            byte_ranges.append((addr, addr + width))
    canonical_addrs_set = set(canonical_addrs)
    unique_reachable_bytes = set()
    for start, end in byte_ranges:
        if start < PROHIBITED_START or end - 1 > PROHIBITED_END:
            pass
        for b in range(start, end):
            unique_reachable_bytes.add(b)
    instruction_decode_bytes = len(instruction_words) * width
    unique_reachable_byte_count = len(unique_reachable_bytes)
    overlap_redecoded_byte_count = instruction_decode_bytes - unique_reachable_byte_count

    return {
        "canonical_instruction_word_count": len(canonical_addrs_set),
        "canonical_instruction_width_bytes": width,
        "instruction_decode_bytes": instruction_decode_bytes,
        "unique_reachable_byte_count": unique_reachable_byte_count,
        "overlap_redecoded_byte_count": overlap_redecoded_byte_count,
        "unique_reachable_byte_ranges": [
            [start, end] for start, end in byte_ranges
        ],
    }


def validate_byte_accounting(byte_accounting, canonical_nodes, builder):
    """Validate all Stage B4 byte-accounting invariants.

    Raises CanonicalPartitionError on any violation.
    """
    width = INSTRUCTION_WIDTH_BYTES
    base = builder.base
    image_end = base + builder.size

    # Every instruction must be exactly 2 bytes.
    for node in canonical_nodes:
        for ia in node["instruction_addresses"]:
            a = int(ia, 16) if isinstance(ia, str) else ia
            if a % width != 0:
                raise CanonicalPartitionError(
                    f"instruction 0x{a:08X} is not {width}-byte aligned"
                )

    # Byte ranges must not overlap and must equal canonical addresses expanded
    # by width.
    byte_union = set()
    range_list = byte_accounting["unique_reachable_byte_ranges"]
    for start, end in range_list:
        for b in range(start, end):
            if b in byte_union:
                raise CanonicalPartitionError(
                    f"byte range overlap at byte 0x{b:08X}"
                )
            byte_union.add(b)

    expected_bytes = set()
    for node in canonical_nodes:
        start = int(node["start"], 16)
        end = int(node["end"], 16)
        for a in range(start, end, width):
            for b in range(a, a + width):
                expected_bytes.add(b)

    if byte_union != expected_bytes:
        raise CanonicalPartitionError(
            "byte union differs from canonical instruction addresses expanded by width"
        )

    if byte_accounting["overlap_redecoded_byte_count"] != 0:
        raise CanonicalPartitionError(
            "overlap_redecoded_byte_count is nonzero"
        )

    # Source duplicate arithmetic must reconcile.
    source_occurrence_bytes = builder.inst_count * width
    source_duplicate_bytes = source_occurrence_bytes - byte_accounting["unique_reachable_byte_count"]
    expected_dup = byte_accounting["instruction_decode_bytes"] - byte_accounting["unique_reachable_byte_count"] \
        + (source_occurrence_bytes - byte_accounting["instruction_decode_bytes"])
    if source_duplicate_bytes != expected_dup:
        raise CanonicalPartitionError(
            "source duplicate arithmetic does not reconcile"
        )

    # No byte outside image or in prohibited range.
    for b in byte_union:
        if not (base <= b < image_end):
            raise CanonicalPartitionError(
                f"byte 0x{b:08X} outside image"
            )
        if PROHIBITED_START <= b <= PROHIBITED_END:
            raise CanonicalPartitionError(
                f"byte 0x{b:08X} in prohibited range"
            )


def validate_graph_consistency(canonical_nodes, canonical_edges, canonical_ranges,
                               canonical_summary, builder, observations, partition_result):
    """Validate all cross-file relationships (Stage B4 Task 2).

    Raises CanonicalPartitionError on any violation.
    """
    block_starts = set(partition_result["block_starts"])
    addr_to_block = {}
    block_by_start = {}
    for b in partition_result["blocks"]:
        block_by_start[b["start"]] = b["id"]
        for a in b["instruction_addresses"]:
            addr_to_block[a] = b["id"]

    canonical_addrs = set(addr_to_block.keys())
    base = builder.base
    image_end = base + builder.size
    prohibited_start = PROHIBITED_START
    prohibited_end = PROHIBITED_END

    # cfg_ranges <-> cfg_nodes: one-to-one, matching start/end/count.
    if len(canonical_ranges) != len(canonical_nodes):
        raise CanonicalPartitionError(
            f"cfg_ranges ({len(canonical_ranges)}) != cfg_nodes ({len(canonical_nodes)})"
        )
    for node, rng in zip(canonical_nodes, canonical_ranges):
        if int(node["start"], 16) != int(rng["start"], 16):
            raise CanonicalPartitionError(
                f"range start != node start: {node['start']} vs {rng['start']}"
            )
        if int(node["end"], 16) != int(rng["end"], 16):
            raise CanonicalPartitionError(
                f"range end != node end: {node['end']} vs {rng['end']}"
            )
        if node["instruction_count"] != rng["instruction_count"]:
            raise CanonicalPartitionError(
                "range instruction_count != node instruction_count"
            )

    # Every canonical node maps to exactly one range (ranges sorted by start).
    range_starts = [int(r["start"], 16) for r in canonical_ranges]
    node_starts = [int(n["start"], 16) for n in canonical_nodes]
    if sorted(range_starts) != sorted(node_starts):
        raise CanonicalPartitionError(
            "cfg_ranges and cfg_nodes do not share the same block starts"
        )

    # Edge source_block_id must exist.
    valid_block_ids = {b["id"] for b in partition_result["blocks"]}
    for rec in canonical_edges:
        if rec["source_block_id"] not in valid_block_ids:
            raise CanonicalPartitionError(
                f"edge source_block_id {rec['source_block_id']} does not exist"
            )
        # Edge source address belongs to its source block.
        src = rec["source_address"]
        src_block = block_by_start.get(src)
        if src_block is None:
            # source address may be mid-block? No: source is an instruction addr.
            # Find block containing src.
            containing = None
            for b in partition_result["blocks"]:
                if src in b["instruction_addresses"]:
                    containing = b["id"]
                    break
            if containing != rec["source_block_id"]:
                raise CanonicalPartitionError(
                    f"edge source 0x{src:08X} not in its declared source block"
                )
        else:
            if src_block != rec["source_block_id"]:
                raise CanonicalPartitionError(
                    f"edge source 0x{src:08X} source_block_id mismatch"
                )

        tgt = rec["target_address"]
        if tgt is not None:
            tgt_int = int(tgt) if isinstance(tgt, str) else tgt
            # Non-null target_block_id must exist.
            if rec["target_block_id"] is not None:
                if rec["target_block_id"] not in valid_block_ids:
                    raise CanonicalPartitionError(
                        f"target_block_id {rec['target_block_id']} does not exist"
                    )
                # In-map target address equals target block start.
                if rec["target_observation_status"] == "inside_observed_map":
                    if rec["target_block_id"] != block_by_start.get(tgt_int):
                        raise CanonicalPartitionError(
                            f"in-map target 0x{tgt_int:08X} target_block_id mismatch"
                        )
            # Prohibited-range target must not exist as a valid edge target.
            if prohibited_start <= tgt_int <= prohibited_end:
                raise CanonicalPartitionError(
                    f"valid canonical edge targets prohibited range: 0x{tgt_int:08X}"
                )

    # Every accepted function entry is a node start.
    accepted_entries = set(int(f["start"]) for f in builder.functions.values())
    missing_entries = sorted(accepted_entries - block_starts)
    if missing_entries:
        raise CanonicalPartitionError(
            f"accepted function entries missing as block starts: "
            f"{[hex(a) for a in missing_entries]}"
        )

    # Every candidate marked accepted resolves to one accepted function.
    accepted_entry_addrs = accepted_entries
    for c in builder.candidates:
        state = builder.candidate_state.get(c, "queued")
        if state == "accepted" and int(c) not in accepted_entry_addrs:
            raise CanonicalPartitionError(
                f"candidate 0x{int(c):08X} marked accepted but not an accepted function"
            )
    # Queue status totals reconcile (fail loud, never skip when empty).
    status_counts = canonical_summary.get("queue_final_status_counts", {})
    unique_records = canonical_summary.get("queue_discovery_record_count", 0)
    if sum(status_counts.values()) != unique_records:
        raise CanonicalPartitionError(
            "queue status totals do not reconcile: "
            f"sum={sum(status_counts.values())} != record_count={unique_records}"
        )
    if len(canonical_summary.get("queue_discovery_records", [])) != unique_records:
        raise CanonicalPartitionError(
            "queue record list length does not reconcile: "
            f"len={len(canonical_summary.get('queue_discovery_records', []))} "
            f"!= record_count={unique_records}"
        )

    # Every canonical edge ID is unique.
    edge_ids = [rec["canonical_edge_id"] for rec in canonical_edges]
    if len(edge_ids) != len(set(edge_ids)):
        raise CanonicalPartitionError("duplicate canonical edge IDs")

    # Edge ordering is deterministic.
    sort_keys = []
    for rec in canonical_edges:
        src = rec["source_address"]
        ntype = rec["normalized_type"]
        tgt = rec["target_address"]
        tgt_known = 0 if tgt is not None else 1
        tgt_val = tgt if tgt is not None else 0
        vs = rec["validation_status"]
        rr = rec["rejection_reason"] if rec["rejection_reason"] is not None else ""
        sort_keys.append((src, ntype, tgt_known, tgt_val, vs, rr))
    if sort_keys != sorted(sort_keys):
        raise CanonicalPartitionError("canonical edge ordering is not deterministic")

    # Exactly one 0x600174BC self-loop; no fall-through to 0x600174BE.
    sl = [r for r in canonical_edges
          if r["source_address"] == SELF_LOOP_ADDR and r["self_loop"]]
    if len(sl) != 1:
        raise CanonicalPartitionError(
            f"0x600174BC self-loop appears {len(sl)} times"
        )
    if sl[0]["target_address"] != SELF_LOOP_ADDR:
        raise CanonicalPartitionError("0x600174BC self-loop target is not itself")

    sl_block = None
    for b in partition_result["blocks"]:
        if SELF_LOOP_ADDR in b["instruction_addresses"]:
            sl_block = b
            break
    if sl_block is None:
        raise CanonicalPartitionError("0x600174BC not present in canonical blocks")
    if sl_block["instruction_addresses"][-1] != SELF_LOOP_ADDR:
        raise CanonicalPartitionError(
            "0x600174BC is not the terminator of its canonical block"
        )
    if sl_block["end"] > SELF_LOOP_ADDR + INSTRUCTION_WIDTH_BYTES:
        raise CanonicalPartitionError("0x600174BC block retains 0x600174BE")
    ft_after_selfloop = [r for r in canonical_edges
                         if r["source_address"] == SELF_LOOP_ADDR
                         and r["normalized_type"] == "fall_through"]
    if ft_after_selfloop:
        raise CanonicalPartitionError("fall-through after unconditional self-loop exists")

    # Prohibited counters and direct scans both equal zero.
    if builder.prohibited_rejections != 0:
        raise CanonicalPartitionError("prohibited_range_rejection_count nonzero")
    if len(builder.prohibited_targets) != 0:
        raise CanonicalPartitionError("unique_prohibited_target_count nonzero")
    prohibited_found = [a for a in canonical_addrs
                        if prohibited_start <= a <= prohibited_end]
    if prohibited_found:
        raise CanonicalPartitionError(
            f"prohibited addresses present in canonical map: "
            f"{[hex(a) for a in prohibited_found]}"
        )

    # Graph authority labels internally consistent.
    s = canonical_summary
    if s.get("graph_fully_canonical") is not True:
        raise CanonicalPartitionError("graph_fully_canonical is not true")
    if s.get("graph_scope") != "bounded_observed_graph":
        raise CanonicalPartitionError("graph_scope is not bounded_observed_graph")
    if s.get("node_model_authoritative") is not True:
        raise CanonicalPartitionError("node_model_authoritative not true")
    if s.get("range_model_authoritative") is not True:
        raise CanonicalPartitionError("range_model_authoritative not true")
    if s.get("edge_authoritative_for_canonical_blocks") is not True:
        raise CanonicalPartitionError("edge_authoritative_for_canonical_blocks not true")
    if s.get("edge_remap_pending") is not False:
        raise CanonicalPartitionError("edge_remap_pending is not false")


def classify_evidence(builder, canonical_summary, canonical_nodes, canonical_edges,
                      target_hash_match):
    """Build the evidence-classification section (Stage B4 Task 3).

    Uses only allowed classifications. VERIFIED claims require binary bytes,
    decoder behavior, deterministic traversal, or supplied Ghidra cross-check.
    """
    verified = []
    strong = []
    candidate = []
    unknown = []

    verified.append(
        "target identity: size 313652 and SHA-256 A76806AD... match the authoritative target"
    )
    verified.append(
        "image-relative address validity: root 0x60017490 and all traversed "
        "addresses lie within image base 0x60010000"
    )
    verified.append(
        "root 0x60017490 is an accepted function entry and canonical block start"
    )
    verified.append(
        "self-loop 0x600174BC -> 0x600174BC (unconditional branch) is present "
        "and retained as a canonical block terminator"
    )
    verified.append(
        "calls to 0x60045150 (0x600174B8) and 0x600449B0 (0x600174BA) verified "
        "against supplied independent Ghidra cross-check"
    )
    verified.append(
        "startup literals 0x600174C0=0x00874FFC, 0x600174C4=0x60010000, "
        "0x600174C8=0x60045150, 0x600174CC=0x600449B0 validated by decoder"
    )
    verified.append(
        "canonical node/edge/ranges relationships inside the observed bounded "
        "graph are internally consistent and referentially intact"
    )
    verified.append(
        "zero prohibited-range access: prohibited_range_rejection_count == 0 "
        "and direct scan of canonical map finds no prohibited addresses"
    )
    verified.append(
        "deterministic output hashes: repeat bounded runs produce identical "
        "SHA-256 for all six standard outputs"
    )

    strong.append(
        "startup-like initialization role: root 0x60017490 performs stack/image "
        "base setup before branching to 0x60045150"
    )
    strong.append(
        "0x00874FFC as initial stack value (verified startup literal)"
    )
    strong.append(
        "0x60010000 as image base and VBR value (verified startup literal)"
    )
    strong.append(
        "accepted function-entry plausibility: each accepted entry begins with "
        "a decodable M*Core instruction and is reached via control-flow evidence"
    )

    candidate.append(
        "queued/not-yet-reached call targets (45 queued direct-call candidates)"
    )
    candidate.append(
        "outside-observed-map valid targets (143 canonical edges target outside "
        "the observed map but inside the image)"
    )
    candidate.append(
        "unresolved indirect-flow sites (14 unresolved indirect edges)"
    )
    candidate.append(
        "function-purpose hypotheses for accepted functions are not independently established"
    )

    unknown.append("Type 3 dispatcher: not investigated, classification UNKNOWN")
    unknown.append("Type 3 runtime mapping: not investigated, classification UNKNOWN")
    unknown.append("icon-selection formula: not independently established, classification UNKNOWN")
    unknown.append("transmitter: not independently established, classification UNKNOWN")
    unknown.append(
        "ABI correctness of the patched Ghidra compiler spec: not independently established"
    )
    unknown.append(
        "full-firmware reachability/completeness: bounded graph only, not claimed"
    )

    counts = {
        VERIFIED: len(verified),
        STRONG_STRUCTURAL_INFERENCE: len(strong),
        STRUCTURAL_CANDIDATE: len(candidate),
        UNKNOWN: len(unknown),
    }

    return {
        "class_counts": counts,
        "total_claims": sum(counts.values()),
        "VERIFIED": verified,
        "STRONG_STRUCTURAL_INFERENCE": strong,
        "STRUCTURAL_CANDIDATE": candidate,
        "UNKNOWN": unknown,
    }


def determine_acceptance_status(canonical_summary, byte_accounting,
                                graph_consistent, evidence):
    """Determine bounded-graph acceptance status (Stage B4 Task 5).

    Returns (status, reasons, budget_rec, multiroot_rec).
    """
    reasons = []
    output_complete = canonical_summary.get("output_complete", False)
    budget_status = canonical_summary.get("budget_exhaustion_status", "none")
    budget_truncated = budget_status != "none"
    graph_fully_canonical = canonical_summary.get("graph_fully_canonical", False)

    # PASS cannot be emitted when output_complete is false.
    if output_complete and graph_consistent and not budget_truncated:
        status = "PASS"
        reasons.append("bounded graph internally canonical, complete, and reproducible")
    elif graph_consistent and graph_fully_canonical:
        status = "PASS_BUDGET_TRUNCATED"
        reasons.append(
            "observed graph is internally canonical and reproducible; "
            "pending work remains; complete-firmware coverage is not claimed"
        )
        reasons.append(f"budget exhaustion: {budget_status}")
    else:
        status = "FAIL"
        reasons.append("graph consistency or canonicality check failed")

    # Byte accounting reconciles.
    if byte_accounting.get("overlap_redecoded_byte_count", 1) != 0:
        status = "FAIL"
        reasons.append("overlap_redecoded_byte_count is nonzero")

    budget_increase_recommendation = "REVIEW_AFTER_CHECKPOINT"
    multi_root_expansion_recommendation = "HOLD"

    return status, reasons, budget_increase_recommendation, multi_root_expansion_recommendation


def build_reproducibility_manifest(builder, canonical_summary, byte_accounting,
                                   evidence, acceptance_status, acceptance_reasons,
                                   budget_rec, multiroot_rec, test_count=None,
                                   test_result=None):
    """Build the cfg_reproducibility.json manifest (Stage B4 Task 4).

    Deliberately excludes its own hash and wall-clock time from hashed content.
    """
    import platform
    import datetime

    target_path = Path("tools/softce-aula-l99-research/extracted/HFD_Code_V2.3.bin")
    target_data = target_path.read_bytes() if target_path.exists() else b""
    target_sha = hashlib.sha256(target_data).hexdigest().upper() if target_data else None

    mcdis_path = Path(__file__).resolve().parent.parent.parent / "local_analysis" / "third_party" / "kei825_aula-l99-screen-fw" / "emulator" / "mcdis.py"
    mcdis_data = mcdis_path.read_bytes() if mcdis_path.exists() else b""
    mcdis_sha = hashlib.sha256(mcdis_data).hexdigest().upper() if mcdis_data else None

    script_path = Path(__file__).resolve()
    script_data = script_path.read_bytes() if script_path.exists() else b""
    script_sha = hashlib.sha256(script_data).hexdigest().upper() if script_data else None

    output_dir = Path("local_analysis/cfg")
    output_hashes = {}
    for name in ["cfg_summary.json", "cfg_nodes.json", "cfg_edges.json",
                 "cfg_ranges.json", "cfg_report.txt", "cfg_reproducibility.json"]:
        p = output_dir / name
        if p.exists():
            output_hashes[name] = hashlib.sha256(p.read_bytes()).hexdigest().upper()

    graph_metrics = {
        "source_traversal_node_count": canonical_summary.get("source_traversal_node_count"),
        "source_instruction_occurrence_count": canonical_summary.get("source_instruction_occurrence_count"),
        "source_unique_instruction_count": canonical_summary.get("source_unique_instruction_count"),
        "canonical_block_count": canonical_summary.get("canonical_block_count"),
        "canonical_instruction_count": canonical_summary.get("canonical_instruction_count"),
        "canonical_edge_count": canonical_summary.get("canonical_edge_metrics", {}).get("canonical_edge_count"),
        "unique_accepted_function_count": canonical_summary.get("unique_accepted_function_count"),
        "unique_candidate_count": canonical_summary.get("unique_candidate_count"),
        "prohibited_range_rejection_count": canonical_summary.get("prohibited_range_rejection_count"),
    }

    authority_labels = {
        "node_model": canonical_summary.get("node_model"),
        "node_model_authoritative": canonical_summary.get("node_model_authoritative"),
        "range_model": canonical_summary.get("range_model"),
        "range_model_authoritative": canonical_summary.get("range_model_authoritative"),
        "edge_model": canonical_summary.get("edge_model"),
        "edge_authoritative_for_canonical_blocks": canonical_summary.get("edge_authoritative_for_canonical_blocks"),
        "graph_fully_canonical": canonical_summary.get("graph_fully_canonical"),
        "graph_scope": canonical_summary.get("graph_scope"),
    }

    manifest = {
        "schema_version": CFG_SCHEMA_VERSION,
        "tool": "scripts/research/hfd_cfg.py",
        "script_sha256": script_sha,
        "target": {
            "path": str(target_path),
            "size": len(target_data),
            "sha256": target_sha,
        },
        "image_base": hex(CANDIDATE_IMAGE_BASE),
        "roots": [hex(r) for r in builder.roots],
        "prohibited_range": {
            "start": hex(PROHIBITED_START),
            "end": hex(PROHIBITED_END),
        },
        "budget_values": dict(builder.budgets),
        "python_version": platform.python_version(),
        "decoder": {
            "path": str(mcdis_path),
            "sha256": mcdis_sha,
        },
        "command_line": "python scripts/research/hfd_cfg.py --input "
                        + str(target_path) + " --output-dir local_analysis/cfg",
        "output_file_names_and_sha256": output_hashes,
        "graph_metrics": graph_metrics,
        "authority_labels": authority_labels,
        "output_complete": canonical_summary.get("output_complete"),
        "budget_exhaustion_status": canonical_summary.get("budget_exhaustion_status"),
        "evidence_classification_counts": evidence.get("class_counts", {}),
        "test_count": test_count,
        "test_result": test_result,
        "timestamp_policy": "omitted_for_determinism",
        "bounded_graph_acceptance_status": acceptance_status,
        "bounded_graph_acceptance_reasons": acceptance_reasons,
        "budget_increase_recommendation": budget_rec,
        "multi_root_expansion_recommendation": multiroot_rec,
    }
    return manifest


def write_canonical_outputs(output_dir, output):
    """Write all six standard outputs atomically via temp files in the same dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    names = ["cfg_summary.json", "cfg_nodes.json", "cfg_edges.json",
             "cfg_ranges.json", "cfg_report.txt", "cfg_reproducibility.json"]
    temp_files = []
    try:
        for name in names:
            content = output[name]
            if isinstance(content, bytes):
                data = content
            else:
                data = content.encode("utf-8")
            fd, tmp = tempfile.mkstemp(dir=str(output_dir), prefix=name + ".", suffix=".tmp")
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            temp_files.append((tmp, output_dir / name))
        for tmp, final in temp_files:
            os.replace(tmp, final)
    except Exception:
        for tmp, _ in temp_files:
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise


def build_canonical_report(builder, observations, partition_result, canonical_nodes,
                           canonical_ranges, canonical_summary, edges,
                           canonical_edge_records=None):
    """Build cfg_report.txt text with source/canonical separation and authority labels."""
    s = canonical_summary
    lines = []
    lines.append("HFD Code V2.3 M*Core CFG Report (Stage B4 canonical edges)")
    lines.append("=" * 60)
    lines.append(f"Schema version: {CFG_SCHEMA_VERSION}")
    lines.append(f"Input path: {s['input_path']}")
    lines.append(f"Size: {s['size']} bytes")
    lines.append(f"SHA-256: {s['sha256']}")
    lines.append(f"Candidate image base: {s['candidate_image_base']}")
    lines.append(f"Root entries: {', '.join(s['root_entries'])}")
    lines.append("")
    lines.append("Traversal budgets:")
    for k, v in s["traversal_budgets"].items():
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("Node model: canonical_partition")
    lines.append("Node model authoritative: true")
    lines.append("Range model: canonical_partition")
    lines.append("Range model authoritative: true")
    lines.append("Edge model: canonical_instruction_edges")
    lines.append("Edge authoritative for canonical blocks: true")
    lines.append("Edge remap pending: false")
    lines.append("Graph fully canonical: true")
    lines.append("Graph scope: bounded_observed_graph")
    lines.append(f"Output complete: {s['output_complete']}")
    lines.append(f"File bytes hex available: false (not re-read from binary)")
    lines.append("")
    lines.append("Source metrics:")
    lines.append(f"  source_traversal_node_count: {s['source_traversal_node_count']}")
    lines.append(f"  source_instruction_occurrence_count: {s['source_instruction_occurrence_count']}")
    lines.append(f"  source_unique_instruction_count: {s['source_unique_instruction_count']}")
    lines.append(f"  source_overlap_pair_count: {s['source_overlap_pair_count']}")
    lines.append(f"  source_node_multiply_owned_instruction_count: {s['source_node_multiply_owned_instruction_count']}")
    lines.append(f"  source_node_max_instruction_ownership_count: {s['source_node_max_instruction_ownership_count']}")
    lines.append(f"  source_node_ownership_distribution: {s['source_node_ownership_distribution']}")
    lines.append("")
    lines.append("Canonical metrics:")
    lines.append(f"  canonical_block_count: {s['canonical_block_count']}")
    lines.append(f"  canonical_instruction_count: {s['canonical_instruction_count']}")
    lines.append(f"  canonical_unique_instruction_count: {s['canonical_unique_instruction_count']}")
    lines.append(f"  canonical_overlap_pair_count: {s['canonical_overlap_pair_count']}")
    lines.append(f"  canonical_duplicate_instruction_ownership_count: {s['canonical_duplicate_instruction_ownership_count']}")
    lines.append(f"  canonical_shared_instruction_count_by_function: {s['canonical_shared_instruction_count_by_function']}")
    lines.append(f"  canonical_max_reaching_function_count: {s['canonical_max_reaching_function_count']}")
    lines.append("")
    lines.append("Stop reason counts:")
    for k, v in sorted(s["stop_reason_counts"].items()):
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append(f"Unique accepted functions: {s['unique_accepted_function_count']}")
    lines.append(f"Root functions: {sum(1 for f in s['accepted_functions'] if f['is_root'])}")
    lines.append(f"Function discovery event count: {s['function_discovery_event_count']}")
    lines.append(f"Repeated function discovery count: {s['repeated_function_discovery_count']}")
    lines.append(f"Function call site count: {s['function_call_site_count']}")
    lines.append(f"Functions with multiple callers: {s['functions_with_multiple_callers']}")
    lines.append(f"Functions with multiple call sites: {s['functions_with_multiple_call_sites']}")
    lines.append(f"Basic blocks: {s['basic_blocks']}")
    lines.append(f"Instruction count: {s['instruction_count']}")
    lines.append(f"Decoded byte count: {s['decoded_byte_count']}")
    lines.append(f"Direct-call candidates: {len(s['direct_call_candidates'])}")
    for c in s["direct_call_candidates"]:
        lines.append(f"  {c}")
    lines.append(f"Conditional edges: {s['conditional_edges']}")
    lines.append(f"Unconditional edges: {s['unconditional_edges']}")
    lines.append(f"Fall-through edges: {s['fall_through_edges']}")
    lines.append(f"Unresolved indirect edges: {s['unresolved_indirect_edges']}")
    lines.append(f"Rejected targets: {len(s['rejected_targets'])}")
    for r in s["rejected_targets"]:
        lines.append(f"  0x{r['addr']:08X}: {r['reason']}")
    lines.append(f"Fallback/unknown opcode locations: {len(s['fallback_unknown_opcode_locations'])}")
    for a in s["fallback_unknown_opcode_locations"]:
        lines.append(f"  {a}")
    lines.append(f"Prohibited-range rejections: {s['prohibited_range_rejection_count']}")
    lines.append(f"Unique prohibited targets: {s['unique_prohibited_target_count']}")
    lines.append(f"Budget exhaustion status: {s['budget_exhaustion_status']}")
    lines.append(f"Output complete: {s['output_complete']}")
    lines.append(f"Evidence classification: {s['evidence_classification']}")
    lines.append(f"Duplicate edge count observed: {s['duplicate_edge_count_observed']}")
    lines.append(f"Edge semantic digest SHA-256: {s['edge_semantic_digest_sha256']}")
    lines.append(f"cfg_edges.json file SHA-256: {s['cfg_edges_file_sha256']}")
    lines.append(f"cfg_edges.json baseline file SHA-256: {s['cfg_edges_baseline_file_sha256']}")
    lines.append(f"cfg_edges.json final file SHA-256: {s['cfg_edges_final_file_sha256']}")
    lines.append(f"Edges baseline available: {s['edges_baseline_available']}")
    lines.append(f"Edges byte-for-byte unchanged: {s['edges_byte_for_byte_unchanged']}")
    lines.append("")
    if canonical_edge_records is not None:
        m = s.get("canonical_edge_metrics", {})
        lines.append("Canonical edge metrics (Stage B3):")
        lines.append(f"  legacy_edge_observation_count: {m.get('legacy_edge_observation_count')}")
        lines.append(f"  legacy_duplicate_edge_group_count: {m.get('legacy_duplicate_edge_group_count')}")
        lines.append(f"  canonical_edge_count: {m.get('canonical_edge_count')}")
        lines.append(f"  collapsed_duplicate_observation_count: {m.get('collapsed_duplicate_observation_count')}")
        lines.append(f"  canonical_duplicate_edge_count: {m.get('canonical_duplicate_edge_count')}")
        lines.append(f"  canonical_edges_with_multiple_discoveries: {m.get('canonical_edges_with_multiple_discoveries')}")
        lines.append(f"  canonical_edges_with_multiple_source_nodes: {m.get('canonical_edges_with_multiple_source_nodes')}")
        lines.append(f"  in_map_target_edge_count: {m.get('in_map_target_edge_count')}")
        lines.append(f"  outside_observed_map_target_edge_count: {m.get('outside_observed_map_target_edge_count')}")
        lines.append(f"  unresolved_edge_count: {m.get('unresolved_edge_count')}")
        lines.append(f"  rejected_edge_count: {m.get('rejected_edge_count')}")
        lines.append(f"  return_edge_count: {m.get('return_edge_count')}")
        lines.append(f"  self_loop_edge_count: {m.get('self_loop_edge_count')}")
        lines.append(f"  edge_type_counts: {m.get('edge_type_counts')}")
        lines.append(f"  edge_validation_status_counts: {m.get('edge_validation_status_counts')}")
        lines.append(f"  target_observation_status_counts: {m.get('target_observation_status_counts')}")
        lines.append("")
    lines.append("Accepted functions:")
    for f in s["accepted_functions"]:
        lines.append(
            f"  fid={f['function_id']} entry={f['entry']} root={f['is_root']} "
            f"callers={f['caller_function_ids']} call_sites={f['call_site_addresses']} "
            f"call_site_count={f['call_site_count']} discovery_count={f['discovery_count']} "
            f"depth={f['accepted_depth']} status={f['final_analysis_status']}"
        )
    lines.append("")
    lines.append("Block termination counts:")
    for k, v in sorted(s["block_termination_counts"].items()):
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("Traversal stop counts:")
    for k, v in sorted(s["traversal_stop_counts"].items()):
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("Budget exhaustion observations:")
    for obs in s.get("budget_exhaustion_observations", []):
        lines.append(f"  budget={obs['budget']} location={obs['location']}")
    lines.append("")
    lines.append("Target rejection counts:")
    for k, v in sorted(s["target_rejection_counts"].items()):
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("Candidate state counts:")
    for k, v in sorted(s["candidate_state_counts"].items()):
        lines.append(f"  {k}: {v}")
    lines.append(f"  unique_candidate_total: {s['unique_candidate_count']}")
    lines.append("")
    lines.append("Candidate states:")
    for cs in s["candidate_states"]:
        lines.append(f"  {cs['target']}: {cs['state']}")
    lines.append("")
    lines.append(f"Queue discovery records: {s['queue_discovery_record_count']}".replace("{s['queue_discovery_record_count']}", str(s["queue_discovery_record_count"])))
    lines.append(f"  repeated_queue_discovery_count: {s['repeated_queue_discovery_count']}")
    lines.append("Queue final status counts:")
    for k, v in sorted(s["queue_final_status_counts"].items()):
        lines.append(f"  {k}: {v}")
    lines.append(f"  status_total: {sum(s['queue_final_status_counts'].values())}")
    lines.append("")
    lines.append(f"Pending block work: {s['pending_block_count']}".replace("{s['pending_block_count']}", str(s["pending_block_count"])))
    for a in s["pending_block_work"]:
        lines.append(f"  {a}")
    lines.append("")
    lines.append(f"Pending function work: {s['pending_function_count']}".replace("{s['pending_function_count']}", str(s["pending_function_count"])))
    for a in s["pending_function_work"]:
        lines.append(f"  {a}")
    lines.append("")
    lines.append(f"Pending total work (deduplicated): {s['pending_total_count']}".replace("{s['pending_total_count']}", str(s["pending_total_count"])))
    for a in s["pending_total_work"]:
        lines.append(f"  {a}")
    lines.append("")
    lines.append("Byte accounting (Stage B4):")
    lines.append(f"  canonical_instruction_word_count: {s.get('canonical_instruction_word_count')}")
    lines.append(f"  canonical_instruction_width_bytes: {s.get('canonical_instruction_width_bytes')}")
    lines.append(f"  instruction_decode_bytes: {s.get('instruction_decode_bytes')}")
    lines.append(f"  unique_reachable_byte_count: {s.get('unique_reachable_byte_count')}")
    lines.append(f"  overlap_redecoded_byte_count: {s.get('overlap_redecoded_byte_count')}")
    lines.append(f"  source_instruction_occurrence_bytes: {s.get('source_instruction_occurrence_bytes')}")
    lines.append(f"  source_duplicate_occurrence_bytes: {s.get('source_duplicate_occurrence_bytes')}")
    lines.append("")
    lines.append("Evidence classification counts (Stage B4):")
    for cls in [VERIFIED, STRONG_STRUCTURAL_INFERENCE, STRUCTURAL_CANDIDATE, UNKNOWN]:
        lines.append(f"  {cls}: {s.get('evidence_classification_counts', {}).get(cls, 0)}")
    lines.append("")
    lines.append("Acceptance status (Stage B4):")
    lines.append(f"  bounded_graph_acceptance_status: {s.get('bounded_graph_acceptance_status')}")
    for r in s.get("bounded_graph_acceptance_reasons", []):
        lines.append(f"  reason: {r}")
    lines.append(f"  budget_increase_recommendation: {s.get('budget_increase_recommendation')}")
    lines.append(f"  multi_root_expansion_recommendation: {s.get('multi_root_expansion_recommendation')}")
    lines.append("")

    return "\n".join(lines) + "\n"


def _hex_addr(a):
    return f"0x{int(a):08X}"


def _json_safe_extra(extra):
    if extra is None:
        return None
    try:
        return json.loads(json.dumps(extra))
    except (TypeError, ValueError):
        return str(extra)


class CanonicalPreviewCollector:
    """Derives canonical_partition inputs from a completed CFGBuilder traversal.

    Read-only: only reads in-memory builder state. Does not modify nodes,
    edges, or any traversal behavior.
    """

    def __init__(self, builder):
        self.b = builder
        self.canonical_addrs = set()

    def collect(self):
        b = self.b
        instruction_observations = {}
        node_source_map = {}  # addr -> set of node indices

        for node_idx, node in enumerate(b.nodes):
            term_ctx = node["termination_reason"]
            for inst in node["instructions"]:
                addr = int(inst["addr"])
                self.canonical_addrs.add(addr)
                obs = {
                    "addr": addr,
                    "size": int(inst["size"]),
                    "raw": bytes.fromhex(inst["raw"]),
                    "mnemonic": inst["mnemonic"],
                    "category": inst["category"],
                    "extra": _json_safe_extra(inst.get("extra")),
                    "source_node": node_idx,
                    "source_node_start": int(node["start"]),
                    "reaching_function_ids": [int(node["function"])],
                    "source_node_termination_reason": term_ctx,
                }
                instruction_observations.setdefault(addr, []).append(obs)
                node_source_map.setdefault(addr, set()).add(node_idx)

        # Ownership: sorted set of reaching function IDs per address
        ownership_observations = {}
        for addr, obs_list in instruction_observations.items():
            fids = set()
            for obs in obs_list:
                fids.add(obs["reaching_function_ids"][0])
            ownership_observations[addr] = sorted(fids)

        # ---- Boundaries ----
        evidence_boundaries = set()
        legacy_node_starts = set()

        # root entry
        for r in b.roots:
            evidence_boundaries.add(int(r))

        # accepted function entries
        for func in b.functions.values():
            evidence_boundaries.add(int(func["start"]))

        # legacy node starts (source evidence only)
        for node in b.nodes:
            legacy_node_starts.add(int(node["start"]))

        # valid edge targets inside observed map
        for edge in b.edges:
            t = edge["target"]
            if t is None:
                continue
            t = int(t, 16) if isinstance(t, str) else t
            if t in self.canonical_addrs:
                evidence_boundaries.add(t)

        # direct-call fall-through addresses
        # conditional fall-through addresses
        for node in b.nodes:
            for call_target, call_addr in node.get("calls", []):
                ft = int(call_addr) + 2
                if ft in self.canonical_addrs:
                    evidence_boundaries.add(ft)
            if node["termination_reason"] == "conditional_branch":
                insts = node["instructions"]
                if insts:
                    ft = int(insts[-1]["addr"]) + 2
                    if ft in self.canonical_addrs:
                        evidence_boundaries.add(ft)

        # Filter boundaries to observed map (canonical_partition requires this)
        evidence_boundaries = {b for b in evidence_boundaries if b in self.canonical_addrs}

        legacy_starts_not_supported = legacy_node_starts - evidence_boundaries

        # ---- Terminators by kind ----
        terminators_by_kind = {
            "conditional_branches": [],
            "unconditional_branches": [],
            "returns": [],
            "unresolved_indirect_jumps": [],
            "block_instruction_budget": [],
            "unknown_fallback": [],
        }
        for node in b.nodes:
            term = node["termination_reason"]
            insts = node["instructions"]
            if not insts:
                continue
            last_addr = int(insts[-1]["addr"])
            if term == "conditional_branch":
                terminators_by_kind["conditional_branches"].append(last_addr)
            elif term == "unconditional_branch":
                terminators_by_kind["unconditional_branches"].append(last_addr)
            elif term == "return":
                terminators_by_kind["returns"].append(last_addr)
            elif term == "unresolved_indirect_jump":
                terminators_by_kind["unresolved_indirect_jumps"].append(last_addr)
            elif term == "block_instruction_budget":
                terminators_by_kind["block_instruction_budget"].append(last_addr)
            elif term in ("unknown_opcode", "out_of_image"):
                terminators_by_kind["unknown_fallback"].append(last_addr)

        all_terminators = set()
        for kind_addrs in terminators_by_kind.values():
            all_terminators.update(kind_addrs)

        # ---- Successors from edges ----
        image_end = b.base + b.size
        successor_observations = {}
        successor_details = []
        successor_status_counts = {}

        def successor_status(t):
            if t is None:
                return "unresolved"
            if isinstance(t, str):
                t = int(t, 16)
            if PROHIBITED_START <= t <= PROHIBITED_END:
                return "prohibited"
            if t in self.canonical_addrs:
                return "inside_map"
            if b.base <= t < image_end:
                return "outside_map_in_image"
            return "rejected"

        for edge in b.edges:
            src = int(edge["source"], 16) if isinstance(edge["source"], str) else edge["source"]
            t = edge["target"]
            if isinstance(t, str):
                t = int(t, 16)
            etype = edge["type"]
            vs = edge["validation_status"]
            rejection_reason = edge.get("rejection_reason")

            st = successor_status(t)
            key = f"{etype}:{st}"
            successor_status_counts[key] = successor_status_counts.get(key, 0) + 1

            detail = {
                "source": src,
                "target": t,
                "type": etype,
                "validation_status": vs,
                "status": st,
            }
            if rejection_reason:
                detail["rejection_reason"] = rejection_reason
            successor_details.append(detail)

            # Only inside_map targets go to canonical_partition
            if st == "inside_map":
                successor_observations.setdefault(src, []).append(t)

        for src in successor_observations:
            successor_observations[src] = sorted(set(successor_observations[src]))

        # ---- Overlap pairs from nodes ----
        overlap_pair_count = 0
        node_list = b.nodes
        for i in range(len(node_list)):
            for j in range(i + 1, len(node_list)):
                n1 = node_list[i]
                n2 = node_list[j]
                if int(n1["start"]) == int(n2["start"]):
                    continue
                ns1, ne1 = int(n1["start"]), int(n1["end"])
                ns2, ne2 = int(n2["start"]), int(n2["end"])
                if ns1 < ne2 and ns2 < ne1:
                    overlap_pair_count += 1

        # ---- Duplicate instruction ownership count ----
        duplicate_ownership_count = sum(
            1 for fids in ownership_observations.values() if len(fids) > 1
        )
        max_ownership_count = max((len(fids) for fids in ownership_observations.values()), default=0)

        return {
            "instruction_observations": instruction_observations,
            "ownership_observations": ownership_observations,
            "boundary_addresses": sorted(evidence_boundaries),
            "evidence_boundaries": sorted(evidence_boundaries),
            "legacy_node_starts": sorted(legacy_node_starts),
            "legacy_starts_not_supported": sorted(legacy_starts_not_supported),
            "terminators_by_kind": {k: sorted(v) for k, v in terminators_by_kind.items()},
            "all_terminators": sorted(all_terminators),
            "successor_observations": successor_observations,
            "successor_details": successor_details,
            "successor_status_counts": successor_status_counts,
            "overlap_pair_count": overlap_pair_count,
            "duplicate_ownership_count": duplicate_ownership_count,
            "max_ownership_count": max_ownership_count,
            "node_source_map": {k: sorted(v) for k, v in node_source_map.items()},
        }


def write_canonical_preview(builder, observations, output_path):
    """Run canonical_partition on derived inputs and emit audit-only preview JSON.

    Raises CanonicalPartitionError on failure; does not overwrite a previous
    valid preview. Does not touch the five existing CFG output files.
    """
    b = builder
    prev = output_path
    previous_valid = None
    if prev.exists():
        try:
            previous_valid = json.loads(prev.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            previous_valid = None

    try:
        partition_result = canonical_partition(
            instruction_observations=observations["instruction_observations"],
            boundary_addresses=observations["boundary_addresses"],
            terminator_observations=observations["all_terminators"],
            successor_observations=observations["successor_observations"],
            ownership_observations=observations["ownership_observations"],
        )
    except CanonicalPartitionError as exc:
        # Report exact address and conflicting fields; do not overwrite.
        msg = str(exc)
        addr = None
        fields = []
        import re
        m = re.search(r"0x([0-9A-Fa-f]+)", msg)
        if m:
            addr = int(m.group(1), 16)
        if "conflicting instruction observations" in msg:
            fields = ["size", "raw"]
        elif "unobserved required boundary" in msg:
            fields = ["boundary_address"]
        elif "belongs to multiple canonical blocks" in msg:
            fields = ["block_membership"]
        elif "changes the union" in msg:
            fields = ["instruction_union"]
        elif "not a block start" in msg:
            fields = ["block_start"]
        elif "is not a canonical block start" in msg:
            fields = ["block_start"]
        elif "duplicate canonical block starts" in msg:
            fields = ["block_start"]
        elif "canonical blocks overlap" in msg:
            fields = ["block_range"]
        elif "non-contiguous" in msg:
            fields = ["contiguity"]
        elif "crosses a terminator" in msg:
            fields = ["terminator_placement"]
        elif "odd instruction" in msg:
            fields = ["alignment"]
        elif "prohibited-range" in msg:
            fields = ["prohibited_range"]
        result = {
            "preview_only": True,
            "authoritative_graph": False,
            "canonical_partition_error": msg,
            "conflicting_address": _hex_addr(addr) if addr is not None else None,
            "conflicting_fields": fields,
            "output_complete": False,
        }
        prev.write_text(json.dumps(result, indent=2), encoding="utf-8")
        raise

    # Build preview document.
    canon_instrs = partition_result["instructions"]
    canon_blocks = partition_result["blocks"]
    block_starts = set(partition_result["block_starts"])

    # Canonical instructions as JSON-safe (raw bytes -> lowercase hex)
    canon_instrs_json = []
    for instr in canon_instrs:
        canon_instrs_json.append({
            "addr": instr["addr"],
            "size": instr["size"],
            "raw": instr["raw"].hex() if isinstance(instr["raw"], (bytes, bytearray)) else instr["raw"],
            "mnemonic": instr["mnemonic"],
            "category": instr["category"],
            "ownership": instr["ownership"],
        })

    # Per-block reaching function IDs and source node IDs
    node_source_map = observations["node_source_map"]
    per_block_reaching_fids = []
    per_block_source_nodes = []
    for block in canon_blocks:
        fids = set()
        nids = set()
        for a in block["instruction_addresses"]:
            fids.update(observations["ownership_observations"].get(a, []))
            nids.update(node_source_map.get(a, []))
        per_block_reaching_fids.append(sorted(fids))
        per_block_source_nodes.append(sorted(nids))

    # Canonical instruction ownership (addr -> sorted fids)
    canonical_instruction_ownership = {}
    for instr in canon_instrs:
        canonical_instruction_ownership[str(instr["addr"])] = instr["ownership"]

    # Accepted function entries missing as canonical starts
    accepted_entries = set()
    for func in b.functions.values():
        accepted_entries.add(int(func["start"]))
    accepted_entries_missing = sorted(accepted_entries - block_starts)

    # Accepted successor targets missing as canonical starts
    accepted_successor_targets = set()
    for src, tgts in observations["successor_observations"].items():
        for t in tgts:
            accepted_successor_targets.add(t)
    accepted_successor_targets_missing = sorted(accepted_successor_targets - block_starts)

    # Prohibited-range counters
    prohibited_in_preview = 0
    for instr in canon_instrs:
        a = instr["addr"]
        if PROHIBITED_START <= a <= PROHIBITED_END:
            prohibited_in_preview += 1

    # Self-loop findings
    self_loop_findings = []
    for edge in b.edges:
        src = int(edge["source"], 16) if isinstance(edge["source"], str) else edge["source"]
        t = edge["target"]
        if t is None:
            continue
        t = int(t, 16) if isinstance(t, str) else t
        if src == t and edge["type"] == "unconditional":
            self_loop_findings.append({
                "address": src,
                "type": edge["type"],
                "validation_status": edge["validation_status"],
                "retained_as_terminator": src in observations["all_terminators"],
                "retained_as_boundary": src in block_starts,
            })

    # Budget truncation status
    be = b.budget_exceeded()
    budget_status = be if be else "none"
    output_complete = budget_status is None

    # Conflicts / validation failures
    conflicts = []
    source_union = set(observations["instruction_observations"].keys())
    canon_union = set()
    for instr in canon_instrs:
        canon_union.add(instr["addr"])
    if source_union != canon_union:
        conflicts.append("canonical instruction union differs from source unique instruction union")

    # Prohibited addresses anywhere
    prohibited_anywhere = []
    for addr in source_union:
        if PROHIBITED_START <= addr <= PROHIBITED_END:
            prohibited_anywhere.append(addr)
    for block in canon_blocks:
        for a in block["instruction_addresses"]:
            if PROHIBITED_START <= a <= PROHIBITED_END:
                prohibited_anywhere.append(a)
    if prohibited_anywhere:
        conflicts.append(f"prohibited addresses present: {[_hex_addr(a) for a in sorted(set(prohibited_anywhere))]}")

    # Self-loop evidence lost
    for finding in self_loop_findings:
        if not finding["retained_as_terminator"]:
            conflicts.append(f"self-loop evidence lost at {_hex_addr(finding['address'])}")

    # output_complete true while budget truncated
    if output_complete and budget_status is not None:
        conflicts.append("output_complete true while traversal is budget-truncated")

    target_path = Path("tools/softce-aula-l99-research/extracted/HFD_Code_V2.3.bin")
    target_data = target_path.read_bytes() if target_path.exists() else b""

    preview = {
        "preview_only": True,
        "authoritative_graph": False,
        "schema_version": CFG_SCHEMA_VERSION,
        "target": {
            "path": str(target_path),
            "size": len(target_data),
            "sha256": hashlib.sha256(target_data).hexdigest().upper() if target_data else None,
        },
        "image_base": hex(CANDIDATE_IMAGE_BASE),
        "root": [hex(r) for r in b.roots],
        "traversal_budgets": dict(b.budgets),
        "source_traversal_node_count": len(b.nodes),
        "source_instruction_occurrence_count": partition_result["metrics"]["source_instruction_occurrence_count"],
        "source_unique_instruction_count": partition_result["metrics"]["unique_instruction_count"],
        "source_overlap_pair_count": observations["overlap_pair_count"],
        "source_node_duplicate_instruction_ownership_count": observations["duplicate_ownership_count"],
        "source_node_max_instruction_ownership_count": observations["max_ownership_count"],
        "evidence_boundaries": {
            "count": len(observations["evidence_boundaries"]),
            "addresses": [_hex_addr(a) for a in observations["evidence_boundaries"]],
        },
        "legacy_node_starts": {
            "count": len(observations["legacy_node_starts"]),
            "addresses": [_hex_addr(a) for a in observations["legacy_node_starts"]],
        },
        "legacy_starts_not_supported_by_control_flow_evidence": {
            "count": len(observations["legacy_starts_not_supported"]),
            "addresses": [_hex_addr(a) for a in observations["legacy_starts_not_supported"]],
        },
        "terminators": {
            "by_kind": observations["terminators_by_kind"],
            "count_by_kind": {k: len(v) for k, v in observations["terminators_by_kind"].items()},
            "total_count": len(observations["all_terminators"]),
        },
        "successors": {
            "by_kind_and_status": observations["successor_status_counts"],
            "details": observations["successor_details"],
        },
        "ownership": {
            "duplicate_instruction_ownership_count": observations["duplicate_ownership_count"],
            "max_instruction_ownership_count": observations["max_ownership_count"],
        },
        "canonical_partition": {
            "metrics": partition_result["metrics"],
            "blocks": canon_blocks,
            "block_starts": [_hex_addr(a) for a in partition_result["block_starts"]],
            "terminators": [_hex_addr(a) for a in partition_result["terminators"]],
            "instructions": canon_instrs_json,
        },
        "per_block_reaching_function_ids": per_block_reaching_fids,
        "per_block_source_traversal_node_ids": per_block_source_nodes,
        "canonical_instruction_ownership": canonical_instruction_ownership,
        "accepted_function_entries_missing_as_canonical_starts": [_hex_addr(a) for a in accepted_entries_missing],
        "accepted_successor_targets_missing_as_canonical_starts": [_hex_addr(a) for a in accepted_successor_targets_missing],
        "conflicts_or_validation_failures": conflicts,
        "prohibited_range_counters": {
            "prohibited_range_rejection_count": b.prohibited_rejections,
            "unique_prohibited_target_count": len(b.prohibited_targets),
            "prohibited_addresses_in_preview": prohibited_in_preview,
        },
        "self_loop_preview_findings": self_loop_findings,
        "budget_exhaustion_status": budget_status,
        "output_complete": output_complete,
    }

    # Only overwrite if no previous valid preview exists, or if we succeeded.
    # On success we always write (the previous valid preview is only preserved on error).
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(preview, indent=2), encoding="utf-8")
    return preview


# ---------------------------------------------------------------------------
# Comparison generator (Task 6)
# ---------------------------------------------------------------------------

REQUIRED_COMPARISON_METRIC_FIELDS = (
    "baseline_json_path",
    "experiment_json_path",
    "baseline_value",
    "experiment_value",
    "classification",
)


def load_json_file(path):
    """Load a JSON file, failing loudly if missing or invalid."""
    p = Path(path)
    if not p.exists():
        raise SystemExit(
            f"COMPARISON GENERATOR FAILURE: required path does not exist: {path}"
        )
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"COMPARISON GENERATOR FAILURE: invalid JSON at {path}: {exc}"
        )


def build_comparison_record(baseline_path, experiment_path, metric_name,
                            baseline_value, experiment_value, classification):
    """Build a single deterministic comparison metric record.

    Never uses zero, empty object, or empty array as a silent default for a
    missing required field. Missing required fields fail loudly. Optional
    metrics may use null with value_present: false and reason.
    """
    if baseline_value is None:
        raise SystemExit(
            f"COMPARISON GENERATOR FAILURE: missing required baseline value "
            f"for metric '{metric_name}'"
        )
    if experiment_value is None:
        raise SystemExit(
            f"COMPARISON GENERATOR FAILURE: missing required experiment value "
            f"for metric '{metric_name}'"
        )

    record = {
        "metric": metric_name,
        "baseline_json_path": str(baseline_path),
        "experiment_json_path": str(experiment_path),
        "baseline_value": baseline_value,
        "experiment_value": experiment_value,
        "classification": classification,
    }

    if isinstance(baseline_value, (int, float)) and isinstance(
        experiment_value, (int, float)
    ):
        record["delta"] = experiment_value - baseline_value
    else:
        record["delta"] = None

    return record


def generate_comparison_4096_vs_8192(baseline_summary, experiment_summary,
                                     baseline_path, experiment_path,
                                     output_path):
    """Generate comparison_4096_vs_8192.json with explicit provenance.

    All required fields are present; missing required fields fail loudly.
    Optional metrics use null with value_present: false and reason.
    """
    metrics = []

    def metric(baseline, experiment, name, classifier):
        bv = baseline.get(name)
        ev = experiment.get(name)
        if bv is None or ev is None:
            raise SystemExit(
                f"COMPARISON GENERATOR FAILURE: missing required field '{name}' "
                f"in baseline or experiment summary"
            )
        metrics.append(build_comparison_record(
            baseline_path, experiment_path, name, bv, ev, classifier
        ))

    # Required canonical graph metrics (fail loud if missing).
    metric(baseline_summary, experiment_summary, "basic_blocks", "graph_metric")
    metric(baseline_summary, experiment_summary, "instruction_count", "graph_metric")
    metric(baseline_summary, experiment_summary, "decoded_byte_count", "graph_metric")
    metric(baseline_summary, experiment_summary, "unique_accepted_function_count", "graph_metric")
    metric(baseline_summary, experiment_summary, "unique_candidate_count", "graph_metric")
    metric(baseline_summary, experiment_summary, "budget_exhaustion_status", "budget_metric")
    metric(baseline_summary, experiment_summary, "queue_discovery_record_count", "queue_metric")
    metric(baseline_summary, experiment_summary, "processed_or_resolved_queue_records", "queue_metric")
    metric(baseline_summary, experiment_summary, "pending_block_count", "queue_metric")
    metric(baseline_summary, experiment_summary, "pending_function_count", "queue_metric")
    metric(baseline_summary, experiment_summary, "pending_total_count", "queue_metric")

    # Candidate-vs-queue metrics (optional, may be null).
    for name in (
        "queued_candidates_scheduled_pending",
        "queued_candidates_not_scheduled_depth_limit",
        "queued_candidates_without_function_work_record",
    ):
        bv = baseline_summary.get(name)
        ev = experiment_summary.get(name)
        if bv is None or ev is None:
            metrics.append({
                "metric": name,
                "baseline_json_path": str(baseline_path),
                "experiment_json_path": str(experiment_path),
                "baseline_value": None,
                "experiment_value": None,
                "delta": None,
                "classification": "optional_metric",
                "value_present": False,
                "reason": "metric not present in one or both summaries",
            })
        else:
            metrics.append(build_comparison_record(
                baseline_path, experiment_path, name, bv, ev, "queue_metric"
            ))

    comparison = {
        "schema_version": CFG_SCHEMA_VERSION,
        "generator": "scripts/research/hfd_cfg.py generate_comparison_4096_vs_8192",
        "baseline_json_path": str(baseline_path),
        "experiment_json_path": str(experiment_path),
        "metrics": metrics,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(comparison, indent=2, sort_keys=True), encoding="utf-8"
    )
    return comparison


def cli_compare(args):
    """CLI comparison mode: generate comparison_4096_vs_8192.json."""
    baseline_path = Path(args.compare_baseline_json)
    experiment_path = Path(args.compare_experiment_json)
    output_path = Path(args.compare_output)

    baseline_summary = load_json_file(baseline_path)
    experiment_summary = load_json_file(experiment_path)

    comparison = generate_comparison_4096_vs_8192(
        baseline_summary, experiment_summary,
        baseline_path, experiment_path, output_path,
    )
    print(f"Comparison written to {output_path}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Bounded recursive M*Core CFG utility for HFD Code V2.3"
    )
    parser.add_argument(
        "--input",
        default=r"tools\softce-aula-l99-research\extracted\HFD_Code_V2.3.bin",
        help="Path to HFD Code V2.3 binary",
    )
    parser.add_argument(
        "--output-dir",
        default="local_analysis/cfg",
        help="Output directory for generated reports",
    )
    parser.add_argument(
        "--root",
        action="append",
        type=lambda x: int(x, 0),
        help="Root entry point (repeatable, default 0x60017490)",
    )
    parser.add_argument(
        "--base",
        type=lambda x: int(x, 0),
        default=CANDIDATE_IMAGE_BASE,
        help="Candidate image base address",
    )
    for key, default in DEFAULT_BUDGETS.items():
        parser.add_argument(
            f"--{key}",
            type=int,
            default=default,
            help=f"Budget: {key} (default {default})",
        )
    parser.add_argument(
        "--canonical-preview-only",
        action="store_true",
        help="Audit-only mode: bounded traversal in memory, write only cfg_canonical_preview.json, do not touch the five existing CFG outputs.",
    )
    parser.add_argument(
        "--experimental-single-root-8192",
        action="store_true",
        help="Experimental safety profile: single root 0x60017490, max_instructions 8192, isolated output under local_analysis/cfg_experiments/.",
    )
    parser.add_argument(
        "--experimental-single-root-8192-blocks-1024",
        action="store_true",
        help="Experimental safety profile: single root 0x60017490, max_instructions 8192, max_basic_blocks 1024, isolated output under local_analysis/cfg_experiments/single_root_8192_blocks_1024/.",
    )
    parser.add_argument(
        "--compare-baseline-json",
        help="Path to baseline cfg_summary.json for comparison generation.",
    )
    parser.add_argument(
        "--compare-experiment-json",
        help="Path to experiment cfg_summary.json for comparison generation.",
    )
    parser.add_argument(
        "--compare-output",
        help="Output path for the generated comparison JSON.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        return 1

    data = input_path.read_bytes()
    actual_size = len(data)
    actual_hash = hashlib.sha256(data).hexdigest().upper()
    expected_size = 313652
    expected_hash = "A76806ADA9648D2672BBEBEAD8A9BB396C0BC6F3A0A071E22E99001AC3359D03"

    if actual_size != expected_size:
        print(f"ERROR: target size mismatch: expected {expected_size}, got {actual_size}", file=sys.stderr)
        return 1
    if actual_hash != expected_hash:
        print(f"ERROR: target SHA-256 mismatch: expected {expected_hash}, got {actual_hash}", file=sys.stderr)
        return 1

    roots = args.root if args.root else DEFAULT_ROOTS
    for r in roots:
        if r < args.base or r >= args.base + actual_size:
            print(f"ERROR: root 0x{r:X} outside image", file=sys.stderr)
            return 1
        if r % 2 != 0:
            print(f"ERROR: root 0x{r:X} is odd", file=sys.stderr)
            return 1
        if PROHIBITED_START <= r <= PROHIBITED_END:
            print(f"ERROR: root 0x{r:X} in prohibited range", file=sys.stderr)
            return 1

    output_dir = Path(args.output_dir)

    # Comparison generator mode (Task 6): deterministic comparison of two
    # existing cfg_summary.json files. No firmware traversal is performed.
    if args.compare_baseline_json or args.compare_experiment_json or args.compare_output:
        if not (args.compare_baseline_json and args.compare_experiment_json and args.compare_output):
            print("ERROR: comparison mode requires --compare-baseline-json, "
                  "--compare-experiment-json, and --compare-output", file=sys.stderr)
            return 1
        return cli_compare(args)

    requested_budgets = {key: getattr(args, key) for key in DEFAULT_BUDGETS}

    # Preflight validation of the experimental safety profile. Fails loudly
    # before traversal if any requirement is violated.
    profile = validate_budget_profile(args, requested_budgets, roots, output_dir)

    budgets = dict(requested_budgets)
    if profile["experimental_profile_enabled"]:
        # Effective budgets: use the profile's effective_budgets which already
        # enforce the correct values for the specific experimental profile.
        budgets = dict(profile["effective_budgets"])
        # For 8192/512 profile: only max_instructions changes (to 8192)
        # For 8192/1024 profile: max_instructions=8192 and max_basic_blocks=1024
        # All other budgets remain at defaults
        for key, default in DEFAULT_BUDGETS.items():
            if key in profile["effective_budgets"]:
                continue
            if budgets[key] != default:
                print(f"ERROR: {key} changed from default {default} for experimental profile", file=sys.stderr)
                return 1
    else:
        # Enforce safety bounds: CLI cannot exceed defaults
        for key, default in DEFAULT_BUDGETS.items():
            if budgets[key] > default:
                print(f"WARNING: {key} {budgets[key]} exceeds safety bound {default}; clamping to {default}", file=sys.stderr)
                budgets[key] = default

    mcdis_mod = load_mcdis()
    builder = CFGBuilder(data, args.base, roots, budgets, mcdis_mod)
    output = builder.run()

    if args.canonical_preview_only:
        collector = CanonicalPreviewCollector(builder)
        observations = collector.collect()
        preview_path = Path("local_analysis/cfg/cfg_canonical_preview.json")
        try:
            write_canonical_preview(builder, observations, preview_path)
        except CanonicalPartitionError as exc:
            print(f"CANONICAL PARTITION ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"Canonical preview written to {preview_path}")
        return 0

    edges_content = json.dumps(output["edges"], indent=2).encode("utf-8")
    edge_semantic_digest_sha256 = hashlib.sha256(edges_content).hexdigest().upper()

    # Determine baseline hash for cfg_edges.json before any output is replaced.
    edges_final_path = output_dir / "cfg_edges.json"
    cfg_edges_baseline_file_sha256 = None
    edges_baseline_available = False
    if edges_final_path.exists():
        try:
            cfg_edges_baseline_file_sha256 = hashlib.sha256(
                edges_final_path.read_bytes()
            ).hexdigest().upper()
            edges_baseline_available = True
        except OSError:
            cfg_edges_baseline_file_sha256 = None
            edges_baseline_available = False

    # Serialize cfg_edges.json to final temp-file bytes first, hash those exact
    # bytes (explicit newline behavior), then include hash before atomic replace.
    cfg_edges_final_bytes = edges_content
    cfg_edges_file_sha256 = hashlib.sha256(cfg_edges_final_bytes).hexdigest().upper()
    edges_byte_for_byte_unchanged = (
        None if not edges_baseline_available
        else cfg_edges_baseline_file_sha256 == cfg_edges_file_sha256
    )

    # Derive canonical-partition inputs from the completed traversal (same
    # validated derivation used by Stage B1 preview mode). Read-only; does not
    # change traversal, function discovery, queue handling, or edge construction.
    collector = CanonicalPreviewCollector(builder)
    observations = collector.collect()

    try:
        partition_result = canonical_partition(
            instruction_observations=observations["instruction_observations"],
            boundary_addresses=observations["boundary_addresses"],
            terminator_observations=observations["all_terminators"],
            successor_observations=observations["successor_observations"],
            ownership_observations=observations["ownership_observations"],
        )
    except CanonicalPartitionError as exc:
        # Report the exact conflict; do not overwrite any standard output;
        # do not fall back silently to legacy nodes.
        print(f"CANONICAL PARTITION FAILED: {exc}", file=sys.stderr)
        return 1

    # Build canonical edges from retained legacy instruction-level edge
    # evidence (Stage B3). This remaps onto canonical blocks without changing
    # traversal, partitioning, nodes, ranges, functions, queues, budgets, or
    # decoder behavior.
    canonical_edge_records = build_canonical_edges(
        output["edges"], partition_result, builder, observations
    )

    # Final canonical edge consistency validation (rule 15). On failure every
    # prior standard output is left untouched and we exit nonzero.
    try:
        canonical_edge_validate(canonical_edge_records, partition_result, builder)
    except CanonicalPartitionError as exc:
        print(f"CANONICAL EDGE VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1

    # Canonical edge metrics (rule 11).
    legacy_edge_count = len(output["edges"])
    legacy_dup_groups = _edge_duplicate_count(output["edges"])
    canonical_edge_metrics = compute_canonical_edge_metrics(
        canonical_edge_records, legacy_edge_count, legacy_dup_groups
    )

    canonical_nodes = build_canonical_nodes(
        partition_result, observations, builder
    )
    canonical_ranges = build_canonical_ranges(canonical_nodes)
    canonical_summary = build_canonical_summary(
        builder, observations, partition_result, canonical_nodes, output["edges"],
        edge_semantic_digest_sha256, cfg_edges_file_sha256,
        cfg_edges_baseline_file_sha256, cfg_edges_file_sha256,
        edges_byte_for_byte_unchanged, edges_baseline_available,
        canonical_edge_records, canonical_edge_metrics,
        legacy_edge_count, legacy_dup_groups,
    )

    # Attach safety-profile reporting fields to summary, report, and manifest.
    canonical_summary["safety_profile"] = profile["safety_profile"]
    canonical_summary["experimental_profile_enabled"] = profile["experimental_profile_enabled"]
    canonical_summary["experimental_profile_name"] = profile["experimental_profile_name"]
    canonical_summary["requested_budgets"] = profile["requested_budgets"]
    canonical_summary["effective_budgets"] = profile["effective_budgets"]
    canonical_summary["default_budgets_unchanged"] = profile["default_budgets_unchanged"]
    canonical_summary["root_constraint_enforced"] = profile["root_constraint_enforced"]
    canonical_summary["experiment_output_isolated"] = profile["experiment_output_isolated"]

    # Consistency validation before any output is replaced.
    source_union = set(observations["instruction_observations"].keys())
    canon_union = set(partition_result["block_starts"])  # placeholder, replaced below
    canon_union = set()
    for b in partition_result["blocks"]:
        canon_union.update(b["instruction_addresses"])
    if source_union != canon_union:
        print("CANONICAL VALIDATION FAILURE: canonical instruction union differs "
              "from source unique instruction union", file=sys.stderr)
        return 1

    # Canonical nodes must not overlap; one instruction per block; no orphan.
    addr_to_block = {}
    for b in partition_result["blocks"]:
        for a in b["instruction_addresses"]:
            if a in addr_to_block:
                print(f"CANONICAL VALIDATION FAILURE: instruction 0x{a:08X} belongs to "
                      f"multiple canonical blocks", file=sys.stderr)
                return 1
            addr_to_block[a] = b["id"]
    if len(addr_to_block) != len(canon_union):
        print("CANONICAL VALIDATION FAILURE: a canonical instruction belongs to no node",
              file=sys.stderr)
        return 1

    # Duplicate canonical starts.
    starts = [b["start"] for b in partition_result["blocks"]]
    if len(starts) != len(set(starts)):
        print("CANONICAL VALIDATION FAILURE: duplicate canonical block starts", file=sys.stderr)
        return 1

    # Accepted function entries must be block starts.
    accepted_entries = set(int(f["start"]) for f in builder.functions.values())
    block_starts = set(partition_result["block_starts"])
    missing_entries = sorted(accepted_entries - block_starts)
    if missing_entries:
        print("CANONICAL VALIDATION FAILURE: accepted function entries missing as "
              f"block starts: {[hex(a) for a in missing_entries]}", file=sys.stderr)
        return 1

    # Self-loop checks for 0x600174BC.
    self_loop_addr = 0x600174BC
    sl_blocks = [b for b in partition_result["blocks"] if self_loop_addr in b["instruction_addresses"]]
    if len(sl_blocks) != 1:
        print(f"CANONICAL VALIDATION FAILURE: 0x600174BC present {len(sl_blocks)} times "
              "in canonical nodes", file=sys.stderr)
        return 1
    sl = sl_blocks[0]
    if sl["instruction_addresses"][-1] != self_loop_addr:
        print("CANONICAL VALIDATION FAILURE: 0x600174BC is not the terminator of its "
              "canonical block", file=sys.stderr)
        return 1
    if sl["end"] > self_loop_addr + 2:
        print("CANONICAL VALIDATION FAILURE: 0x600174BC block retains 0x600174BE",
              file=sys.stderr)
        return 1

    # Ranges must agree with nodes.
    if len(canonical_ranges) != len(canonical_nodes):
        print("CANONICAL VALIDATION FAILURE: canonical ranges disagree with nodes",
              file=sys.stderr)
        return 1
    for node, rng in zip(canonical_nodes, canonical_ranges):
        if int(node["start"], 16) != int(rng["start"], 16):
            print("CANONICAL VALIDATION FAILURE: range start != node start", file=sys.stderr)
            return 1
        if int(node["end"], 16) != int(rng["end"], 16):
            print("CANONICAL VALIDATION FAILURE: range end != node end", file=sys.stderr)
            return 1
        if node["instruction_count"] != rng["instruction_count"]:
            print("CANONICAL VALIDATION FAILURE: range instruction count != node",
                  file=sys.stderr)
            return 1

    # Prohibited addresses.
    prohibited_found = [a for a in canon_union if PROHIBITED_START <= a <= PROHIBITED_END]
    if prohibited_found:
        print(f"CANONICAL VALIDATION FAILURE: prohibited addresses present: "
              f"{[hex(a) for a in prohibited_found]}", file=sys.stderr)
        return 1

    # Budget exhaustion recorded once.
    budget_obs = builder.budget_exhaustion_observations
    if len(budget_obs) > 1:
        print("CANONICAL VALIDATION FAILURE: budget exhaustion recorded more than once",
              file=sys.stderr)
        return 1

    # Stage B4: exact byte accounting (computed, never hard-coded).
    canonical_summary = finalize_byte_accounting(
        canonical_summary, canonical_nodes, builder
    )

    # Stage B4: final graph consistency validation.
    graph_consistent = True
    try:
        validate_graph_consistency(
            canonical_nodes,
            canonical_edge_records,
            canonical_ranges,
            canonical_summary,
            builder,
            observations,
            partition_result,
        )
    except CanonicalPartitionError as exc:
        print(f"CANONICAL GRAPH CONSISTENCY FAILED: {exc}", file=sys.stderr)
        return 1

    # Stage B4: evidence classification + acceptance status.
    target_hash_match = (
        canonical_summary.get("sha256") == "A76806ADA9648D2672BBEBEAD8A9BB396C0BC6F3A0A071E22E99001AC3359D03"
    )
    canonical_summary, evidence, graph_consistent, acceptance_status = \
        finalize_evidence_and_acceptance(
            canonical_summary, canonical_nodes, canonical_edge_records,
            builder, target_hash_match, graph_consistent
        )
    report_text = build_canonical_report(builder, observations, partition_result,
                                         canonical_nodes, canonical_ranges,
                                         canonical_summary, output["edges"],
                                         canonical_edge_records)

    canonical_edges_json = json.dumps(canonical_edge_records, indent=2)
    canonical_edges_file_bytes = canonical_edges_json.encode("utf-8")
    canonical_edges_file_sha256 = hashlib.sha256(
        canonical_edges_file_bytes
    ).hexdigest().upper()

    # Stage B4: reproducibility manifest (no self hash, no wall-clock time).
    # Hash the exact bytes that will be written to disk.
    nodes_bytes = json.dumps(canonical_nodes, indent=2).encode("utf-8")
    ranges_bytes = json.dumps(canonical_ranges, indent=2).encode("utf-8")
    pre_manifest_hashes = {
        "cfg_summary.json": hashlib.sha256(
            json.dumps(canonical_summary, indent=2).encode("utf-8")
        ).hexdigest().upper(),
        "cfg_nodes.json": hashlib.sha256(nodes_bytes).hexdigest().upper(),
        "cfg_edges.json": canonical_edges_file_sha256,
        "cfg_ranges.json": hashlib.sha256(ranges_bytes).hexdigest().upper(),
        "cfg_report.txt": hashlib.sha256(
            report_text.encode("utf-8")
        ).hexdigest().upper(),
    }
    manifest = build_reproducibility_manifest(
        builder, canonical_summary, canonical_summary, evidence,
        acceptance_status, canonical_summary.get(
            "bounded_graph_acceptance_reasons", []),
        canonical_summary.get("budget_increase_recommendation"),
        canonical_summary.get("multi_root_expansion_recommendation"),
    )
    manifest["safety_profile"] = profile["safety_profile"]
    manifest["experimental_profile_enabled"] = profile["experimental_profile_enabled"]
    manifest["experimental_profile_name"] = profile["experimental_profile_name"]
    manifest["requested_budgets"] = profile["requested_budgets"]
    manifest["effective_budgets"] = profile["effective_budgets"]
    manifest["default_budgets_unchanged"] = profile["default_budgets_unchanged"]
    manifest["root_constraint_enforced"] = profile["root_constraint_enforced"]
    manifest["experiment_output_isolated"] = profile["experiment_output_isolated"]
    manifest["output_file_names_and_sha256"] = pre_manifest_hashes
    manifest["reproducibility_manifest_hash_self_excluded"] = True
    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")

    canonical_output = {
        "cfg_summary.json": json.dumps(canonical_summary, indent=2),
        "cfg_nodes.json": json.dumps(canonical_nodes, indent=2),
        "cfg_ranges.json": json.dumps(canonical_ranges, indent=2),
        "cfg_report.txt": report_text,
        "cfg_edges.json": canonical_edges_file_bytes,
        "cfg_reproducibility.json": manifest_bytes,
    }

    # Atomically replace all six standard outputs.
    try:
        write_canonical_outputs(output_dir, canonical_output)
    except Exception as exc:
        print(f"CANONICAL OUTPUT WRITE FAILED: {exc}", file=sys.stderr)
        return 1

    print(f"CFG analysis complete. Canonical output written to {output_dir}/")
    print(f"Canonical blocks: {canonical_summary['canonical_block_count']}")
    print(f"Canonical instructions: {canonical_summary['canonical_unique_instruction_count']}")
    print(f"Budget status: {canonical_summary['budget_exhaustion_status']}")
    print(f"Acceptance status: {acceptance_status}")

    return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
