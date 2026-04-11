import unittest

from tools.sie_autoppt.planning.content_profiler import classify_density, profile_bullets
from tools.sie_autoppt.planning.layout_policy import resolve_layout_decision


class LayoutPolicyTests(unittest.TestCase):
    def test_profile_bullets_marks_compact_content(self):
        profile = profile_bullets(["Assess", "Design", "Launch"])

        self.assertEqual(profile.item_count, 3)
        self.assertEqual(profile.density, "compact")
        self.assertFalse(profile.has_long_item)

    def test_profile_bullets_marks_dense_content(self):
        profile = profile_bullets(
            [
                "This is a deliberately long content item that should push the density classification into the dense bucket.",
                "Another long item describing implementation nuances and rollout sequencing across teams.",
            ]
        )

        self.assertEqual(profile.density, "dense")
        self.assertTrue(profile.has_long_item)

    def test_classify_density_accepts_custom_thresholds(self):
        density = classify_density(70, 70, thresholds={"compact": 40, "balanced": 80, "dense": 120})

        self.assertEqual(density, "balanced")

    def test_layout_policy_reports_capacity_without_catalog(self):
        profile = profile_bullets(["A", "B", "C", "D"])
        decision = resolve_layout_decision(
            requested_pattern_id="process_flow",
            fallback_pattern_id="general_business",
            content_profile=profile,
            preferred_item_counts=(3, 5, 9),
            available_layout_variants=set(),
        )

        self.assertEqual(decision.pattern_id, "process_flow")
        self.assertIsNone(decision.layout_variant)
        self.assertEqual(decision.layout_hints["desired_capacity"], 5)
        self.assertEqual(decision.layout_hints["desired_layout_variant"], "")
        self.assertEqual(decision.max_items_per_page, 5)

    def test_layout_policy_preserves_manifest_variant_when_available(self):
        profile = profile_bullets(["A", "B", "C", "D"])
        decision = resolve_layout_decision(
            requested_pattern_id="process_flow",
            fallback_pattern_id="general_business",
            content_profile=profile,
            preferred_item_counts=(3, 5, 9),
            available_layout_variants={"process_flow_5"},
            pattern_variants={
                "process_flow": (
                    {"id": "process_flow_3", "capacity": 3},
                    {"id": "process_flow_5", "capacity": 5},
                )
            },
        )

        self.assertEqual(decision.layout_variant, "process_flow_5")

    def test_layout_policy_uses_template_variant_catalog_when_provided(self):
        profile = profile_bullets(["A", "B", "C", "D"])
        decision = resolve_layout_decision(
            requested_pattern_id="general_business",
            fallback_pattern_id="process_flow",
            content_profile=profile,
            preferred_item_counts=(3, 5, 9),
            available_layout_variants={"gb_manifest_5"},
            pattern_variants={
                "general_business": (
                    {"id": "gb_manifest_3", "capacity": 3},
                    {"id": "gb_manifest_5", "capacity": 5},
                )
            },
        )

        self.assertEqual(decision.layout_variant, "gb_manifest_5")
        self.assertEqual(decision.layout_hints["desired_layout_variant"], "gb_manifest_5")

    def test_template_variant_catalog_is_authoritative_when_present(self):
        profile = profile_bullets(["A", "B", "C", "D"])
        decision = resolve_layout_decision(
            requested_pattern_id="process_flow",
            fallback_pattern_id="general_business",
            content_profile=profile,
            preferred_item_counts=(3, 5, 9),
            available_layout_variants={"process_flow_5"},
            pattern_variants={"general_business": ({"id": "general_business_5", "capacity": 5},)},
        )

        self.assertIsNone(decision.layout_variant)
        self.assertEqual(decision.layout_hints["desired_capacity"], 5)
        self.assertEqual(decision.layout_hints["desired_layout_variant"], "")

    def test_layout_policy_reports_capacity_without_inventing_unknown_variant_ids(self):
        profile = profile_bullets(
            [
                "Dense item one with substantial wording for readability review.",
                "Dense item two with substantial wording for readability review.",
                "Dense item three with substantial wording for readability review.",
                "Dense item four with substantial wording for readability review.",
                "Dense item five with substantial wording for readability review.",
                "Dense item six with substantial wording for readability review.",
            ]
        )
        decision = resolve_layout_decision(
            requested_pattern_id="org_governance",
            fallback_pattern_id="general_business",
            content_profile=profile,
            preferred_item_counts=(3, 5, 9),
            available_layout_variants=set(),
        )

        self.assertIsNone(decision.layout_variant)
        self.assertEqual(decision.layout_hints["desired_capacity"], 9)
        self.assertEqual(decision.layout_hints["desired_layout_variant"], "")
        self.assertEqual(decision.max_items_per_page, 9)
