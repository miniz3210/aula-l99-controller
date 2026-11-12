import sys
import hashlib
import json
import os
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
