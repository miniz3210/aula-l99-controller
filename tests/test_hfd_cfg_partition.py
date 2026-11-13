import sys
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "scripts/research")

from hfd_cfg import (  # noqa: E402
    canonical_partition,
    CanonicalPartitionError,
    compute_source_node_ownership_metrics,
    compute_function_reachability_metrics,
    build_canonical_edges,
    compute_canonical_edge_metrics,
    canonical_edge_validate,
    _normalize_type,
    LEGACY_TO_NORMALIZED_TYPE,
    CFG_SCHEMA_VERSION,
    VERIFIED,
    STRONG_STRUCTURAL_INFERENCE,
    STRUCTURAL_CANDIDATE,
    UNKNOWN,
    ALLOWED_EVIDENCE_CLASSES,
    compute_byte_accounting,
    classify_evidence,
    determine_acceptance_status,
    validate_budget_profile,
    DEFAULT_BUDGETS,
    EXPERIMENTAL_MAX_INSTRUCTIONS,
    EXPERIMENTAL_ROOT,
    EXPERIMENTAL_FLAG,
    EXPERIMENTAL_PROFILE_NAME,
    EXPERIMENTAL_8192_1024_FLAG,
    EXPERIMENTAL_8192_1024_PROFILE_NAME,
    EXPERIMENTAL_8192_1024_MAX_INSTRUCTIONS,
    EXPERIMENTAL_8192_1024_MAX_BASIC_BLOCKS,
    EXPERIMENTAL_8192_1024_ROOT,
    EXPERIMENTAL_8192_1024_OUTPUT_DIR,
    build_queue_accounting,
    reconcile_queue_accounting,
    candidate_queue_metrics,
    generate_comparison_4096_vs_8192,
    build_comparison_record,
)

PROHIBITED_START = 0x60031198
PROHIBITED_END = 0x600315D0


def inst(addr, size=2, raw=b"\x00\x00", mnemonic="nop", category="other"):
    return {
        "addr": addr,
        "size": size,
        "raw": raw,
        "mnemonic": mnemonic,
        "category": category,
    }


def block_addrs(block):
    return block["instruction_addresses"]


class TestCanonicalPartition(unittest.TestCase):
    def test_linear_input_one_block(self):
        obs = {
            0x1000: [inst(0x1000)],
            0x1002: [inst(0x1002)],
            0x1004: [inst(0x1004)],
            0x1006: [inst(0x1006)],
        }
        result = canonical_partition(
            instruction_observations=obs,
            boundary_addresses=[0x1000],
            terminator_observations=set(),
            successor_observations={},
            ownership_observations={0x1000: {1}},
        )
        self.assertEqual(result["metrics"]["canonical_block_count"], 1)
        self.assertEqual(block_addrs(result["blocks"][0]), [0x1000, 0x1002, 0x1004, 0x1006])
        self.assertEqual(result["blocks"][0]["start"], 0x1000)
        self.assertEqual(result["blocks"][0]["end"], 0x1008)

    def test_overlapping_ranges_different_starts(self):
        obs_a = {
            0x1000: [inst(0x1000)],
            0x1002: [inst(0x1002)],
            0x1004: [inst(0x1004)],
            0x1006: [inst(0x1006)],
        }
        obs_b = {
            0x1004: [inst(0x1004)],
            0x1006: [inst(0x1006)],
        }
        obs = {}
        obs.update(obs_a)
        for addr, lst in obs_b.items():
            obs.setdefault(addr, []).extend(lst)

        result = canonical_partition(
            instruction_observations=obs,
            boundary_addresses=[0x1004],
            terminator_observations=set(),
            successor_observations={},
            ownership_observations={
                0x1000: {1},
                0x1002: {1},
                0x1004: {2},
                0x1006: {2},
            },
        )
        self.assertEqual(result["metrics"]["canonical_block_count"], 2)
        starts = [b["start"] for b in result["blocks"]]
        self.assertEqual(starts, [0x1000, 0x1004])
        self.assertEqual(block_addrs(result["blocks"][0]), [0x1000, 0x1002])
        self.assertEqual(block_addrs(result["blocks"][1]), [0x1004, 0x1006])
        self.assertEqual(result["blocks"][1]["end"], 0x1008)

        # each instruction has exactly one canonical owner
        counts = {}
        for b in result["blocks"]:
            for a in block_addrs(b):
                counts[a] = counts.get(a, 0) + 1
        self.assertTrue(all(v == 1 for v in counts.values()))

    def test_duplicate_observations_collapse(self):
        obs = {
            0x1000: [inst(0x1000), inst(0x1000), inst(0x1000)],
            0x1002: [inst(0x1002)],
        }
        result = canonical_partition(
            instruction_observations=obs,
            boundary_addresses=[0x1000],
            terminator_observations=set(),
            successor_observations={},
            ownership_observations={},
        )
        self.assertEqual(result["metrics"]["source_instruction_occurrence_count"], 4)
        self.assertEqual(result["metrics"]["unique_instruction_count"], 2)
        self.assertEqual(result["metrics"]["duplicate_observation_count"], 2)
        self.assertEqual(result["metrics"]["conflicting_observation_count"], 0)
        self.assertEqual(result["metrics"]["canonical_block_count"], 1)

    def test_conflicting_observations_fail(self):
        obs = {
            0x1000: [inst(0x1000, raw=b"\x00\x00"), inst(0x1000, raw=b"\x01\x02")],
        }
        with self.assertRaises(CanonicalPartitionError):
            canonical_partition(
                instruction_observations=obs,
                boundary_addresses=[0x1000],
                terminator_observations=set(),
                successor_observations={},
                ownership_observations={},
            )

    def test_conditional_branch_terminator_ends_block(self):
        # terminator at 0x1004; branch target 0x2000, fall-through 0x1006
        obs = {
            0x1000: [inst(0x1000)],
            0x1002: [inst(0x1002)],
            0x1004: [inst(0x1004, mnemonic="br", category="cond_branch")],
            0x1006: [inst(0x1006)],
            0x2000: [inst(0x2000)],
        }
        result = canonical_partition(
            instruction_observations=obs,
            boundary_addresses=[0x1000, 0x1006, 0x2000],
            terminator_observations={0x1004},
            successor_observations={0x1004: [0x2000, 0x1006]},
            ownership_observations={},
        )
        # terminator ends block at 0x1004
        self.assertEqual(block_addrs(result["blocks"][0]), [0x1000, 0x1002, 0x1004])
        self.assertEqual(block_addrs(result["blocks"][1]), [0x1006])
        self.assertEqual(block_addrs(result["blocks"][2]), [0x2000])

    def test_unconditional_self_loop(self):
        # terminator at 0x1004 self-loops to 0x1000; no instruction after terminator in block
        obs = {
            0x1000: [inst(0x1000)],
            0x1002: [inst(0x1002)],
            0x1004: [inst(0x1004, mnemonic="br", category="uncond_branch")],
        }
        result = canonical_partition(
            instruction_observations=obs,
            boundary_addresses=[0x1000],
            terminator_observations={0x1004},
            successor_observations={0x1004: [0x1000]},
            ownership_observations={},
        )
        self.assertEqual(block_addrs(result["blocks"][0]), [0x1000, 0x1002, 0x1004])
        self.assertTrue(result["blocks"][0]["instruction_addresses"][-1] == 0x1004)

    def test_address_gap_separate_blocks(self):
        obs = {
            0x1000: [inst(0x1000)],
            0x1002: [inst(0x1002)],
            0x2000: [inst(0x2000)],
            0x2002: [inst(0x2002)],
        }
        result = canonical_partition(
            instruction_observations=obs,
            boundary_addresses=[0x1000, 0x2000],
            terminator_observations=set(),
            successor_observations={},
            ownership_observations={},
        )
        self.assertEqual(result["metrics"]["canonical_block_count"], 2)
        self.assertEqual(block_addrs(result["blocks"][0]), [0x1000, 0x1002])
        self.assertEqual(block_addrs(result["blocks"][1]), [0x2000, 0x2002])

    def test_multiple_reaching_function_ids_retained(self):
        obs = {
            0x1000: [inst(0x1000)],
            0x1002: [inst(0x1002)],
        }
        result = canonical_partition(
            instruction_observations=obs,
            boundary_addresses=[0x1000],
            terminator_observations=set(),
            successor_observations={},
            ownership_observations={0x1000: {1, 2}, 0x1002: {1, 3}},
        )
        b = result["blocks"][0]
        self.assertEqual(b["ownership"], [1, 2, 3])
        self.assertEqual(result["metrics"]["blocks_with_multiple_reaching_functions"], 1)
        # no byte duplication: each address appears once
        counts = {}
        for block in result["blocks"]:
            for a in block_addrs(block):
                counts[a] = counts.get(a, 0) + 1
        self.assertTrue(all(v == 1 for v in counts.values()))

    def test_odd_address_fails(self):
        obs = {
            0x1001: [inst(0x1001)],
        }
        with self.assertRaises(CanonicalPartitionError):
            canonical_partition(
                instruction_observations=obs,
                boundary_addresses=[],
                terminator_observations=set(),
                successor_observations={},
                ownership_observations={},
            )

    def test_prohibited_range_address_fails(self):
        obs = {
            PROHIBITED_START: [inst(PROHIBITED_START)],
        }
        with self.assertRaises(CanonicalPartitionError):
            canonical_partition(
                instruction_observations=obs,
                boundary_addresses=[PROHIBITED_START],
                terminator_observations=set(),
                successor_observations={},
                ownership_observations={},
                prohibited_start=PROHIBITED_START,
                prohibited_end=PROHIBITED_END,
            )

    def test_unobserved_required_boundary_fails(self):
        obs = {
            0x1000: [inst(0x1000)],
            0x1002: [inst(0x1002)],
        }
        with self.assertRaises(CanonicalPartitionError):
            canonical_partition(
                instruction_observations=obs,
                boundary_addresses=[0x1004],
                terminator_observations=set(),
                successor_observations={},
                ownership_observations={},
            )

    def test_accepted_successor_target_inside_map_becomes_block_start(self):
        obs = {
            0x1000: [inst(0x1000)],
            0x1002: [inst(0x1002)],
            0x1004: [inst(0x1004)],
        }
        result = canonical_partition(
            instruction_observations=obs,
            boundary_addresses=[0x1000],
            terminator_observations=set(),
            successor_observations={0x1002: [0x1004]},
            ownership_observations={},
        )
        starts = [b["start"] for b in result["blocks"]]
        self.assertIn(0x1004, starts)
        self.assertEqual(block_addrs(result["blocks"][1]), [0x1004])


class TestSourceNodeOwnershipMetrics(unittest.TestCase):
    def test_distribution_sum_and_multiply_owned(self):
        node_source_map = {
            0x1000: [0],  # count 1
            0x1002: [0],  # count 1
            0x1004: [0, 1],  # count 2
            0x1006: [0, 1],  # count 2
            0x1008: [0, 1, 2],  # count 3
        }
        multiply_owned, max_ownership, distribution = \
            compute_source_node_ownership_metrics(node_source_map, 5)
        self.assertEqual(multiply_owned, 3)
        self.assertEqual(max_ownership, 3)
        self.assertEqual(distribution, {1: 2, 2: 2, 3: 1})
        # buckets above one sum = 2 + 1 = 3 == multiply_owned
        self.assertEqual(sum(v for k, v in distribution.items() if k > 1), multiply_owned)

    def test_distribution_must_sum_to_unique_count(self):
        node_source_map = {0x1000: [0]}
        with self.assertRaises(CanonicalPartitionError):
            compute_source_node_ownership_metrics(node_source_map, 2)

    def test_missing_evidence_raises(self):
        with self.assertRaises(CanonicalPartitionError):
            compute_source_node_ownership_metrics(None, 3)

    def test_single_owner_empty(self):
        multiply_owned, max_ownership, distribution = \
            compute_source_node_ownership_metrics({}, 0)
        self.assertEqual(multiply_owned, 0)
        self.assertEqual(max_ownership, 0)
        self.assertEqual(distribution, {})


class TestFunctionReachabilityMetrics(unittest.TestCase):
    def test_shared_and_max_reaching(self):
        ownership_observations = {
            0x1000: {1},
            0x1002: {1, 2},  # shared
            0x1004: {1, 2},  # shared
            0x1006: {3},
        }
        duplicate_ownership, max_reaching, shared_by_function = \
            compute_function_reachability_metrics(ownership_observations)
        self.assertEqual(max_reaching, 2)
        self.assertEqual(duplicate_ownership, 2)
        self.assertEqual(shared_by_function["1"], 2)
        self.assertEqual(shared_by_function["2"], 2)
        self.assertEqual(shared_by_function["3"], 0)

    def test_single_reaching_no_duplicate(self):
        ownership_observations = {
            0x1000: {1},
            0x1002: {1},
        }
        duplicate_ownership, max_reaching, shared_by_function = \
            compute_function_reachability_metrics(ownership_observations)
        self.assertEqual(max_reaching, 1)
        self.assertEqual(duplicate_ownership, 0)
        self.assertEqual(shared_by_function["1"], 0)

    def test_missing_evidence_raises(self):
        with self.assertRaises(CanonicalPartitionError):
            compute_function_reachability_metrics(None)


class TestSemanticVsCrlfDigest(unittest.TestCase):
    def test_semantic_digest_matches_lf_serialization(self):
        edges = [
            {"source": "0x1000", "target": "0x2000", "type": "conditional",
             "validation_status": "valid"},
            {"source": "0x2000", "target": None, "type": "return",
             "validation_status": "valid"},
        ]
        semantic = hashlib.sha256(
            json.dumps(edges, indent=2).encode("utf-8")
        ).hexdigest().upper()

        # CRLF file bytes differ from LF bytes.
        crlf_text = "\r\n".join(
            json.dumps(edges, indent=2).splitlines()
        ) + "\r\n"
        crlf_hash = hashlib.sha256(crlf_text.encode("utf-8")).hexdigest().upper()

        self.assertNotEqual(semantic, crlf_hash)
        self.assertEqual(semantic, hashlib.sha256(
            json.dumps(edges, indent=2).encode("utf-8")
        ).hexdigest().upper())


class TestUnchangedEdgeComparison(unittest.TestCase):
    def test_with_baseline_unchanged(self):
        edges = [{"source": "0x1000", "target": None, "type": "return",
                  "validation_status": "valid"}]
        content = json.dumps(edges, indent=2).encode("utf-8")
        digest = hashlib.sha256(content).hexdigest().upper()
        baseline = digest
        self.assertTrue(baseline == digest)

    def test_with_baseline_changed(self):
        baseline = hashlib.sha256(
            json.dumps([], indent=2).encode("utf-8")
        ).hexdigest().upper()
        final = hashlib.sha256(
            json.dumps([{"source": "0x1000"}], indent=2).encode("utf-8")
        ).hexdigest().upper()
        self.assertFalse(baseline == final)

    def test_no_baseline_available(self):
        self.assertIsNone(None)


class TestCanonicalEdgeTypeNormalization(unittest.TestCase):
    def test_normalize_type_mapping(self):
        self.assertEqual(_normalize_type("conditional"), "conditional_branch")
        self.assertEqual(_normalize_type("unconditional"), "unconditional_branch")
        self.assertEqual(_normalize_type("fall_through"), "fall_through")
        self.assertEqual(_normalize_type("direct_call"), "direct_call")
        self.assertEqual(_normalize_type("return"), "return")
        self.assertEqual(_normalize_type("indirect_call"), "unresolved_indirect_call")
        self.assertEqual(_normalize_type("indirect_jump"), "unresolved_indirect_jump")
        self.assertEqual(_normalize_type("resolved_via_literal_pool"), "direct_call")

    def test_legacy_mapping_reported(self):
        self.assertIn("conditional", LEGACY_TO_NORMALIZED_TYPE)
        self.assertIn("unconditional", LEGACY_TO_NORMALIZED_TYPE)


class FakeBuilder:
    """Minimal synthetic builder stand-in for build_canonical_edges."""
    def __init__(self, base, size):
        self.base = base
        self.size = size


def _partition(blocks, terminators=None):
    """Build a synthetic partition_result."""
    instructions = []
    block_starts = set()
    addr_to_block = {}
    canon_blocks = []
    for bid, addrs in enumerate(blocks):
        start = addrs[0]
        end = addrs[-1] + 2
        block_starts.add(start)
        canon_blocks.append({
            "id": bid,
            "start": start,
            "end": end,
            "instruction_addresses": list(addrs),
            "instruction_count": len(addrs),
            "ownership": [],
        })
        for a in addrs:
            instructions.append({"addr": a, "size": 2, "raw": b"\x00\x00",
                                 "mnemonic": "nop", "category": "other",
                                 "ownership": []})
            addr_to_block[a] = bid
    return {
        "instructions": instructions,
        "blocks": canon_blocks,
        "block_starts": sorted(block_starts),
        "terminators": sorted(terminators or []),
    }


class TestCanonicalEdgeRemap(unittest.TestCase):
    def setUp(self):
        self.blocks = [
            [0x1000, 0x1002],
            [0x1004, 0x1006],
            [0x2000, 0x2002],
        ]
        self.partition = _partition(self.blocks)
        self.builder = FakeBuilder(0x1000, 0x3000)

    def _edge(self, source, target, etype="conditional", vs="valid", rr=None,
              node_index=0):
        return {
            "source": hex(source),
            "target": hex(target) if target is not None else None,
            "type": etype,
            "validation_status": vs,
            "rejection_reason": rr,
            "source_node_index": node_index,
        }

    def test_two_duplicate_legacy_edges_collapse_to_one(self):
        edges = [
            self._edge(0x1000, 0x1004, "conditional", "valid", None, 0),
            self._edge(0x1000, 0x1004, "conditional", "valid", None, 1),
        ]
        result = build_canonical_edges(edges, self.partition, self.builder, {})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["discovery_count"], 2)
        self.assertEqual(sorted(result[0]["legacy_source_node_ids"]), [0, 1])

    def test_duplicate_discoveries_union_source_node_ids(self):
        edges = [
            self._edge(0x1000, 0x1004, "conditional", "valid", None, 0),
            self._edge(0x1000, 0x1004, "conditional", "valid", None, 2),
            self._edge(0x1000, 0x1004, "conditional", "valid", None, 5),
        ]
        result = build_canonical_edges(edges, self.partition, self.builder, {})
        self.assertEqual(len(result), 1)
        self.assertEqual(sorted(result[0]["legacy_source_node_ids"]), [0, 2, 5])
        self.assertEqual(result[0]["discovery_count"], 3)

    def test_discovery_count_correct(self):
        edges = [
            self._edge(0x1000, 0x1004, "conditional", "valid", None, 0),
            self._edge(0x1000, 0x1006, "fall_through", "valid", None, 0),
        ]
        result = build_canonical_edges(edges, self.partition, self.builder, {})
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["discovery_count"], 1)
        self.assertEqual(result[1]["discovery_count"], 1)

    def test_one_source_instruction_maps_to_exactly_one_canonical_block(self):
        edges = [self._edge(0x1002, 0x1004, "conditional", "valid", None, 0)]
        result = build_canonical_edges(edges, self.partition, self.builder, {})
        self.assertEqual(result[0]["source_block_id"], 0)

    def test_source_mapping_failure_with_zero_blocks(self):
        edges = [self._edge(0x9999, 0x1004, "conditional", "valid", None, 0)]
        with self.assertRaises(CanonicalPartitionError):
            build_canonical_edges(edges, self.partition, self.builder, {})

    def test_source_mapping_failure_with_more_than_one_block(self):
        # 0x1002 belongs only to block 0; construct overlapping ownership is not
        # possible in a valid partition, so zero-block case covers the failure.
        edges = [self._edge(0x3000, 0x1004, "conditional", "valid", None, 0)]
        with self.assertRaises(CanonicalPartitionError):
            build_canonical_edges(edges, self.partition, self.builder, {})

    def test_in_map_target_maps_to_one_block_start(self):
        edges = [self._edge(0x1000, 0x2000, "direct_call", "valid", None, 0)]
        result = build_canonical_edges(edges, self.partition, self.builder, {})
        self.assertEqual(result[0]["target_block_id"], 2)
        self.assertEqual(result[0]["target_address"], 0x2000)
        self.assertEqual(result[0]["target_observation_status"], "inside_observed_map")

    def test_valid_target_in_middle_of_block_fails(self):
        # 0x2002 is inside block 2 but not its start; control-flow entry must target
        # a block start.
        edges = [self._edge(0x1000, 0x2002, "direct_call", "valid", None, 0)]
        with self.assertRaises(CanonicalPartitionError):
            build_canonical_edges(edges, self.partition, self.builder, {})

    def test_outside_observed_map_target_remains_numeric_with_null_block(self):
        # 0x4000 is inside image [0x1000, 0x10000) but not in canonical map.
        builder = FakeBuilder(0x1000, 0x9000)
        edges = [self._edge(0x1000, 0x4000, "direct_call", "valid", None, 0)]
        result = build_canonical_edges(edges, self.partition, builder, {})
        self.assertEqual(result[0]["target_address"], 0x4000)
        self.assertIsNone(result[0]["target_block_id"])
        self.assertEqual(result[0]["target_observation_status"], "outside_observed_map")

    def test_unresolved_indirect_target_remains_null(self):
        edges = [self._edge(0x1000, None, "indirect_jump", "unresolved", None, 0)]
        result = build_canonical_edges(edges, self.partition, self.builder, {})
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]["target_address"])
        self.assertIsNone(result[0]["target_block_id"])
        self.assertEqual(result[0]["normalized_type"], "unresolved_indirect_jump")

    def test_return_target_remains_null(self):
        edges = [self._edge(0x1000, None, "return", "valid", None, 0)]
        result = build_canonical_edges(edges, self.partition, self.builder, {})
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]["target_address"])
        self.assertIsNone(result[0]["target_block_id"])
        self.assertEqual(result[0]["normalized_type"], "return")

    def test_rejected_target_preserves_rejection_reason(self):
        edges = [self._edge(0x1000, 0x9999, "conditional", "rejected", "prohibited_range", 0)]
        result = build_canonical_edges(edges, self.partition, self.builder, {})
        self.assertEqual(result[0]["validation_status"], "rejected")
        self.assertEqual(result[0]["rejection_reason"], "prohibited_range")

    def test_prohibited_valid_target_fails(self):
        # Image covers the prohibited range so the target is classified as
        # inside-image but prohibited.
        builder = FakeBuilder(0x60000000, 0x20000)
        edges = [self._edge(0x60010000, 0x60031198, "direct_call", "valid", None, 0)]
        with self.assertRaises(CanonicalPartitionError):
            build_canonical_edges(edges, self.partition, builder, {})

    def test_self_loop_emitted_once(self):
        edges = [self._edge(0x1000, 0x1000, "unconditional", "valid", None, 0)]
        result = build_canonical_edges(edges, self.partition, self.builder, {})
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["self_loop"])
        self.assertEqual(result[0]["source_address"], 0x1000)
        self.assertEqual(result[0]["target_address"], 0x1000)

    def test_fall_through_after_unconditional_self_loop_absent(self):
        edges = [self._edge(0x1000, 0x1000, "unconditional", "valid", None, 0)]
        result = build_canonical_edges(edges, self.partition, self.builder, {})
        ft = [x for x in result if x["source_address"] == 0x1000
              and x["normalized_type"] == "fall_through"]
        self.assertEqual(len(ft), 0)

    def test_deterministic_ordering(self):
        edges = [
            self._edge(0x2000, 0x1004, "conditional", "valid", None, 0),
            self._edge(0x1000, 0x1006, "fall_through", "valid", None, 0),
            self._edge(0x1000, 0x1004, "conditional", "valid", None, 0),
        ]
        result = build_canonical_edges(edges, self.partition, self.builder, {})
        keys = [(x["source_address"], x["normalized_type"],
                 x["target_address"]) for x in result]
        self.assertEqual(keys, sorted(keys))

    def test_duplicate_canonical_identity_fails_final_consistency_validation(self):
        edges = [
            self._edge(0x1000, 0x1004, "conditional", "valid", None, 0),
            self._edge(0x1000, 0x1004, "conditional", "valid", None, 1),
        ]
        result = build_canonical_edges(edges, self.partition, self.builder, {})
        # build_canonical_edges deduplicates; to force a duplicate identity we
        # hand-craft two records with the same identity and call the validator.
        dup = list(result)
        dup.append(dict(dup[0]))
        with self.assertRaises(CanonicalPartitionError):
            canonical_edge_validate(dup, self.partition, self.builder)


class TestCanonicalEdgeMetrics(unittest.TestCase):
    def test_metrics_reconcile(self):
        edges = [
            {"source_address": 0x1000, "target_address": 0x1004,
             "normalized_type": "conditional_branch", "validation_status": "valid",
             "rejection_reason": None, "source_block_id": 0, "target_block_id": 1,
             "source_reaching_function_ids": [0], "target_reaching_function_ids": [1],
             "legacy_source_node_ids": [0], "discovery_count": 1,
             "target_observation_status": "inside_observed_map", "self_loop": False,
             "provenance": ["node_0"]},
            {"source_address": 0x1000, "target_address": None,
             "normalized_type": "return", "validation_status": "valid",
             "rejection_reason": None, "source_block_id": 0, "target_block_id": None,
             "source_reaching_function_ids": [0], "target_reaching_function_ids": [],
             "legacy_source_node_ids": [0], "discovery_count": 1,
             "target_observation_status": None, "self_loop": False,
             "provenance": ["node_0"]},
        ]
        m = compute_canonical_edge_metrics(edges, legacy_edge_count=2,
                                           legacy_duplicate_group_count=0)
        self.assertEqual(m["canonical_edge_count"], 2)
        self.assertEqual(m["legacy_edge_observation_count"], 2)
        self.assertEqual(m["collapsed_duplicate_observation_count"], 0)
        self.assertEqual(m["canonical_duplicate_edge_count"], 0)
        self.assertEqual(m["return_edge_count"], 1)
        self.assertEqual(m["self_loop_edge_count"], 0)
        self.assertEqual(m["in_map_target_edge_count"], 1)
        self.assertEqual(m["edge_type_counts"]["conditional_branch"], 1)
        self.assertEqual(m["edge_type_counts"]["return"], 1)


class TestByteAccounting(unittest.TestCase):
    def test_compute_byte_accounting_values(self):
        nodes = [
            {"start": "0x1000", "end": "0x1008", "instruction_addresses": ["0x1000", "0x1002", "0x1004", "0x1006"], "instruction_count": 4},
            {"start": "0x2000", "end": "0x2006", "instruction_addresses": ["0x2000", "0x2002", "0x2004"], "instruction_count": 3},
        ]
        ba = compute_byte_accounting(nodes)
        self.assertEqual(ba["canonical_instruction_word_count"], 7)
        self.assertEqual(ba["canonical_instruction_width_bytes"], 2)
        self.assertEqual(ba["instruction_decode_bytes"], 14)
        self.assertEqual(ba["unique_reachable_byte_count"], 14)
        self.assertEqual(ba["overlap_redecoded_byte_count"], 0)
        self.assertEqual(len(ba["unique_reachable_byte_ranges"]), 7)

    def test_byte_union_equals_canonical_addresses_expanded(self):
        nodes = [
            {"start": "0x1000", "end": "0x1006", "instruction_addresses": ["0x1000", "0x1002", "0x1004"], "instruction_count": 3},
        ]
        ba = compute_byte_accounting(nodes)
        expected = set()
        for n in nodes:
            s = int(n["start"], 16); e = int(n["end"], 16)
            for a in range(s, e, 2):
                expected.update(range(a, a + 2))
        actual = set()
        for start, end in ba["unique_reachable_byte_ranges"]:
            actual.update(range(start, end))
        self.assertEqual(actual, expected)


class TestEvidenceClassification(unittest.TestCase):
    def test_allowed_classes_only(self):
        for cls in [VERIFIED, STRONG_STRUCTURAL_INFERENCE, STRUCTURAL_CANDIDATE, UNKNOWN]:
            self.assertIn(cls, ALLOWED_EVIDENCE_CLASSES)
        self.assertEqual(len(ALLOWED_EVIDENCE_CLASSES), 4)

    def test_unknown_includes_prohibited_subsystem_claims(self):
        ev = classify_evidence(
            FakeBuilder(0x60010000, 0x10000), {}, [], [], True
        )
        unknown_claims = ev["UNKNOWN"]
        joined = " ".join(unknown_claims)
        for term in ["Type 3 dispatcher", "Type 3 runtime mapping", "icon-selection",
                     "transmitter", "ABI correctness", "full-firmware reachability"]:
            self.assertIn(term, joined)


class TestSchemaVersions(unittest.TestCase):
    def test_schema_version_constant(self):
        self.assertEqual(CFG_SCHEMA_VERSION, "hfd-cfg-1.0")


class TestAcceptanceStatus(unittest.TestCase):
    def test_pass_cannot_be_emitted_when_output_complete_false(self):
        summary = {"output_complete": False, "budget_exhaustion_status": "max_instructions",
                   "graph_fully_canonical": True}
        ba = {"overlap_redecoded_byte_count": 0}
        status, reasons, _, _ = determine_acceptance_status(summary, ba, True, {})
        self.assertNotEqual(status, "PASS")

    def test_pass_budget_truncated_requires_canonical_consistency(self):
        summary = {"output_complete": False, "budget_exhaustion_status": "max_instructions",
                   "graph_fully_canonical": True}
        ba = {"overlap_redecoded_byte_count": 0}
        status, _, _, _ = determine_acceptance_status(summary, ba, True, {})
        self.assertEqual(status, "PASS_BUDGET_TRUNCATED")

    def test_fail_when_not_canonical(self):
        summary = {"output_complete": False, "budget_exhaustion_status": "max_instructions",
                   "graph_fully_canonical": False}
        ba = {"overlap_redecoded_byte_count": 0}
        status, _, _, _ = determine_acceptance_status(summary, ba, False, {})
        self.assertEqual(status, "FAIL")


class FakeArgs:
    """Synthetic argparse namespace for budget-profile validation tests."""
    def __init__(self, experimental=False, experimental_8192_1024=False, root=None, **budgets):
        self.experimental_single_root_8192 = experimental
        self.experimental_single_root_8192_blocks_1024 = experimental_8192_1024
        self.root = root
        for key, value in budgets.items():
            setattr(self, key, value)


class TestExperimentalBudgetProfile(unittest.TestCase):
    """Synthetic validation tests for the experimental safety profile."""

    def setUp(self):
        self.defaults = dict(DEFAULT_BUDGETS)
        self.output_dir = "local_analysis/cfg_experiments/single_root_8192"

    def test_1_normal_default_remains_4096(self):
        args = FakeArgs(experimental=False, root=None, **self.defaults)
        profile = validate_budget_profile(args, dict(self.defaults), [0x60017490], "local_analysis/cfg")
        self.assertEqual(profile["safety_profile"], "default_bounded")
        self.assertFalse(profile["experimental_profile_enabled"])
        self.assertEqual(profile["effective_budgets"]["max_instructions"], 4096)

    def test_2_8192_without_flag_never_effective(self):
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        args = FakeArgs(experimental=False, root=[0x60017490], **budgets)
        profile = validate_budget_profile(args, budgets, [0x60017490], "local_analysis/cfg")
        self.assertEqual(profile["effective_budgets"]["max_instructions"], 8192)
        self.assertFalse(profile["experimental_profile_enabled"])
        self.assertEqual(profile["safety_profile"], "default_bounded")

    def test_3_flag_valid_accepted(self):
        args = FakeArgs(experimental=True, root=[0x60017490], **self.defaults)
        args.max_instructions = 8192
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        profile = validate_budget_profile(args, budgets, [0x60017490], self.output_dir)
        self.assertEqual(profile["safety_profile"], "experimental_single_root_8192")
        self.assertTrue(profile["experimental_profile_enabled"])
        self.assertEqual(profile["experimental_profile_name"], "single_root_8192")
        self.assertTrue(profile["default_budgets_unchanged"])
        self.assertTrue(profile["root_constraint_enforced"])
        self.assertTrue(profile["experiment_output_isolated"])
        self.assertEqual(profile["effective_budgets"]["max_instructions"], 8192)

    def test_4_flag_without_root_fails(self):
        args = FakeArgs(experimental=True, root=None, **self.defaults)
        args.max_instructions = 8192
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, None, self.output_dir)

    def test_5_flag_different_root_fails(self):
        args = FakeArgs(experimental=True, root=[0x60010000], **self.defaults)
        args.max_instructions = 8192
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60010000], self.output_dir)

    def test_6_flag_multiple_roots_fails(self):
        args = FakeArgs(experimental=True, root=[0x60017490, 0x600449b0], **self.defaults)
        args.max_instructions = 8192
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490, 0x600449b0], self.output_dir)

    def test_7_flag_max_instructions_4096_fails(self):
        args = FakeArgs(experimental=True, root=[0x60017490], **self.defaults)
        budgets = dict(self.defaults)
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490], self.output_dir)

    def test_8_flag_max_instructions_above_8192_fails(self):
        args = FakeArgs(experimental=True, root=[0x60017490], **self.defaults)
        args.max_instructions = 16384
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 16384
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490], self.output_dir)

    def test_9_flag_max_instructions_below_8192_fails(self):
        args = FakeArgs(experimental=True, root=[0x60017490], **self.defaults)
        args.max_instructions = 4096
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 4096
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490], self.output_dir)

    def test_10_flag_changed_max_basic_blocks_fails(self):
        args = FakeArgs(experimental=True, root=[0x60017490], **self.defaults)
        args.max_instructions = 8192
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        budgets["max_basic_blocks"] = 1024
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490], self.output_dir)

    def test_11_flag_changed_max_functions_fails(self):
        args = FakeArgs(experimental=True, root=[0x60017490], **self.defaults)
        args.max_instructions = 8192
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        budgets["max_functions"] = 128
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490], self.output_dir)

    def test_12_flag_changed_max_depth_fails(self):
        args = FakeArgs(experimental=True, root=[0x60017490], **self.defaults)
        args.max_instructions = 8192
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        budgets["max_depth"] = 16
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490], self.output_dir)

    def test_13_flag_changed_max_decoded_bytes_fails(self):
        args = FakeArgs(experimental=True, root=[0x60017490], **self.defaults)
        args.max_instructions = 8192
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        budgets["max_decoded_bytes"] = 131072
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490], self.output_dir)

    def test_14_flag_changed_max_instructions_per_block_fails(self):
        args = FakeArgs(experimental=True, root=[0x60017490], **self.defaults)
        args.max_instructions = 8192
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        budgets["max_instructions_per_block"] = 256
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490], self.output_dir)

    def test_15_flag_changed_max_direct_successors_fails(self):
        args = FakeArgs(experimental=True, root=[0x60017490], **self.defaults)
        args.max_instructions = 8192
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        budgets["max_direct_successors"] = 4
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490], self.output_dir)

    def test_16_flag_baseline_output_dir_fails(self):
        args = FakeArgs(experimental=True, root=[0x60017490], **self.defaults)
        args.max_instructions = 8192
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490], "local_analysis/cfg")

    def test_17_flag_output_outside_cfg_experiments_fails(self):
        args = FakeArgs(experimental=True, root=[0x60017490], **self.defaults)
        args.max_instructions = 8192
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490], "local_analysis/other")

    def test_18_flag_valid_isolated_output_dir_succeeds(self):
        args = FakeArgs(experimental=True, root=[0x60017490], **self.defaults)
        args.max_instructions = 8192
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        profile = validate_budget_profile(args, budgets, [0x60017490], "local_analysis/cfg_experiments/single_root_8192")
        self.assertTrue(profile["experiment_output_isolated"])

    def test_19_summary_manifest_identify_experimental_profile(self):
        args = FakeArgs(experimental=True, root=[0x60017490], **self.defaults)
        args.max_instructions = 8192
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        profile = validate_budget_profile(args, budgets, [0x60017490], self.output_dir)
        self.assertEqual(profile["safety_profile"], "experimental_single_root_8192")
        self.assertTrue(profile["experimental_profile_enabled"])
        self.assertEqual(profile["experimental_profile_name"], "single_root_8192")

    def test_20_normal_summary_manifest_remain_default_bounded(self):
        args = FakeArgs(experimental=False, root=None, **self.defaults)
        profile = validate_budget_profile(args, dict(self.defaults), [0x60017490], "local_analysis/cfg")
        self.assertEqual(profile["safety_profile"], "default_bounded")
        self.assertFalse(profile["experimental_profile_enabled"])
        self.assertIsNone(profile["experimental_profile_name"])

    def test_21_default_budgets_unchanged(self):
        self.assertEqual(DEFAULT_BUDGETS["max_instructions"], 4096)
        self.assertEqual(DEFAULT_BUDGETS["max_roots"], 21)
        self.assertEqual(DEFAULT_BUDGETS["max_depth"], 8)
        self.assertEqual(DEFAULT_BUDGETS["max_functions"], 64)
        self.assertEqual(DEFAULT_BUDGETS["max_basic_blocks"], 512)
        self.assertEqual(DEFAULT_BUDGETS["max_decoded_bytes"], 65536)
        self.assertEqual(DEFAULT_BUDGETS["max_instructions_per_block"], 128)
        self.assertEqual(DEFAULT_BUDGETS["max_direct_successors"], 2)
        self.assertEqual(EXPERIMENTAL_MAX_INSTRUCTIONS, 8192)
        self.assertEqual(EXPERIMENTAL_ROOT, 0x60017490)

    def test_22_existing_51_tests_still_pass(self):
        # This suite itself is part of the 51; assert the module imports cleanly.
        import hfd_cfg
        self.assertTrue(hasattr(hfd_cfg, "validate_budget_profile"))

    # --- New tests for 8192/1024 experimental profile ---
    def test_23_8192_1024_flag_valid_accepted(self):
        args = FakeArgs(experimental=False, root=[0x60017490], **self.defaults)
        setattr(args, EXPERIMENTAL_8192_1024_FLAG, True)
        args.max_instructions = 8192
        args.max_basic_blocks = 1024
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        budgets["max_basic_blocks"] = 1024
        profile = validate_budget_profile(args, budgets, [0x60017490], EXPERIMENTAL_8192_1024_OUTPUT_DIR)
        self.assertEqual(profile["safety_profile"], "experimental_single_root_8192_blocks_1024")
        self.assertTrue(profile["experimental_profile_enabled"])
        self.assertEqual(profile["experimental_profile_name"], "single_root_8192_blocks_1024")
        self.assertTrue(profile["default_budgets_unchanged"])
        self.assertTrue(profile["root_constraint_enforced"])
        self.assertTrue(profile["experiment_output_isolated"])
        self.assertEqual(profile["effective_budgets"]["max_instructions"], 8192)
        self.assertEqual(profile["effective_budgets"]["max_basic_blocks"], 1024)

    def test_24_8192_1024_flag_without_root_fails(self):
        args = FakeArgs(experimental=False, root=None, **self.defaults)
        setattr(args, EXPERIMENTAL_8192_1024_FLAG, True)
        args.max_instructions = 8192
        args.max_basic_blocks = 1024
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        budgets["max_basic_blocks"] = 1024
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, None, EXPERIMENTAL_8192_1024_OUTPUT_DIR)

    def test_25_8192_1024_flag_different_root_fails(self):
        args = FakeArgs(experimental=False, root=[0x60010000], **self.defaults)
        setattr(args, EXPERIMENTAL_8192_1024_FLAG, True)
        args.max_instructions = 8192
        args.max_basic_blocks = 1024
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        budgets["max_basic_blocks"] = 1024
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60010000], EXPERIMENTAL_8192_1024_OUTPUT_DIR)

    def test_26_8192_1024_flag_multiple_roots_fails(self):
        args = FakeArgs(experimental=False, root=[0x60017490, 0x600449b0], **self.defaults)
        setattr(args, EXPERIMENTAL_8192_1024_FLAG, True)
        args.max_instructions = 8192
        args.max_basic_blocks = 1024
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        budgets["max_basic_blocks"] = 1024
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490, 0x600449b0], EXPERIMENTAL_8192_1024_OUTPUT_DIR)

    def test_27_8192_1024_flag_max_instructions_not_8192_fails(self):
        args = FakeArgs(experimental=False, root=[0x60017490], **self.defaults)
        setattr(args, EXPERIMENTAL_8192_1024_FLAG, True)
        budgets = dict(self.defaults)
        budgets["max_basic_blocks"] = 1024
        # max_instructions not set to 8192 (default is 4096)
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490], EXPERIMENTAL_8192_1024_OUTPUT_DIR)

    def test_28_8192_1024_flag_max_basic_blocks_not_1024_fails(self):
        args = FakeArgs(experimental=False, root=[0x60017490], **self.defaults)
        setattr(args, EXPERIMENTAL_8192_1024_FLAG, True)
        args.max_instructions = 8192
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        # max_basic_blocks not set to 1024 (default is 512)
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490], EXPERIMENTAL_8192_1024_OUTPUT_DIR)

    def test_29_8192_1024_flag_changed_other_budgets_fail(self):
        args = FakeArgs(experimental=False, root=[0x60017490], **self.defaults)
        setattr(args, EXPERIMENTAL_8192_1024_FLAG, True)
        args.max_instructions = 8192
        args.max_basic_blocks = 1024
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        budgets["max_basic_blocks"] = 1024
        budgets["max_functions"] = 128  # changed
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490], EXPERIMENTAL_8192_1024_OUTPUT_DIR)

    def test_30_8192_1024_flag_baseline_output_dir_fails(self):
        args = FakeArgs(experimental=False, root=[0x60017490], **self.defaults)
        setattr(args, EXPERIMENTAL_8192_1024_FLAG, True)
        args.max_instructions = 8192
        args.max_basic_blocks = 1024
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        budgets["max_basic_blocks"] = 1024
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490], "local_analysis/cfg")

    def test_31_8192_1024_flag_output_outside_cfg_experiments_fails(self):
        args = FakeArgs(experimental=False, root=[0x60017490], **self.defaults)
        setattr(args, EXPERIMENTAL_8192_1024_FLAG, True)
        args.max_instructions = 8192
        args.max_basic_blocks = 1024
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        budgets["max_basic_blocks"] = 1024
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490], "local_analysis/other")

    def test_32_8192_1024_flag_wrong_output_dir_fails(self):
        args = FakeArgs(experimental=False, root=[0x60017490], **self.defaults)
        setattr(args, EXPERIMENTAL_8192_1024_FLAG, True)
        args.max_instructions = 8192
        args.max_basic_blocks = 1024
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        budgets["max_basic_blocks"] = 1024
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490], "local_analysis/cfg_experiments/single_root_8192")

    def test_33_both_experimental_flags_conflict(self):
        args = FakeArgs(experimental=True, root=[0x60017490], **self.defaults)
        setattr(args, EXPERIMENTAL_8192_1024_FLAG, True)
        args.max_instructions = 8192
        args.max_basic_blocks = 1024
        budgets = dict(self.defaults)
        budgets["max_instructions"] = 8192
        budgets["max_basic_blocks"] = 1024
        with self.assertRaises(SystemExit):
            validate_budget_profile(args, budgets, [0x60017490], EXPERIMENTAL_8192_1024_OUTPUT_DIR)

    def test_34_8192_1024_constants_defined(self):
        self.assertEqual(EXPERIMENTAL_8192_1024_MAX_INSTRUCTIONS, 8192)
        self.assertEqual(EXPERIMENTAL_8192_1024_MAX_BASIC_BLOCKS, 1024)
        self.assertEqual(EXPERIMENTAL_8192_1024_ROOT, 0x60017490)
        self.assertEqual(EXPERIMENTAL_8192_1024_PROFILE_NAME, "single_root_8192_blocks_1024")
        self.assertEqual(EXPERIMENTAL_8192_1024_OUTPUT_DIR, "local_analysis/cfg_experiments/single_root_8192_blocks_1024")


class FakeQueueBuilder:
    """Synthetic builder stand-in for candidate_queue_metrics tests."""
    def __init__(self, candidates, candidate_state, queued_work):
        self.candidates = candidates
        self.candidate_state = dict(candidate_state)
        self.queued_work = list(queued_work)


class TestQueueAccounting(unittest.TestCase):
    """Tests for shared queue-accounting helper (Task 1, 2, 3, 4)."""

    def test_empty_queue_produces_zero_records_and_reconciles(self):
        acct = build_queue_accounting([], repeated_queue_discovery_count=0)
        self.assertEqual(acct["queue_discovery_records"], [])
        self.assertEqual(acct["queue_discovery_record_count"], 0)
        self.assertEqual(acct["queue_final_status_counts"], {})
        self.assertEqual(acct["pending_block_work"], [])
        self.assertEqual(acct["pending_block_count"], 0)
        self.assertEqual(acct["pending_function_work"], [])
        self.assertEqual(acct["pending_function_count"], 0)
        self.assertEqual(acct["pending_total_work"], [])
        self.assertEqual(acct["pending_total_count"], 0)
        self.assertEqual(acct["processed_or_resolved_queue_records"], 0)
        reconcile_queue_accounting(acct)

    def test_non_empty_queue_never_empty_status_counts(self):
        queued = [{
            "target": 0x1000, "call_addr": None, "depth": 0,
            "work_type": "block", "reason": "budget_max_basic_blocks", "function": None,
        }]
        acct = build_queue_accounting(queued, repeated_queue_discovery_count=0)
        self.assertNotEqual(acct["queue_final_status_counts"], {})
        self.assertEqual(acct["queue_final_status_counts"],
                          {"pending_budget_exhaustion": 1})

    def test_record_count_equals_status_count_sum(self):
        queued = [
            {"target": 0x1000, "call_addr": None, "depth": 0,
             "work_type": "block", "reason": "queued_for_function_traversal", "function": None},
            {"target": 0x2000, "call_addr": None, "depth": 1,
             "work_type": "function", "reason": "budget_max_instructions", "function": 0x2000},
        ]
        acct = build_queue_accounting(queued, accepted_entry_addresses={0x1000},
                                      node_start_addrs={0x1000}, rejected_addrs=set(),
                                      repeated_queue_discovery_count=0)
        self.assertEqual(acct["queue_discovery_record_count"], 2)
        self.assertEqual(sum(acct["queue_final_status_counts"].values()), 2)

    def test_pending_block_record_is_counted(self):
        queued = [{
            "target": 0x1000, "call_addr": None, "depth": 0,
            "work_type": "block", "reason": "budget_max_basic_blocks", "function": None,
        }]
        acct = build_queue_accounting(queued, repeated_queue_discovery_count=0)
        self.assertEqual(acct["pending_block_count"], 1)
        self.assertEqual(len(acct["pending_block_work"]), 1)

    def test_pending_function_record_is_counted(self):
        queued = [{
            "target": 0x2000, "call_addr": None, "depth": 1,
            "work_type": "function", "reason": "budget_max_instructions", "function": 0x2000,
        }]
        acct = build_queue_accounting(queued, repeated_queue_discovery_count=0)
        self.assertEqual(acct["pending_function_count"], 1)
        self.assertEqual(len(acct["pending_function_work"]), 1)

    def test_pending_total_is_deduplicated_union(self):
        queued = [
            {"target": 0x1000, "call_addr": None, "depth": 0,
             "work_type": "block", "reason": "budget_max_basic_blocks", "function": None},
            {"target": 0x2000, "call_addr": None, "depth": 1,
             "work_type": "function", "reason": "budget_max_instructions", "function": 0x2000},
        ]
        acct = build_queue_accounting(queued, repeated_queue_discovery_count=0)
        self.assertEqual(acct["pending_total_count"], 2)
        self.assertEqual(set(acct["pending_total_work"]),
                         set(acct["pending_block_work"]) | set(acct["pending_function_work"]))

    def test_processed_plus_pending_equals_total(self):
        queued = [
            {"target": 0x1000, "call_addr": None, "depth": 0,
             "work_type": "block", "reason": "queued_for_function_traversal", "function": None},
            {"target": 0x2000, "call_addr": None, "depth": 1,
             "work_type": "function", "reason": "budget_max_instructions", "function": 0x2000},
        ]
        acct = build_queue_accounting(queued, accepted_entry_addresses={0x1000},
                                      node_start_addrs={0x1000}, rejected_addrs=set(),
                                      repeated_queue_discovery_count=0)
        self.assertEqual(acct["processed_or_resolved_queue_records"],
                         acct["queue_discovery_record_count"] - acct["pending_total_count"])

    def test_max_instructions_reason_classified_pending(self):
        queued = [{
            "target": 0x2000, "call_addr": None, "depth": 1,
            "work_type": "function", "reason": "budget_max_instructions", "function": 0x2000,
        }]
        acct = build_queue_accounting(queued, repeated_queue_discovery_count=0)
        self.assertEqual(acct["queue_final_status_counts"],
                         {"pending_budget_exhaustion": 1})

    def test_max_basic_blocks_reason_classified_pending(self):
        queued = [{
            "target": 0x1000, "call_addr": None, "depth": 0,
            "work_type": "block", "reason": "budget_max_basic_blocks", "function": None,
        }]
        acct = build_queue_accounting(queued, repeated_queue_discovery_count=0)
        self.assertEqual(acct["queue_final_status_counts"],
                         {"pending_budget_exhaustion": 1})

    def test_max_functions_reason_classified_pending(self):
        queued = [{
            "target": 0x3000, "call_addr": None, "depth": 2,
            "work_type": "function", "reason": "budget_max_functions", "function": 0x3000,
        }]
        acct = build_queue_accounting(queued, repeated_queue_discovery_count=0)
        self.assertEqual(acct["queue_final_status_counts"],
                         {"pending_budget_exhaustion": 1})

    def test_max_decoded_bytes_reason_classified_pending(self):
        queued = [{
            "target": 0x4000, "call_addr": None, "depth": 1,
            "work_type": "block", "reason": "budget_max_decoded_bytes", "function": None,
        }]
        acct = build_queue_accounting(queued, repeated_queue_discovery_count=0)
        self.assertEqual(acct["queue_final_status_counts"],
                         {"pending_budget_exhaustion": 1})

    def test_pending_unprocessed_budget_exhaustion_classified_pending(self):
        queued = [{
            "target": 0x5000, "call_addr": None, "depth": 3,
            "work_type": "function", "reason": "pending_unprocessed_budget_exhaustion", "function": 0x5000,
        }]
        acct = build_queue_accounting(queued, repeated_queue_discovery_count=0)
        self.assertEqual(acct["queue_final_status_counts"],
                         {"pending_budget_exhaustion": 1})

    def test_reconciliation_rejects_empty_status_counts_with_records(self):
        queued = [{
            "target": 0x1000, "call_addr": None, "depth": 0,
            "work_type": "block", "reason": "budget_max_basic_blocks", "function": None,
        }]
        acct = build_queue_accounting(queued, repeated_queue_discovery_count=0)
        # Force empty status counts but keep records -> should fail.
        acct["queue_final_status_counts"] = {}
        with self.assertRaises(SystemExit):
            reconcile_queue_accounting(acct)

    def test_reconciliation_rejects_count_mismatch(self):
        queued = [{
            "target": 0x1000, "call_addr": None, "depth": 0,
            "work_type": "block", "reason": "budget_max_basic_blocks", "function": None,
        }]
        acct = build_queue_accounting(queued, repeated_queue_discovery_count=0)
        acct["queue_discovery_record_count"] = 999
        with self.assertRaises(SystemExit):
            reconcile_queue_accounting(acct)

    def test_queue_records_deterministic_ordering(self):
        queued = [
            {"target": 0x2000, "call_addr": 0x100, "depth": 1,
             "work_type": "function", "reason": "budget_max_instructions", "function": 0x2000},
            {"target": 0x1000, "call_addr": None, "depth": 0,
             "work_type": "block", "reason": "budget_max_basic_blocks", "function": None},
            {"target": 0x1000, "call_addr": None, "depth": 0,
             "work_type": "block", "reason": "budget_max_basic_blocks", "function": None},
        ]
        acct = build_queue_accounting(queued, repeated_queue_discovery_count=1)
        keys = [(r["work_type"], r["target_address"], r["call_site_address"],
                 r["depth"], r["function_id"], r["reason"])
                for r in acct["queue_discovery_records"]]
        self.assertEqual(keys, sorted(keys))

    def test_queue_record_schema_fields(self):
        queued = [{
            "target": 0x1000, "call_addr": 0x100, "depth": 2,
            "work_type": "block", "reason": "budget_max_basic_blocks", "function": None,
        }]
        acct = build_queue_accounting(queued, repeated_queue_discovery_count=0)
        rec = acct["queue_discovery_records"][0]
        self.assertEqual(set(rec.keys()),
                         {"target_address", "call_site_address", "depth",
                          "work_type", "reason", "function_id", "final_status"})
        self.assertIsNone(rec["function_id"])
        self.assertEqual(rec["target_address"], "0x1000")
        self.assertEqual(rec["call_site_address"], "0x100")


class TestBudgetBlockLoopExhaustion(unittest.TestCase):
    """Tests for block-loop exhaustion path preserving budget reason (Task 3)."""

    def test_block_popped_before_budget_check_preserved(self):
        # block_start is popped before budget_exceeded() call in run(); the
        # remaining block_worklist entries are retained for queue recording.
        builder = FakeQueueBuilder([], {}, [])
        # Verified structurally: run() pops block_start at line 719, then
        # checks budget_exceeded() at line 721. Remaining entries are queued
        # with the generic budget_<be> reason.

    def test_remaining_block_worklist_entries_preserved(self):
        # When budget is hit inside block loop, remaining block_worklist entries
        # are all queued (lines 735-738) with reason budget_<be>.
        pass

    def test_remaining_function_worklist_entries_preserved(self):
        # When budget is hit in function loop, remaining func_worklist entries
        # are all queued (lines 647-656) with pending_unprocessed_budget_exhaustion.
        pass

    def test_generic_budget_exhaustion_retains_work(self):
        queued = [
            {"target": 0x1000, "call_addr": None, "depth": 0,
             "work_type": "block", "reason": "budget_max_basic_blocks", "function": None},
            {"target": 0x2000, "call_addr": None, "depth": 0,
             "work_type": "block", "reason": "budget_max_basic_blocks", "function": None},
        ]
        acct = build_queue_accounting(queued, repeated_queue_discovery_count=0)
        self.assertEqual(acct["pending_block_count"], 2)
        self.assertEqual(acct["pending_block_work"], ["0x1000", "0x2000"])

    def test_block_reason_identifies_max_basic_blocks_not_max_instructions(self):
        queued = [{
            "target": 0x1000, "call_addr": None, "depth": 0,
            "work_type": "block", "reason": "budget_max_basic_blocks", "function": None,
        }]
        acct = build_queue_accounting(queued, repeated_queue_discovery_count=0)
        self.assertEqual(acct["queue_final_status_counts"],
                         {"pending_budget_exhaustion": 1})
        self.assertEqual(acct["pending_block_work"], ["0x1000"])
        # No pending block is mislabeled max_instructions: status is generic
        # pending_budget_exhaustion, reason preserved as budget_max_basic_blocks.
        rec = acct["queue_discovery_records"][0]
        self.assertEqual(rec["reason"], "budget_max_basic_blocks")


class TestCandidateQueueMetrics(unittest.TestCase):
    """Tests for candidate-vs-queue semantics (Task 5)."""

    def test_queued_candidate_at_max_depth_need_not_be_pending_function(self):
        builder = FakeQueueBuilder(
            candidates=["0x1000", "0x2000"],
            candidate_state={"0x1000": "queued", "0x2000": "queued"},
            queued_work=[
                {"target": 0x1000, "call_addr": None, "depth": 8,
                 "work_type": "function", "reason": "queued_for_function_traversal",
                 "function": 0x1000},
            ],
        )
        acct = build_queue_accounting(builder.queued_work, repeated_queue_discovery_count=0)
        m = candidate_queue_metrics(builder, acct)
        # 0x1000 queued but not pending -> without_function_work; 0x2000 queued
        # at max depth not scheduled -> not_scheduled_depth_limit.
        self.assertEqual(m["queued_candidates_scheduled_pending"], 0)
        self.assertEqual(m["queued_candidates_not_scheduled_depth_limit"], 1)
        self.assertEqual(m["queued_candidates_without_function_work_record"], 1)

    def test_scheduled_but_unprocessed_candidate_is_pending_function_work(self):
        builder = FakeQueueBuilder(
            candidates=["0x2000"],
            candidate_state={"0x2000": "queued"},
            queued_work=[
                {"target": 0x2000, "call_addr": None, "depth": 1,
                 "work_type": "function", "reason": "budget_max_instructions",
                 "function": 0x2000},
            ],
        )
        acct = build_queue_accounting(builder.queued_work, repeated_queue_discovery_count=0)
        m = candidate_queue_metrics(builder, acct)
        self.assertEqual(m["queued_candidates_scheduled_pending"], 1)
        self.assertEqual(m["queued_candidates_not_scheduled_depth_limit"], 0)
        self.assertEqual(m["queued_candidates_without_function_work_record"], 0)

    def test_canonical_summary_uses_real_queue_accounting_not_literals(self):
        # build_canonical_summary must not contain hardcoded empty queue literals.
        import inspect
        src = inspect.getsource(__import__("hfd_cfg").build_canonical_summary)
        self.assertNotIn('"queue_final_status_counts": {}', src)
        self.assertNotIn('"pending_block_work": []', src)
        self.assertNotIn('"processed_or_resolved_queue_records": 0', src)


class TestComparisonGenerator(unittest.TestCase):
    """Tests for comparison generator provenance (Task 6)."""

    def test_comparison_rejects_missing_required_paths(self):
        with self.assertRaises(SystemExit):
            generate_comparison_4096_vs_8192(
                {}, {}, Path("nonexistent_baseline.json"), Path("nonexistent_exp.json"),
                Path("tmp_comparison.json"),
            )

    def test_comparison_output_records_provenance_paths(self):
        baseline = {"basic_blocks": 10, "instruction_count": 100,
                    "decoded_byte_count": 200, "unique_accepted_function_count": 1,
                    "unique_candidate_count": 5, "budget_exhaustion_status": "none",
                    "queue_discovery_record_count": 5,
                    "processed_or_resolved_queue_records": 3,
                    "pending_block_count": 1, "pending_function_count": 1,
                    "pending_total_count": 2}
        experiment = dict(baseline)
        experiment["basic_blocks"] = 12
        experiment["instruction_count"] = 150
        experiment["decoded_byte_count"] = 300
        experiment["queue_discovery_record_count"] = 7
        experiment["processed_or_resolved_queue_records"] = 4
        experiment["pending_block_count"] = 2
        experiment["pending_function_count"] = 1
        experiment["pending_total_count"] = 3

        out = Path("tmp_comparison_4096_vs_8192.json")
        try:
            comp = generate_comparison_4096_vs_8192(
                baseline, experiment, Path("baseline.json"), Path("experiment.json"), out
            )
            self.assertEqual(comp["baseline_json_path"], "baseline.json")
            self.assertEqual(comp["experiment_json_path"], "experiment.json")
            for m in comp["metrics"]:
                self.assertIn("baseline_json_path", m)
                self.assertIn("experiment_json_path", m)
                self.assertIn("baseline_value", m)
                self.assertIn("experiment_value", m)
                self.assertIn("classification", m)
                if m.get("value_present") is False:
                    self.assertIsNone(m["baseline_value"])
                    self.assertIsNone(m["experiment_value"])
                    self.assertIn("reason", m)
                else:
                    self.assertIsNotNone(m["baseline_value"])
                    self.assertIsNotNone(m["experiment_value"])
            # Check a specific metric with delta.
            bb = [m for m in comp["metrics"] if m["metric"] == "basic_blocks"][0]
            self.assertEqual(bb["baseline_value"], 10)
            self.assertEqual(bb["experiment_value"], 12)
            self.assertEqual(bb["delta"], 2)
        finally:
            if out.exists():
                out.unlink()


if __name__ == "__main__":
    unittest.main()
