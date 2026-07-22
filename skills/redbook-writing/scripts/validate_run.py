#!/usr/bin/env python3
"""Validate a redbook-writing research/content run.

Copy-only validation uses the standard library. Visual artifact validation is
fail-closed and requires Pillow so that an image is fully decoded rather than
trusted from a file header.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sqlite3
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urlsplit, urlunsplit

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:  # Visual delivery must fail closed when Pillow is absent.
    Image = None
    UnidentifiedImageError = OSError


SCHEMAS: dict[str, list[str]] = {
    "query-log.csv": [
        "query_id",
        "platform",
        "query",
        "search_surface",
        "sort_or_filter",
        "run_at",
        "result_count",
        "selected_source_ids",
        "selected_account_ids",
        "selected_post_ids",
        "new_valid_accounts",
        "new_content_patterns",
        "notes",
    ],
    "source-log.csv": [
        "source_id",
        "source_layer",
        "platform",
        "source_type",
        "title",
        "author_org",
        "published_at",
        "collected_at",
        "url",
        "query_id",
        "access_status",
        "evidence_form",
        "evidence_grade",
        "notes_file",
    ],
    "claim-ledger.csv": [
        "claim_id",
        "category",
        "claim_text",
        "source_ids",
        "counter_source_ids",
        "evidence_grade",
        "claim_status",
        "scope",
        "confidence_reason",
        "skill_action",
        "last_verified_at",
        "verification_class",
    ],
    "accounts.csv": [
        "account_id",
        "account_name",
        "profile_url",
        "head_type",
        "follower_count",
        "window_start",
        "window_end",
        "recent_sample_n",
        "recent_median_visible_engagement",
        "recent_max_visible_engagement",
        "outlier_multiple",
        "audience_evidence",
        "commercial_distance",
        "collected_at",
        "source_ids",
        "confidence",
        "status",
    ],
    "posts.csv": [
        "post_id",
        "note_id",
        "title",
        "url",
        "account_id",
        "published_at",
        "date_confidence",
        "collected_at",
        "queries_matched",
        "search_surface",
        "sort_or_filter",
        "rank_observed",
        "format",
        "visible_engagement",
        "engagement_breakdown_available",
        "account_baseline_multiple",
        "hook",
        "page_or_scene_structure",
        "need_signal",
        "cover_mechanism",
        "evidence_level",
        "confidence",
        "duplicate_of",
        "cluster_id",
        "status",
        "performance_tier",
        "style_capture_status",
        "style_library_post_id",
        "style_observation_ids",
        "style_skip_reason",
    ],
    "trend-template-samples.csv": [
        "template_sample_id",
        "template_id",
        "family_id",
        "post_id",
        "note_id",
        "url",
        "account_id",
        "query_ids",
        "parent_query_id",
        "query_round",
        "search_surface",
        "sort_or_filter",
        "rank_observed",
        "published_at",
        "date_confidence",
        "collected_at",
        "carrier",
        "primary_job",
        "template_type",
        "remix_relation",
        "creative_family_id",
        "lineage_cluster_id",
        "supply_origin",
        "hook_observation",
        "shot_grammar_observation",
        "edit_grammar_observation",
        "participation_signal",
        "visible_engagement",
        "account_baseline_multiple",
        "performance_tier",
        "evidence_role",
        "duplicate_of",
        "category_scope",
        "comment_evidence_ids",
        "source_ids",
        "access_status",
        "source_snapshot_sha256",
        "capture_status",
        "limitations",
    ],
    "topics.csv": [
        "topic_id",
        "topic",
        "primary_job",
        "entry_surface",
        "target_audience",
        "specific_scenario",
        "core_promise_or_tension",
        "evidence_ids",
        "counterexamples",
        "lifecycle",
        "format",
        "format_reason",
        "commercial_distance",
        "rule_scopes",
        "measurement_plan",
        "hypothesis_id",
        "priority",
        "status",
        "last_seen_at",
    ],
    "acquisition-channels.csv": [
        "channel_id",
        "direction",
        "platform",
        "account_scope",
        "audience_state",
        "channel_role",
        "native_format",
        "source_asset_id",
        "public_identity",
        "eligibility_ids",
        "surfaces",
        "permitted_cta",
        "prohibited_cta",
        "landing_asset",
        "primary_metric",
        "metric_availability",
        "data_source",
        "event_definition",
        "diagnostic_metrics",
        "attribution_method",
        "attribution_level",
        "baseline_window",
        "test_window",
        "minimum_events",
        "decision_rule",
        "compliance_scope",
        "evidence_ids",
        "confidence",
        "owner",
        "status",
        "source_asset_sha256",
        "consent_ids",
    ],
    "sku-registry.csv": [
        "eligibility_id",
        "sku_id",
        "sku_name",
        "platform",
        "account_scope",
        "surface",
        "source_asset_id",
        "status",
        "evidence_ids",
        "platform_ticket",
        "verified_at",
        "expires_at",
        "material_limits",
        "qualification_requirements",
        "notes",
        "source_asset_sha256",
        "qualification_claim_id",
    ],
    "offer-registry.csv": [
        "eligibility_id",
        "offer_id",
        "offer_name",
        "offer_type",
        "platform",
        "account_scope",
        "surface",
        "source_asset_id",
        "status",
        "evidence_ids",
        "platform_ticket",
        "verified_at",
        "expires_at",
        "permission_or_consent_requirements",
        "prohibited_uses",
        "notes",
        "source_asset_sha256",
        "qualification_claim_id",
    ],
    "authorization-log.csv": [
        "authorization_id",
        "subject_scope",
        "source_asset_id",
        "material_id",
        "material_sha256",
        "material_type",
        "permission_scope",
        "commercial_use",
        "anonymization_requirements",
        "granted_at",
        "expires_at",
        "withdrawal_process",
        "evidence_locator",
        "verified_by",
        "verified_at",
        "status",
        "authorized_output_sha256",
    ],
}

COMMON_FILES = {
    "run.yaml",
    "research.md",
    "query-log.csv",
    "source-log.csv",
    "claim-ledger.csv",
}
MODE_FILES = {
    "mechanism": set(),
    "discovery": {"accounts.csv", "posts.csv", "topics.csv"},
    "refresh": {"accounts.csv", "posts.csv", "topics.csv"},
    "draft": {"topics.csv"},
}

ID_FIELDS = {
    "query-log.csv": "query_id",
    "source-log.csv": "source_id",
    "claim-ledger.csv": "claim_id",
    "accounts.csv": "account_id",
    "posts.csv": "post_id",
    "trend-template-samples.csv": "template_sample_id",
    "topics.csv": "topic_id",
    "acquisition-channels.csv": "channel_id",
    "sku-registry.csv": "eligibility_id",
    "offer-registry.csv": "eligibility_id",
    "authorization-log.csv": "authorization_id",
}

REQUIRED_ROW_FIELDS = {
    "query-log.csv": {"query_id", "platform", "query", "search_surface", "run_at"},
    "source-log.csv": {
        "source_id",
        "source_layer",
        "source_type",
        "title",
        "collected_at",
        "url",
        "access_status",
        "evidence_grade",
    },
    "claim-ledger.csv": {
        "claim_id",
        "category",
        "claim_text",
        "source_ids",
        "evidence_grade",
        "claim_status",
        "scope",
        "confidence_reason",
        "skill_action",
        "last_verified_at",
        "verification_class",
    },
    "accounts.csv": {
        "account_id",
        "account_name",
        "profile_url",
        "head_type",
        "window_start",
        "window_end",
        "recent_sample_n",
        "collected_at",
        "confidence",
        "status",
    },
    "posts.csv": {
        "post_id",
        "title",
        "url",
        "account_id",
        "collected_at",
        "queries_matched",
        "format",
        "evidence_level",
        "confidence",
        "status",
    },
    "trend-template-samples.csv": {
        "template_sample_id",
        "template_id",
        "family_id",
        "post_id",
        "note_id",
        "url",
        "account_id",
        "query_ids",
        "query_round",
        "search_surface",
        "collected_at",
        "carrier",
        "primary_job",
        "template_type",
        "remix_relation",
        "creative_family_id",
        "lineage_cluster_id",
        "supply_origin",
        "evidence_role",
        "source_ids",
        "access_status",
        "capture_status",
    },
    "topics.csv": {
        "topic_id",
        "topic",
        "primary_job",
        "target_audience",
        "specific_scenario",
        "core_promise_or_tension",
        "evidence_ids",
        "lifecycle",
        "format",
        "measurement_plan",
        "status",
        "last_seen_at",
    },
    "acquisition-channels.csv": {
        "channel_id",
        "direction",
        "platform",
        "account_scope",
        "audience_state",
        "channel_role",
        "native_format",
        "source_asset_id",
        "public_identity",
        "surfaces",
        "permitted_cta",
        "primary_metric",
        "metric_availability",
        "data_source",
        "event_definition",
        "attribution_method",
        "attribution_level",
        "decision_rule",
        "compliance_scope",
        "owner",
        "status",
    },
    "sku-registry.csv": {
        "eligibility_id",
        "sku_id",
        "sku_name",
        "platform",
        "account_scope",
        "surface",
        "status",
        "evidence_ids",
    },
    "offer-registry.csv": {
        "eligibility_id",
        "offer_id",
        "offer_name",
        "offer_type",
        "platform",
        "account_scope",
        "surface",
        "status",
        "evidence_ids",
    },
    "authorization-log.csv": {
        "authorization_id",
        "subject_scope",
        "source_asset_id",
        "material_id",
        "material_sha256",
        "material_type",
        "permission_scope",
        "commercial_use",
        "anonymization_requirements",
        "granted_at",
        "withdrawal_process",
        "evidence_locator",
        "verified_by",
        "verified_at",
        "status",
        "authorized_output_sha256",
    },
}

APPROVED_ELIGIBILITY = {"approved", "confirmed"}
BLOCKED_CHANNEL_STATES = {"blocked", "draft"}
BLOCKED_CHANNEL_PREFIXES = ("blocked_", "draft_", "needs_")
FORBIDDEN_CHANNEL_STATUS_TOKENS = {
    "active",
    "allowed",
    "approved",
    "enabled",
    "launch",
    "live",
    "publishable",
    "ready",
}
CLAIM_STATUSES = {
    "confirmed",
    "supported_experience",
    "hypothesis",
    "contradicted",
    "unknown",
}
VERIFICATION_CLASSES = {
    "current_runtime",
    "experience",
    "historical_research",
    "hypothesis",
    "mechanism_evidence",
}
EVIDENCE_GRADES = {"A", "B", "C", "D"}
EVIDENCE_GRADE_RANK = {"A": 0, "B": 1, "C": 2, "D": 3}
SOURCE_LAYERS = {
    "official",
    "engineering",
    "academic",
    "industry",
    "creator_experience",
    "rumor",
}
ACCESS_STATUSES = {"full", "partial", "snippet_only", "blocked", "dead_link"}
SOURCE_LAYER_MIN_GRADE_RANK = {
    "official": 0,
    "engineering": 0,
    "academic": 0,
    "industry": 1,
    "creator_experience": 2,
    "rumor": 3,
}
ACCESS_MIN_GRADE_RANK = {
    "full": 0,
    "partial": 0,
    "snippet_only": 2,
    "blocked": 3,
    "dead_link": 2,
}
CONFIRMED_SOURCE_LAYERS = {"official", "engineering", "academic"}
RUNTIME_CLAIM_CATEGORIES = {
    "advertising_law",
    "compliance",
    "competition_law",
    "current_rule",
    "current_rules",
    "governance",
    "platform_capability",
    "policy",
    "privacy",
    "sensitive_commercial",
    "sku_eligibility",
    "sku_compliance",
    "offer_eligibility",
}
RUNTIME_CATEGORY_MARKERS = {
    "compliance",
    "current",
    "governance",
    "law",
    "policy",
    "privacy",
    "rule",
    "rules",
    "合规",
    "政策",
    "更新",
    "法律",
    "治理",
    "规则",
    "隐私",
}
EVIDENCE_LEVELS = {"observed", "calculated", "inferred", "hypothesis"}
CONFIDENCES = {"high", "medium", "low"}
TOPIC_STATUSES = {"experimental", "active", "deprecated"}
RUN_STATUSES = {"in_progress", "complete", "blocked"}
HEAD_TYPES = {"scale", "recent_performance", "audience_precision", "commercial_adjacent"}
ACCOUNT_STATUSES = {"candidate", "focus", "excluded", "stale"}
COMMERCIAL_DISTANCES = {"far", "adjacent", "near", "direct"}
POST_STATUSES = {"active", "excluded", "stale"}
DIRECT_DEMAND_SOURCE_TOKENS = {
    "interview",
    "survey",
    "transcript",
    "customer_research",
    "user_material",
    "backend_screenshot",
}
CONTENT_SAMPLE_TOKENS = {"post", "note", "comment"}
ACCOUNT_SAMPLE_TOKENS = {"account", "creator_profile", "note", "post", "profile"}
PRIMARY_JOBS = {
    "recommendation_reach",
    "search_capture",
    "relationship_building",
    "commercial_conversion",
}
V2_BUSINESS_OBJECTIVES = {"traffic_first", "engagement_proxy"}
V2_STYLE_REQUIREMENTS = {"none", "copy", "visual", "both"}
V2_STYLE_BINDING_STATUSES = {"grounded", "needs_style_research"}
V2_PERFORMANCE_VISIBILITY_SCOPES = {"first_party_analytics", "public_proxy"}
V2_PERFORMANCE_EVIDENCE_SCOPES = {
    "not_performance_evidence",
    "public_proxy_association",
    "first_party_traffic_validated",
}
V2_RULE_CLAIM_KINDS = {
    "series_constant",
    "task_fit",
    "contrastive_performance_hypothesis",
}
V2_FEATURE_CONTRASTS = {"invariant", "differentiated", "not_applicable"}
V2_TRAFFIC_PRIMARY_METRICS = {
    "impressions",
    "reach",
    "engagement_proxy",
    "unavailable",
}
V2_TRAFFIC_VERDICTS = {
    "win",
    "loss",
    "inconclusive",
    "unavailable",
    "insufficient",
    "not_applicable",
}
V2_TRAFFIC_STAGES = {
    "feed_stop",
    "read_through",
    "save_share",
    "comment_cocreation",
    "profile_follow",
}
V2_JOB_PRIMARY_METRICS_BY_JOB = {
    "feed_stop": {"valid_open_rate", "first_screen_hold_rate", "unavailable"},
    "search_answer": {
        "search_answer_completion_rate",
        "read_through_rate",
        "save_rate",
        "unavailable",
    },
    "explain": {
        "read_through_rate",
        "correct_restatement_rate",
        "save_rate",
        "unavailable",
    },
    "trust_build": {
        "qualified_question_rate",
        "evidence_acceptance_rate",
        "save_rate",
        "unavailable",
    },
    "decision_support": {
        "comparison_completion_rate",
        "decision_question_rate",
        "save_rate",
        "unavailable",
    },
    "relationship_build": {
        "profile_visit_rate",
        "follow_rate",
        "return_rate",
        "unavailable",
    },
    "conversion": {"qualified_action_rate", "conversion_rate", "unavailable"},
    "authority_statement": {
        "read_through_rate",
        "source_check_rate",
        "correction_rate",
        "unavailable",
    },
}
V2_JOB_PROXY_METRICS = {"comment_semantic_proxy"}
V2_JOB_METRIC_DATA_SCOPES = {
    "first_party_analytics",
    "public_proxy",
    "unavailable",
}
V2_JOB_METRIC_DENOMINATORS = {
    "impressions",
    "reach",
    "opens",
    "qualified_opens",
    "readers",
    "search_entries",
    "comments",
    "profile_visits",
    "eligible_users",
    "unavailable",
}
V2_VISUAL_DELIVERY_REQUIREMENTS = {"none", "brief", "rendered"}
V2_VISUAL_DELIVERY_STATUSES = {
    "not_requested",
    "brief_only",
    "prototype_only",
    "rendered_needs_review",
    "rendered_pass",
}
V2_CTA_PRODUCT_SCOPES = {
    "none",
    "general_product",
    "adult_product",
    "relationship_education_only",
}
V2_PRODUCTION_GATE_STATUSES = {
    "not_applicable",
    "ready",
    "needs_revision",
    "needs_platform_confirmation",
    "blocked_safety",
    "blocked_rights",
    "unknown",
}
V2_PERFORMANCE_TIERS = {"high", "ordinary", "low", "unknown"}
V2_STYLE_CAPTURE_STATUSES = {"complete", "partial", "skipped", "not_required"}
V2_DRAFT_META = {
    "style_contract_version",
    "business_objective",
    "style_requirement",
    "style_library_path",
    "style_taxonomy_version",
    "style_query_category",
    "style_query_carrier",
    "style_query_primary_job",
    "style_query_required_constraint_codes",
    "style_query_required_material_codes",
    "style_query_available_material_codes",
    "style_query_active_constraint_codes",
    "style_query_active_contraindication_codes",
    "style_binding_source",
    "style_binding_status",
    "draft_binding_id",
    "draft_binding_sha256",
    "style_rule_ids",
    "primary_style_archetype_id",
    "primary_style_archetype_version",
    "primary_style_archetype_snapshot_sha256",
    "performance_rule_claim_kind",
    "style_feature_contrast",
    "performance_evidence_scope",
    "primary_performance_rule_id",
    "performance_visibility_scope",
    "traffic_primary_metric",
    "traffic_verdict",
    "traffic_stage",
    "traffic_observation_surface",
    "traffic_outcome_checkpoint_id",
    "traffic_outcome_receipt_sha256",
    "job_primary_metric",
    "job_metric_event_definition",
    "job_metric_denominator",
    "job_metric_data_scope",
    "job_metric_verdict",
    "visual_delivery_requirement",
    "visual_delivery_status",
    "expected_slide_indices",
    "cta_product_scope",
    "production_gate_status",
    "production_gate_receipt_ids",
}
LIFECYCLES = {"hot", "periodic", "evergreen_search"}
DIRECTIONS = {
    "external_to_xhs",
    "xhs_to_native_conversion",
    "xhs_to_approved_external",
    "owned_retention",
}
XHS_PLATFORM_NAMES = {"xiaohongshu", "redbook", "小红书"}
NON_SPECIFIC_SCOPES = {
    "*",
    "all",
    "all_accounts",
    "all_platforms",
    "all_surfaces",
    "any",
    "any_account",
    "any_platform",
    "any_surface",
    "multi_account",
    "multi_platform",
    "multi_surface",
    "none",
    "tbd",
    "unassigned",
    "unknown",
    "待定",
    "任意平台",
    "全部平台",
    "全平台",
    "全账户",
    "全账号",
    "全表面",
    "全触点",
    "所有平台",
    "所有账户",
    "所有账号",
    "所有表面",
    "所有触点",
}

DRAFT_HEADINGS = {
    "证据与目标用户",
    "标题版本",
    "封面版本",
    "成稿",
    "关键词与话题",
    "事实与证明",
    "CTA 与披露",
    "合规审校",
    "创意审校",
    "观测计划",
}
V2_DRAFT_HEADINGS = {"流量机制绑定", "趋势模板绑定", "视觉方向绑定"}
TREND_TEMPLATE_REQUIREMENTS = {"none", "research", "draft"}
TREND_SAMPLE_ROLES = {"seed", "support", "counterexample", "boundary"}
TREND_REMIX_RELATIONS = {
    "direct_remake",
    "slot_substitution",
    "category_transfer",
    "parody",
    "tutorial",
    "generator",
    "unrelated_same_phrase",
}
TREND_SUPPLY_ORIGINS = {
    "spontaneous",
    "brand_campaign",
    "platform_program",
    "paid_distribution",
    "mixed",
    "unknown",
}
TREND_REPLICATION_STATUSES = {"query_candidate", "observed", "replicated"}
TREND_LIFECYCLE_PHASES = {
    "unknown",
    "rising",
    "mature",
    "fatigued",
    "evergreen_carrier",
}
TREND_DECISIONS = {"shoot", "adapt", "observe", "skip"}
TREND_CURRENT_STATUSES = {"current", "superseded"}
TREND_RIGHTS_STATUSES = {
    "grammar_only",
    "authorized_assets",
    "needs_review",
    "blocked",
    "unknown",
}
TREND_SAFETY_STATUSES = {"passed", "needs_review", "blocked", "unknown"}
TREND_DISCOVERY_LANES = {"named_trend", "unnamed_structure_cluster"}
TREND_ALLOWED_PERFORMANCE_SCOPES = {
    "not_performance_evidence",
    "public_proxy_association",
}
TREND_CANDIDATE_FIELDS = {
    "record_type",
    "schema_version",
    "candidate_record_id",
    "run_id",
    "candidate_version",
    "supersedes_candidate_record_id",
    "template_id",
    "family_id",
    "canonical_name",
    "aliases",
    "template_types",
    "discovery_queries",
    "discovery_lanes",
    "source_sample_ids",
    "support_sample_ids",
    "counterexample_sample_ids",
    "boundary_sample_ids",
    "independent_account_count",
    "category_scopes",
    "carrier_scopes",
    "primary_job_scopes",
    "traffic_stage_scopes",
    "supply_origin",
    "supply_origin_evidence_ids",
    "first_seen_at",
    "last_seen_at",
    "sample_window",
    "window_comparisons",
    "hook_grammar",
    "shot_grammar",
    "edit_grammar",
    "participation_loop",
    "slot_map",
    "required_material_codes",
    "optional_material_codes",
    "contraindications",
    "rights_status",
    "safety_status",
    "authorized_asset_ids",
    "source_asset_hashes",
    "replication_status",
    "lifecycle_phase",
    "lifecycle_reason",
    "confidence",
    "evidence_level",
    "performance_evidence_scope",
    "decision",
    "adaptation_notes",
    "last_refreshed_at",
    "limitations",
    "record_sha256",
}
TREND_TEMPLATE_CONTRACT_FIELDS = {
    "template_contract_status",
    "candidate_record_id",
    "template_id",
    "family_id",
    "candidate_version",
    "replication_status",
    "lifecycle_phase",
    "last_refreshed_at",
    "decision",
    "source_sample_ids",
    "support_sample_ids",
    "counterexample_sample_ids",
    "fixed_slots",
    "replaced_slots",
    "new_semantic_contribution",
    "material_evidence_map",
    "failure_condition",
}
V2_MECHANISM_CONTRACT_STATUSES = {
    "needs_research",
    "bound_candidate",
    "bound_grounded",
}
V2_MECHANISM_CONTRACT_FIELDS = {
    "contract_status",
    "primary_mechanism_id",
    "mechanism_ids",
    "counterexample_ids",
    "material_codes",
    "material_evidence_map",
    "mechanism_application_map",
    "research_gap",
}
V2_MECHANISM_SLOTS = {
    "content": {"content"},
    "carrier_or_truth": {"carrier_router", "truth_gate"},
    "learning_or_governance": {"feedback", "measurement", "governance"},
}
V2_MATERIAL_REF_TYPES = {
    "promise": {"draft_anchor"},
    "real_proof": {"source", "claim", "post", "authorized_material"},
    "user_language": {"source", "post", "authorized_material"},
    "scene_observation": {"source", "post", "authorized_material"},
    "before_after_sequence": {"source", "post", "authorized_material"},
    "constraint_cost": {"source", "claim", "post", "authorized_material"},
    "work_object": {"source", "post", "authorized_material"},
    "current_source": {"source", "claim"},
    "comparison_candidates": {"source", "claim", "post"},
    "uniform_protocol": {"source", "claim", "draft_anchor"},
    "search_intent_sample": {"query", "source", "post"},
    "proof_inventory": {"source", "claim", "post", "authorized_material", "draft_anchor"},
    "human_use_record": {"source", "post", "authorized_material"},
    "rights_clearance": {"authorization"},
    "series_promise": {"draft_anchor"},
    "fresh_payload": {"source", "post", "authorized_material"},
    "authorized_experience": {"authorization", "authorized_material", "source"},
    "actionable_method": {"source", "claim", "post", "draft_anchor"},
    "problem_evidence": {"source", "claim", "post", "authorized_material"},
    "category_facts": {"source", "claim"},
    "real_comments": {"source", "post", "authorized_material"},
    "first_party_metrics": {"source", "claim"},
    "comment_semantics": {"source", "post", "draft_anchor"},
    "variant_log": {"source", "draft_anchor"},
    "ai_draft": {"source", "draft_anchor"},
    "human_review": {"source", "draft_anchor"},
    "source_ledger": {"query", "source", "claim", "account", "post", "draft_anchor"},
    "version_log": {"source", "draft_anchor"},
    "authorized_chat_original": {"authorization", "authorized_material"},
    "fiction_disclosure": {"draft_anchor"},
    "real_process_video": {"source", "authorization", "authorized_material"},
    "current_interface_capture": {"source", "authorized_material"},
    "privacy_redaction": {"authorization", "draft_anchor"},
    "real_person_authorized": {"authorization", "authorized_material"},
    "spoken_claim_sources": {"source", "claim"},
    "surface_entry_observation": {"query", "source", "post", "account"},
    "independent_demand_signal": {"query", "source", "post"},
    "supply_source_audit": {"source", "post", "account", "draft_anchor"},
    "freshness_signal": {"source", "claim", "post", "draft_anchor"},
}
V2_VISUAL_CONTRACT_STATUSES = {
    "not_requested",
    "needs_visual_research",
    "prototype_gap",
    "selected_exploration",
    "selected_production",
}
V2_VISUAL_CONTRACT_FIELDS = {
    "visual_contract_status",
    "visual_direction_card_ids",
    "selection_mode",
    "asset_manifest_path",
    "asset_manifest_sha256",
    "style_library_path",
    "draft_binding_id",
    "active_contraindication_codes",
    "research_gap",
}
V2_VISUAL_PROTOTYPE_FIELDS = {
    "prototype_asset_id",
    "draft_id",
    "visual_brief_id",
    "concept_id",
    "attention_path",
    "prototype_prompt_sha256",
    "asset_path",
    "asset_sha256",
    "width",
    "height",
    "render_method",
    "binding_rule_bundle_sha256",
    "style_rule_refs",
    "starter_prompt_id",
    "starter_prompt_sha256",
    "feed_preview_path",
    "feed_preview_sha256",
    "feed_review_status",
    "full_review_status",
    "selection_status",
    "selection_reason",
    "revision_of",
    "notes",
}
V2_VISUAL_BRIEF_FIELDS = {
    "visual_brief_id", "draft_id", "brief_revision", "visual_brief_sha256",
    "binding_snapshot_sha256", "primary_job", "carrier", "audience_state",
    "attention_paths", "functional_need", "lived_scene", "motive_codes",
    "perceivable_outcome", "brand_to_user_translation_trace", "offer_or_sku_ref",
    "distribution_mode", "content_owner_id", "reviewer_ids",
    "reviewer_independence_status", "content_model_id", "content_model_version",
    "model_lifecycle_stage", "page_role_plan", "required_material_codes",
    "forbidden_feature_codes", "brand_prominence", "prototype_count",
    "feed_preview_size", "full_size", "constraint_codes",
    "benchmark_library_post_ids", "target_hypothesis_sha256",
    "benchmark_set_sha256", "attention_path_set_sha256",
    "generation_prompt_sha256", "supersedes_visual_brief_id",
    "reset_of_visual_brief_id", "created_at",
}
V2_DRAFT_ASSET_FIELDS = {
    "draft_asset_id",
    "draft_id",
    "draft_binding_id",
    "slide_index",
    "asset_path",
    "asset_sha256",
    "width",
    "height",
    "render_method",
    "binding_rule_bundle_sha256",
    "style_rule_refs",
    "starter_prompt_sha256",
    "review_status",
    "review_receipt_id",
    "revision_of",
    "notes",
}
V2_FINAL_RENDER_METHODS = {
    "deterministic_layout",
    "manual_design",
    "image_model",
    "hybrid",
    "authorized_capture",
}
V2_VISUAL_REVIEW_FIELDS = {
    "review_receipt_id", "draft_id", "draft_asset_id", "asset_sha256",
    "binding_sha256", "slide_index", "content_owner_id", "reviewer_id",
    "reviewer_independence_status", "reviewed_at",
    "feed_review_status", "full_review_status", "review_status", "issues",
    "receipt_sha256",
}
DRAFT_META = {
    "draft_id",
    "topic_id",
    "platform",
    "account_scope",
    "primary_job",
    "lifecycle",
    "truth_label",
    "truth_disclosure_text",
    "truth_disclosure_location",
    "authorization_ids",
    "source_material_ids",
    "commercial_relationship",
    "disclosure_text",
    "disclosure_location",
    "answer_location",
    "cta_type",
    "eligibility_ids",
    "surfaces",
    "status",
}
DRAFT_NONEMPTY_META = DRAFT_META - {"eligibility_ids", "surfaces"}
TRUTH_LABELS = {
    "first_person_documented",
    "authorized_anonymized",
    "authorized_adaptation",
    "composite_cases",
    "fictional_scenario",
    "factual_explainer",
}
COMMERCIAL_RELATIONSHIPS = {
    "none",
    "owned_product",
    "sponsored",
    "gifted",
    "affiliate",
    "commissioned_creator",
    "other_disclosed",
}
COMMERCIAL_DISCLOSURE_PATTERNS = {
    "owned_product": (r"自有", r"自营", r"本店", r"品牌方", r"我方产品"),
    "sponsored": (r"广告", r"品牌合作", r"商业合作", r"赞助"),
    "gifted": (r"赠品", r"获赠", r"品牌赠送", r"免费提供"),
    "affiliate": (r"佣金", r"返佣", r"联盟", r"推广分成"),
    "commissioned_creator": (
        r"受委托",
        r"委托创作",
        r"有偿创作",
        r"付费创作",
        r"品牌合作",
    ),
    "other_disclosed": (r"商业关系", r"利益关系", r"合作关系", r"有偿", r"付费"),
}
COMMERCIAL_DISCLOSURE_CONFLICT_PATTERNS = {
    "owned_product": (r"(?:不是|并非|没有|无|不存在|不属于|非).{0,6}(?:自有|自营|品牌方)",),
    "sponsored": (r"(?:不是|并非|没有|无|不存在|不属于|非).{0,6}(?:广告|品牌合作|商业合作|赞助)",),
    "gifted": (r"(?:不是|并非|没有|无|不存在|不属于|非).{0,6}(?:赠品|获赠|赠送|免费提供)",),
    "affiliate": (r"(?:不是|并非|没有|无|不存在|不属于|非).{0,6}(?:佣金|返佣|联盟|推广分成)",),
    "commissioned_creator": (r"(?:不是|并非|没有|无|不存在|不属于|非).{0,6}(?:受委托|委托创作|有偿创作|付费创作|品牌合作)",),
    "other_disclosed": (r"(?:不是|并非|没有|无|不存在|不属于|非).{0,6}(?:商业关系|利益关系|合作关系|有偿|付费)",),
}
NONCOMMERCIAL_CTA_TYPES = {"none", "save", "follow", "comment_question", "read_series"}
COMMERCIAL_CTA_TYPES = {"product_component", "leadgen", "approved_external", "paid_offer"}
CTA_TYPES = NONCOMMERCIAL_CTA_TYPES | COMMERCIAL_CTA_TYPES
DRAFT_STATUSES = {"needs_review", "ready", "blocked"}
CTA_REQUIRED_REGISTRY_KINDS = {
    "product_component": {"sku", "offer"},
    "leadgen": {"offer"},
    "approved_external": {"offer"},
    "paid_offer": {"offer"},
}
PRODUCT_OFFER_TYPES = {"commerce", "product", "product_sale", "retail", "trial"}
AUTHORIZATION_MATERIAL_TYPES = {
    "case_record",
    "chat_record",
    "first_party",
    "interview",
    "other",
    "submission",
}
AUTHORIZATION_PERMISSION_SCOPES = {
    "adaptation",
    "anonymized_publish",
    "composite",
    "cross_platform_attribution",
    "verbatim",
}
AUTHORIZATION_COMMERCIAL_USE = {"approved", "prohibited"}
AUTHORIZATION_STATUSES = {"approved", "expired", "pending", "withdrawn"}
AUTH_REQUIRED_TRUTH_LABELS = {
    "authorized_anonymized": ("anonymized_publish", 1),
    "authorized_adaptation": ("adaptation", 1),
    "composite_cases": ("composite", 2),
}
APPROVAL_SOURCE_TYPES = {
    "approval_record",
    "platform_approval_record",
    "platform_ticket",
    "work_order",
}
TRUTH_DISCLOSURE_PATTERNS = {
    "first_person_documented": (
        r"(?:本人(?:亲历|真实记录|记录)|我的亲历记录)",
    ),
    "authorized_anonymized": (
        r"(?:经|已获).{0,6}授权.{0,12}(?:匿名|脱敏)",
    ),
    "authorized_adaptation": (
        r"(?:经|已获).{0,6}授权.{0,12}改编",
    ),
    "composite_cases": (
        r"(?:多案例|多个.{0,6}案例|多份.{0,6}材料).{0,16}(?:合成|综合改编)",
        r"(?:合成|综合改编).{0,16}(?:多案例|多个.{0,6}案例|多份.{0,6}材料)",
    ),
    "fictional_scenario": (
        r"本(?:文|内容|故事|对话|情境)?为(?:明确)?虚构",
        r"虚构情境(?:演绎|练习)",
        r"情境演绎.{0,12}(?:明确虚构|非真人经历)",
    ),
    "factual_explainer": (
        r"(?:事实说明|事实科普|资料说明|基于可核验资料的说明)",
    ),
}
TRUTH_DISCLOSURE_CONFLICT_PATTERNS = {
    "first_person_documented": (r"(?:不是|并非|不属于|非)本人", r"虚构", r"情境演绎"),
    "authorized_anonymized": (r"(?:未经|未获|没有|无|并非|不是)授权",),
    "authorized_adaptation": (r"(?:未经|未获|没有|无|并非|不是)授权",),
    "composite_cases": (r"(?:不是|并非|不属于|非)合成", r"(?:单一|一个)真人"),
    "fictional_scenario": (
        r"(?:不是|并非|不属于|非)虚构",
        r"真人真事",
        r"真人真实投稿",
        r"真实投稿",
        r"真实发生",
        r"亲身经历",
    ),
    "factual_explainer": (
        r"(?:不是|并非|不属于|非)事实",
        r"虚构",
        r"(?:未经|未)核实",
    ),
}
VISIBLE_DISCLOSURE_LOCATIONS = {"首屏", "第一页", "首段", "开头", "标题下"}
VISIBLE_COMMERCIAL_DISCLOSURE_LOCATIONS = {
    "首屏",
    "第一页",
    "首段",
    "开头",
    "标题下",
    "CTA前",
    "正文CTA前",
}


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    location: str
    message: str


def split_ids(value: str | None) -> list[str]:
    if not value:
        return []
    return [item for item in re.split(r"[;|\s]+", value.strip()) if item]


def canonical_post_url(value: str | None) -> str:
    """Return a tracking-free URL identity for duplicate/evidence checks."""
    raw = (value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return raw
    if not parsed.scheme or not parsed.netloc:
        return raw.rstrip("/")
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") or "/",
            "",
            "",
        )
    )


def parse_iso(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def parse_dateish(value: str) -> date | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        return parse_iso(normalized)


def parse_timestamp_utc(value: object) -> datetime:
    """Parse SQLite/ISO timestamps and normalize naive SQLite UTC to UTC."""
    normalized = str(value).strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_partial_iso(value: str) -> date | None:
    if re.fullmatch(r"\d{4}", value):
        return date(int(value), 1, 1)
    if re.fullmatch(r"\d{4}-\d{2}", value):
        try:
            return date(int(value[:4]), int(value[5:7]), 1)
        except ValueError:
            return None
    return parse_iso(value)


def parse_top_level_yaml(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        if not raw or raw[0].isspace() or raw.lstrip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*?)\s*$", raw)
        if not match:
            continue
        value = match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[match.group(1)] = value
    return values


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    values: dict[str, str] = {}
    for raw in text[4:end].splitlines():
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*?)\s*$", raw)
        if match:
            value = match.group(2).strip().strip("\"'")
            values[match.group(1)] = value
    return values


def markdown_section(text: str, heading: str) -> str:
    match = re.search(
        rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def visible_markdown(text: str) -> str:
    """Remove common non-rendered/hidden HTML before validating visible contracts."""
    cleaned = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    cleaned = re.sub(
        r"<(?:script|style|template|noscript|details)\b[^>]*>.*?</(?:script|style|template|noscript|details)\s*>",
        "",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    hidden_block = re.compile(
        r"<(?P<tag>[a-z][a-z0-9:-]*)\b"
        r"(?=[^>]*(?:\bhidden\b|aria-hidden\s*=\s*['\"]?true|"
        r"class\s*=\s*['\"][^'\"]*(?:hidden|sr-only|visually-hidden)|"
        r"style\s*=\s*['\"][^'\"]*(?:display\s*:\s*none|visibility\s*:\s*hidden)))"
        r"[^>]*>.*?</(?P=tag)\s*>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    previous = None
    while previous != cleaned:
        previous = cleaned
        cleaned = hidden_block.sub("", cleaned)
    cleaned = re.sub(r"!\[[^\]]*\]\([^\n)]*\)", "", cleaned)
    cleaned = re.sub(r"!\[[^\]]*\]\[[^\]]*\]", "", cleaned)
    cleaned = re.sub(
        r"(?m)^\s*\[[^\]]+\]:\s*\S+.*$",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\[([^\]]+)\]\([^\n)]*\)", r"\1", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", cleaned)
    cleaned = re.sub(r"</?[a-z][^>]*>", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def parse_contract_block(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        match = re.match(r"^([a-z][a-z0-9_]*):\s*(.*?)\s*$", raw.strip())
        if match:
            values[match.group(1)] = match.group(2).strip().strip("\"'")
    return values


def normalize_none(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    return "none" if normalized in {"", "none"} else normalized


def exact_tokens(value: str | None) -> set[str]:
    """Return normalized identifier-like tokens without substring matching."""
    return {
        token
        for token in re.split(r"[^a-z0-9]+", (value or "").strip().lower())
        if token
    }


def normalized_descriptor(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")


def source_descriptors(row: dict[str, str]) -> set[str]:
    return {
        descriptor
        for descriptor in (
            normalized_descriptor(row.get("source_type")),
            normalized_descriptor(row.get("evidence_form")),
        )
        if descriptor
    }


def claim_requires_runtime_verification(category: str | None) -> bool:
    raw = (category or "").strip().lower()
    normalized = normalized_descriptor(raw)
    if normalized in RUNTIME_CLAIM_CATEGORIES:
        return True
    english_tokens = set(normalized.split("_"))
    if english_tokens & {marker for marker in RUNTIME_CATEGORY_MARKERS if marker.isascii()}:
        return True
    return any(marker in raw for marker in RUNTIME_CATEGORY_MARKERS if not marker.isascii())


def claim_text_requires_runtime_verification(claim_text: str | None) -> bool:
    text = (claim_text or "").strip().lower()
    platform_markers = (
        "平台",
        "小红书",
        "redbook",
        "抖音",
        "douyin",
        "知乎",
        "b站",
        "微信",
    )
    capability_markers = (
        "入口",
        "能力",
        "功能",
        "组件",
        "外跳",
        "私信",
        "信息流",
        "资格",
        "准入",
        "禁入",
        "可用",
        "支持",
        "允许",
        "开放",
    )
    currency_markers = (
        "当前",
        "现行",
        "目前",
        "现已",
        "已开放",
        "已上线",
        "截至",
        "仍可",
        "不再",
        "官方页面",
        "官方规则",
        "后台",
    )
    return (
        any(marker in text for marker in platform_markers)
        and any(marker in text for marker in capability_markers)
        and any(marker in text for marker in currency_markers)
    )


def scope_is_specific(value: str | None) -> bool:
    raw = (value or "").strip()
    normalized = raw.lower().replace("-", "_").replace(" ", "_")
    if normalized in NON_SPECIFIC_SCOPES or normalized.startswith(("all_", "any_", "multi_")):
        return False
    if any(separator in raw for separator in (";", "|", ",", "，", "、", "/", "+", "&", "＆")):
        return False
    return bool(raw)


def claim_scope_is_specific(value: str | None) -> bool:
    raw = (value or "").strip()
    normalized = re.sub(r"[\s_-]+", "", raw.lower())
    if not raw:
        return False
    banned = {
        "all",
        "allplatforms",
        "anyplatform",
        "multiplatform",
        "全平台",
        "全部平台",
        "所有平台",
        "全站",
        "通用",
        "小红书",
        "xiaohongshu",
        "redbook",
    }
    broad_markers = (
        "allsurface",
        "allaccount",
        "anysurface",
        "anyaccount",
        "全部入口",
        "所有入口",
        "全入口",
        "全部表面",
        "所有表面",
        "全账号",
        "全账户",
        "所有账号",
        "所有账户",
    )
    return normalized not in banned and not any(marker in normalized for marker in broad_markers)


def platform_is_xhs(value: str | None) -> bool:
    return (value or "").strip().lower() in XHS_PLATFORM_NAMES


def platforms_equivalent(left: str | None, right: str | None) -> bool:
    if platform_is_xhs(left) and platform_is_xhs(right):
        return True
    return (left or "").strip().lower() == (right or "").strip().lower()


def parse_scope_contract(value: str | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in (value or "").split("|"):
        if "=" not in part:
            continue
        key, raw = part.split("=", 1)
        key = key.strip()
        if key:
            result[key] = raw.strip()
    return result


def valid_sha256(value: str | None) -> bool:
    return bool(re.fullmatch(r"[a-fA-F0-9]{64}", (value or "").strip()))


def canonical_json_sha256(payload: dict[str, object], omitted_key: str) -> str:
    canonical = {key: value for key, value in payload.items() if key != omitted_key}
    return hashlib.sha256(
        json.dumps(
            canonical,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def channel_status_class(value: str | None) -> str | None:
    """Return active/blocked only for machine-readable, non-contradictory statuses."""
    status = (value or "").strip().lower()
    if status == "active":
        return "active"
    if status in BLOCKED_CHANNEL_STATES:
        return "blocked"
    if not status.startswith(BLOCKED_CHANNEL_PREFIXES):
        return None
    tokens = exact_tokens(status)
    if tokens & FORBIDDEN_CHANNEL_STATUS_TOKENS:
        return None
    return "blocked"


class RunValidator:
    def __init__(
        self,
        run_dir: Path,
        strict: bool = False,
        allow_legacy_contract: bool = False,
    ) -> None:
        self.run_dir = run_dir
        self.strict = strict
        self.allow_legacy_contract = allow_legacy_contract
        self.legacy_contract = False
        self.issues: list[Issue] = []
        self.rows: dict[str, list[dict[str, str]]] = {}
        self.run: dict[str, str] = {}
        self.style_taxonomy_v2: dict[str, object] = {}
        self.traffic_mechanism_library: dict[str, object] = {}
        self.trend_candidates: list[dict[str, object]] = []

    def _is_v2(self) -> bool:
        return self.run.get("run_contract_version", "").strip() == "2"

    def _load_style_taxonomy_v2(self) -> None:
        path = Path(__file__).resolve().parents[1] / "assets" / "style-taxonomy-v2.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.error("style_taxonomy_unavailable", "run.yaml", str(exc))
            return
        if payload.get("taxonomy_version") != 2:
            self.error(
                "style_taxonomy_unavailable",
                "run.yaml",
                "style taxonomy must declare taxonomy_version=2",
            )
            return
        self.style_taxonomy_v2 = payload

    def _load_traffic_mechanism_library(self) -> None:
        path = Path(__file__).resolve().parents[1] / "assets" / "traffic-mechanisms-v1.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.error("mechanism_library_unavailable", "run.yaml", str(exc))
            return
        cards = payload.get("mechanisms")
        if payload.get("schema_version") != "1.0.0" or not isinstance(cards, list):
            self.error(
                "mechanism_library_unavailable",
                "run.yaml",
                "traffic mechanism library must be schema_version=1.0.0",
            )
            return
        ids = [
            card.get("mechanism_id")
            for card in cards
            if isinstance(card, dict)
        ]
        if len(ids) != len(cards) or any(not value for value in ids) or len(set(ids)) != len(ids):
            self.error(
                "mechanism_library_unavailable",
                "run.yaml",
                "traffic mechanism IDs must be present and unique",
            )
            return
        self.traffic_mechanism_library = payload

    def _v2_codes(self, key: str) -> set[str]:
        value = self.style_taxonomy_v2.get(key, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            self.error(
                "style_taxonomy_unavailable",
                "run.yaml",
                f"style taxonomy key {key} must be a string array",
            )
            return set()
        return set(value)

    def add(self, severity: str, code: str, location: str, message: str) -> None:
        self.issues.append(Issue(severity, code, location, message))

    def error(self, code: str, location: str, message: str) -> None:
        self.add("error", code, location, message)

    def warn(self, code: str, location: str, message: str) -> None:
        self.add("warning", code, location, message)

    def validate(self) -> list[Issue]:
        if not self.run_dir.is_dir():
            self.error("missing_run_dir", str(self.run_dir), "run directory does not exist")
            return self.issues
        self._load_run()
        self._check_required_files()
        self._load_csvs()
        self._load_trend_candidates()
        self._check_completion()
        self._check_rows()
        self._check_dates()
        self._check_trend_templates()
        self._check_references()
        self._check_sources()
        self._check_claims()
        self._check_accounts_and_posts()
        self._check_style_capture_receipts()
        self._check_topics()
        self._check_registry_rows()
        self._check_authorizations()
        self._check_channels()
        self._check_drafts()
        return sorted(
            self.issues,
            key=lambda item: (item.severity != "error", item.code, item.location, item.message),
        )

    def _load_run(self) -> None:
        path = self.run_dir / "run.yaml"
        if not path.exists():
            return
        try:
            self.run = parse_top_level_yaml(path)
        except UnicodeDecodeError as exc:
            self.error("invalid_encoding", "run.yaml", str(exc))
            return
        required = {
            "run_id",
            "mode",
            "status",
            "created_at",
            "category",
            "target_audience",
            "primary_goal",
            "commercial_goal",
            "window_start",
            "window_end",
            "assumptions",
            "limitations",
        }
        for key in sorted(required - self.run.keys()):
            self.error("missing_run_field", "run.yaml", f"missing top-level field: {key}")
        for key in sorted((required - {"assumptions", "limitations"}) & self.run.keys()):
            if not self.run.get(key, "").strip():
                self.error(
                    "missing_run_value",
                    "run.yaml",
                    f"top-level field cannot be blank: {key}",
                )
        mode = self.run.get("mode", "")
        if mode and mode not in MODE_FILES:
            self.error("invalid_mode", "run.yaml", f"unsupported mode: {mode}")
        status = self.run.get("status", "")
        if status and status not in RUN_STATUSES:
            self.error("invalid_status", "run.yaml", f"unsupported status: {status}")
        for field in ("created_at", "window_start", "window_end"):
            value = self.run.get(field, "")
            if value and parse_iso(value) is None:
                self.error("invalid_date", "run.yaml", f"{field} must be YYYY-MM-DD")
        window_start = parse_iso(self.run.get("window_start", ""))
        window_end = parse_iso(self.run.get("window_end", ""))
        created = parse_iso(self.run.get("created_at", ""))
        if window_start and window_end and window_start > window_end:
            self.error("invalid_date_order", "run.yaml", "window_start cannot be after window_end")
        if created and window_end and window_end > created:
            self.error("future_date", "run.yaml", "window_end cannot be after created_at")
        contract_version = self.run.get("run_contract_version", "").strip()
        if not contract_version:
            if self.allow_legacy_contract:
                self.legacy_contract = True
            else:
                self.error(
                    "missing_run_contract_version",
                    "run.yaml",
                    "run_contract_version=2 is required; use --allow-legacy-contract only to inspect an older run",
                )
        else:
            if not self._is_v2():
                self.error(
                    "invalid_run_contract_version",
                    "run.yaml",
                    "run_contract_version must be 2",
                )
            else:
                self._load_style_taxonomy_v2()
                self._load_traffic_mechanism_library()
                self._check_v2_run_contract()

    def _check_v2_run_contract(self) -> None:
        required = {
            "business_objective",
            "objective_primary_job",
            "performance_visibility_scope",
            "style_requirement",
            "style_library_path",
            "style_taxonomy_version",
            "trend_template_requirement",
        }
        for key in sorted(required):
            if not self.run.get(key, "").strip():
                self.error("missing_v2_run_field", "run.yaml", f"missing or blank field: {key}")

        objective = self.run.get("business_objective", "")
        if objective not in V2_BUSINESS_OBJECTIVES:
            self.error(
                "invalid_v2_style_enum",
                "run.yaml",
                f"invalid business_objective: {objective}",
            )
        primary_job = self.run.get("objective_primary_job", "")
        primary_jobs = self._v2_codes("primary_job")
        if primary_job not in primary_jobs:
            self.error(
                "invalid_v2_style_enum",
                "run.yaml",
                f"invalid objective_primary_job: {primary_job}",
            )
        visibility = self.run.get("performance_visibility_scope", "")
        if visibility not in V2_PERFORMANCE_VISIBILITY_SCOPES:
            self.error(
                "invalid_v2_style_enum",
                "run.yaml",
                f"invalid performance_visibility_scope: {visibility}",
            )
        requirement = self.run.get("style_requirement", "")
        if requirement not in V2_STYLE_REQUIREMENTS:
            self.error(
                "invalid_v2_style_enum",
                "run.yaml",
                f"invalid style_requirement: {requirement}",
            )
        mode = self.run.get("mode", "")
        if mode == "mechanism" and requirement != "none":
            self.error(
                "style_requirement_mismatch",
                "run.yaml",
                "mechanism mode requires style_requirement=none",
            )
        elif mode in {"discovery", "refresh"} and requirement != "both":
            self.error(
                "style_requirement_mismatch",
                "run.yaml",
                f"{mode} mode requires style_requirement=both",
            )
        elif mode == "draft" and requirement == "none":
            self.error(
                "style_requirement_mismatch",
                "run.yaml",
                "draft mode requires copy, visual, or both",
            )
        if self.run.get("style_taxonomy_version", "") != "2":
            self.error(
                "invalid_v2_style_enum",
                "run.yaml",
                "style_taxonomy_version must be 2",
            )
        trend_requirement = self.run.get("trend_template_requirement", "none")
        if trend_requirement not in TREND_TEMPLATE_REQUIREMENTS:
            self.error(
                "invalid_trend_template_requirement",
                "run.yaml",
                "trend_template_requirement must be none, research, or draft",
            )
        if trend_requirement == "research" and mode not in {"discovery", "refresh"}:
            self.error(
                "trend_template_mode_mismatch",
                "run.yaml",
                "trend_template_requirement=research requires discovery or refresh mode",
            )
        if trend_requirement == "draft" and mode != "draft":
            self.error(
                "trend_template_mode_mismatch",
                "run.yaml",
                "trend_template_requirement=draft requires draft mode",
            )

    def _check_required_files(self) -> None:
        mode = self.run.get("mode", "")
        required = COMMON_FILES | MODE_FILES.get(mode, set())
        if self.run.get("trend_template_requirement", "none") != "none":
            required |= {
                "accounts.csv",
                "posts.csv",
                "trend-template-samples.csv",
                "trend-template-candidates.jsonl",
            }
        for name in sorted(required):
            if not (self.run_dir / name).exists():
                self.error("missing_file", name, f"required for mode {mode or 'unknown'}")
        if mode == "draft":
            drafts = self.run_dir / "drafts"
            if not drafts.is_dir():
                self.error("missing_file", "drafts/", "draft mode requires a drafts directory")
            elif not any(drafts.glob("*.md")):
                self.error("missing_file", "drafts/", "draft mode requires at least one Markdown draft")

    def _check_completion(self) -> None:
        if self.run.get("status") != "complete":
            return
        mode = self.run.get("mode", "")
        required_nonempty = {"query-log.csv", "source-log.csv", "claim-ledger.csv"}
        required_nonempty |= MODE_FILES.get(mode, set())
        if self.run.get("trend_template_requirement", "none") != "none":
            required_nonempty |= {
                "accounts.csv",
                "posts.csv",
                "trend-template-samples.csv",
            }
        for name in sorted(required_nonempty):
            if name in self.rows and not self.rows[name]:
                self.error(
                    "incomplete_run",
                    name,
                    f"completed {mode} run cannot use an empty required dataset",
                )
        if (
            self.run.get("trend_template_requirement", "none") != "none"
            and not self.trend_candidates
        ):
            self.error(
                "incomplete_run",
                "trend-template-candidates.jsonl",
                "completed trend-template run requires at least one candidate record",
            )
        if (
            self.run.get("trend_template_requirement", "none") == "research"
            and self.trend_candidates
            and not any(
                row.get("replication_status") in {"observed", "replicated"}
                for row in self.trend_candidates
            )
        ):
            self.error(
                "incomplete_run",
                "trend-template-candidates.jsonl",
                "completed trend research needs at least one opened, observed candidate; query leads alone are not completion",
            )
        research = self.run_dir / "research.md"
        if research.exists():
            content = re.sub(r"[#>*_`\-\s]", "", research.read_text(encoding="utf-8-sig"))
            if not content:
                self.error(
                    "incomplete_run",
                    "research.md",
                    "completed run requires substantive research content",
                )

    def _load_csvs(self) -> None:
        for name, schema in SCHEMAS.items():
            path = self.run_dir / name
            if not path.exists():
                continue
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    headers = reader.fieldnames or []
                    missing = [field for field in schema if field not in headers]
                    if missing:
                        self.error(
                            "schema_mismatch",
                            name,
                            "missing columns: " + ", ".join(missing),
                        )
                    loaded: list[dict[str, str]] = []
                    for raw in reader:
                        if None in raw:
                            self.error("malformed_csv", name, "row has more values than headers")
                            continue
                        loaded.append({key: (value or "").strip() for key, value in raw.items()})
                    self.rows[name] = loaded
            except (OSError, UnicodeDecodeError, csv.Error) as exc:
                self.error("unreadable_csv", name, str(exc))

    def _load_trend_candidates(self) -> None:
        path = self.run_dir / "trend-template-candidates.jsonl"
        if not path.exists():
            return
        try:
            for index, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError as exc:
                    self.error(
                        "malformed_trend_candidate",
                        f"{path.name}:{index}",
                        str(exc),
                    )
                    continue
                if not isinstance(row, dict):
                    self.error(
                        "malformed_trend_candidate",
                        f"{path.name}:{index}",
                        "each JSONL line must be an object",
                    )
                    continue
                self.trend_candidates.append(row)
        except (OSError, UnicodeDecodeError) as exc:
            self.error("unreadable_jsonl", path.name, str(exc))

    def _check_trend_templates(self) -> None:
        requirement = self.run.get("trend_template_requirement", "none")
        samples = self.rows.get("trend-template-samples.csv", [])
        if requirement == "none" and not samples and not self.trend_candidates:
            return

        query_ids = self._id_set("query-log.csv")
        source_ids = self._id_set("source-log.csv")
        post_ids = self._id_set("posts.csv")
        account_ids = self._id_set("accounts.csv")
        post_by_id = {
            row.get("post_id", ""): row
            for row in self.rows.get("posts.csv", [])
            if row.get("post_id", "")
        }
        sample_by_id = {
            row.get("template_sample_id", ""): row
            for row in samples
            if row.get("template_sample_id", "")
        }

        for index, row in enumerate(samples, start=2):
            location = f"trend-template-samples.csv:{index}"
            role = row.get("evidence_role", "")
            if role not in TREND_SAMPLE_ROLES:
                self.error("invalid_trend_sample_enum", location, f"invalid evidence_role: {role}")
            remix = row.get("remix_relation", "")
            if remix not in TREND_REMIX_RELATIONS:
                self.error("invalid_trend_sample_enum", location, f"invalid remix_relation: {remix}")
            supply = row.get("supply_origin", "")
            if supply not in TREND_SUPPLY_ORIGINS:
                self.error("invalid_trend_sample_enum", location, f"invalid supply_origin: {supply}")
            capture = row.get("capture_status", "")
            if capture not in {"complete", "partial", "blocked", "excluded"}:
                self.error("invalid_trend_sample_enum", location, f"invalid capture_status: {capture}")
            access = row.get("access_status", "")
            if access not in {"full", "partial", "snippet_only", "blocked", "dead_link"}:
                self.error("invalid_trend_sample_enum", location, f"invalid access_status: {access}")
            try:
                query_round = int(row.get("query_round", ""))
            except ValueError:
                query_round = 0
            if query_round not in {1, 2, 3, 4}:
                self.error("invalid_trend_query_round", location, "query_round must be 1, 2, 3, or 4")
            snapshot_hash = row.get("source_snapshot_sha256", "")
            if snapshot_hash and not valid_sha256(snapshot_hash):
                self.error(
                    "invalid_trend_snapshot_hash",
                    location,
                    "source_snapshot_sha256 must be blank or a 64-character SHA-256",
                )
            if capture == "complete" and access != "full":
                self.error(
                    "trend_capture_mismatch",
                    location,
                    "complete capture requires access_status=full",
                )
            observations = [
                row.get("hook_observation", ""),
                row.get("shot_grammar_observation", ""),
                row.get("edit_grammar_observation", ""),
            ]
            if not any(value and value not in {"unknown", "not_applicable"} for value in observations):
                self.error(
                    "trend_structure_missing",
                    location,
                    "at least one hook/shot/edit observation must be substantive",
                )
            for query_id in split_ids(row.get("query_ids", "")):
                if query_id not in query_ids:
                    self.error("dangling_reference", location, f"unknown query_id: {query_id}")
            parent_query = row.get("parent_query_id", "")
            if parent_query and parent_query != "none" and parent_query not in query_ids:
                self.error("dangling_reference", location, f"unknown parent_query_id: {parent_query}")
            post_id = row.get("post_id", "")
            if post_id not in post_ids:
                self.error("dangling_reference", location, f"unknown post_id: {post_id}")
            else:
                post_row = post_by_id[post_id]
                mismatched_fields = [
                    field
                    for field in ("note_id", "account_id", "published_at")
                    if row.get(field, "") != post_row.get(field, "")
                ]
                if canonical_post_url(row.get("url")) != canonical_post_url(
                    post_row.get("url")
                ):
                    mismatched_fields.append("url")
                if mismatched_fields:
                    self.error(
                        "trend_sample_post_mismatch",
                        location,
                        "trend sample must exactly inherit post identity fields from posts.csv: "
                        + ", ".join(sorted(set(mismatched_fields))),
                    )
            if row.get("account_id", "") not in account_ids:
                self.error("dangling_reference", location, f"unknown account_id: {row.get('account_id', '')}")
            for source_id in split_ids(row.get("source_ids", "")):
                if source_id not in source_ids:
                    self.error("dangling_reference", location, f"unknown source_id: {source_id}")

        record_by_id: dict[str, dict[str, object]] = {}
        by_template: dict[str, list[dict[str, object]]] = {}
        for index, row in enumerate(self.trend_candidates, start=1):
            location = f"trend-template-candidates.jsonl:{index}"
            missing = sorted(TREND_CANDIDATE_FIELDS - set(row))
            extra = sorted(set(row) - TREND_CANDIDATE_FIELDS)
            if missing or extra:
                details = []
                if missing:
                    details.append("missing fields: " + ", ".join(missing))
                if extra:
                    details.append("unknown fields: " + ", ".join(extra))
                self.error("trend_candidate_schema", location, "; ".join(details))
                continue
            record_id = row.get("candidate_record_id")
            template_id = row.get("template_id")
            family_id = row.get("family_id")
            if not isinstance(record_id, str) or not record_id:
                self.error("trend_candidate_schema", location, "candidate_record_id must be non-empty")
                continue
            if record_id in record_by_id:
                self.error("duplicate_id", location, f"duplicate candidate_record_id: {record_id}")
            record_by_id[record_id] = row
            if isinstance(template_id, str) and template_id:
                by_template.setdefault(template_id, []).append(row)
            else:
                self.error("trend_candidate_schema", location, "template_id must be non-empty")
            if not isinstance(family_id, str) or not family_id:
                self.error("trend_candidate_schema", location, "family_id must be non-empty")
            if row.get("record_type") != "trend_template_candidate" or row.get("schema_version") != 1:
                self.error(
                    "trend_candidate_schema",
                    location,
                    "record_type/schema_version must be trend_template_candidate/1",
                )
            if row.get("run_id") != self.run.get("run_id"):
                self.error("trend_run_mismatch", location, "candidate run_id must match run.yaml")
            version = row.get("candidate_version")
            if not isinstance(version, int) or isinstance(version, bool) or version < 1:
                self.error("trend_version_invalid", location, "candidate_version must be a positive integer")
            supplied_hash = row.get("record_sha256")
            calculated_hash = canonical_json_sha256(row, "record_sha256")
            if not isinstance(supplied_hash, str) or supplied_hash.lower() != calculated_hash:
                self.error("trend_record_hash_mismatch", location, "record_sha256 does not match canonical record")

            replication = row.get("replication_status")
            lifecycle = row.get("lifecycle_phase")
            decision = row.get("decision")
            rights = row.get("rights_status")
            safety = row.get("safety_status")
            supply = row.get("supply_origin")
            scope = row.get("performance_evidence_scope")
            if replication not in TREND_REPLICATION_STATUSES:
                self.error("invalid_trend_candidate_enum", location, f"invalid replication_status: {replication}")
            if lifecycle not in TREND_LIFECYCLE_PHASES:
                self.error("invalid_trend_candidate_enum", location, f"invalid lifecycle_phase: {lifecycle}")
            if decision not in TREND_DECISIONS:
                self.error("invalid_trend_candidate_enum", location, f"invalid decision: {decision}")
            if rights not in TREND_RIGHTS_STATUSES:
                self.error("invalid_trend_candidate_enum", location, f"invalid rights_status: {rights}")
            if safety not in TREND_SAFETY_STATUSES:
                self.error("invalid_trend_candidate_enum", location, f"invalid safety_status: {safety}")
            if supply not in TREND_SUPPLY_ORIGINS:
                self.error("invalid_trend_candidate_enum", location, f"invalid supply_origin: {supply}")
            if scope not in TREND_ALLOWED_PERFORMANCE_SCOPES:
                self.error(
                    "trend_performance_scope",
                    location,
                    "template candidate cannot self-declare first-party traffic validation",
                )

            array_fields = (
                "aliases",
                "template_types",
                "discovery_queries",
                "discovery_lanes",
                "source_sample_ids",
                "support_sample_ids",
                "counterexample_sample_ids",
                "boundary_sample_ids",
                "category_scopes",
                "carrier_scopes",
                "primary_job_scopes",
                "traffic_stage_scopes",
                "supply_origin_evidence_ids",
                "window_comparisons",
                "required_material_codes",
                "optional_material_codes",
                "contraindications",
                "authorized_asset_ids",
                "source_asset_hashes",
                "limitations",
            )
            for field in array_fields:
                if not isinstance(row.get(field), list):
                    self.error("trend_candidate_schema", location, f"{field} must be an array")

            lanes = row.get("discovery_lanes", [])
            if isinstance(lanes, list) and any(item not in TREND_DISCOVERY_LANES for item in lanes):
                self.error("invalid_trend_candidate_enum", location, "discovery_lanes contains an unknown value")
            if replication in {"observed", "replicated"} and not lanes:
                self.error("trend_discovery_evidence", location, "observed candidates require a discovery lane")
            queries = row.get("discovery_queries", [])
            if isinstance(queries, list):
                for item in queries:
                    if not isinstance(item, dict) or not {
                        "query_id",
                        "parent_query_id",
                        "round",
                        "source",
                    }.issubset(item):
                        self.error(
                            "trend_discovery_evidence",
                            location,
                            "each discovery query requires query_id, parent_query_id, round, and source",
                        )
                        continue
                    if item.get("query_id") not in query_ids:
                        self.error("dangling_reference", location, f"unknown discovery query: {item.get('query_id')}")
                    parent = item.get("parent_query_id")
                    if parent not in {None, "none"} and parent not in query_ids:
                        self.error("dangling_reference", location, f"unknown discovery parent query: {parent}")
                    if item.get("round") not in {1, 2, 3, 4}:
                        self.error("invalid_trend_query_round", location, "discovery query round must be 1-4")

            role_fields = {
                "source_sample_ids": "seed",
                "support_sample_ids": "support",
                "counterexample_sample_ids": "counterexample",
                "boundary_sample_ids": "boundary",
            }
            role_sets: dict[str, set[str]] = {}
            referenced_samples: list[dict[str, str]] = []
            for field, expected_role in role_fields.items():
                values = row.get(field, [])
                value_set = set(values) if isinstance(values, list) else set()
                role_sets[field] = value_set
                for sample_id in value_set:
                    sample_row = sample_by_id.get(str(sample_id))
                    if sample_row is None:
                        self.error("dangling_reference", location, f"unknown sample ID: {sample_id}")
                        continue
                    referenced_samples.append(sample_row)
                    if sample_row.get("evidence_role") != expected_role:
                        self.error(
                            "trend_sample_role_mismatch",
                            location,
                            f"{sample_id} must have evidence_role={expected_role}",
                        )
                    if sample_row.get("template_id") != template_id or sample_row.get("family_id") != family_id:
                        self.error(
                            "trend_sample_scope_mismatch",
                            location,
                            f"{sample_id} template/family does not match candidate",
                        )
            role_names = list(role_sets)
            for position, left in enumerate(role_names):
                for right in role_names[position + 1 :]:
                    overlap = role_sets[left] & role_sets[right]
                    if overlap:
                        self.error(
                            "trend_sample_role_overlap",
                            location,
                            f"sample IDs cannot occupy two evidence roles: {sorted(overlap)}",
                        )

            referenced_identity_rows = [
                sample_by_id[sample_id]
                for value_set in role_sets.values()
                for sample_id in value_set
                if sample_id in sample_by_id
            ]
            for identity_name, identity_value in (
                ("post_id", lambda item: item.get("post_id", "")),
                ("note_id", lambda item: item.get("note_id", "")),
                ("canonical_url", lambda item: canonical_post_url(item.get("url"))),
            ):
                identities = [
                    identity_value(item)
                    for item in referenced_identity_rows
                    if identity_value(item)
                ]
                duplicates = sorted(
                    value for value, count in Counter(identities).items() if count > 1
                )
                if duplicates:
                    self.error(
                        "trend_post_role_overlap",
                        location,
                        f"one post cannot occupy multiple trend evidence rows ({identity_name}): {duplicates}",
                    )

            support_rows = [
                sample_by_id[sample_id]
                for sample_id in role_sets["support_sample_ids"]
                if sample_id in sample_by_id
                and not sample_by_id[sample_id].get("duplicate_of", "")
            ]
            unique_accounts = {
                item.get("account_id", "") for item in support_rows if item.get("account_id", "")
            }
            unique_lineages = {
                item.get("lineage_cluster_id", "")
                for item in support_rows
                if item.get("lineage_cluster_id", "")
            }
            unique_posts = {
                item.get("note_id", "")
                or canonical_post_url(item.get("url"))
                or item.get("post_id", "")
                for item in support_rows
                if item.get("note_id", "")
                or canonical_post_url(item.get("url"))
                or item.get("post_id", "")
            }
            derived_independent = min(
                len(unique_accounts), len(unique_lineages), len(unique_posts)
            )
            if row.get("independent_account_count") != derived_independent:
                self.error(
                    "trend_independence_mismatch",
                    location,
                    "independent_account_count must be recomputed from unique support accounts, lineage clusters, and post identities",
                )
            if replication == "query_candidate":
                if any(role_sets.values()) or decision not in {"observe", "skip"} or lifecycle != "unknown":
                    self.error(
                        "trend_replication_evidence",
                        location,
                        "query_candidate cannot claim samples, lifecycle, or a production decision",
                    )
            elif replication == "observed":
                if not role_sets["source_sample_ids"] or role_sets["support_sample_ids"]:
                    self.error(
                        "trend_replication_evidence",
                        location,
                        "observed requires a seed and cannot claim independent support",
                    )
            elif replication == "replicated":
                if derived_independent < 2 or len(role_sets["support_sample_ids"]) < 2:
                    self.error(
                        "trend_replication_evidence",
                        location,
                        "replicated requires at least two independent support accounts and lineages",
                    )

            sample_window = row.get("sample_window")
            sample_window_start = None
            sample_window_end = None
            if isinstance(sample_window, dict):
                sample_window_start = parse_iso(str(sample_window.get("start", "")))
                sample_window_end = parse_iso(str(sample_window.get("end", "")))
                if (
                    not sample_window_start
                    or not sample_window_end
                    or sample_window_start > sample_window_end
                    or not sample_window.get("timezone")
                    or sample_window.get("end_inclusive") is not True
                ):
                    self.error(
                        "trend_window_mismatch",
                        location,
                        "sample_window requires valid start/end, timezone, and end_inclusive=true",
                    )
            else:
                self.error("trend_window_mismatch", location, "sample_window must be an object")

            for sample_row in referenced_samples:
                published = parse_iso(sample_row.get("published_at", ""))
                if not published:
                    self.error(
                        "trend_window_mismatch",
                        location,
                        f"referenced sample {sample_row.get('template_sample_id', '')} needs a precise published_at",
                    )
                elif sample_window_start and sample_window_end and not (
                    sample_window_start <= published <= sample_window_end
                ):
                    self.error(
                        "trend_window_mismatch",
                        location,
                        f"referenced sample {sample_row.get('template_sample_id', '')} falls outside sample_window",
                    )

            comparisons = row.get("window_comparisons", [])
            valid_comparisons: list[tuple[date, date, set[str], int]] = []
            comparison_sample_ids: list[str] = []
            if isinstance(comparisons, list):
                for comparison_index, comparison in enumerate(comparisons, start=1):
                    if not isinstance(comparison, dict) or not {
                        "start",
                        "end",
                        "support_sample_ids",
                        "independent_derivatives",
                    }.issubset(comparison):
                        self.error(
                            "trend_lifecycle_evidence",
                            location,
                            f"window_comparisons[{comparison_index}] requires start, end, support_sample_ids, and independent_derivatives",
                        )
                        continue
                    comparison_start = parse_iso(str(comparison.get("start", "")))
                    comparison_end = parse_iso(str(comparison.get("end", "")))
                    comparison_ids = comparison.get("support_sample_ids")
                    declared_count = comparison.get("independent_derivatives")
                    if (
                        not comparison_start
                        or not comparison_end
                        or comparison_start > comparison_end
                        or not isinstance(comparison_ids, list)
                        or not comparison_ids
                        or not isinstance(declared_count, int)
                        or isinstance(declared_count, bool)
                        or declared_count < 1
                    ):
                        self.error(
                            "trend_lifecycle_evidence",
                            location,
                            f"window_comparisons[{comparison_index}] contains an invalid window, sample list, or count",
                        )
                        continue
                    if sample_window_start and sample_window_end and not (
                        sample_window_start <= comparison_start <= comparison_end <= sample_window_end
                    ):
                        self.error(
                            "trend_lifecycle_evidence",
                            location,
                            f"window_comparisons[{comparison_index}] falls outside sample_window",
                        )
                    comparison_id_set = {str(value) for value in comparison_ids}
                    comparison_sample_ids.extend(comparison_id_set)
                    unknown_or_wrong_role = sorted(
                        comparison_id_set - role_sets["support_sample_ids"]
                    )
                    if unknown_or_wrong_role:
                        self.error(
                            "trend_lifecycle_evidence",
                            location,
                            f"window_comparisons[{comparison_index}] has non-support sample IDs: {unknown_or_wrong_role}",
                        )
                        continue
                    comparison_rows = [sample_by_id[value] for value in comparison_id_set]
                    dates_match = True
                    for comparison_row in comparison_rows:
                        published = parse_iso(comparison_row.get("published_at", ""))
                        if not published or not comparison_start <= published <= comparison_end:
                            dates_match = False
                            self.error(
                                "trend_lifecycle_evidence",
                                location,
                                f"{comparison_row.get('template_sample_id', '')} is not dated inside window_comparisons[{comparison_index}]",
                            )
                    comparison_accounts = {
                        item.get("account_id", "")
                        for item in comparison_rows
                        if item.get("account_id", "")
                    }
                    comparison_lineages = {
                        item.get("lineage_cluster_id", "")
                        for item in comparison_rows
                        if item.get("lineage_cluster_id", "")
                    }
                    comparison_posts = {
                        item.get("note_id", "")
                        or canonical_post_url(item.get("url"))
                        or item.get("post_id", "")
                        for item in comparison_rows
                    }
                    derived_count = min(
                        len(comparison_accounts),
                        len(comparison_lineages),
                        len(comparison_posts),
                    )
                    if declared_count != derived_count:
                        self.error(
                            "trend_lifecycle_evidence",
                            location,
                            f"window_comparisons[{comparison_index}] independent_derivatives must equal {derived_count}",
                        )
                    if dates_match and declared_count == derived_count:
                        valid_comparisons.append(
                            (
                                comparison_start,
                                comparison_end,
                                comparison_id_set,
                                derived_count,
                            )
                        )
            if lifecycle != "unknown":
                if len(valid_comparisons) < 2:
                    self.error(
                        "trend_lifecycle_evidence",
                        location,
                        f"{lifecycle} requires at least two valid comparable window observations",
                    )
                duplicate_window_samples = sorted(
                    value
                    for value, count in Counter(comparison_sample_ids).items()
                    if count > 1
                )
                if duplicate_window_samples:
                    self.error(
                        "trend_lifecycle_evidence",
                        location,
                        "support samples cannot be reused across lifecycle windows: "
                        + ", ".join(duplicate_window_samples),
                    )
                if set(comparison_sample_ids) != role_sets["support_sample_ids"]:
                    self.error(
                        "trend_lifecycle_evidence",
                        location,
                        "lifecycle windows must partition every candidate support sample exactly once",
                    )
                ordered = sorted(valid_comparisons, key=lambda item: (item[0], item[1]))
                if any(left[1] >= right[0] for left, right in zip(ordered, ordered[1:])):
                    self.error(
                        "trend_lifecycle_evidence",
                        location,
                        "lifecycle comparison windows must be ordered and non-overlapping",
                    )
                if len(ordered) >= 2:
                    previous_count = ordered[-2][3]
                    latest_count = ordered[-1][3]
                    if lifecycle == "rising" and latest_count < previous_count:
                        self.error(
                            "trend_lifecycle_evidence",
                            location,
                            "rising cannot have fewer independent derivatives in the latest window",
                        )
                    if lifecycle == "fatigued" and latest_count >= previous_count:
                        self.error(
                            "trend_lifecycle_evidence",
                            location,
                            "fatigued requires fewer independent derivatives in the latest window",
                        )
            if replication != "replicated" and lifecycle != "unknown":
                self.error(
                    "trend_lifecycle_evidence",
                    location,
                    "non-replicated candidates must keep lifecycle_phase=unknown",
                )

            slot_map = row.get("slot_map")
            if not isinstance(slot_map, dict) or not {"fixed", "replaceable", "new_semantic_contribution"}.issubset(slot_map):
                self.error(
                    "trend_slot_map",
                    location,
                    "slot_map requires fixed, replaceable, and new_semantic_contribution",
                )
            production_decision = decision in {"shoot", "adapt"}
            if production_decision:
                if replication != "replicated" or lifecycle not in {
                    "rising",
                    "mature",
                    "evergreen_carrier",
                }:
                    self.error(
                        "trend_decision_not_eligible",
                        location,
                        "shoot/adapt requires replicated evidence and a live or evergreen lifecycle",
                    )
                if not role_sets["counterexample_sample_ids"]:
                    self.error(
                        "trend_decision_not_eligible",
                        location,
                        "shoot/adapt requires at least one independent counterexample",
                    )
                if rights not in {"grammar_only", "authorized_assets"}:
                    self.error("trend_rights_gate", location, "shoot/adapt requires a cleared rights status")
                if safety != "passed":
                    self.error("trend_safety_gate", location, "shoot/adapt requires safety_status=passed")
                for sample_row in referenced_samples:
                    if (
                        sample_row.get("capture_status") != "complete"
                        or sample_row.get("access_status") != "full"
                        or not valid_sha256(sample_row.get("source_snapshot_sha256"))
                    ):
                        self.error(
                            "trend_replay_evidence",
                            location,
                            "shoot/adapt requires complete referenced samples with a replayable snapshot hash",
                        )
                for field in (
                    "category_scopes",
                    "carrier_scopes",
                    "primary_job_scopes",
                    "traffic_stage_scopes",
                ):
                    if not isinstance(row.get(field), list) or not row.get(field):
                        self.error("trend_retrieval_scope", location, f"shoot/adapt requires {field}")
                if isinstance(slot_map, dict):
                    if not slot_map.get("fixed") or not slot_map.get("replaceable"):
                        self.error("trend_slot_map", location, "shoot/adapt requires fixed and replaceable slots")
                    contribution = slot_map.get("new_semantic_contribution")
                    if not isinstance(contribution, str) or contribution in {"", "none", "unknown"}:
                        self.error("trend_slot_map", location, "shoot/adapt requires a new semantic contribution")
                run_start = parse_iso(self.run.get("window_start", ""))
                run_end = parse_iso(self.run.get("window_end", ""))
                if (
                    not sample_window_start
                    or not sample_window_end
                    or (run_start and sample_window_start > run_start)
                    or (run_end and sample_window_end < run_end)
                ):
                    self.error(
                        "trend_window_mismatch",
                        location,
                        "production candidate sample_window must cover the run window",
                    )
                latest_comparison_end = max(
                    (item[1] for item in valid_comparisons), default=None
                )
                if run_end and (
                    latest_comparison_end is None or latest_comparison_end < run_end
                ):
                    self.error(
                        "trend_window_mismatch",
                        location,
                        "production lifecycle evidence must include a comparison window ending on or after run window_end",
                    )
                if row.get("last_refreshed_at") != self.run.get("created_at"):
                    self.error(
                        "trend_refresh_mismatch",
                        location,
                        "shoot/adapt candidate must be refreshed on the current run date",
                    )
            if rights == "authorized_assets":
                assets = row.get("authorized_asset_ids", [])
                hashes = row.get("source_asset_hashes", [])
                if not isinstance(assets, list) or not assets or not isinstance(hashes, list) or not hashes:
                    self.error(
                        "trend_rights_gate",
                        location,
                        "authorized_assets requires asset IDs and source asset hashes",
                    )
                elif any(not isinstance(value, str) or not valid_sha256(value) for value in hashes):
                    self.error("trend_rights_gate", location, "source_asset_hashes must be SHA-256 values")
                else:
                    current_authorizations = {
                        item.get("material_id", ""): item
                        for item in self.rows.get("authorization-log.csv", [])
                        if item.get("material_id", "")
                        and self._authorization_is_current(item)
                        and item.get("commercial_use") == "approved"
                        and set(split_ids(item.get("permission_scope"))).intersection(
                            {"adaptation", "verbatim"}
                        )
                    }
                    missing_assets = sorted(set(assets) - set(current_authorizations))
                    expected_hashes = {
                        current_authorizations[asset_id].get("material_sha256", "").lower()
                        for asset_id in assets
                        if asset_id in current_authorizations
                    }
                    if missing_assets or set(value.lower() for value in hashes) != expected_hashes:
                        self.error(
                            "trend_rights_gate",
                            location,
                            "authorized_asset_ids/source_asset_hashes must exactly resolve to current approved authorization-log material records",
                        )

        for template_id, records in by_template.items():
            if len(records) != 1:
                self.error(
                    "trend_version_invalid",
                    "trend-template-candidates.jsonl",
                    f"run-local candidate snapshot must contain exactly one current record for {template_id}",
                )
            for item in records:
                version = item.get("candidate_version")
                supersedes = item.get("supersedes_candidate_record_id")
                if version == 1 and supersedes is not None:
                    self.error(
                        "trend_version_invalid",
                        str(item.get("candidate_record_id")),
                        "version 1 must not supersede another record",
                    )
                if isinstance(version, int) and version > 1:
                    if not isinstance(supersedes, str) or not supersedes:
                        self.error(
                            "trend_version_invalid",
                            str(item.get("candidate_record_id")),
                            "each later version must reference its prior immutable candidate_record_id",
                        )

    def _check_rows(self) -> None:
        for name, rows in self.rows.items():
            id_field = ID_FIELDS[name]
            seen_ids: dict[str, int] = {}
            for index, row in enumerate(rows, start=2):
                location = f"{name}:{index}"
                for field in sorted(REQUIRED_ROW_FIELDS[name]):
                    if not row.get(field, ""):
                        self.error("missing_value", location, f"{field} is required")
                row_id = row.get(id_field, "")
                if row_id:
                    if row_id in seen_ids:
                        self.error(
                            "duplicate_id",
                            location,
                            f"{row_id} duplicates row {seen_ids[row_id]}",
                        )
                    else:
                        seen_ids[row_id] = index

            for url_field in ("url", "profile_url"):
                seen_urls: dict[str, int] = {}
                for index, row in enumerate(rows, start=2):
                    value = row.get(url_field, "")
                    if not value:
                        continue
                    if not re.match(r"^https?://", value):
                        self.error("invalid_url", f"{name}:{index}", f"invalid {url_field}: {value}")
                    normalized = value.rstrip("/")
                    if normalized in seen_urls:
                        self.error(
                            "duplicate_url",
                            f"{name}:{index}",
                            f"{value} duplicates row {seen_urls[normalized]}",
                        )
                    else:
                        seen_urls[normalized] = index

    def _check_dates(self) -> None:
        run_date = parse_iso(self.run.get("created_at", ""))
        for index, row in enumerate(self.rows.get("query-log.csv", []), start=2):
            location = f"query-log.csv:{index}"
            observed = parse_dateish(row.get("run_at", ""))
            if observed is None:
                self.error("invalid_date", location, "run_at must be an ISO date or timestamp")
            elif run_date and observed > run_date:
                self.error("future_date", location, "run_at cannot be after the run date")

        for index, row in enumerate(self.rows.get("source-log.csv", []), start=2):
            location = f"source-log.csv:{index}"
            collected = parse_iso(row.get("collected_at", ""))
            published_raw = row.get("published_at", "")
            published = parse_partial_iso(published_raw) if published_raw else None
            if collected is None:
                self.error("invalid_date", location, "collected_at must be YYYY-MM-DD")
            elif run_date and collected > run_date:
                self.error("future_date", location, "collected_at cannot be after the run date")
            if published_raw and published is None:
                self.error(
                    "invalid_date",
                    location,
                    "published_at must be YYYY, YYYY-MM, YYYY-MM-DD, or blank",
                )
            if published and collected and published > collected:
                self.error("invalid_date_order", location, "published_at cannot be after collected_at")

        for index, row in enumerate(self.rows.get("accounts.csv", []), start=2):
            location = f"accounts.csv:{index}"
            start = parse_iso(row.get("window_start", ""))
            end = parse_iso(row.get("window_end", ""))
            collected = parse_iso(row.get("collected_at", ""))
            if start is None or end is None or collected is None:
                self.error(
                    "invalid_date",
                    location,
                    "window_start, window_end, and collected_at must be YYYY-MM-DD",
                )
            if start and end and start > end:
                self.error("invalid_date_order", location, "window_start cannot be after window_end")
            if end and collected and end > collected:
                self.error(
                    "invalid_date_order",
                    location,
                    "window_end cannot be after collected_at",
                )
            if end and run_date and end > run_date:
                self.error("future_date", location, "window_end cannot be after the run date")
            if collected and run_date and collected > run_date:
                self.error("future_date", location, "collected_at cannot be after the run date")

        for index, row in enumerate(self.rows.get("posts.csv", []), start=2):
            location = f"posts.csv:{index}"
            collected = parse_iso(row.get("collected_at", ""))
            published = parse_iso(row.get("published_at", "")) if row.get("published_at") else None
            if collected is None:
                self.error("invalid_date", location, "collected_at must be YYYY-MM-DD")
            elif run_date and collected > run_date:
                self.error("future_date", location, "collected_at cannot be after the run date")
            if published and collected and published > collected:
                self.error("invalid_date_order", location, "published_at cannot be after collected_at")

        for index, row in enumerate(self.rows.get("trend-template-samples.csv", []), start=2):
            location = f"trend-template-samples.csv:{index}"
            collected = parse_iso(row.get("collected_at", ""))
            published = parse_iso(row.get("published_at", "")) if row.get("published_at") else None
            if collected is None:
                self.error("invalid_date", location, "collected_at must be YYYY-MM-DD")
            elif run_date and collected > run_date:
                self.error("future_date", location, "collected_at cannot be after the run date")
            if published and collected and published > collected:
                self.error("invalid_date_order", location, "published_at cannot be after collected_at")

        for index, row in enumerate(self.rows.get("topics.csv", []), start=2):
            location = f"topics.csv:{index}"
            last_seen = parse_iso(row.get("last_seen_at", ""))
            if last_seen is None:
                self.error("invalid_date", location, "last_seen_at must be YYYY-MM-DD")
            elif run_date and last_seen > run_date:
                self.error("future_date", location, "last_seen_at cannot be after the run date")

        for index, row in enumerate(self.rows.get("authorization-log.csv", []), start=2):
            location = f"authorization-log.csv:{index}"
            granted = parse_iso(row.get("granted_at", ""))
            verified = parse_iso(row.get("verified_at", ""))
            expires_raw = row.get("expires_at", "")
            expires = parse_iso(expires_raw) if expires_raw else None
            if granted is None or verified is None or (expires_raw and expires is None):
                self.error(
                    "invalid_authorization_date",
                    location,
                    "granted_at/verified_at and optional expires_at must be YYYY-MM-DD",
                )
            if granted and verified and granted > verified:
                self.error(
                    "invalid_date_order",
                    location,
                    "granted_at cannot be after verified_at",
                )
            if granted and expires and expires < granted:
                self.error(
                    "invalid_date_order",
                    location,
                    "expires_at cannot be before granted_at",
                )
            if run_date and verified and verified > run_date:
                self.error("future_date", location, "verified_at cannot be after the run date")

    def _id_set(self, filename: str) -> set[str]:
        field = ID_FIELDS[filename]
        return {row.get(field, "") for row in self.rows.get(filename, []) if row.get(field, "")}

    def _check_id_refs(
        self,
        filename: str,
        field: str,
        known: set[str],
        *,
        required: bool = False,
    ) -> None:
        for index, row in enumerate(self.rows.get(filename, []), start=2):
            refs = split_ids(row.get(field))
            if required and not refs:
                self.error("missing_reference", f"{filename}:{index}", f"{field} is empty")
            for ref in refs:
                if ref not in known:
                    self.error(
                        "dangling_reference",
                        f"{filename}:{index}",
                        f"{field} references unknown id {ref}",
                    )

    def _check_references(self) -> None:
        query_ids = self._id_set("query-log.csv")
        source_ids = self._id_set("source-log.csv")
        account_ids = self._id_set("accounts.csv")
        post_ids = self._id_set("posts.csv")
        claim_ids = self._id_set("claim-ledger.csv")
        authorization_ids = self._id_set("authorization-log.csv")

        self._check_id_refs("source-log.csv", "query_id", query_ids)
        self._check_id_refs("query-log.csv", "selected_source_ids", source_ids)
        if "accounts.csv" in self.rows:
            self._check_id_refs("query-log.csv", "selected_account_ids", account_ids)
            self._check_id_refs("accounts.csv", "source_ids", source_ids, required=True)
        if "posts.csv" in self.rows:
            self._check_id_refs("query-log.csv", "selected_post_ids", post_ids)
            self._check_id_refs("posts.csv", "account_id", account_ids, required=True)
            self._check_id_refs("posts.csv", "queries_matched", query_ids, required=True)
        self._check_id_refs("claim-ledger.csv", "source_ids", source_ids, required=True)
        self._check_id_refs("claim-ledger.csv", "counter_source_ids", source_ids)
        registry_evidence = source_ids | claim_ids
        self._check_id_refs(
            "sku-registry.csv",
            "evidence_ids",
            registry_evidence,
            required=True,
        )
        self._check_id_refs(
            "offer-registry.csv",
            "evidence_ids",
            registry_evidence,
            required=True,
        )
        for filename in ("sku-registry.csv", "offer-registry.csv"):
            self._check_id_refs(filename, "platform_ticket", source_ids)
            self._check_id_refs(filename, "qualification_claim_id", claim_ids)
        self._check_id_refs("acquisition-channels.csv", "consent_ids", authorization_ids)
        evidence_ids = source_ids | account_ids | post_ids | claim_ids
        self._check_id_refs("topics.csv", "evidence_ids", evidence_ids, required=True)

    def _check_sources(self) -> None:
        for index, row in enumerate(self.rows.get("source-log.csv", []), start=2):
            location = f"source-log.csv:{index}"
            layer = row.get("source_layer", "")
            access = row.get("access_status", "")
            grade = row.get("evidence_grade", "")
            if layer not in SOURCE_LAYERS:
                self.error("invalid_enum", location, f"unknown source_layer: {layer}")
            if access not in ACCESS_STATUSES:
                self.error("invalid_enum", location, f"unknown access_status: {access}")
            if grade not in EVIDENCE_GRADES:
                self.error("invalid_enum", location, f"unknown evidence_grade: {grade}")
            if (
                grade in EVIDENCE_GRADES
                and layer in SOURCE_LAYER_MIN_GRADE_RANK
                and access in ACCESS_MIN_GRADE_RANK
            ):
                minimum_rank = max(
                    SOURCE_LAYER_MIN_GRADE_RANK[layer],
                    ACCESS_MIN_GRADE_RANK[access],
                )
                if EVIDENCE_GRADE_RANK[grade] < minimum_rank:
                    minimum_grade = next(
                        item for item, rank in EVIDENCE_GRADE_RANK.items() if rank == minimum_rank
                    )
                    self.error(
                        "source_grade_conflict",
                        location,
                        f"{layer}/{access} source cannot exceed grade {minimum_grade}",
                    )

    def _check_claims(self) -> None:
        run_date = parse_iso(self.run.get("created_at", ""))
        sources = {
            row.get("source_id", ""): row
            for row in self.rows.get("source-log.csv", [])
            if row.get("source_id", "")
        }
        for index, row in enumerate(self.rows.get("claim-ledger.csv", []), start=2):
            location = f"claim-ledger.csv:{index}"
            grade = row.get("evidence_grade", "")
            status = row.get("claim_status", "")
            verification_class = row.get("verification_class", "")
            runtime_claim = verification_class == "current_runtime"
            if verification_class not in VERIFICATION_CLASSES:
                self.error(
                    "invalid_enum",
                    location,
                    f"invalid verification_class: {verification_class}",
                )
            if (
                (
                    claim_requires_runtime_verification(row.get("category"))
                    or claim_text_requires_runtime_verification(row.get("claim_text"))
                )
                and verification_class
                and verification_class != "current_runtime"
            ):
                self.error(
                    "verification_class_conflict",
                    location,
                    "category appears runtime-sensitive; explicitly classify it current_runtime or rename it as a bounded historical claim",
                )
            if verification_class == "hypothesis" and status not in {"hypothesis", "unknown"}:
                self.error(
                    "verification_class_conflict",
                    location,
                    "verification_class=hypothesis requires claim_status hypothesis or unknown",
                )
            if grade not in EVIDENCE_GRADES:
                self.error("invalid_enum", location, f"unknown evidence_grade: {grade}")
            if status not in CLAIM_STATUSES:
                self.error("invalid_enum", location, f"unknown claim_status: {status}")
            if status == "confirmed" and grade in {"C", "D"}:
                self.error(
                    "grade_status_conflict",
                    location,
                    f"grade {grade} cannot support confirmed status",
                )
            if grade == "D" and status == "supported_experience":
                self.error(
                    "grade_status_conflict",
                    location,
                    "grade D cannot be promoted to supported_experience",
                )
            supporting_sources = [
                sources[source_id]
                for source_id in split_ids(row.get("source_ids"))
                if source_id in sources
            ]
            eligible_confirmed_layers = (
                {"official"} if runtime_claim else CONFIRMED_SOURCE_LAYERS
            )
            if status == "confirmed" and not any(
                source.get("source_layer") in eligible_confirmed_layers
                and source.get("access_status") in {"full", "partial"}
                and source.get("evidence_grade") in {"A", "B"}
                and (
                    not runtime_claim
                    or (run_date and parse_iso(source.get("collected_at", "")) == run_date)
                )
                for source in supporting_sources
            ):
                self.error(
                    "confirmed_source_conflict",
                    location,
                    "confirmed current claims require a same-run official A/B source; other confirmed claims require accessible official, engineering, or academic A/B evidence",
                )
            supporting_grades = [
                source.get("evidence_grade", "")
                for source in supporting_sources
                if source.get("evidence_grade", "") in EVIDENCE_GRADES
            ]
            if grade in EVIDENCE_GRADES and supporting_grades:
                best_source_grade = min(
                    supporting_grades,
                    key=lambda item: EVIDENCE_GRADE_RANK[item],
                )
                if EVIDENCE_GRADE_RANK[grade] < EVIDENCE_GRADE_RANK[best_source_grade]:
                    self.error(
                        "grade_source_conflict",
                        location,
                        f"claim grade {grade} exceeds best supporting source grade {best_source_grade}",
                    )
            verified = parse_iso(row.get("last_verified_at", ""))
            if not claim_scope_is_specific(row.get("scope")):
                self.error(
                    "invalid_claim_scope",
                    location,
                    "claim scope must identify a concrete module, entry point, time, or content/commercial surface",
                )
            if verified is None:
                self.error("invalid_date", location, "last_verified_at must be YYYY-MM-DD")
            elif run_date and verified > run_date:
                self.error(
                    "future_date",
                    location,
                    "last_verified_at cannot be after the run date",
                )
            elif (
                run_date
                and runtime_claim
                and verified != run_date
            ):
                self.error(
                    "not_verified_this_run",
                    location,
                    "current rules and platform capabilities must be verified in this run",
                )
            if runtime_claim and run_date and not any(
                parse_iso(source.get("collected_at", "")) == run_date
                and source.get("access_status") in {"full", "partial"}
                for source in supporting_sources
            ):
                self.error(
                    "current_source_not_refreshed",
                    location,
                    "runtime rule/law/policy claim needs at least one accessible supporting source collected in this run",
                )

    def _check_accounts_and_posts(self) -> None:
        sources = {
            row.get("source_id", ""): row
            for row in self.rows.get("source-log.csv", [])
            if row.get("source_id", "")
        }
        for index, row in enumerate(self.rows.get("accounts.csv", []), start=2):
            location = f"accounts.csv:{index}"
            if row.get("confidence") not in CONFIDENCES:
                self.error("invalid_enum", location, "confidence must be high, medium, or low")
            head_types = set(split_ids(row.get("head_type")))
            if not head_types or not head_types.issubset(HEAD_TYPES):
                self.error("invalid_enum", location, f"invalid head_type: {row.get('head_type')}")
            if row.get("commercial_distance") not in COMMERCIAL_DISTANCES:
                self.error(
                    "invalid_enum",
                    location,
                    f"invalid commercial_distance: {row.get('commercial_distance')}",
                )
            if row.get("status") not in ACCOUNT_STATUSES:
                self.error("invalid_enum", location, f"invalid account status: {row.get('status')}")
            if row.get("status") in {"candidate", "focus"} and not any(
                source_id in sources
                and self._source_supports_account_sample(sources[source_id], row)
                for source_id in split_ids(row.get("source_ids"))
            ):
                self.error(
                    "account_source_mismatch",
                    location,
                    "candidate/focus account needs an accessible account/profile source whose URL matches profile_url",
                )
            sample = row.get("recent_sample_n", "")
            if sample and (not sample.isdigit() or int(sample) < 0):
                self.error("invalid_number", location, "recent_sample_n must be a non-negative integer")
            sample_n = int(sample) if sample.isdigit() else None
            if sample_n == 0 and (
                row.get("status") == "focus" or row.get("confidence") == "high"
            ):
                self.error(
                    "account_sample_conflict",
                    location,
                    "focus or high-confidence account cannot have a zero recent sample",
                )
            if "scale" in head_types and not re.search(
                r"\d", row.get("follower_count", "")
            ):
                self.error(
                    "missing_scale_metric",
                    location,
                    "scale head_type requires an observed follower_count containing a visible numeric value; otherwise remove scale",
                )
            numeric: dict[str, float] = {}
            for field in (
                "recent_median_visible_engagement",
                "recent_max_visible_engagement",
                "outlier_multiple",
            ):
                raw = row.get(field, "")
                if not raw:
                    continue
                try:
                    value = float(raw.replace(",", ""))
                except ValueError:
                    self.error("invalid_number", location, f"{field} must be numeric or blank")
                    continue
                if not math.isfinite(value) or value < 0:
                    self.error(
                        "invalid_number",
                        location,
                        f"{field} must be a finite non-negative number",
                    )
                    continue
                numeric[field] = value
            median = numeric.get("recent_median_visible_engagement")
            maximum = numeric.get("recent_max_visible_engagement")
            multiple = numeric.get("outlier_multiple")
            if median is not None and maximum is not None and maximum < median:
                self.error(
                    "invalid_baseline_order",
                    location,
                    "recent_max_visible_engagement cannot be below the recent median",
                )
            if median == 0 and multiple is not None:
                self.error(
                    "outlier_mismatch",
                    location,
                    "outlier_multiple must be blank when the median is zero",
                )
            elif median and maximum is not None and multiple is not None:
                expected = maximum / median
                if abs(multiple - expected) > max(0.01, expected * 0.01):
                    self.error(
                        "outlier_mismatch",
                        location,
                        f"outlier_multiple {multiple:g} does not match max/median {expected:g}",
                    )

            if (
                "recent_performance" in head_types
                and row.get("status") in {"candidate", "focus"}
                and (
                    sample_n is None
                    or sample_n <= 0
                    or not all(
                        field in numeric
                        for field in (
                            "recent_median_visible_engagement",
                            "recent_max_visible_engagement",
                            "outlier_multiple",
                        )
                    )
                )
            ):
                self.error(
                    "missing_performance_baseline",
                    location,
                    "recent_performance candidate/focus requires a positive recent sample plus numeric median, max, and outlier_multiple; otherwise remove that head_type",
                )

        note_ids: dict[str, int] = {}
        for index, row in enumerate(self.rows.get("posts.csv", []), start=2):
            location = f"posts.csv:{index}"
            if row.get("evidence_level") not in EVIDENCE_LEVELS:
                self.error("invalid_enum", location, f"invalid evidence_level: {row.get('evidence_level')}")
            if row.get("confidence") not in CONFIDENCES:
                self.error("invalid_enum", location, "confidence must be high, medium, or low")
            note_id = row.get("note_id", "")
            if note_id:
                if note_id in note_ids:
                    self.error(
                        "duplicate_note_id",
                        location,
                        f"{note_id} duplicates row {note_ids[note_id]}",
                    )
                else:
                    note_ids[note_id] = index
            published = row.get("published_at", "")
            date_confidence = row.get("date_confidence", "")
            if published and parse_iso(published) is None:
                self.error("invalid_date", location, "published_at must be YYYY-MM-DD or blank")
            if date_confidence not in {"high", "medium", "low", "unknown"}:
                self.error("invalid_enum", location, f"invalid date_confidence: {date_confidence}")
            if row.get("status") not in POST_STATUSES:
                self.error("invalid_enum", location, f"invalid post status: {row.get('status')}")
            if self._is_v2():
                performance_tier = row.get("performance_tier", "")
                if performance_tier not in V2_PERFORMANCE_TIERS:
                    self.error(
                        "invalid_v2_style_enum",
                        location,
                        f"invalid performance_tier: {performance_tier}",
                    )
                capture_status = row.get("style_capture_status", "")
                if capture_status not in V2_STYLE_CAPTURE_STATUSES:
                    self.error(
                        "invalid_v2_style_enum",
                        location,
                        f"invalid style_capture_status: {capture_status}",
                    )
                if capture_status == "complete" and not (
                    row.get("style_library_post_id", "").strip()
                    and row.get("style_observation_ids", "").strip()
                ):
                    self.error(
                        "incomplete_style_capture",
                        location,
                        "complete style capture requires library post and observation IDs",
                    )
                if capture_status in {"partial", "skipped", "not_required"} and not row.get(
                    "style_skip_reason", ""
                ).strip():
                    self.error(
                        "missing_style_skip_reason",
                        location,
                        f"{capture_status} style capture requires style_skip_reason",
                    )
            multiple = row.get("account_baseline_multiple", "").strip()
            if multiple:
                try:
                    value = float(multiple.replace(",", ""))
                    if not math.isfinite(value) or value < 0:
                        raise ValueError
                except ValueError:
                    self.error(
                        "invalid_number",
                        location,
                        "account_baseline_multiple must be a non-negative number or blank",
                    )

    def _check_style_capture_receipts(self) -> None:
        if not self._is_v2():
            return
        posts = self.rows.get("posts.csv", [])
        if not posts:
            return
        mode = self.run.get("mode", "")
        completed_research = (
            mode in {"discovery", "refresh"}
            and self.run.get("status") == "complete"
        )
        topic_post_ids = {
            value
            for topic in self.rows.get("topics.csv", [])
            for value in split_ids(topic.get("evidence_ids"))
        }
        required_posts = {
            row.get("post_id", "")
            for row in posts
            if row.get("status") == "active"
            and (
                row.get("performance_tier") in {"high", "low"}
                or row.get("post_id", "") in topic_post_ids
            )
        }
        if completed_research:
            for index, row in enumerate(posts, start=2):
                if (
                    row.get("post_id", "") in required_posts
                    and row.get("style_capture_status") != "complete"
                ):
                    self.error(
                        "incomplete_style_capture",
                        f"posts.csv:{index}",
                        "completed discovery/refresh requires complete copy+visual capture for every active high/low or topic-evidence post",
                    )

        captured = [row for row in posts if row.get("style_capture_status") == "complete"]
        if not captured:
            return
        raw_library_path = self.run.get("style_library_path", "").strip()
        library_path = (self.run_dir / raw_library_path).resolve()
        if not library_path.is_file():
            self.error(
                "style_capture_receipt_missing",
                "posts.csv",
                f"complete style capture requires the SQLite library: {raw_library_path}",
            )
            return
        try:
            from style_library import (  # type: ignore
                StyleLibraryError,
                _preflight_existing_database,
            )
        except ImportError as exc:
            self.error("style_capture_receipt_invalid", "posts.csv", str(exc))
            return
        try:
            if _preflight_existing_database(library_path) != 2:
                raise StyleLibraryError("schema_version_mismatch")
        except StyleLibraryError as exc:
            self.error("style_capture_receipt_invalid", "posts.csv", str(exc))
            return
        posts_csv_path = self.run_dir / "posts.csv"
        posts_csv_sha = hashlib.sha256(posts_csv_path.read_bytes()).hexdigest()
        try:
            uri_path = quote(str(library_path), safe="/")
            con = sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA query_only = ON")
            foreign_key_violations = con.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_key_violations:
                self.error(
                    "style_capture_receipt_invalid",
                    "posts.csv",
                    "style library contains foreign-key violations",
                )
                return
            for index, row in enumerate(posts, start=2):
                if row.get("style_capture_status") != "complete":
                    continue
                location = f"posts.csv:{index}"
                library_post_id = row.get("style_library_post_id", "").strip()
                style_post = con.execute(
                    "SELECT * FROM style_posts WHERE library_post_id=?",
                    (library_post_id,),
                ).fetchone()
                if style_post is None:
                    self.error(
                        "style_capture_receipt_missing",
                        location,
                        f"unknown style_library_post_id {library_post_id}",
                    )
                    continue
                identity_mismatches = []
                if str(style_post["platform"]).strip().lower() not in {
                    str(row.get("platform", "xiaohongshu")).strip().lower(),
                    "xiaohongshu", "小红书", "redbook",
                }:
                    identity_mismatches.append("platform")
                if row.get("note_id") and style_post["note_id"] != row.get("note_id"):
                    identity_mismatches.append("note_id")
                if row.get("url") and str(style_post["canonical_url"] or "").rstrip("/") != row.get(
                    "url", ""
                ).rstrip("/"):
                    identity_mismatches.append("canonical_url")
                if style_post["category"] != self.run.get("category", ""):
                    identity_mismatches.append("category")
                if identity_mismatches:
                    self.error(
                        "style_capture_receipt_mismatch",
                        location,
                        "style post identity disagrees on: "
                        + ", ".join(identity_mismatches),
                    )
                run_ref = con.execute(
                    """
                    SELECT 1 FROM run_post_refs
                    WHERE run_id=? AND run_post_id=? AND library_post_id=?
                    """,
                    (self.run.get("run_id"), row.get("post_id"), library_post_id),
                ).fetchone()
                if run_ref is None:
                    self.error(
                        "style_capture_receipt_missing",
                        location,
                        "run_post_refs does not bind this run post to the library post",
                    )
                observation = con.execute(
                    """
                    SELECT * FROM style_post_observations
                    WHERE run_id=? AND run_post_id=? AND library_post_id=?
                      AND source_csv_sha256=? AND observation_state='complete'
                    """,
                    (
                        self.run.get("run_id"), row.get("post_id"),
                        library_post_id, posts_csv_sha,
                    ),
                ).fetchone()
                if observation is None:
                    self.error(
                        "style_capture_receipt_missing",
                        location,
                        "no complete style_post_observation matches the exact posts.csv snapshot",
                    )
                elif observation["performance_tier"] != row.get("performance_tier"):
                    self.error(
                        "style_capture_receipt_mismatch",
                        location,
                        "performance_tier does not match the recomputed SQLite observation",
                    )
                observation_ids = set(split_ids(row.get("style_observation_ids")))
                if not observation_ids:
                    continue
                placeholders = ",".join("?" for _ in observation_ids)
                copy_ids = {
                    item[0]
                    for item in con.execute(
                        f"""
                        SELECT observation_id FROM copy_observations
                        WHERE library_post_id=? AND observation_id IN ({placeholders})
                        """,
                        (library_post_id, *sorted(observation_ids)),
                    ).fetchall()
                }
                visual_ids = {
                    item[0]
                    for item in con.execute(
                        f"""
                        SELECT visual_observation_id FROM visual_observations
                        WHERE library_post_id=? AND visual_observation_id IN ({placeholders})
                        """,
                        (library_post_id, *sorted(observation_ids)),
                    ).fetchall()
                }
                if copy_ids | visual_ids != observation_ids:
                    self.error(
                        "style_capture_receipt_missing",
                        location,
                        "style_observation_ids contain unknown or cross-post IDs",
                    )
                style_requirement = self.run.get("style_requirement", "both")
                missing_required_observation = (
                    (style_requirement in {"copy", "both"} and not copy_ids)
                    or (style_requirement in {"visual", "both"} and not visual_ids)
                )
                if missing_required_observation:
                    self.error(
                        "incomplete_style_capture",
                        location,
                        "complete style capture lacks the copy/visual observation required by run.style_requirement",
                    )
        except sqlite3.Error as exc:
            self.error("style_capture_receipt_invalid", "posts.csv", str(exc))
        finally:
            if "con" in locals():
                con.close()

    def _source_is_demand_sample(self, row: dict[str, str]) -> bool:
        if row.get("access_status") not in {"full", "partial"}:
            return False
        if row.get("evidence_grade") == "D":
            return False
        descriptors = source_descriptors(row)
        if descriptors & DIRECT_DEMAND_SOURCE_TOKENS:
            return True
        return row.get("source_layer") in {"creator_experience", "industry"} and bool(
            descriptors & CONTENT_SAMPLE_TOKENS
        )

    def _source_supports_account_sample(
        self,
        row: dict[str, str],
        account: dict[str, str],
    ) -> bool:
        descriptors = source_descriptors(row)
        source_url = row.get("url", "").rstrip("/")
        profile_url = account.get("profile_url", "").rstrip("/")
        return (
            row.get("access_status") in {"full", "partial"}
            and row.get("evidence_grade") != "D"
            and (
                bool(descriptors & ACCOUNT_SAMPLE_TOKENS)
                or any(
                    descriptor.endswith(("_account", "_note", "_post", "_profile"))
                    for descriptor in descriptors
                )
            )
            and bool(source_url and profile_url and source_url == profile_url)
        )

    def _post_is_usable_sample(self, row: dict[str, str]) -> bool:
        return (
            row.get("status") == "active"
            and row.get("evidence_level") in {"observed", "calculated"}
        )

    def _post_has_performance_metric(self, row: dict[str, str]) -> bool:
        visible = row.get("visible_engagement", "").strip().lower()
        if (
            visible in {"", "none", "n/a", "na", "unknown", "不可得", "未显示"}
            or not re.search(r"\d", visible)
        ):
            return False
        try:
            multiple = float(row.get("account_baseline_multiple", "").replace(",", ""))
        except ValueError:
            return False
        return math.isfinite(multiple) and multiple >= 0

    def _post_is_current_sample(
        self,
        post: dict[str, str],
        accounts: dict[str, dict[str, str]],
        sources: dict[str, dict[str, str]],
    ) -> bool:
        if not self._post_is_usable_sample(post):
            return False
        published = parse_iso(post.get("published_at", ""))
        window_start = parse_iso(self.run.get("window_start", ""))
        window_end = parse_iso(self.run.get("window_end", ""))
        if published is None or post.get("date_confidence") not in {"high", "medium"}:
            return False
        if window_start and published < window_start:
            return False
        if window_end and published > window_end:
            return False
        account = accounts.get(post.get("account_id", ""))
        return bool(
            account
            and account.get("status") in {"candidate", "focus"}
            and any(
                source_id in sources
                and self._source_supports_account_sample(sources[source_id], account)
                for source_id in split_ids(account.get("source_ids"))
            )
        )

    def _check_topics(self) -> None:
        posts = {row.get("post_id", ""): row for row in self.rows.get("posts.csv", [])}
        accounts = {
            row.get("account_id", ""): row
            for row in self.rows.get("accounts.csv", [])
            if row.get("account_id", "")
        }
        sources = {
            row.get("source_id", ""): row
            for row in self.rows.get("source-log.csv", [])
            if row.get("source_id", "")
        }
        known_counter_ids = (
            set(posts)
            | set(accounts)
            | set(sources)
            | self._id_set("claim-ledger.csv")
        )
        allowed_primary_jobs = (
            self._v2_codes("primary_job") if self._is_v2() else PRIMARY_JOBS
        )
        for index, row in enumerate(self.rows.get("topics.csv", []), start=2):
            location = f"topics.csv:{index}"
            if row.get("primary_job") not in allowed_primary_jobs:
                self.error("invalid_enum", location, f"invalid primary_job: {row.get('primary_job')}")
            if row.get("lifecycle") not in LIFECYCLES:
                self.error("invalid_enum", location, f"invalid lifecycle: {row.get('lifecycle')}")
            if row.get("status") not in TOPIC_STATUSES:
                self.error("invalid_enum", location, f"invalid topic status: {row.get('status')}")
            evidence_refs = split_ids(row.get("evidence_ids"))
            usable_posts = [
                posts[ref]
                for ref in evidence_refs
                if ref in posts and self._post_is_usable_sample(posts[ref])
            ]
            demand_sources = [
                sources[ref]
                for ref in evidence_refs
                if ref in sources and self._source_is_demand_sample(sources[ref])
            ]
            if row.get("status") == "experimental" and not (usable_posts or demand_sources):
                self.error(
                    "insufficient_topic_sample",
                    location,
                    "experimental topic needs a traceable demand or content sample",
                )
            if row.get("status") != "active":
                continue
            missing_metric_ids = [
                post.get("post_id", "")
                for post in usable_posts
                if not self._post_has_performance_metric(post)
            ]
            if missing_metric_ids:
                self.error(
                    "missing_post_metric",
                    location,
                    "active topic performance samples need visible_engagement and numeric account_baseline_multiple; mark the topic experimental if the sample is non-performance evidence: "
                    + ";".join(missing_metric_ids),
                )
            counterexamples = row.get("counterexamples", "").strip().lower()
            referenced_counter_ids = {
                counter_id
                for counter_id in known_counter_ids
                if re.search(
                    rf"(?<![A-Za-z0-9_-]){re.escape(counter_id)}(?![A-Za-z0-9_-])",
                    row.get("counterexamples", ""),
                )
            }
            if counterexamples in {"", "none", "n/a", "na", "暂无", "无"}:
                self.error(
                    "missing_counterexample",
                    location,
                    "active topic requires at least one traceable counterexample and bounded interpretation",
                )
            elif not referenced_counter_ids:
                self.error(
                    "invalid_counterexample_reference",
                    location,
                    "active topic counterexamples must cite an existing source/account/post/claim ID",
                )
            elif referenced_counter_ids & set(evidence_refs):
                self.error(
                    "counterexample_evidence_overlap",
                    location,
                    "the same source/account/post/claim ID cannot be both supporting evidence and a counterexample",
                )
            referenced_posts = [
                post
                for post in usable_posts
                if self._post_has_performance_metric(post)
                and self._post_is_current_sample(post, accounts, sources)
            ]
            independent_accounts = {
                post.get("account_id", "") for post in referenced_posts if post.get("account_id", "")
            }
            if len(referenced_posts) < 2 or len(independent_accounts) < 2:
                self.error(
                    "insufficient_independent_samples",
                    location,
                    "active topic needs at least two referenced posts from two accounts; use experimental otherwise",
                )

    def _registry(self) -> dict[str, dict[str, str]]:
        registry: dict[str, dict[str, str]] = {}
        for filename in ("sku-registry.csv", "offer-registry.csv"):
            for index, row in enumerate(self.rows.get(filename, []), start=2):
                eligibility_id = row.get("eligibility_id", "")
                if eligibility_id in registry:
                    self.error(
                        "duplicate_id",
                        f"{filename}:{index}",
                        f"eligibility_id {eligibility_id} already exists in another registry",
                    )
                registry[eligibility_id] = row
        return registry

    def _eligibility_has_valid_provenance(self, item: dict[str, str]) -> bool:
        run_date = parse_iso(self.run.get("created_at", ""))
        sources = {
            row.get("source_id", ""): row
            for row in self.rows.get("source-log.csv", [])
            if row.get("source_id", "")
        }
        claims = {
            row.get("claim_id", ""): row
            for row in self.rows.get("claim-ledger.csv", [])
            if row.get("claim_id", "")
        }
        ticket_id = item.get("platform_ticket", "").strip()
        ticket = sources.get(ticket_id)
        qualification_id = item.get("qualification_claim_id", "").strip()
        qualification = claims.get(qualification_id)
        evidence_ids = set(split_ids(item.get("evidence_ids")))
        if ticket is None or qualification is None:
            return False
        if not {ticket_id, qualification_id}.issubset(evidence_ids):
            return False
        if not (
            ticket.get("source_layer") == "official"
            and ticket.get("access_status") in {"full", "partial"}
            and ticket.get("evidence_grade") in {"A", "B"}
            and source_descriptors(ticket) & APPROVAL_SOURCE_TYPES
            and platforms_equivalent(ticket.get("platform"), item.get("platform"))
            and run_date
            and parse_iso(ticket.get("collected_at", "")) == run_date
        ):
            return False
        expected_category = "sku_eligibility" if "sku_id" in item else "offer_eligibility"
        if not (
            qualification.get("category") == expected_category
            and qualification.get("claim_status") == "confirmed"
            and qualification.get("evidence_grade") in {"A", "B"}
            and ticket_id in split_ids(qualification.get("source_ids"))
            and run_date
            and parse_iso(qualification.get("last_verified_at", "")) == run_date
        ):
            return False
        scope = parse_scope_contract(qualification.get("scope"))
        expected_scope = {
            "platform": item.get("platform", ""),
            "account_scope": item.get("account_scope", ""),
            "surface": item.get("surface", ""),
            "source_asset_id": item.get("source_asset_id", ""),
            "source_asset_sha256": item.get("source_asset_sha256", ""),
        }
        if "sku_id" in item:
            expected_scope["sku_id"] = item.get("sku_id", "")
        else:
            expected_scope["offer_id"] = item.get("offer_id", "")
            expected_scope["offer_type"] = item.get("offer_type", "")
        return all(
            platforms_equivalent(scope.get(key), value)
            if key == "platform"
            else scope.get(key) == value
            for key, value in expected_scope.items()
        )

    def _eligibility_is_current(self, item: dict[str, str]) -> bool:
        if item.get("status", "") not in APPROVED_ELIGIBILITY:
            return False
        run_date = parse_iso(self.run.get("created_at", ""))
        verified = parse_iso(item.get("verified_at", ""))
        if verified is None or (run_date and verified > run_date):
            return False
        if not scope_is_specific(item.get("account_scope")):
            return False
        if not scope_is_specific(item.get("platform")):
            return False
        if not scope_is_specific(item.get("surface")):
            return False
        if not scope_is_specific(item.get("source_asset_id")):
            return False
        if not valid_sha256(item.get("source_asset_sha256")):
            return False
        if not item.get("platform_ticket", "").strip():
            return False
        if not self._eligibility_has_valid_provenance(item):
            return False
        expires_raw = item.get("expires_at", "")
        if expires_raw:
            expires = parse_iso(expires_raw)
            if expires is None or (run_date and expires < run_date):
                return False
        elif run_date and verified != run_date:
            return False
        return True

    def _check_registry_rows(self) -> None:
        run_date = parse_iso(self.run.get("created_at", ""))
        for filename in ("sku-registry.csv", "offer-registry.csv"):
            for index, row in enumerate(self.rows.get(filename, []), start=2):
                if row.get("status", "") not in APPROVED_ELIGIBILITY:
                    continue
                location = f"{filename}:{index}"
                if not all(
                    scope_is_specific(row.get(field))
                    for field in ("platform", "account_scope", "surface", "source_asset_id")
                ):
                    self.error(
                        "unscoped_eligibility",
                        location,
                        "approved/confirmed eligibility requires one specific platform, account_scope, surface, and source_asset_id",
                    )
                if not row.get("platform_ticket", "").strip():
                    self.error(
                        "missing_approval_record",
                        location,
                        "approved/confirmed eligibility requires a platform ticket or exact approval record",
                    )
                if not valid_sha256(row.get("source_asset_sha256")):
                    self.error(
                        "invalid_source_asset_hash",
                        location,
                        "approved/confirmed eligibility requires a 64-character SHA-256 of the approved creative",
                    )
                if not self._eligibility_has_valid_provenance(row):
                    self.error(
                        "invalid_qualification_evidence",
                        location,
                        "approved/confirmed eligibility needs a same-run official approval-record source and matching sku/offer eligibility claim bound to the exact tuple and creative hash",
                    )
                verified = parse_iso(row.get("verified_at", ""))
                if verified is None:
                    self.error(
                        "invalid_eligibility_date",
                        location,
                        "approved/confirmed eligibility requires verified_at",
                    )
                elif run_date and verified > run_date:
                    self.error(
                        "future_date",
                        location,
                        "verified_at cannot be after the run date",
                    )
                expires_raw = row.get("expires_at", "")
                if expires_raw:
                    expires = parse_iso(expires_raw)
                    if expires is None:
                        self.error(
                            "invalid_eligibility_date",
                            location,
                            "expires_at must be YYYY-MM-DD or blank",
                        )
                    elif run_date and expires < run_date:
                        self.error(
                            "expired_eligibility",
                            location,
                            f"eligibility expired on {expires_raw}",
                        )
                elif verified and run_date and verified != run_date:
                    self.error(
                        "stale_eligibility",
                        location,
                        "eligibility without expires_at must be reverified in this run",
                    )

    def _authorization_is_current(self, row: dict[str, str]) -> bool:
        if row.get("status", "") != "approved":
            return False
        run_date = parse_iso(self.run.get("created_at", ""))
        verified = parse_iso(row.get("verified_at", ""))
        granted = parse_iso(row.get("granted_at", ""))
        if verified is None or granted is None or (run_date and verified > run_date):
            return False
        expires_raw = row.get("expires_at", "")
        if expires_raw:
            expires = parse_iso(expires_raw)
            return bool(expires and (not run_date or expires >= run_date))
        return bool(not run_date or verified == run_date)

    def _check_authorizations(self) -> None:
        run_date = parse_iso(self.run.get("created_at", ""))
        for index, row in enumerate(self.rows.get("authorization-log.csv", []), start=2):
            location = f"authorization-log.csv:{index}"
            if row.get("material_type", "") not in AUTHORIZATION_MATERIAL_TYPES:
                self.error(
                    "invalid_enum",
                    location,
                    f"invalid material_type: {row.get('material_type')}",
                )
            permissions = set(split_ids(row.get("permission_scope")))
            if not permissions or not permissions.issubset(AUTHORIZATION_PERMISSION_SCOPES):
                self.error(
                    "invalid_enum",
                    location,
                    f"invalid permission_scope: {row.get('permission_scope')}",
                )
            if row.get("commercial_use", "") not in AUTHORIZATION_COMMERCIAL_USE:
                self.error(
                    "invalid_enum",
                    location,
                    f"invalid commercial_use: {row.get('commercial_use')}",
                )
            if row.get("status", "") not in AUTHORIZATION_STATUSES:
                self.error(
                    "invalid_enum",
                    location,
                    f"invalid authorization status: {row.get('status')}",
                )
            if not scope_is_specific(row.get("subject_scope")):
                self.error(
                    "unscoped_authorization",
                    location,
                    "subject_scope must identify one documented subject or controlled case set",
                )
            if row.get("status") == "approved" and not all(
                scope_is_specific(row.get(field))
                for field in ("source_asset_id", "material_id")
            ):
                self.error(
                    "unscoped_authorization",
                    location,
                    "approved authorization must bind one source_asset_id and one material_id",
                )
            if row.get("status") == "approved" and not valid_sha256(
                row.get("material_sha256")
            ):
                self.error(
                    "invalid_authorization_hash",
                    location,
                    "approved authorization requires the SHA-256 fingerprint of the consented source material",
                )
            if row.get("status") == "approved" and not valid_sha256(
                row.get("authorized_output_sha256")
            ):
                self.error(
                    "invalid_authorization_hash",
                    location,
                    "approved authorization requires the SHA-256 of the reviewed output or consent-linked channel asset",
                )
            if row.get("status") == "approved" and not self._authorization_is_current(row):
                expires = parse_iso(row.get("expires_at", "")) if row.get("expires_at") else None
                if expires and run_date and expires < run_date:
                    code = "expired_authorization"
                else:
                    code = "stale_authorization"
                self.error(
                    code,
                    location,
                    "approved authorization must be current; without expires_at it must be reverified in this run",
                )

    def _check_draft_authorization(
        self,
        path: Path,
        meta: dict[str, str],
        authorizations: dict[str, dict[str, str]],
    ) -> None:
        truth_label = meta.get("truth_label", "")
        raw_ids = normalize_none(meta.get("authorization_ids"))
        refs = [] if raw_ids == "none" else split_ids(meta.get("authorization_ids"))
        raw_material_ids = normalize_none(meta.get("source_material_ids"))
        material_ids = (
            [] if raw_material_ids == "none" else split_ids(meta.get("source_material_ids"))
        )
        actual_output_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if truth_label in {"factual_explainer", "fictional_scenario"}:
            if refs or material_ids:
                self.error(
                    "truth_authorization_conflict",
                    path.name,
                    f"{truth_label} must use authorization_ids=none and source_material_ids=none; choose an authorized truth label for case material",
                )
            return
        if truth_label == "first_person_documented" and refs == ["self_only"]:
            if not material_ids or not all(scope_is_specific(item) for item in material_ids):
                self.error(
                    "authorization_material_mismatch",
                    path.name,
                    "first_person_documented requires specific source_material_ids even for self_only",
                )
            return
        requirement = AUTH_REQUIRED_TRUTH_LABELS.get(truth_label)
        if truth_label == "first_person_documented" and not refs:
            self.error(
                "authorization_required",
                path.name,
                "first_person_documented requires authorization_ids=self_only or current records for other people",
            )
            return
        if requirement and len(set(refs)) < requirement[1]:
            self.error(
                "authorization_required",
                path.name,
                f"{truth_label} requires at least {requirement[1]} current authorization record(s)",
            )
        if not refs:
            return
        required_permissions = {requirement[0]} if requirement else set()
        if truth_label == "first_person_documented":
            required_permissions = {"anonymized_publish", "verbatim"}
        authorized_material_ids: set[str] = set()
        authorized_material_hashes: set[str] = set()
        authorized_subject_scopes: set[str] = set()
        for ref in refs:
            if ref == "self_only":
                self.error(
                    "authorization_required",
                    path.name,
                    f"self_only is not valid for {truth_label}",
                )
                continue
            row = authorizations.get(ref)
            if row is None:
                self.error(
                    "authorization_required",
                    path.name,
                    f"unknown authorization_id {ref}",
                )
                continue
            if not self._authorization_is_current(row):
                self.error(
                    "authorization_required",
                    path.name,
                    f"authorization {ref} is not current and approved",
                )
            if row.get("source_asset_id", "") != meta.get("draft_id", ""):
                self.error(
                    "authorization_asset_mismatch",
                    path.name,
                    f"authorization {ref} is not scoped to draft_id {meta.get('draft_id', '')}",
                )
            if row.get("authorized_output_sha256", "") != actual_output_hash:
                self.error(
                    "authorization_output_mismatch",
                    path.name,
                    f"draft bytes no longer match the reviewed output authorized by {ref}",
                )
            if row.get("material_id", ""):
                authorized_material_ids.add(row.get("material_id", ""))
            if valid_sha256(row.get("material_sha256")):
                authorized_material_hashes.add(row.get("material_sha256", "").lower())
            if row.get("subject_scope", ""):
                authorized_subject_scopes.add(row.get("subject_scope", ""))
            permissions = set(split_ids(row.get("permission_scope")))
            if required_permissions and not required_permissions & permissions:
                self.error(
                    "authorization_scope_mismatch",
                    path.name,
                    f"authorization {ref} lacks one of the required publication permissions: {', '.join(sorted(required_permissions))}",
                )
            if (
                meta.get("commercial_relationship") not in {"", "none"}
                and row.get("commercial_use") != "approved"
            ):
                self.error(
                    "authorization_scope_mismatch",
                    path.name,
                    f"authorization {ref} prohibits commercial use",
                )
        if truth_label == "composite_cases" and (
            len(authorized_material_ids) < 2
            or len(authorized_material_hashes) < 2
            or len(authorized_subject_scopes) < 2
        ):
            self.error(
                "insufficient_distinct_cases",
                path.name,
                "composite_cases requires at least two distinct subject_scope, material_id, and material_sha256 values; renamed or duplicate consent rows for one case do not count",
            )
        if set(material_ids) != authorized_material_ids:
            self.error(
                "authorization_material_mismatch",
                path.name,
                "source_material_ids must exactly match the material_id values in referenced authorizations",
            )

    def _check_channels(self) -> None:
        channels = self.rows.get("acquisition-channels.csv")
        if channels is None:
            return
        if "sku-registry.csv" not in self.rows or "offer-registry.csv" not in self.rows:
            self.error(
                "missing_file",
                "acquisition-channels.csv",
                "channels require both sku-registry.csv and offer-registry.csv",
            )
        registry = self._registry()
        known_evidence = self._id_set("source-log.csv") | self._id_set("claim-ledger.csv")
        for index, row in enumerate(channels, start=2):
            location = f"acquisition-channels.csv:{index}"
            direction = row.get("direction", "")
            if direction not in DIRECTIONS:
                self.error("invalid_enum", location, f"invalid direction: {direction}")
            channel_platform = row.get("platform", "")
            if direction in {"xhs_to_native_conversion", "xhs_to_approved_external"} and not platform_is_xhs(
                channel_platform
            ):
                self.error(
                    "direction_platform_mismatch",
                    location,
                    f"{direction} requires platform=xiaohongshu/小红书",
                )
            if direction == "external_to_xhs" and platform_is_xhs(channel_platform):
                self.error(
                    "direction_platform_mismatch",
                    location,
                    "external_to_xhs requires one specific non-Xiaohongshu source platform",
                )
            refs = split_ids(row.get("eligibility_ids"))
            surfaces = set(split_ids(row.get("surfaces")))
            cta = row.get("permitted_cta", "").strip().lower()
            has_cta = cta not in {"", "none", "no_cta"}
            if has_cta and not refs:
                self.error("missing_reference", location, "CTA requires eligibility_ids")
            if has_cta and not split_ids(row.get("evidence_ids")):
                self.error("missing_reference", location, "CTA requires current evidence_ids")
            for evidence_id in split_ids(row.get("evidence_ids")):
                if evidence_id not in known_evidence:
                    self.error(
                        "dangling_reference",
                        location,
                        f"evidence_ids references unknown id {evidence_id}",
                    )
            referenced_rows: list[dict[str, str]] = []
            for ref in refs:
                item = registry.get(ref)
                if item is None:
                    self.error("dangling_reference", location, f"unknown eligibility_id {ref}")
                    continue
                referenced_rows.append(item)
            registry_surfaces = {item.get("surface", "") for item in referenced_rows}
            if referenced_rows and surfaces != registry_surfaces:
                self.error(
                    "surface_mismatch",
                    location,
                    f"channel surfaces {sorted(surfaces)} do not match registry {sorted(registry_surfaces)}",
                )
            wrong_platform = [
                item.get("eligibility_id", "")
                for item in referenced_rows
                if item.get("platform", "") != channel_platform
            ]
            if wrong_platform:
                self.error(
                    "platform_mismatch",
                    location,
                    "channel platform does not match eligibility: " + ", ".join(wrong_platform),
                )
            channel_account = row.get("account_scope", "")
            wrong_account = [
                item.get("eligibility_id", "")
                for item in referenced_rows
                if item.get("account_scope", "") != channel_account
            ]
            if wrong_account:
                self.error(
                    "account_scope_mismatch",
                    location,
                    "channel account_scope does not match eligibility: " + ", ".join(wrong_account),
                )
            unapproved = [
                item for item in referenced_rows if not self._eligibility_is_current(item)
            ]
            wrong_asset = [
                item.get("eligibility_id", "")
                for item in referenced_rows
                if item.get("status", "") in APPROVED_ELIGIBILITY
                and (
                    item.get("source_asset_id", "") != row.get("source_asset_id", "")
                    or item.get("source_asset_sha256", "")
                    != row.get("source_asset_sha256", "")
                )
            ]
            if wrong_asset:
                self.error(
                    "source_asset_mismatch",
                    location,
                    "channel source_asset_id does not match approval record: "
                    + ", ".join(wrong_asset),
                )
            status = row.get("status", "")
            status_class = channel_status_class(status)
            if status_class is None:
                self.error(
                    "invalid_channel_status",
                    location,
                    "status must be active or an unambiguous blocked/draft/needs_* state",
                )
            is_blocked = status_class == "blocked"
            if status_class == "active" and not all(
                scope_is_specific(value)
                for value in (channel_platform, channel_account, *surfaces)
            ):
                self.error(
                    "unscoped_channel",
                    location,
                    "active channel requires one specific platform, account_scope, and surface",
                )
            if status_class == "active" and not valid_sha256(
                row.get("source_asset_sha256")
            ):
                self.error(
                    "invalid_source_asset_hash",
                    location,
                    "active channel requires the SHA-256 of the exact source asset",
                )
            if has_cta and unapproved and not is_blocked:
                ids = [item.get("eligibility_id", "") for item in unapproved]
                self.error(
                    "eligibility_not_approved",
                    location,
                    "active CTA references unapproved eligibility: " + ", ".join(ids),
                )
            if direction == "external_to_xhs" and row.get("attribution_level") not in {
                "directional",
                "user_level_with_consent",
            }:
                self.error(
                    "invalid_attribution",
                    location,
                    "external_to_xhs is directional unless a consented user-level link exists",
                )
            if row.get("attribution_level") == "user_level_with_consent":
                authorization_rows = {
                    item.get("authorization_id", ""): item
                    for item in self.rows.get("authorization-log.csv", [])
                    if item.get("authorization_id", "")
                }
                consent_ids = split_ids(row.get("consent_ids"))
                valid_consents = [
                    authorization_rows[consent_id]
                    for consent_id in consent_ids
                    if consent_id in authorization_rows
                    and self._authorization_is_current(authorization_rows[consent_id])
                    and "cross_platform_attribution"
                    in split_ids(authorization_rows[consent_id].get("permission_scope"))
                    and authorization_rows[consent_id].get("commercial_use") == "approved"
                    and authorization_rows[consent_id].get("source_asset_id")
                    == row.get("source_asset_id")
                    and authorization_rows[consent_id].get("authorized_output_sha256")
                    == row.get("source_asset_sha256")
                ]
                if len(valid_consents) != len(consent_ids) or not consent_ids:
                    self.error(
                        "missing_consent_evidence",
                        location,
                        "user-level attribution requires current explicit consent records bound to this source asset",
                    )
            if direction == "xhs_to_approved_external" and not is_blocked:
                present_kinds = {
                    "sku" if "sku_id" in item else "offer" for item in referenced_rows
                }
                product_offer_present = any(
                    item.get("offer_type", "") in PRODUCT_OFFER_TYPES
                    for item in referenced_rows
                    if "offer_id" in item
                )
                landing_asset = row.get("landing_asset", "").strip()
                landing_is_specific = bool(
                    re.fullmatch(r"https?://\S+", landing_asset)
                    or scope_is_specific(landing_asset)
                )
                external_jump_invalid = (
                    "approved_external_destination" not in surfaces
                    or not refs
                    or bool(unapproved)
                    or "offer" not in present_kinds
                    or (product_offer_present and "sku" not in present_kinds)
                    or bool(wrong_platform)
                    or bool(wrong_account)
                    or bool(wrong_asset)
                    or not landing_is_specific
                )
                if external_jump_invalid:
                    self.error(
                        "external_jump_not_approved",
                        location,
                        "active external jump requires a specific destination plus current matching offer eligibility; product offers also require SKU eligibility, all bound to the exact platform, account, surface, asset ID, and hash",
                    )

    def _check_draft_eligibility(
        self,
        path: Path,
        meta: dict[str, str],
        registry: dict[str, dict[str, str]],
    ) -> None:
        cta_type = meta.get("cta_type", "")
        if cta_type not in COMMERCIAL_CTA_TYPES:
            return
        refs = split_ids(meta.get("eligibility_ids"))
        surfaces = set(split_ids(meta.get("surfaces")))
        if not refs:
            self.error("draft_eligibility", path.name, "commercial draft CTA needs eligibility_ids")
            return
        referenced_rows: list[dict[str, str]] = []
        actual_asset_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        for ref in refs:
            item = registry.get(ref)
            if item is None:
                self.error("draft_eligibility", path.name, f"unknown eligibility_id {ref}")
                continue
            referenced_rows.append(item)
            if not self._eligibility_is_current(item):
                self.error("draft_eligibility", path.name, f"eligibility {ref} is not current and approved")
            if item.get("surface") not in surfaces:
                self.error(
                    "surface_mismatch",
                    path.name,
                    f"draft surfaces do not include registry surface {item.get('surface')}",
                )
            if item.get("platform", "") != meta.get("platform", ""):
                self.error(
                    "platform_mismatch",
                    path.name,
                    f"draft platform does not match eligibility {ref}",
                )
            if item.get("account_scope", "") != meta.get("account_scope", ""):
                self.error(
                    "account_scope_mismatch",
                    path.name,
                    f"draft account_scope does not match eligibility {ref}",
                )
            if item.get("source_asset_id", "") != meta.get("draft_id", ""):
                self.error(
                    "source_asset_mismatch",
                    path.name,
                    f"draft_id does not match approved source_asset_id for {ref}",
                )
            if item.get("source_asset_sha256", "") != actual_asset_hash:
                self.error(
                    "source_asset_mismatch",
                    path.name,
                    f"draft content hash does not match approved source_asset_sha256 for {ref}",
                )
        registry_surfaces = {item.get("surface", "") for item in referenced_rows}
        present_kinds = {
            "sku" if "sku_id" in item else "offer" for item in referenced_rows
        }
        required_kinds = set(CTA_REQUIRED_REGISTRY_KINDS.get(cta_type, set()))
        if any(
            item.get("offer_type", "") in PRODUCT_OFFER_TYPES
            for item in referenced_rows
            if "offer_id" in item
        ):
            required_kinds.add("sku")
        missing_kinds = sorted(required_kinds - present_kinds)
        if missing_kinds:
            self.error(
                "eligibility_kind_mismatch",
                path.name,
                f"{cta_type} requires registry kind(s): {', '.join(missing_kinds)}",
            )
        if referenced_rows and surfaces != registry_surfaces:
            self.error(
                "surface_mismatch",
                path.name,
                f"draft surfaces {sorted(surfaces)} do not exactly match registry {sorted(registry_surfaces)}",
            )

    def _check_v2_draft_style_contract(
        self,
        path: Path,
        meta: dict[str, str],
    ) -> None:
        def invalid(field: str, value: str) -> None:
            self.error(
                "invalid_v2_style_enum",
                path.name,
                f"invalid {field}: {value}",
            )

        if meta.get("style_contract_version", "") != "2":
            invalid("style_contract_version", meta.get("style_contract_version", ""))

        objective = meta.get("business_objective", "")
        if objective not in V2_BUSINESS_OBJECTIVES:
            invalid("business_objective", objective)
        elif objective != self.run.get("business_objective", ""):
            self.error(
                "style_run_mismatch",
                path.name,
                "draft business_objective must match run.yaml",
            )

        requirement = meta.get("style_requirement", "")
        if requirement not in V2_STYLE_REQUIREMENTS:
            invalid("style_requirement", requirement)
        elif requirement != self.run.get("style_requirement", ""):
            self.error(
                "style_run_mismatch",
                path.name,
                "draft style_requirement must match run.yaml",
            )

        if meta.get("style_library_path", "") != self.run.get("style_library_path", ""):
            self.error(
                "style_run_mismatch",
                path.name,
                "draft style_library_path must match run.yaml",
            )
        if meta.get("style_taxonomy_version", "") != "2":
            invalid("style_taxonomy_version", meta.get("style_taxonomy_version", ""))
        category = meta.get("style_query_category", "").strip()
        if category.lower() in {"", "none", "unknown", "待填写"}:
            self.error(
                "style_query_incomplete",
                path.name,
                "style_query_category must name the current content category",
            )
        elif category != self.run.get("category", "").strip():
            self.error(
                "style_query_mismatch",
                path.name,
                "style_query_category must exactly match run.yaml category",
            )

        primary_jobs = self._v2_codes("primary_job")
        query_job = meta.get("style_query_primary_job", "")
        if query_job not in primary_jobs:
            invalid("style_query_primary_job", query_job)
        elif query_job != meta.get("primary_job", ""):
            self.error(
                "style_query_mismatch",
                path.name,
                "style_query_primary_job must match draft primary_job",
            )
        if query_job and query_job != self.run.get("objective_primary_job", ""):
            self.error(
                "style_run_mismatch",
                path.name,
                "style_query_primary_job must match run objective_primary_job",
            )

        carrier = meta.get("style_query_carrier", "")
        carriers = self._v2_codes("carrier")
        if requirement == "none":
            if carrier not in {"", "none"}:
                invalid("style_query_carrier", carrier)
        elif carrier not in carriers:
            invalid("style_query_carrier", carrier)

        def checked_codes(field: str, taxonomy_key: str) -> set[str]:
            values = {
                value
                for value in split_ids(meta.get(field, ""))
                if value.lower() != "none"
            }
            unknown = sorted(values - self._v2_codes(taxonomy_key))
            if unknown:
                invalid(field, ",".join(unknown))
            return values

        available_style_materials = checked_codes(
            "style_query_available_material_codes", "material_code"
        )
        required_style_materials = checked_codes(
            "style_query_required_material_codes", "material_code"
        )
        required_constraints = checked_codes(
            "style_query_required_constraint_codes", "production_constraint_code"
        )
        active_constraints = checked_codes(
            "style_query_active_constraint_codes", "production_constraint_code"
        )
        checked_codes(
            "style_query_active_contraindication_codes", "contraindication_code"
        )
        if requirement != "none" and not available_style_materials:
            self.error(
                "style_query_incomplete",
                path.name,
                "style query requires at least one controlled available material code",
            )
        if required_style_materials - available_style_materials:
            self.error(
                "style_query_material_gap",
                path.name,
                "required style materials must be present in available materials",
            )
        if required_constraints - active_constraints:
            self.error(
                "style_query_constraint_gap",
                path.name,
                "required style constraints must be present in active constraints",
            )

        binding_status = meta.get("style_binding_status", "")
        if binding_status == "starter_applied":
            self.error(
                "starter_gate_incomplete",
                path.name,
                "starter binding is unavailable until the qualified-cell release gate passes",
            )
        elif binding_status not in V2_STYLE_BINDING_STATUSES:
            invalid("style_binding_status", binding_status)
        binding_source = meta.get("style_binding_source", "")
        if binding_source not in {"none", "library"}:
            invalid("style_binding_source", binding_source)
        if binding_status == "grounded" and binding_source != "library":
            self.error(
                "style_not_grounded",
                path.name,
                "grounded style requires style_binding_source=library",
            )
        if binding_status == "needs_style_research" and binding_source != "none":
            self.error(
                "style_not_grounded",
                path.name,
                "needs_style_research cannot claim a library binding",
            )
        draft_status = meta.get("status", "")
        if requirement != "none" and draft_status == "ready" and binding_status != "grounded":
            self.error(
                "style_not_grounded",
                path.name,
                "ready draft with a style requirement must be grounded",
            )
        if binding_status == "needs_style_research" and draft_status not in {
            "needs_review",
            "blocked",
        }:
            self.error(
                "style_not_grounded",
                path.name,
                "needs_style_research requires draft status needs_review or blocked",
            )

        claim_kind = meta.get("performance_rule_claim_kind", "")
        if claim_kind not in V2_RULE_CLAIM_KINDS:
            invalid("performance_rule_claim_kind", claim_kind)
        contrast = meta.get("style_feature_contrast", "")
        if contrast not in V2_FEATURE_CONTRASTS:
            invalid("style_feature_contrast", contrast)
        evidence_scope = meta.get("performance_evidence_scope", "")
        if evidence_scope not in V2_PERFORMANCE_EVIDENCE_SCOPES:
            invalid("performance_evidence_scope", evidence_scope)
        if evidence_scope == "first_party_traffic_validated":
            self.error(
                "first_party_scope_release_gate",
                path.name,
                "first_party_traffic_validated is disabled until this validator can import "
                "the original analytics export and recompute the experiment verdict; a "
                "hand-populated checkpoint database is not traffic validation",
            )
        if claim_kind in {"series_constant", "task_fit"} and evidence_scope != "not_performance_evidence":
            self.error(
                "nonperformance_rule_scope",
                path.name,
                f"{claim_kind} must remain not_performance_evidence",
            )
        if contrast == "invariant" and (
            claim_kind != "series_constant"
            or evidence_scope != "not_performance_evidence"
        ):
            self.error(
                "shared_feature_not_performance",
                path.name,
                "a feature shared by high and low samples is a series constant, not a performance rule",
            )
        if evidence_scope in {
            "public_proxy_association",
            "first_party_traffic_validated",
        } and (
            claim_kind != "contrastive_performance_hypothesis"
            or contrast != "differentiated"
        ):
            self.error(
                "performance_scope_without_contrast",
                path.name,
                "performance evidence requires a differentiated contrastive hypothesis",
            )
        primary_performance_rule_id = normalize_none(
            meta.get("primary_performance_rule_id")
        )
        if evidence_scope == "not_performance_evidence":
            if primary_performance_rule_id != "none":
                self.error(
                    "primary_performance_rule_mismatch",
                    path.name,
                    "non-performance drafts must use primary_performance_rule_id=none",
                )
        else:
            if not scope_is_specific(primary_performance_rule_id):
                self.error(
                    "primary_performance_rule_missing",
                    path.name,
                    "performance evidence requires one explicit primary_performance_rule_id",
                )
            if binding_status != "grounded":
                self.error(
                    "primary_performance_rule_missing",
                    path.name,
                    "a primary performance rule requires a grounded published binding",
                )

        visibility = meta.get("performance_visibility_scope", "")
        if visibility not in V2_PERFORMANCE_VISIBILITY_SCOPES:
            invalid("performance_visibility_scope", visibility)
        elif visibility != self.run.get("performance_visibility_scope", ""):
            self.error(
                "style_run_mismatch",
                path.name,
                "draft performance_visibility_scope must match run.yaml",
            )
        traffic_metric = meta.get("traffic_primary_metric", "")
        if traffic_metric not in V2_TRAFFIC_PRIMARY_METRICS:
            invalid("traffic_primary_metric", traffic_metric)
        traffic_verdict = meta.get("traffic_verdict", "")
        if traffic_verdict not in V2_TRAFFIC_VERDICTS:
            invalid("traffic_verdict", traffic_verdict)
        traffic_stage = meta.get("traffic_stage", "")
        if traffic_stage not in V2_TRAFFIC_STAGES:
            invalid("traffic_stage", traffic_stage)

        job_metric = meta.get("job_primary_metric", "")
        job = meta.get("primary_job", "")
        allowed_job_metrics = V2_JOB_PRIMARY_METRICS_BY_JOB.get(job, set())
        job_metric_scope = meta.get("job_metric_data_scope", "")
        job_metric_denominator = meta.get("job_metric_denominator", "")
        job_metric_verdict = meta.get("job_metric_verdict", "")
        job_metric_definition = meta.get("job_metric_event_definition", "").strip()
        if job_metric_scope not in V2_JOB_METRIC_DATA_SCOPES:
            invalid("job_metric_data_scope", job_metric_scope)
        if job_metric_denominator not in V2_JOB_METRIC_DENOMINATORS:
            invalid("job_metric_denominator", job_metric_denominator)
        if job_metric_verdict not in V2_TRAFFIC_VERDICTS:
            invalid("job_metric_verdict", job_metric_verdict)
        if not job_metric_definition or job_metric_definition.lower() == "none":
            self.error(
                "job_metric_contract",
                path.name,
                "job_metric_event_definition must state the event and denominator boundary",
            )
        if job_metric_scope == "public_proxy":
            if (
                job_metric not in V2_JOB_PROXY_METRICS
                or job_metric_denominator != "comments"
                or job_metric_verdict != "not_applicable"
            ):
                self.error(
                    "job_metric_public_proxy",
                    path.name,
                    "public job diagnostics are limited to comment_semantic_proxy/comments/not_applicable",
                )
        elif job_metric_scope == "unavailable":
            if (
                job_metric != "unavailable"
                or job_metric_denominator != "unavailable"
                or job_metric_verdict not in {"unavailable", "insufficient"}
            ):
                self.error(
                    "job_metric_unavailable",
                    path.name,
                    "unavailable job data requires unavailable metric/denominator and unavailable or insufficient verdict",
                )
        elif job_metric_scope == "first_party_analytics":
            if job_metric not in allowed_job_metrics - {"unavailable"}:
                self.error(
                    "job_metric_job_mismatch",
                    path.name,
                    f"{job_metric} is not a primary metric for primary_job={job}",
                )
            if job_metric_denominator == "unavailable":
                self.error(
                    "job_metric_contract",
                    path.name,
                    "first-party job metric requires an explicit denominator",
                )
        elif job_metric and job_metric not in allowed_job_metrics | V2_JOB_PROXY_METRICS:
            invalid("job_primary_metric", job_metric)
        if job_metric_verdict in {"win", "loss"} and job_metric_scope != "first_party_analytics":
            self.error(
                "job_metric_verdict_scope",
                path.name,
                "job metric win/loss requires first-party analytics",
            )
        if visibility == "public_proxy" and traffic_verdict != "not_applicable":
            self.error(
                "public_proxy_traffic_verdict",
                path.name,
                "public proxy evidence can only use traffic_verdict=not_applicable",
            )
        if visibility == "public_proxy" and traffic_metric != "engagement_proxy":
            self.error(
                "traffic_primary_metric",
                path.name,
                "public proxy evidence must be labelled engagement_proxy, not traffic",
            )
        if objective == "engagement_proxy" and (
            visibility != "public_proxy"
            or traffic_metric != "engagement_proxy"
            or traffic_verdict != "not_applicable"
        ):
            self.error(
                "public_proxy_traffic_verdict",
                path.name,
                "engagement_proxy objective requires public_proxy and not_applicable traffic verdict",
            )
        if objective == "traffic_first" and traffic_verdict in {"win", "loss"} and not (
            visibility == "first_party_analytics"
            and traffic_metric in {"impressions", "reach"}
        ):
            self.error(
                "traffic_primary_metric",
                path.name,
                "traffic win/loss requires first-party impressions or reach",
            )
        if evidence_scope == "first_party_traffic_validated" and not (
            visibility == "first_party_analytics"
            and traffic_metric in {"impressions", "reach"}
        ):
            self.error(
                "traffic_primary_metric",
                path.name,
                "first_party_traffic_validated requires first-party impressions or reach",
            )
        outcome_surface = normalize_none(meta.get("traffic_observation_surface"))
        outcome_id = normalize_none(meta.get("traffic_outcome_checkpoint_id"))
        outcome_sha = normalize_none(meta.get("traffic_outcome_receipt_sha256"))
        if evidence_scope == "first_party_traffic_validated":
            if traffic_verdict != "inconclusive":
                self.error(
                    "traffic_verdict_release_gate",
                    path.name,
                    "this release records first-party checkpoints but does not promote win/loss until verdict recomputation is published",
                )
            if binding_status != "grounded":
                self.error(
                    "traffic_outcome_receipt_missing",
                    path.name,
                    "first-party traffic validation requires a grounded published style binding",
                )
            if not scope_is_specific(outcome_surface):
                self.error(
                    "traffic_outcome_receipt_missing",
                    path.name,
                    "first-party traffic validation requires one exact observation surface",
                )
            if outcome_id == "none" or not valid_sha256(outcome_sha):
                self.error(
                    "traffic_outcome_receipt_missing",
                    path.name,
                    "first-party traffic validation requires checkpoint ID and receipt SHA-256",
                )
        elif any(value != "none" for value in (outcome_surface, outcome_id, outcome_sha)):
            self.error(
                "traffic_outcome_receipt_mismatch",
                path.name,
                "non-validated evidence scope cannot claim first-party outcome receipt fields",
            )
        if traffic_verdict in {"win", "loss"} and evidence_scope != "first_party_traffic_validated":
            self.error(
                "traffic_outcome_receipt_missing",
                path.name,
                "traffic win/loss requires performance_evidence_scope=first_party_traffic_validated",
            )
        if job_metric_verdict in {"win", "loss"}:
            self.error(
                "job_metric_verdict_release_gate",
                path.name,
                "job win/loss is disabled until an immutable recomputable job-outcome publication exists",
            )

        visual_requirement = meta.get("visual_delivery_requirement", "")
        if visual_requirement not in V2_VISUAL_DELIVERY_REQUIREMENTS:
            invalid("visual_delivery_requirement", visual_requirement)
        visual_status = meta.get("visual_delivery_status", "")
        if visual_status not in V2_VISUAL_DELIVERY_STATUSES:
            invalid("visual_delivery_status", visual_status)
        allowed_visual_states = {
            "none": {"not_requested"},
            "brief": {"brief_only", "prototype_only"},
            "rendered": {"rendered_needs_review", "rendered_pass"},
        }
        if visual_status not in allowed_visual_states.get(visual_requirement, set()):
            self.error(
                "visual_delivery_state_mismatch",
                path.name,
                f"visual_delivery_requirement={visual_requirement} cannot use visual_delivery_status={visual_status}",
            )
        if visual_requirement == "rendered" and draft_status == "ready" and visual_status != "rendered_pass":
            self.error(
                "rendered_delivery_missing",
                path.name,
                "ready rendered delivery requires visual_delivery_status=rendered_pass",
            )
        if visual_status == "rendered_pass" and visual_requirement != "rendered":
            self.error(
                "rendered_delivery_mismatch",
                path.name,
                "rendered_pass requires visual_delivery_requirement=rendered",
            )
        if visual_status == "rendered_pass":
            self._check_rendered_assets(path, meta, require_pass=True)
        elif visual_status == "rendered_needs_review":
            if draft_status == "ready":
                self.error(
                    "rendered_asset_review_missing",
                    path.name,
                    "rendered_needs_review cannot be marked ready",
                )
            self._check_rendered_assets(path, meta, require_pass=False)

        expected_slide_indices = self._contract_ids(meta.get("expected_slide_indices"))
        if visual_status in {"rendered_needs_review", "rendered_pass"}:
            try:
                parsed_expected = [int(value) for value in expected_slide_indices]
            except ValueError:
                parsed_expected = []
            if (
                not parsed_expected
                or len(set(parsed_expected)) != len(parsed_expected)
                or sorted(parsed_expected) != list(range(1, max(parsed_expected, default=0) + 1))
            ):
                self.error(
                    "expected_slide_contract",
                    path.name,
                    "rendered delivery requires explicit contiguous expected_slide_indices starting at 1",
                )
        elif expected_slide_indices:
            self.error(
                "expected_slide_contract",
                path.name,
                "expected_slide_indices must be none unless rendered assets were requested",
            )

        product_scope = meta.get("cta_product_scope", "").strip()
        if product_scope not in V2_CTA_PRODUCT_SCOPES:
            invalid("cta_product_scope", product_scope)
        gate_status = meta.get("production_gate_status", "").strip()
        if gate_status not in V2_PRODUCTION_GATE_STATUSES:
            invalid("production_gate_status", gate_status)
        receipt_ids = [
            value
            for value in split_ids(meta.get("production_gate_receipt_ids", ""))
            if value.lower() != "none"
        ]
        cta_type = meta.get("cta_type", "")
        if cta_type in COMMERCIAL_CTA_TYPES and product_scope == "relationship_education_only":
            self.error(
                "relationship_education_not_product_eligibility",
                path.name,
                "relationship education does not establish product eligibility",
            )
        if cta_type in COMMERCIAL_CTA_TYPES and product_scope == "adult_product":
            gate_ready = gate_status == "ready" and bool(receipt_ids)
            explicitly_blocked = draft_status == "blocked" and gate_status in {
                "needs_revision",
                "needs_platform_confirmation",
                "blocked_safety",
                "blocked_rights",
                "unknown",
            }
            if not (gate_ready or explicitly_blocked):
                self.error(
                    "sensitive_commercial_gate",
                    path.name,
                    "adult-product CTA requires a current production-gate receipt or an explicitly blocked draft",
                )
            if gate_ready:
                self._check_production_gate_receipts(path, meta, receipt_ids)

    @staticmethod
    def _decoded_image_dimensions(asset_path: Path) -> tuple[int, int] | None:
        """Fully decode a supported image and return its true dimensions.

        ``Image.verify`` catches truncated containers while the second open and
        ``load`` force pixel decoding. Merely parsing PNG/GIF/JPEG/WebP headers is
        insufficient evidence that a reviewer could actually open the asset.
        """
        if Image is None:
            return None
        try:
            with Image.open(asset_path) as image:
                if image.format not in {"PNG", "JPEG", "GIF", "WEBP"}:
                    return None
                image.verify()
            with Image.open(asset_path) as image:
                if image.format not in {"PNG", "JPEG", "GIF", "WEBP"}:
                    return None
                image.load()
                width, height = image.size
        except (OSError, ValueError, UnidentifiedImageError):
            return None
        if width < 1 or height < 1:
            return None
        return int(width), int(height)

    def _check_rendered_assets(
        self,
        path: Path,
        meta: dict[str, str],
        *,
        require_pass: bool,
    ) -> None:
        if Image is None:
            self.error(
                "visual_decoder_unavailable",
                path.name,
                "visual artifact validation requires Pillow; install redbook-writing/requirements-visual.txt",
            )
            return
        manifest_path = self.run_dir / "draft-assets.csv"
        if meta.get("style_binding_status") != "grounded":
            self.error(
                "rendered_asset_receipt_missing",
                path.name,
                "rendered assets require a grounded, published style binding",
            )
        if not manifest_path.is_file():
            self.error(
                "rendered_asset_receipt_missing",
                path.name,
                "rendered delivery requires draft-assets.csv",
            )
            return
        try:
            with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                fields = set(reader.fieldnames or [])
                all_rows = list(reader)
                rows = [row for row in all_rows if row.get("draft_id") == meta.get("draft_id")]
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            self.error("rendered_asset_receipt_invalid", path.name, str(exc))
            return
        if fields != V2_DRAFT_ASSET_FIELDS:
            self.error(
                "rendered_asset_receipt_invalid",
                "draft-assets.csv",
                "header must exactly match the v2 draft asset contract",
            )
            return
        if not rows:
            self.error(
                "rendered_asset_receipt_missing",
                path.name,
                "no final asset rows match this draft_id",
            )
            return
        all_asset_ids = [row.get("draft_asset_id", "").strip() for row in all_rows]
        duplicate_asset_ids = sorted(
            asset_id
            for asset_id, count in Counter(all_asset_ids).items()
            if asset_id and count > 1
        )
        if duplicate_asset_ids:
            self.error(
                "rendered_asset_receipt_invalid",
                "draft-assets.csv",
                "draft_asset_id must be globally unique across the manifest: "
                + ", ".join(duplicate_asset_ids),
            )
        review_receipts: dict[str, dict[str, object]] = {}
        if require_pass:
            reviews_path = self.run_dir / "visual-review-receipts.jsonl"
            if not reviews_path.is_file():
                self.error(
                    "rendered_asset_review_missing",
                    path.name,
                    "rendered_pass requires visual-review-receipts.jsonl",
                )
            else:
                try:
                    for line_number, line in enumerate(
                        reviews_path.read_text(encoding="utf-8-sig").splitlines(), start=1
                    ):
                        if not line.strip():
                            continue
                        item = json.loads(line)
                        if not isinstance(item, dict) or set(item) != V2_VISUAL_REVIEW_FIELDS:
                            raise ValueError(
                                f"line {line_number}: visual review fields do not match v2 contract"
                            )
                        receipt_id = item.get("review_receipt_id")
                        if (
                            not isinstance(receipt_id, str)
                            or not receipt_id
                            or receipt_id in review_receipts
                        ):
                            raise ValueError(
                                f"line {line_number}: review_receipt_id must be present and unique"
                            )
                        canonical = dict(item)
                        supplied_sha = canonical.pop("receipt_sha256", None)
                        calculated_sha = hashlib.sha256(
                            json.dumps(
                                canonical,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            ).encode("utf-8")
                        ).hexdigest()
                        if supplied_sha != calculated_sha:
                            raise ValueError(
                                f"line {line_number}: receipt_sha256 mismatch"
                            )
                        review_receipts[receipt_id] = item
                except (
                    OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError
                ) as exc:
                    self.error("rendered_asset_review_invalid", path.name, str(exc))
        indices: list[int] = []
        expected_indices = [
            int(value)
            for value in self._contract_ids(meta.get("expected_slide_indices"))
            if value.isdigit()
        ]
        asset_ids: set[str] = set()
        review_statuses: list[str] = []
        expected_rules = set(self._contract_ids(meta.get("style_rule_ids")))
        used_rules: set[str] = set()
        for row_number, row in enumerate(rows, start=2):
            location = f"draft-assets.csv:{row_number}"
            asset_id = row.get("draft_asset_id", "").strip()
            if not asset_id or asset_id in asset_ids:
                self.error(
                    "rendered_asset_receipt_invalid",
                    location,
                    "draft_asset_id must be present and unique",
                )
            asset_ids.add(asset_id)
            try:
                slide_index = int(row.get("slide_index", ""))
            except ValueError:
                slide_index = 0
            if slide_index < 1 or slide_index in indices:
                self.error(
                    "rendered_asset_receipt_invalid",
                    location,
                    "slide_index must be a unique positive integer",
                )
            indices.append(slide_index)
            if row.get("draft_binding_id") != meta.get("draft_binding_id"):
                self.error(
                    "rendered_asset_receipt_mismatch",
                    location,
                    "draft_binding_id does not match the draft",
                )
            if row.get("binding_rule_bundle_sha256") != meta.get("draft_binding_sha256"):
                self.error(
                    "rendered_asset_receipt_mismatch",
                    location,
                    "binding_rule_bundle_sha256 does not match the published binding",
                )
            asset_rules = set(self._contract_ids(row.get("style_rule_refs")))
            if not asset_rules or not asset_rules.issubset(expected_rules):
                self.error(
                    "rendered_asset_receipt_mismatch",
                    location,
                    "style_rule_refs must be a non-empty subset of the bound rules",
                )
            used_rules.update(asset_rules)
            review_status = row.get("review_status", "")
            review_statuses.append(review_status)
            if require_pass and review_status != "PASS":
                self.error(
                    "rendered_asset_review_missing",
                    location,
                    "each final asset requires review_status=PASS",
                )
            elif not require_pass and review_status not in {"PASS", "NEEDS_REVIEW"}:
                self.error(
                    "rendered_asset_review_missing",
                    location,
                    "review-pending assets require review_status=NEEDS_REVIEW or PASS",
                )
            receipt_id = normalize_none(row.get("review_receipt_id"))
            if require_pass:
                receipt = review_receipts.get(receipt_id)
                if receipt is None:
                    self.error(
                        "rendered_asset_review_missing",
                        location,
                        f"unknown or missing visual review receipt {receipt_id}",
                    )
                else:
                    reviewed_at = parse_dateish(str(receipt.get("reviewed_at", "")))
                    run_date = parse_iso(self.run.get("created_at", ""))
                    expected_review = {
                        "draft_id": meta.get("draft_id"),
                        "draft_asset_id": asset_id,
                        "asset_sha256": row.get("asset_sha256"),
                        "binding_sha256": meta.get("draft_binding_sha256"),
                        "slide_index": slide_index,
                        "feed_review_status": "PASS",
                        "full_review_status": "PASS",
                        "review_status": "PASS",
                        "reviewer_independence_status": "independent",
                    }
                    review_mismatches = [
                        field
                        for field, expected in expected_review.items()
                        if str(receipt.get(field, "")) != str(expected)
                    ]
                    if (
                        not scope_is_specific(str(receipt.get("reviewer_id", "")))
                        or not scope_is_specific(str(receipt.get("content_owner_id", "")))
                        or receipt.get("reviewer_id") == receipt.get("content_owner_id")
                        or not reviewed_at
                        or (run_date and reviewed_at < run_date)
                        or reviewed_at > date.today()
                    ):
                        review_mismatches.extend(
                            ["content_owner_id", "reviewer_id", "reviewed_at"]
                        )
                    if receipt.get("issues") not in ([], None):
                        review_mismatches.append("issues")
                    if review_mismatches:
                        self.error(
                            "rendered_asset_review_mismatch",
                            location,
                            "visual review receipt disagrees on: "
                            + ", ".join(sorted(set(review_mismatches))),
                        )
            elif receipt_id != "none":
                self.error(
                    "rendered_asset_review_mismatch",
                    location,
                    "rendered_needs_review must not claim a PASS review receipt",
                )
            try:
                width = int(row.get("width", ""))
                height = int(row.get("height", ""))
            except ValueError:
                width = height = 0
            if width < 1 or height < 1:
                self.error(
                    "rendered_asset_receipt_invalid",
                    location,
                    "width and height must be positive integers",
                )
            if row.get("render_method") not in V2_FINAL_RENDER_METHODS:
                self.error(
                    "rendered_asset_receipt_invalid",
                    location,
                    "render_method must be one of: "
                    + ", ".join(sorted(V2_FINAL_RENDER_METHODS)),
                )
            if normalize_none(row.get("starter_prompt_sha256")) != "none":
                self.error(
                    "rendered_asset_receipt_mismatch",
                    location,
                    "starter prompt lineage is disabled; final assets must use the published library binding",
                )
            if normalize_none(row.get("revision_of")) != "none":
                self.error(
                    "rendered_asset_receipt_invalid",
                    location,
                    "final manifest contains current assets only; revision_of must be none",
                )
            raw_asset_path = row.get("asset_path", "").strip()
            asset_path = (self.run_dir / raw_asset_path).resolve()
            try:
                asset_path.relative_to(self.run_dir.resolve())
            except ValueError:
                self.error(
                    "rendered_asset_receipt_invalid",
                    location,
                    "asset_path must stay inside the run directory",
                )
                continue
            if not asset_path.is_file():
                self.error(
                    "rendered_asset_receipt_missing",
                    location,
                    f"asset file is missing: {raw_asset_path}",
                )
                continue
            actual_sha = hashlib.sha256(asset_path.read_bytes()).hexdigest()
            if row.get("asset_sha256") != actual_sha:
                self.error(
                    "rendered_asset_receipt_mismatch",
                    location,
                    "asset_sha256 does not match the final file",
                )
            decoded = self._decoded_image_dimensions(asset_path)
            if decoded is None:
                self.error(
                    "rendered_asset_receipt_invalid",
                    location,
                    "final slide must be a decodable PNG/JPEG/GIF/WebP image by signature",
                )
            elif decoded != (width, height):
                self.error(
                    "rendered_asset_receipt_mismatch",
                    location,
                    "manifest width/height do not match the decoded image",
                )
        if sorted(indices) != list(range(1, len(rows) + 1)):
            self.error(
                "rendered_asset_receipt_invalid",
                path.name,
                "final slide indices must be contiguous from 1 with no gaps or extras",
            )
        if expected_indices and sorted(indices) != sorted(expected_indices):
            self.error(
                "rendered_asset_receipt_mismatch",
                path.name,
                "draft-assets.csv slide indices do not exactly match expected_slide_indices",
            )
        if expected_rules - used_rules:
            self.error(
                "rendered_asset_receipt_mismatch",
                path.name,
                "final assets do not collectively cover every bound style rule: "
                + ", ".join(sorted(expected_rules - used_rules)),
            )
        if not require_pass and review_statuses and all(
            status == "PASS" for status in review_statuses
        ):
            self.error(
                "rendered_asset_review_mismatch",
                path.name,
                "all assets already PASS; use visual_delivery_status=rendered_pass",
            )

    def _check_production_gate_receipts(
        self,
        path: Path,
        meta: dict[str, str],
        receipt_ids: list[str],
    ) -> None:
        receipt_path = self.run_dir / "production-gate-receipts.jsonl"
        if not receipt_path.is_file():
            self.error(
                "production_gate_receipt_missing",
                path.name,
                "production_gate_status=ready requires production-gate-receipts.jsonl",
            )
            return
        rows: dict[str, dict[str, object]] = {}
        try:
            lines = receipt_path.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            self.error("production_gate_receipt_invalid", path.name, str(exc))
            return
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                self.error(
                    "production_gate_receipt_invalid",
                    f"production-gate-receipts.jsonl:{line_number}",
                    exc.msg,
                )
                continue
            receipt_id = row.get("receipt_id") if isinstance(row, dict) else None
            if not isinstance(receipt_id, str) or not receipt_id.strip():
                self.error(
                    "production_gate_receipt_invalid",
                    f"production-gate-receipts.jsonl:{line_number}",
                    "receipt_id is required",
                )
                continue
            if receipt_id in rows:
                self.error(
                    "production_gate_receipt_invalid",
                    f"production-gate-receipts.jsonl:{line_number}",
                    f"duplicate receipt_id {receipt_id}",
                )
                continue
            rows[receipt_id] = row

        registry = self._registry()
        eligibility_rows = [
            registry[value]
            for value in self._contract_ids(meta.get("eligibility_ids"))
            if value in registry
        ]
        expected_skus = {
            row.get("sku_id", "") for row in eligibility_rows if row.get("sku_id", "")
        }
        expected_offers = {
            row.get("offer_id", "") for row in eligibility_rows if row.get("offer_id", "")
        }
        expected_surfaces = set(self._contract_ids(meta.get("surfaces")))
        draft_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        expected_sku_units = {
            (
                row.get("sku_id", ""), row.get("surface", ""),
                row.get("account_scope", ""), row.get("source_asset_id", ""),
                row.get("source_asset_sha256", ""),
            )
            for row in eligibility_rows
            if row.get("sku_id", "")
        }
        expected_offer_units = {
            (
                row.get("offer_id", ""), row.get("surface", ""),
                row.get("account_scope", ""), row.get("source_asset_id", ""),
                row.get("source_asset_sha256", ""),
            )
            for row in eligibility_rows
            if row.get("offer_id", "")
        }
        run_date = parse_iso(self.run.get("created_at", ""))
        required_fields = {
            "receipt_id", "draft_id", "draft_sha256", "exact_sku_id",
            "library_account_id", "delivery_surface", "commercial_relationship",
            "disclosure_text", "audience_age_floor", "minor_access_controls",
            "rule_claim_id", "rule_claim_sha256", "claim_ledger_snapshot_sha256",
            "rule_verified_at", "reviewed_at", "reviewer_id", "gate_status",
            "not_applicable_reason", "brand_role", "agency_role",
            "authorization_scope", "authorization_ids", "authorization_status",
            "authorization_expires_at", "authorization_claim_id",
            "authorization_claim_sha256", "query_matrix_sha256",
            "query_matrix_as_of", "query_matrix_origin", "query_matrix_status",
            "asset_origin_codes", "rights_basis_codes", "consent_status",
            "reuse_scope", "rights_evidence_origin", "rights_evidence_status",
            "rights_evidence_sha256", "series_id", "content_stage", "product_id",
            "ugc_lineage_origin", "ugc_lineage_status", "ugc_lineage_sha256",
            "distribution_mode", "account_capability_codes", "offer_id",
            "destination_id", "asset_version", "metric_name", "metric_source",
            "attribution_source", "distribution_evidence_origin",
            "distribution_evidence_status", "distribution_evidence_sha256",
            "limitations", "receipt_sha256",
        }
        claims = {
            row.get("claim_id", ""): row
            for row in self.rows.get("claim-ledger.csv", [])
            if row.get("claim_id", "")
        }
        sources = {
            row.get("source_id", ""): row
            for row in self.rows.get("source-log.csv", [])
            if row.get("source_id", "")
        }
        authorizations = {
            row.get("authorization_id", ""): row
            for row in self.rows.get("authorization-log.csv", [])
            if row.get("authorization_id", "")
        }
        claim_ledger_path = self.run_dir / "claim-ledger.csv"
        claim_ledger_sha = (
            hashlib.sha256(claim_ledger_path.read_bytes()).hexdigest()
            if claim_ledger_path.is_file()
            else None
        )

        def canonical_row_sha(row: dict[str, str]) -> str:
            return hashlib.sha256(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()

        def is_placeholder(value: object) -> bool:
            normalized = str(value or "").strip().lower()
            return (
                normalized in {
                    "", "unknown", "missing", "required", "none", "null",
                    "required_account", "required_asset_version",
                    "required_destination", "required_exact_sku",
                    "required_human_reviewer", "required_offer",
                    "required_product", "required_relationship",
                    "required_visible_disclosure",
                }
                or normalized.startswith("required_")
                or normalized.startswith("missing_")
            )

        def verify_origin_hash(
            row: dict[str, object],
            *,
            prefix: str,
            mismatches: list[str],
            allow_not_applicable: bool,
        ) -> None:
            status_field = f"{prefix}_status"
            origin_field = f"{prefix}_origin"
            hash_field = f"{prefix}_sha256"
            status = str(row.get(status_field, ""))
            if status == "not_applicable" and allow_not_applicable:
                if is_placeholder(row.get("not_applicable_reason")):
                    mismatches.append("not_applicable_reason")
                return
            if status != "verified":
                mismatches.append(status_field)
                return
            origin = str(row.get(origin_field, "")).strip()
            supplied_hash = str(row.get(hash_field, ""))
            if is_placeholder(origin) or not valid_sha256(supplied_hash):
                mismatches.extend([origin_field, hash_field])
                return
            if "://" not in origin:
                evidence_path = (self.run_dir / origin).resolve()
                try:
                    evidence_path.relative_to(self.run_dir.resolve())
                except ValueError:
                    mismatches.append(origin_field)
                    return
                if not evidence_path.is_file():
                    mismatches.append(origin_field)
                elif hashlib.sha256(evidence_path.read_bytes()).hexdigest() != supplied_hash:
                    mismatches.append(hash_field)

        covered_sku_units: set[tuple[str, str, str, str, str]] = set()
        covered_offer_units: set[tuple[str, str, str, str, str]] = set()
        covered_surfaces: set[str] = set()
        for receipt_id in receipt_ids:
            row = rows.get(receipt_id)
            if row is None:
                self.error(
                    "production_gate_receipt_missing",
                    path.name,
                    f"unknown production gate receipt {receipt_id}",
                )
                continue
            missing = sorted(required_fields - set(row))
            if missing:
                self.error(
                    "production_gate_receipt_invalid",
                    receipt_id,
                    "missing fields: " + ", ".join(missing),
                )
                continue
            canonical = dict(row)
            supplied_sha = canonical.pop("receipt_sha256", None)
            calculated_sha = hashlib.sha256(
                json.dumps(
                    canonical,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            if supplied_sha != calculated_sha:
                self.error(
                    "production_gate_receipt_invalid",
                    receipt_id,
                    "receipt_sha256 does not match the canonical receipt",
                )
            reviewed_at = parse_dateish(str(row.get("reviewed_at", "")))
            rule_verified_at = parse_dateish(str(row.get("rule_verified_at", "")))
            query_matrix_as_of = parse_dateish(str(row.get("query_matrix_as_of", "")))
            floor = row.get("audience_age_floor")
            try:
                age_floor = int(floor) if not isinstance(floor, bool) else 0
            except (TypeError, ValueError):
                age_floor = 0
            exact_checks = {
                "draft_id": meta.get("draft_id"),
                "draft_sha256": draft_sha,
                "library_account_id": meta.get("account_scope"),
                "commercial_relationship": meta.get("commercial_relationship"),
                "disclosure_text": meta.get("disclosure_text"),
                "gate_status": "pass",
                "authorization_status": "approved",
                "rights_evidence_status": "verified",
                "consent_status": "approved",
                "query_matrix_status": "verified",
            }
            mismatches = [
                field
                for field, expected in exact_checks.items()
                if str(row.get(field, "")) != str(expected)
            ]
            sku_id = str(row.get("exact_sku_id", ""))
            offer_id = str(row.get("offer_id", ""))
            surface = str(row.get("delivery_surface", ""))
            sku_unit = (
                sku_id, surface, str(row.get("library_account_id", "")),
                str(row.get("draft_id", "")), str(row.get("draft_sha256", "")),
            )
            offer_unit = (
                offer_id, surface, str(row.get("library_account_id", "")),
                str(row.get("draft_id", "")), str(row.get("draft_sha256", "")),
            )
            if expected_sku_units:
                if sku_unit not in expected_sku_units:
                    mismatches.append("exact_sku_id")
            elif sku_id != "not_applicable":
                mismatches.append("exact_sku_id")
            if expected_offer_units:
                if offer_unit not in expected_offer_units:
                    mismatches.append("offer_id")
            elif offer_id != "not_applicable":
                mismatches.append("offer_id")
            if row.get("delivery_surface") not in expected_surfaces:
                mismatches.append("delivery_surface")
            if age_floor < 18:
                mismatches.append("audience_age_floor")
            for field in (
                "minor_access_controls", "asset_origin_codes", "rights_basis_codes",
                "reuse_scope", "limitations", "authorization_ids",
            ):
                values = row.get(field)
                if (
                    not isinstance(values, list)
                    or not values
                    or not all(isinstance(value, str) and not is_placeholder(value) for value in values)
                ):
                    mismatches.append(field)
            if not reviewed_at or (run_date and reviewed_at != run_date):
                mismatches.append("reviewed_at")
            if not rule_verified_at or (run_date and rule_verified_at > run_date):
                mismatches.append("rule_verified_at")
            if not query_matrix_as_of or (run_date and query_matrix_as_of > run_date):
                mismatches.append("query_matrix_as_of")
            authorization_expires_at = row.get("authorization_expires_at")
            if authorization_expires_at not in {None, "", "not_applicable"}:
                expires = parse_dateish(str(authorization_expires_at))
                if not expires or (run_date and expires < run_date):
                    mismatches.append("authorization_expires_at")
            for field in (
                "asset_version", "destination_id", "reviewer_id", "brand_role",
                "agency_role", "authorization_scope", "content_stage", "product_id",
                "distribution_mode",
            ):
                if is_placeholder(row.get(field)):
                    mismatches.append(field)

            if row.get("claim_ledger_snapshot_sha256") != claim_ledger_sha:
                mismatches.append("claim_ledger_snapshot_sha256")
            for id_field, hash_field in (
                ("rule_claim_id", "rule_claim_sha256"),
                ("authorization_claim_id", "authorization_claim_sha256"),
            ):
                claim_id = str(row.get(id_field, ""))
                claim = claims.get(claim_id)
                if claim is None:
                    mismatches.append(id_field)
                    continue
                if row.get(hash_field) != canonical_row_sha(claim):
                    mismatches.append(hash_field)
                if claim.get("claim_status") != "confirmed":
                    mismatches.append(id_field)
                verified = parse_dateish(claim.get("last_verified_at", ""))
                if not verified or (run_date and verified > run_date):
                    mismatches.append(id_field)
            rule_claim = claims.get(str(row.get("rule_claim_id", "")))
            if rule_claim and parse_dateish(rule_claim.get("last_verified_at", "")) != rule_verified_at:
                mismatches.append("rule_verified_at")
            base_claim_scope = {
                "platform": meta.get("platform"),
                "account_scope": meta.get("account_scope"),
                "surface": surface,
                "draft_id": meta.get("draft_id"),
                "draft_sha256": draft_sha,
            }
            if expected_skus:
                base_claim_scope["sku_id"] = sku_id
            if expected_offers:
                base_claim_scope["offer_id"] = offer_id
            if rule_claim:
                if rule_claim.get("category") not in {
                    "current_rule", "current_rules", "platform_capability",
                    "compliance", "advertising_law", "governance",
                    "sku_eligibility", "offer_eligibility",
                }:
                    mismatches.append("rule_claim_id")
                rule_scope = parse_scope_contract(rule_claim.get("scope"))
                if any(
                    not platforms_equivalent(rule_scope.get(field), expected)
                    if field == "platform"
                    else rule_scope.get(field) != expected
                    for field, expected in base_claim_scope.items()
                ):
                    mismatches.append("rule_claim_id")
                official_sources = [
                    sources[value]
                    for value in split_ids(rule_claim.get("source_ids"))
                    if value in sources
                    and sources[value].get("source_layer") == "official"
                    and sources[value].get("access_status") in {"full", "partial"}
                    and sources[value].get("evidence_grade") in {"A", "B"}
                ]
                if not official_sources:
                    mismatches.append("rule_claim_id")

            receipt_authorization_ids = row.get("authorization_ids")
            if isinstance(receipt_authorization_ids, list):
                authorization_id_set = {
                    value for value in receipt_authorization_ids if isinstance(value, str)
                }
            else:
                authorization_id_set = set()
            authorization_rows = [
                authorizations[value]
                for value in authorization_id_set
                if value in authorizations
            ]
            if len(authorization_rows) != len(authorization_id_set) or not authorization_rows:
                mismatches.append("authorization_ids")
            for authorization in authorization_rows:
                expires = parse_dateish(authorization.get("expires_at", ""))
                if not (
                    authorization.get("status") == "approved"
                    and authorization.get("commercial_use") == "approved"
                    and authorization.get("source_asset_id") == meta.get("draft_id")
                    and (not authorization.get("expires_at") or not run_date or (expires and expires >= run_date))
                ):
                    mismatches.append("authorization_ids")
            authorization_claim = claims.get(str(row.get("authorization_claim_id", "")))
            if authorization_claim:
                if authorization_claim.get("category") not in {
                    "authorization", "rights", "material_rights", "consent",
                    "commercial_authorization",
                }:
                    mismatches.append("authorization_claim_id")
                authorization_scope = parse_scope_contract(
                    authorization_claim.get("scope")
                )
                expected_authorization_scope = dict(base_claim_scope)
                expected_authorization_scope["authorization_ids"] = ";".join(
                    sorted(authorization_id_set)
                )
                if any(
                    not platforms_equivalent(authorization_scope.get(field), expected)
                    if field == "platform"
                    else authorization_scope.get(field) != expected
                    for field, expected in expected_authorization_scope.items()
                ):
                    mismatches.append("authorization_claim_id")

            verify_origin_hash(
                row, prefix="query_matrix", mismatches=mismatches,
                allow_not_applicable=False,
            )
            verify_origin_hash(
                row, prefix="rights_evidence", mismatches=mismatches,
                allow_not_applicable=False,
            )
            verify_origin_hash(
                row, prefix="ugc_lineage", mismatches=mismatches,
                allow_not_applicable=True,
            )
            paid_distribution = str(row.get("distribution_mode", "")) in {
                "paid", "boosted", "paid_and_organic", "pgy_paid",
            }
            verify_origin_hash(
                row, prefix="distribution_evidence", mismatches=mismatches,
                allow_not_applicable=not paid_distribution,
            )
            capabilities = row.get("account_capability_codes")
            if paid_distribution and (
                not isinstance(capabilities, list)
                or not capabilities
                or not all(isinstance(value, str) and not is_placeholder(value) for value in capabilities)
            ):
                mismatches.append("account_capability_codes")
            if paid_distribution:
                for field in ("metric_name", "metric_source", "attribution_source"):
                    if is_placeholder(row.get(field)):
                        mismatches.append(field)
            if mismatches:
                self.error(
                    "production_gate_receipt_mismatch",
                    receipt_id,
                    "receipt disagrees or is incomplete on: "
                    + ", ".join(sorted(set(mismatches))),
                )
            else:
                if expected_sku_units:
                    covered_sku_units.add(sku_unit)
                if expected_offer_units:
                    covered_offer_units.add(offer_unit)
                covered_surfaces.add(surface)

        coverage_gaps: list[str] = []
        if covered_sku_units != expected_sku_units:
            coverage_gaps.append(
                f"sku units expected={sorted(expected_sku_units)} covered={sorted(covered_sku_units)}"
            )
        if covered_offer_units != expected_offer_units:
            coverage_gaps.append(
                f"offer units expected={sorted(expected_offer_units)} covered={sorted(covered_offer_units)}"
            )
        if covered_surfaces != expected_surfaces:
            coverage_gaps.append(
                f"surface expected={sorted(expected_surfaces)} covered={sorted(covered_surfaces)}"
            )
        if coverage_gaps:
            self.error(
                "production_gate_scope_incomplete",
                path.name,
                "; ".join(coverage_gaps),
            )

    @staticmethod
    def _contract_ids(value: str | None) -> list[str]:
        return [item for item in split_ids(value) if item.lower() != "none"]

    def _known_evidence_ids(self) -> tuple[set[str], set[str]]:
        known: set[str] = set()
        authorization_ids: set[str] = set()
        for filename, id_field in ID_FIELDS.items():
            for row in self.rows.get(filename, []):
                value = row.get(id_field, "").strip()
                if value:
                    known.add(value)
                    if filename == "authorization-log.csv":
                        authorization_ids.add(value)
        for row in self.rows.get("authorization-log.csv", []):
            material_id = row.get("material_id", "").strip()
            if material_id:
                known.add(material_id)
        return known, authorization_ids

    def _evidence_id_types(self) -> dict[str, set[str]]:
        typed: dict[str, set[str]] = {}

        def add(value: str, ref_type: str) -> None:
            value = (value or "").strip()
            if value:
                typed.setdefault(value, set()).add(ref_type)

        file_types = {
            "query-log.csv": ("query_id", "query"),
            "source-log.csv": ("source_id", "source"),
            "claim-ledger.csv": ("claim_id", "claim"),
            "accounts.csv": ("account_id", "account"),
            "posts.csv": ("post_id", "post"),
            "topics.csv": ("topic_id", "topic"),
            "sku-registry.csv": ("eligibility_id", "eligibility"),
            "offer-registry.csv": ("eligibility_id", "eligibility"),
            "authorization-log.csv": ("authorization_id", "authorization"),
        }
        for filename, (id_field, ref_type) in file_types.items():
            for row in self.rows.get(filename, []):
                add(row.get(id_field, ""), ref_type)
        for row in self.rows.get("authorization-log.csv", []):
            add(row.get("material_id", ""), "authorized_material")
        return typed

    def _contract_json(
        self,
        path: Path,
        contract: dict[str, str],
        key: str,
        expected_type: type,
    ) -> object | None:
        raw = contract.get(key, "").strip()
        if raw.lower() in {"", "none"}:
            return None
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            self.error(
                "mechanism_contract_json",
                path.name,
                f"{key} must be one-line valid JSON: {exc.msg}",
            )
            return None
        if not isinstance(value, expected_type):
            self.error(
                "mechanism_contract_json",
                path.name,
                f"{key} must be a JSON {expected_type.__name__}",
            )
            return None
        return value

    def _check_v2_mechanism_contract(
        self,
        path: Path,
        rendered_text: str,
        meta: dict[str, str],
        headings: set[str],
    ) -> None:
        if "流量机制绑定" not in headings:
            return
        contract = parse_contract_block(markdown_section(rendered_text, "流量机制绑定"))
        missing = sorted(V2_MECHANISM_CONTRACT_FIELDS - contract.keys())
        if missing:
            self.error(
                "mechanism_contract_missing",
                path.name,
                "流量机制绑定 missing keys: " + ", ".join(missing),
            )
            return

        status = contract.get("contract_status", "")
        if status not in V2_MECHANISM_CONTRACT_STATUSES:
            self.error(
                "mechanism_contract_status",
                path.name,
                f"invalid contract_status: {status}",
            )
            return
        selected_ids = self._contract_ids(contract.get("mechanism_ids"))
        counterexample_ids = self._contract_ids(contract.get("counterexample_ids"))
        material_codes = set(self._contract_ids(contract.get("material_codes")))
        draft_status = meta.get("status", "")
        research_gap = contract.get("research_gap", "").strip()

        if status == "needs_research":
            if selected_ids or counterexample_ids or material_codes:
                self.error(
                    "mechanism_contract_unbound",
                    path.name,
                    "needs_research cannot claim mechanism, counterexample, or material bindings",
                )
            for key in ("primary_mechanism_id", "material_evidence_map", "mechanism_application_map"):
                if contract.get(key, "").strip().lower() not in {"", "none", "{}"}:
                    self.error(
                        "mechanism_contract_unbound",
                        path.name,
                        f"needs_research requires {key}=none",
                    )
            if not research_gap or research_gap.lower() == "none":
                self.error(
                    "mechanism_research_gap_missing",
                    path.name,
                    "needs_research must name the exact missing evidence or materials",
                )
            if draft_status == "ready":
                self.error(
                    "mechanism_contract_unbound",
                    path.name,
                    "an unbound mechanism contract cannot be ready",
                )
            return

        if status == "bound_candidate" and (
            meta.get("style_binding_status") != "needs_style_research"
            or draft_status != "needs_review"
        ):
            self.error(
                "mechanism_candidate_status",
                path.name,
                "bound_candidate requires style_binding_status=needs_style_research and status=needs_review",
            )
        if status == "bound_grounded" and meta.get("style_binding_status") != "grounded":
            self.error(
                "mechanism_grounded_status",
                path.name,
                "bound_grounded requires an independently published grounded style binding",
            )

        cards = self.traffic_mechanism_library.get("mechanisms", [])
        card_by_id = {
            card.get("mechanism_id"): card
            for card in cards
            if isinstance(card, dict) and card.get("mechanism_id")
        }
        unknown_ids = sorted(set(selected_ids) - set(card_by_id))
        if unknown_ids:
            self.error(
                "unknown_mechanism_id",
                path.name,
                "unknown mechanism IDs: " + ", ".join(unknown_ids),
            )
        if len(selected_ids) != 3 or len(set(selected_ids)) != 3:
            self.error(
                "mechanism_stack_shape",
                path.name,
                "bound contract must select exactly three distinct mechanisms",
            )
        selected_cards = [card_by_id[value] for value in selected_ids if value in card_by_id]
        primary_id = contract.get("primary_mechanism_id", "").strip()
        if primary_id not in selected_ids or card_by_id.get(primary_id, {}).get("mechanism_kind") != "content":
            self.error(
                "primary_mechanism_mismatch",
                path.name,
                "primary_mechanism_id must identify the selected content mechanism",
            )

        slot_counts = {slot: 0 for slot in V2_MECHANISM_SLOTS}
        for card in selected_cards:
            kind = card.get("mechanism_kind")
            for slot, kinds in V2_MECHANISM_SLOTS.items():
                if kind in kinds:
                    slot_counts[slot] += 1
                    break
        if any(count != 1 for count in slot_counts.values()):
            self.error(
                "mechanism_stack_shape",
                path.name,
                "mechanism stack requires one content, one carrier/truth, and one learning/governance card",
            )

        job = meta.get("primary_job", "")
        stage = meta.get("traffic_stage", "")
        carrier = meta.get("style_query_carrier", "")
        for card in selected_cards:
            mechanism_id = card["mechanism_id"]
            activation = card.get("activation", {})
            if job not in activation.get("eligible_primary_jobs", []):
                self.error(
                    "mechanism_job_mismatch",
                    path.name,
                    f"{mechanism_id} is not eligible for primary_job={job}",
                )
            if stage not in activation.get("eligible_traffic_stages", []):
                self.error(
                    "mechanism_stage_mismatch",
                    path.name,
                    f"{mechanism_id} is not eligible for traffic_stage={stage}",
                )
            fit = card.get("carrier_task_fit", {})
            if carrier not in set(fit.get("preferred", [])) | set(fit.get("compatible", [])):
                self.error(
                    "mechanism_carrier_mismatch",
                    path.name,
                    f"{mechanism_id} is not task-fit for carrier={carrier}",
                )
            missing_materials = set(card.get("required_material_codes", [])) - material_codes
            forbidden_materials = set(card.get("forbidden_material_codes", [])) & material_codes
            if missing_materials or forbidden_materials:
                self.error(
                    "mechanism_material_gate",
                    path.name,
                    f"{mechanism_id} missing={sorted(missing_materials)} forbidden={sorted(forbidden_materials)}",
                )
            missing_requires = set(card.get("requires", [])) - set(selected_ids)
            conflicts = set(card.get("conflicts_with", [])) & set(selected_ids)
            if missing_requires or conflicts:
                self.error(
                    "mechanism_relation_gate",
                    path.name,
                    f"{mechanism_id} missing_requires={sorted(missing_requires)} conflicts={sorted(conflicts)}",
                )

        known_materials = set(self.traffic_mechanism_library.get("material_code_taxonomy", []))
        known_forbidden = set(
            self.traffic_mechanism_library.get("forbidden_material_code_taxonomy", [])
        )
        unknown_materials = sorted(material_codes - known_materials - known_forbidden)
        if unknown_materials:
            self.error(
                "mechanism_material_gate",
                path.name,
                "unknown material codes: " + ", ".join(unknown_materials),
            )
        globally_forbidden = sorted(material_codes & known_forbidden)
        if globally_forbidden:
            self.error(
                "mechanism_material_gate",
                path.name,
                "globally forbidden material codes cannot be selected: "
                + ", ".join(globally_forbidden),
            )
        carrier_truth = self.traffic_mechanism_library.get("carrier_truth_conditions", {}).get(
            carrier, {}
        )
        carrier_truth_required_codes: set[str] = set()
        if carrier_truth:
            required_all = set(carrier_truth.get("required_all_material_codes", []))
            carrier_truth_required_codes.update(required_all)
            truth_missing = required_all - material_codes
            required_any = set(carrier_truth.get("required_any_material_codes", []))
            selected_any = required_any.intersection(material_codes)
            carrier_truth_required_codes.update(selected_any)
            if required_any and not selected_any:
                truth_missing.add(carrier_truth.get("missing_material_code", "carrier_truth_material"))
            truth_forbidden = set(carrier_truth.get("forbidden_material_codes", [])) & material_codes
            if truth_missing or truth_forbidden:
                self.error(
                    "carrier_truth_gate",
                    path.name,
                    f"carrier={carrier} missing={sorted(truth_missing)} forbidden={sorted(truth_forbidden)}",
                )

        known_ids, authorization_ids = self._known_evidence_ids()
        evidence_types = self._evidence_id_types()
        counterexample_capable_ids = {
            evidence_id
            for evidence_id, ref_types in evidence_types.items()
            if ref_types.intersection({"source", "claim", "account", "post"})
        }
        unknown_counterexamples = sorted(
            set(counterexample_ids) - counterexample_capable_ids
        )
        if not counterexample_ids or unknown_counterexamples:
            self.error(
                "counterexample_binding",
                path.name,
                "bound mechanism contract needs a real local counterexample ID; unknown="
                + ", ".join(unknown_counterexamples),
            )
        topic = next(
            (
                row
                for row in self.rows.get("topics.csv", [])
                if row.get("topic_id") == meta.get("topic_id")
            ),
            None,
        )
        declared_counterexamples: set[str] = set()
        if topic is not None:
            counter_text = topic.get("counterexamples", "")
            declared_counterexamples = {
                evidence_id
                for evidence_id in counterexample_capable_ids
                if re.search(
                    rf"(?<![A-Za-z0-9_-]){re.escape(evidence_id)}(?![A-Za-z0-9_-])",
                    counter_text,
                )
            }
        undeclared_counterexamples = sorted(
            set(counterexample_ids) - declared_counterexamples
        )
        if undeclared_counterexamples:
            self.error(
                "counterexample_binding",
                path.name,
                "counterexample IDs must be declared with bounded interpretation on the selected topic: "
                + ", ".join(undeclared_counterexamples),
            )

        material_map = self._contract_json(path, contract, "material_evidence_map", dict)
        application_map = self._contract_json(path, contract, "mechanism_application_map", dict)
        if not isinstance(material_map, dict):
            self.error(
                "material_evidence_binding",
                path.name,
                "bound contract requires material_evidence_map to be a non-empty JSON object",
            )
        if not isinstance(application_map, dict):
            self.error(
                "mechanism_application_binding",
                path.name,
                "bound contract requires mechanism_application_map to be a non-empty JSON object",
            )
        draft_prefix = meta.get("draft_id", "") + "#"
        self_produced_codes = {
            "promise",
            "ai_draft",
            "human_review",
            "variant_log",
            "version_log",
            "series_promise",
        }
        required_codes = {
            code
            for card in selected_cards
            for code in card.get("required_material_codes", [])
        }
        required_codes.update(carrier_truth_required_codes)
        bound_material_refs: set[str] = set()
        material_refs_by_code: dict[str, set[str]] = {}
        if isinstance(material_map, dict):
            missing_codes = sorted(required_codes - set(material_map))
            if missing_codes:
                self.error(
                    "material_evidence_binding",
                    path.name,
                    "missing material evidence for: " + ", ".join(missing_codes),
                )
            for code in required_codes & set(material_map):
                refs = material_map.get(code)
                if not isinstance(refs, list) or not refs or not all(
                    isinstance(value, str) and value.strip() for value in refs
                ):
                    self.error(
                        "material_evidence_binding",
                        path.name,
                        f"{code} must map to a non-empty JSON string array",
                    )
                    continue
                real_refs = {value for value in refs if value in known_ids}
                draft_refs = {
                    value for value in refs if draft_prefix and value.startswith(draft_prefix)
                }
                unknown_refs = set(refs) - real_refs - draft_refs
                valid_refs = real_refs | draft_refs
                material_refs_by_code[code] = valid_refs
                bound_material_refs.update(valid_refs)
                if unknown_refs:
                    self.error(
                        "material_evidence_binding",
                        path.name,
                        f"{code} has unknown evidence refs: {sorted(unknown_refs)}",
                    )
                allowed_ref_types = V2_MATERIAL_REF_TYPES.get(code)
                if allowed_ref_types is None:
                    self.error(
                        "material_evidence_binding",
                        path.name,
                        f"{code} has no controlled evidence-type contract",
                    )
                else:
                    incompatible_refs = sorted(
                        value
                        for value in refs
                        if not (
                            ({"draft_anchor"} if value in draft_refs else evidence_types.get(value, set()))
                            & allowed_ref_types
                        )
                    )
                    if incompatible_refs:
                        self.error(
                            "material_evidence_binding",
                            path.name,
                            f"{code} has incompatible evidence ID types: {incompatible_refs}",
                        )
                if code not in self_produced_codes and not real_refs:
                    self.error(
                        "material_evidence_binding",
                        path.name,
                        f"{code} requires at least one local source/post/claim/material ID",
                    )
                if code == "rights_clearance" and not set(refs).intersection(authorization_ids):
                    self.error(
                        "material_evidence_binding",
                        path.name,
                        "rights_clearance requires a referenced authorization_id",
                    )
        overlap = sorted(set(counterexample_ids).intersection(bound_material_refs))
        if overlap:
            self.error(
                "counterexample_binding",
                path.name,
                "counterexample IDs cannot also be bound as supporting material: "
                + ", ".join(overlap),
            )
        if "first_party_metrics" in material_codes and meta.get(
            "performance_visibility_scope"
        ) != "first_party_analytics":
            self.error(
                "mechanism_material_gate",
                path.name,
                "first_party_metrics cannot be claimed under a public_proxy or unavailable scope",
            )

        if isinstance(application_map, dict):
            if set(application_map) != set(selected_ids):
                self.error(
                    "mechanism_application_binding",
                    path.name,
                    "mechanism_application_map keys must exactly equal mechanism_ids",
                )
            for mechanism_id in set(selected_ids).intersection(application_map):
                item = application_map.get(mechanism_id)
                if not isinstance(item, dict):
                    self.error(
                        "mechanism_application_binding",
                        path.name,
                        f"{mechanism_id} application must be an object",
                    )
                    continue
                required_fields = {
                    "input_refs",
                    "title_action",
                    "cover_action",
                    "body_action",
                    "comments_action",
                    "job_metric",
                    "failure_condition",
                    "intentional_deviation",
                }
                missing_fields = sorted(required_fields - set(item))
                if missing_fields:
                    self.error(
                        "mechanism_application_binding",
                        path.name,
                        f"{mechanism_id} missing application fields: {', '.join(missing_fields)}",
                    )
                    continue
                input_refs = item.get("input_refs")
                if not isinstance(input_refs, list) or not input_refs:
                    self.error(
                        "mechanism_application_binding",
                        path.name,
                        f"{mechanism_id} input_refs must be a non-empty array",
                    )
                elif not all(isinstance(value, str) for value in input_refs):
                    self.error(
                        "mechanism_application_binding",
                        path.name,
                        f"{mechanism_id} input_refs must contain only string IDs",
                    )
                else:
                    unbound_inputs = sorted(set(input_refs) - bound_material_refs)
                    if unbound_inputs:
                        self.error(
                            "mechanism_application_binding",
                            path.name,
                            f"{mechanism_id} input_refs are not in material_evidence_map: {unbound_inputs}",
                        )
                    card = card_by_id.get(mechanism_id, {})
                    card_required_codes = set(card.get("required_material_codes", []))
                    if card.get("mechanism_kind") in {"carrier_router", "truth_gate"}:
                        card_required_codes.update(carrier_truth_required_codes)
                    uncovered_codes = sorted(
                        code
                        for code in card_required_codes
                        if not set(input_refs).intersection(
                            material_refs_by_code.get(code, set())
                        )
                    )
                    if uncovered_codes:
                        self.error(
                            "mechanism_application_binding",
                            path.name,
                            f"{mechanism_id} input_refs do not cover its required material codes: {uncovered_codes}",
                        )
                for field in (
                    "title_action",
                    "cover_action",
                    "body_action",
                    "comments_action",
                    "intentional_deviation",
                ):
                    value = item.get(field)
                    substantive = False
                    if isinstance(value, str):
                        cleaned = value.strip()
                        lowered = cleaned.lower()
                        placeholders = {
                            "", "none", "unknown", "tbd", "todo", "n/a", "na",
                            "待填写", "待定", "暂无", "无",
                        }
                        if lowered.startswith("not_applicable:"):
                            reason = cleaned.split(":", 1)[1].strip()
                            substantive = len(reason) >= 4 and reason.lower() not in placeholders
                        elif cleaned.startswith("不适用："):
                            reason = cleaned.split("：", 1)[1].strip()
                            substantive = len(reason) >= 4 and reason.lower() not in placeholders
                        else:
                            substantive = (
                                lowered not in placeholders
                                and not lowered.startswith(("tbd:", "todo:", "待填写："))
                                and len(re.sub(r"\W+", "", cleaned, flags=re.UNICODE)) >= 6
                            )
                    if not substantive:
                        self.error(
                            "mechanism_application_binding",
                            path.name,
                            f"{mechanism_id} {field} must be substantive or not_applicable: reason",
                        )
                if item.get("job_metric") != meta.get("job_primary_metric"):
                    self.error(
                        "mechanism_application_binding",
                        path.name,
                        f"{mechanism_id} job_metric must match the draft job_primary_metric",
                    )
                card = card_by_id.get(mechanism_id, {})
                if item.get("failure_condition") not in card.get("failure_conditions", []):
                    self.error(
                        "mechanism_application_binding",
                        path.name,
                        f"{mechanism_id} failure_condition must quote one packaged failure condition exactly",
                    )

    def _resolve_visual_contract_file(
        self,
        path: Path,
        raw_path: str,
        supplied_sha256: str,
        label: str,
    ) -> Path | None:
        if normalize_none(raw_path) == "none":
            return None
        if not valid_sha256(supplied_sha256):
            self.error(
                "visual_contract_artifact_invalid",
                path.name,
                f"{label} requires a 64-character SHA-256",
            )
            return None
        resolved = (self.run_dir / raw_path).resolve()
        try:
            resolved.relative_to(self.run_dir.resolve())
        except ValueError:
            self.error(
                "visual_contract_artifact_invalid",
                path.name,
                f"{label} must stay inside the run directory",
            )
            return None
        if not resolved.is_file():
            self.error(
                "visual_contract_artifact_missing",
                path.name,
                f"{label} does not exist: {raw_path}",
            )
            return None
        actual_sha = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if actual_sha != supplied_sha256:
            self.error(
                "visual_contract_artifact_mismatch",
                path.name,
                f"{label} SHA-256 does not match its bytes",
            )
            return None
        return resolved

    def _check_visual_prototypes(
        self,
        path: Path,
        meta: dict[str, str],
        selected_card_ids: list[str],
    ) -> None:
        if Image is None:
            self.error(
                "visual_decoder_unavailable",
                path.name,
                "prototype artifact validation requires Pillow; install redbook-writing/requirements-visual.txt",
            )
            return
        prototype_path = self.run_dir / "visual-prototypes.csv"
        if not prototype_path.is_file():
            self.error(
                "visual_prototype_artifact_missing",
                path.name,
                "prototype_only requires visual-prototypes.csv and viewable prototype files",
            )
            return
        try:
            with prototype_path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                fields = set(reader.fieldnames or [])
                rows = [
                    row for row in reader
                    if row.get("draft_id") == meta.get("draft_id")
                ]
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            self.error("visual_prototype_artifact_invalid", path.name, str(exc))
            return
        if fields != V2_VISUAL_PROTOTYPE_FIELDS:
            self.error(
                "visual_prototype_artifact_invalid",
                "visual-prototypes.csv",
                "header must exactly match the v2 prototype contract",
            )
            return
        if not rows:
            self.error(
                "visual_prototype_artifact_missing",
                path.name,
                "no visual prototype rows match this draft_id",
            )
            return
        brief_path = self.run_dir / "visual-briefs.jsonl"
        briefs: dict[str, dict[str, object]] = {}
        if not brief_path.is_file():
            self.error(
                "visual_brief_artifact_missing",
                path.name,
                "prototype_only requires visual-briefs.jsonl",
            )
        else:
            try:
                for line_number, line in enumerate(
                    brief_path.read_text(encoding="utf-8-sig").splitlines(), start=1
                ):
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    if not isinstance(item, dict):
                        raise ValueError("visual brief row must be an object")
                    brief_id = item.get("visual_brief_id")
                    if not isinstance(brief_id, str) or not brief_id or brief_id in briefs:
                        raise ValueError("visual_brief_id must be present and unique")
                    if set(item) != V2_VISUAL_BRIEF_FIELDS:
                        raise ValueError("visual brief fields do not match the v2 contract")
                    canonical = dict(item)
                    supplied_sha = canonical.pop("visual_brief_sha256", None)
                    calculated_sha = hashlib.sha256(
                        json.dumps(
                            canonical,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest()
                    if supplied_sha != calculated_sha:
                        raise ValueError("visual_brief_sha256 mismatch")
                    briefs[brief_id] = item
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self.error("visual_brief_artifact_invalid", path.name, str(exc))
        concept_ids = [row.get("concept_id", "") for row in rows]
        if sorted(concept_ids) != sorted(selected_card_ids) or len(set(concept_ids)) != len(rows):
            self.error(
                "visual_prototype_binding_mismatch",
                path.name,
                "prototype concept_id values must exactly equal the selected direction-card IDs",
            )
        used_brief_ids = {row.get("visual_brief_id", "") for row in rows}
        for brief_id in sorted(used_brief_ids):
            brief = briefs.get(brief_id)
            if brief is None:
                self.error(
                    "visual_brief_artifact_missing",
                    path.name,
                    f"prototype references unknown visual brief {brief_id}",
                )
                continue
            attention_paths = brief.get("attention_paths")
            if not isinstance(attention_paths, list) or attention_paths != selected_card_ids:
                self.error(
                    "visual_prototype_binding_mismatch",
                    brief_id,
                    "visual brief attention_paths must exactly equal selected direction cards",
                )
            exact_brief_fields = {
                "draft_id": meta.get("draft_id"),
                "primary_job": meta.get("primary_job"),
                "carrier": meta.get("style_query_carrier"),
                "model_lifecycle_stage": "explore",
            }
            for field, expected in exact_brief_fields.items():
                if str(brief.get(field, "")) != str(expected):
                    self.error(
                        "visual_prototype_binding_mismatch",
                        brief_id,
                        f"visual brief {field} does not match the draft",
                    )
            if brief.get("prototype_count") != len(selected_card_ids):
                self.error(
                    "visual_prototype_binding_mismatch",
                    brief_id,
                    "visual brief prototype_count does not match selected directions",
                )
            if not valid_sha256(str(brief.get("generation_prompt_sha256", ""))):
                self.error(
                    "visual_brief_artifact_invalid",
                    brief_id,
                    "generation_prompt_sha256 must be a SHA-256",
                )
            expected_binding = (
                meta.get("draft_binding_sha256")
                if meta.get("style_binding_status") == "grounded"
                else "none"
            )
            if normalize_none(str(brief.get("binding_snapshot_sha256", ""))) != normalize_none(
                expected_binding
            ):
                self.error(
                    "visual_prototype_binding_mismatch",
                    brief_id,
                    "visual brief binding snapshot does not match the draft",
                )
        prototype_ids = {row.get("prototype_asset_id", "") for row in rows}
        if "" in prototype_ids or len(prototype_ids) != len(rows):
            self.error(
                "visual_prototype_artifact_invalid",
                path.name,
                "prototype_asset_id values must be present and unique",
            )
        for row_number, row in enumerate(rows, start=2):
            location = f"visual-prototypes.csv:{row_number}"
            brief = briefs.get(row.get("visual_brief_id", ""))
            if row.get("attention_path") != row.get("concept_id"):
                self.error(
                    "visual_prototype_binding_mismatch",
                    location,
                    "attention_path and concept_id must both use the selected direction-card ID",
                )
            if brief and row.get("prototype_prompt_sha256") != brief.get(
                "generation_prompt_sha256"
            ):
                self.error(
                    "visual_prototype_binding_mismatch",
                    location,
                    "prototype prompt hash must match its immutable visual brief",
                )
            for hash_field in (
                "prototype_prompt_sha256", "asset_sha256", "feed_preview_sha256",
            ):
                if not valid_sha256(row.get(hash_field)):
                    self.error(
                        "visual_prototype_artifact_invalid",
                        location,
                        f"{hash_field} must be a SHA-256",
                    )
            try:
                width = int(row.get("width", ""))
                height = int(row.get("height", ""))
            except ValueError:
                width = height = 0
            if width < 1 or height < 1:
                self.error(
                    "visual_prototype_artifact_invalid",
                    location,
                    "width and height must be positive integers",
                )
            for path_field, hash_field in (
                ("asset_path", "asset_sha256"),
                ("feed_preview_path", "feed_preview_sha256"),
            ):
                raw = row.get(path_field, "").strip()
                resolved = (self.run_dir / raw).resolve()
                try:
                    resolved.relative_to(self.run_dir.resolve())
                except ValueError:
                    self.error(
                        "visual_prototype_artifact_invalid",
                        location,
                        f"{path_field} must stay inside the run directory",
                    )
                    continue
                if not resolved.is_file():
                    self.error(
                        "visual_prototype_artifact_missing",
                        location,
                        f"missing {path_field}: {raw}",
                    )
                    continue
                if hashlib.sha256(resolved.read_bytes()).hexdigest() != row.get(hash_field):
                    self.error(
                        "visual_prototype_artifact_mismatch",
                        location,
                        f"{hash_field} does not match {path_field}",
                    )
                decoded = self._decoded_image_dimensions(resolved)
                if decoded is None:
                    self.error(
                        "visual_prototype_artifact_invalid",
                        location,
                        f"{path_field} must be a decodable PNG/JPEG/GIF/WebP by signature",
                    )
                elif path_field == "asset_path" and decoded != (width, height):
                    self.error(
                        "visual_prototype_artifact_mismatch",
                        location,
                        "prototype width/height do not match the decoded image",
                    )
            if row.get("feed_review_status") != "PASS":
                self.error(
                    "visual_prototype_review_missing",
                    location,
                    "prototype requires feed_review_status=PASS",
                )
            if row.get("full_review_status") not in {"PASS", "NEEDS_REVIEW"}:
                self.error(
                    "visual_prototype_review_missing",
                    location,
                    "full_review_status must be PASS or NEEDS_REVIEW",
                )
            if row.get("selection_status") not in {"selected", "rejected", "pending"}:
                self.error(
                    "visual_prototype_review_missing",
                    location,
                    "selection_status must be selected, rejected, or pending",
                )
            if not row.get("selection_reason", "").strip():
                self.error(
                    "visual_prototype_review_missing",
                    location,
                    "selection_reason is required",
                )
            if meta.get("style_binding_status") == "grounded":
                if row.get("binding_rule_bundle_sha256") != meta.get("draft_binding_sha256"):
                    self.error(
                        "visual_prototype_binding_mismatch",
                        location,
                        "prototype binding hash does not match the published draft binding",
                    )
                prototype_rules = set(self._contract_ids(row.get("style_rule_refs")))
                bound_rules = set(self._contract_ids(meta.get("style_rule_ids")))
                if not prototype_rules or not prototype_rules.issubset(bound_rules):
                    self.error(
                        "visual_prototype_binding_mismatch",
                        location,
                        "grounded prototype rule refs must be a non-empty subset of bound rules",
                    )
            elif normalize_none(row.get("binding_rule_bundle_sha256")) != "none":
                self.error(
                    "visual_prototype_binding_mismatch",
                    location,
                    "ungrounded prototype cannot claim a style binding hash",
                )
            elif self._contract_ids(row.get("style_rule_refs")):
                self.error(
                    "visual_prototype_binding_mismatch",
                    location,
                    "ungrounded prototype cannot claim published style rule refs",
                )
            for starter_field in ("starter_prompt_id", "starter_prompt_sha256"):
                if normalize_none(row.get(starter_field)) != "none":
                    self.error(
                        "visual_prototype_binding_mismatch",
                        location,
                        "starter prompt lineage is disabled until its release gate passes",
                    )
            revision_of = normalize_none(row.get("revision_of"))
            if revision_of != "none":
                previous = next(
                    (
                        candidate for candidate in rows
                        if candidate.get("prototype_asset_id") == revision_of
                    ),
                    None,
                )
                if (
                    previous is None
                    or previous.get("draft_id") != row.get("draft_id")
                    or previous.get("concept_id") != row.get("concept_id")
                    or previous.get("prototype_asset_id") == row.get("prototype_asset_id")
                ):
                    self.error(
                        "visual_prototype_artifact_invalid",
                        location,
                        "revision_of must reference an earlier prototype of the same draft/concept",
                    )

    def _check_v2_visual_contract(
        self,
        path: Path,
        rendered_text: str,
        meta: dict[str, str],
        headings: set[str],
    ) -> None:
        if "视觉方向绑定" not in headings:
            return
        contract = parse_contract_block(markdown_section(rendered_text, "视觉方向绑定"))
        missing = sorted(V2_VISUAL_CONTRACT_FIELDS - contract.keys())
        if missing:
            self.error(
                "visual_contract_missing",
                path.name,
                "视觉方向绑定 missing keys: " + ", ".join(missing),
            )
            return
        status = contract.get("visual_contract_status", "")
        if status not in V2_VISUAL_CONTRACT_STATUSES:
            self.error(
                "visual_contract_status",
                path.name,
                f"invalid visual_contract_status: {status}",
            )
            return
        selection_mode = contract.get("selection_mode", "")
        if selection_mode not in {"none", "exploration", "production"}:
            self.error(
                "visual_contract_status",
                path.name,
                f"invalid selection_mode: {selection_mode}",
            )
            return
        selected_ids = self._contract_ids(contract.get("visual_direction_card_ids"))
        research_gap = contract.get("research_gap", "").strip()
        active_contraindications = set(
            self._contract_ids(contract.get("active_contraindication_codes"))
        )
        frontmatter_contraindications = set(
            self._contract_ids(meta.get("style_query_active_contraindication_codes"))
        )
        if active_contraindications != frontmatter_contraindications:
            self.error(
                "visual_contract_binding_mismatch",
                path.name,
                "visual contraindications must exactly match the style query",
            )
        unknown_contraindications = sorted(
            active_contraindications - self._v2_codes("contraindication_code")
        )
        if unknown_contraindications:
            self.error(
                "visual_contract_binding_mismatch",
                path.name,
                "unknown visual contraindications: " + ", ".join(unknown_contraindications),
            )
        if contract.get("style_library_path") != meta.get("style_library_path"):
            self.error(
                "visual_contract_binding_mismatch",
                path.name,
                "visual style_library_path must exactly match frontmatter",
            )
        if normalize_none(contract.get("draft_binding_id")) != normalize_none(
            meta.get("draft_binding_id")
        ):
            self.error(
                "visual_contract_binding_mismatch",
                path.name,
                "visual draft_binding_id must exactly match frontmatter",
            )

        raw_manifest = contract.get("asset_manifest_path", "").strip()
        manifest_sha = contract.get("asset_manifest_sha256", "").strip()
        if status == "not_requested":
            if (
                selected_ids
                or selection_mode != "none"
                or normalize_none(raw_manifest) != "none"
                or normalize_none(manifest_sha) != "none"
                or active_contraindications
                or normalize_none(research_gap) != "none"
            ):
                self.error(
                    "visual_contract_unbound",
                    path.name,
                    "not_requested requires no cards, manifest, contraindications, or research gap",
                )
            if (
                meta.get("visual_delivery_requirement") != "none"
                or meta.get("visual_delivery_status") != "not_requested"
            ):
                self.error(
                    "visual_contract_status",
                    path.name,
                    "not_requested requires visual delivery requirement/status none/not_requested",
                )
            return
        if status == "needs_visual_research":
            if selected_ids or normalize_none(raw_manifest) != "none":
                self.error(
                    "visual_contract_unbound",
                    path.name,
                    "needs_visual_research cannot claim cards or an asset manifest",
                )
            if selection_mode != "exploration":
                self.error(
                    "visual_contract_unbound",
                    path.name,
                    "needs_visual_research must use selection_mode=exploration",
                )
            if normalize_none(manifest_sha) != "none":
                self.error(
                    "visual_contract_unbound",
                    path.name,
                    "needs_visual_research requires asset_manifest_sha256=none",
                )
            if not research_gap or research_gap.lower() == "none":
                self.error(
                    "visual_research_gap_missing",
                    path.name,
                    "needs_visual_research must name the exact missing assets or evidence",
                )
            if meta.get("visual_delivery_status") != "brief_only":
                self.error(
                    "visual_contract_unbound",
                    path.name,
                    "needs_visual_research can only deliver brief_only",
                )
            return

        manifest_path = self._resolve_visual_contract_file(
            path, raw_manifest, manifest_sha, "asset_manifest_path"
        )
        if manifest_path is None:
            return
        style_library_path = None
        draft_binding_id = None
        if selection_mode == "production":
            style_library_path = (
                self.run_dir / meta.get("style_library_path", "")
            ).resolve()
            draft_binding_id = meta.get("draft_binding_id")
        try:
            from select_visual_directions import (  # type: ignore
                ContractError as VisualContractError,
                select_from_paths,
            )
        except ImportError as exc:
            self.error("visual_selector_invalid", path.name, str(exc))
            return
        try:
            selector_payload, selector_code = select_from_paths(
                category=meta.get("style_query_category", ""),
                job=meta.get("primary_job", ""),
                carrier=meta.get("style_query_carrier", ""),
                asset_manifest_path=manifest_path,
                style_library_path=style_library_path,
                draft_binding_id=draft_binding_id,
                active_contraindications=active_contraindications,
                mode=selection_mode,
                limit=2,
            )
        except (OSError, VisualContractError) as exc:
            self.error("visual_selector_invalid", path.name, str(exc))
            return

        selector_status = selector_payload.get("status")
        matches = selector_payload.get("matches", [])
        recomputed_ids = [
            item.get("card_id") for item in matches if isinstance(item, dict)
        ]
        if status == "prototype_gap":
            if selected_ids:
                self.error(
                    "visual_contract_unbound",
                    path.name,
                    "prototype_gap cannot claim selected direction cards",
                )
            if selector_code == 0 or selector_status not in {
                "prototype_gap", "no_eligible_card",
            }:
                self.error(
                    "visual_selector_mismatch",
                    path.name,
                    "prototype_gap must be reproduced by the selector",
                )
            if meta.get("visual_delivery_status") != "brief_only":
                self.error(
                    "visual_contract_unbound",
                    path.name,
                    "prototype_gap can only deliver brief_only",
                )
            if not research_gap or research_gap.lower() == "none":
                self.error(
                    "visual_research_gap_missing",
                    path.name,
                    "prototype_gap must preserve the selector/material gap",
                )
            return

        expected_status = (
            "matched_exploration" if status == "selected_exploration" else "matched"
        )
        if selector_code != 0 or selector_status != expected_status:
            self.error(
                "visual_selector_mismatch",
                path.name,
                "selected visual directions cannot be reproduced: "
                + str(selector_payload.get("message", selector_status)),
            )
            return
        if selected_ids != recomputed_ids:
            self.error(
                "visual_selector_mismatch",
                path.name,
                f"declared cards {selected_ids} do not equal selector result {recomputed_ids}",
            )
        if status == "selected_exploration":
            if selection_mode != "exploration":
                self.error(
                    "visual_contract_status", path.name,
                    "selected_exploration requires selection_mode=exploration",
                )
            if meta.get("status") == "ready" or meta.get("visual_delivery_status") != "prototype_only":
                self.error(
                    "visual_contract_status",
                    path.name,
                    "selected_exploration requires needs_review/prototype_only",
                )
            if selected_ids:
                self._check_visual_prototypes(path, meta, selected_ids)
        else:
            if selection_mode != "production":
                self.error(
                    "visual_contract_status", path.name,
                    "selected_production requires selection_mode=production",
                )
            if meta.get("style_binding_status") != "grounded":
                self.error(
                    "visual_contract_binding_mismatch",
                    path.name,
                    "selected_production requires a grounded published style binding",
                )
            if meta.get("visual_delivery_status") not in {
                "rendered_needs_review", "rendered_pass",
            }:
                self.error(
                    "visual_contract_status",
                    path.name,
                    "selected_production requires a rendered delivery status",
                )

    def _check_grounded_style_binding(self, path: Path, meta: dict[str, str]) -> None:
        fields = {
            "draft_binding_id",
            "draft_binding_sha256",
            "style_rule_ids",
            "primary_style_archetype_id",
            "primary_style_archetype_version",
            "primary_style_archetype_snapshot_sha256",
        }
        binding_status = meta.get("style_binding_status", "")
        if binding_status != "grounded":
            nonempty = [
                field
                for field in fields
                if normalize_none(meta.get(field)) != "none"
            ]
            if nonempty:
                self.error(
                    "style_binding_receipt_mismatch",
                    path.name,
                    "unpublished style state cannot claim binding receipt fields: "
                    + ", ".join(sorted(nonempty)),
                )
            return

        missing = [field for field in fields if normalize_none(meta.get(field)) == "none"]
        if missing:
            self.error(
                "style_binding_receipt_missing",
                path.name,
                "grounded binding missing receipt fields: " + ", ".join(sorted(missing)),
            )
            return
        if meta.get("style_binding_source") != "library":
            self.error(
                "style_binding_receipt_mismatch",
                path.name,
                "grounded binding must use style_binding_source=library",
            )
            return
        raw_library_path = meta.get("style_library_path", "").strip()
        if raw_library_path != self.run.get("style_library_path", "").strip():
            self.error(
                "style_binding_receipt_mismatch",
                path.name,
                "draft style_library_path must exactly match run.yaml",
            )
            return
        library_path = (self.run_dir / raw_library_path).resolve()
        if not library_path.is_file():
            self.error(
                "style_binding_receipt_missing",
                path.name,
                f"style library does not exist: {raw_library_path}",
            )
            return
        expected_rules = self._contract_ids(meta.get("style_rule_ids"))
        try:
            from style_library import (  # type: ignore
                StyleLibraryError,
                _preflight_existing_database,
            )
        except ImportError as exc:
            self.error("style_binding_receipt_invalid", path.name, str(exc))
            return
        try:
            if _preflight_existing_database(library_path) != 2:
                raise StyleLibraryError("schema_version_mismatch")
        except StyleLibraryError as exc:
            self.error("style_binding_receipt_invalid", path.name, str(exc))
            return
        try:
            uri_path = quote(str(library_path), safe="/")
            con = sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA query_only = ON")
            foreign_key_violations = con.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_key_violations:
                self.error(
                    "style_binding_receipt_invalid",
                    path.name,
                    "style library contains foreign-key violations",
                )
                return
            binding = con.execute(
                """
                SELECT binding.*, publication.binding_sha256,
                       archetype.carrier, archetype.primary_job_scope,
                       archetype.category_scope
                FROM draft_style_bindings AS binding
                JOIN draft_binding_publications AS publication
                  ON publication.draft_binding_id = binding.draft_binding_id
                 AND publication.draft_id = binding.draft_id
                JOIN style_archetypes AS archetype
                  ON archetype.archetype_id = binding.archetype_id
                WHERE binding.draft_binding_id=? AND binding.draft_id=?
                """,
                (meta.get("draft_binding_id"), meta.get("draft_id")),
            ).fetchone()
        except sqlite3.Error as exc:
            self.error("style_binding_receipt_invalid", path.name, str(exc))
            return
        finally:
            if "con" in locals():
                con.close()
        if binding is None:
            self.error(
                "style_binding_receipt_missing",
                path.name,
                "no immutable binding publication matches this draft",
            )
            return
        try:
            actual_rules = json.loads(binding["selected_rule_ids"])
        except (TypeError, json.JSONDecodeError):
            actual_rules = []
        try:
            material_plan = json.loads(binding["material_plan_json"])
        except (TypeError, json.JSONDecodeError):
            material_plan = None
        try:
            anti_patterns_checked = json.loads(binding["anti_patterns_checked_json"])
        except (TypeError, json.JSONDecodeError):
            anti_patterns_checked = None
        mismatches: list[str] = []
        expected_pairs = {
            "binding_sha256": meta.get("draft_binding_sha256"),
            "archetype_id": meta.get("primary_style_archetype_id"),
            "archetype_version": meta.get("primary_style_archetype_version"),
            "archetype_snapshot_sha256": meta.get(
                "primary_style_archetype_snapshot_sha256"
            ),
            "carrier": meta.get("style_query_carrier"),
        }
        for field, expected in expected_pairs.items():
            if str(binding[field]) != str(expected):
                mismatches.append(field)
        if str(binding["primary_job_scope"]) != meta.get("primary_job"):
            mismatches.append("primary_job_scope")
        if str(binding["category_scope"]) != meta.get("style_query_category"):
            mismatches.append("category_scope")
        if binding["binding_source"] != "library" or binding["review_status"] != "PASS":
            mismatches.append("review_status")
        if actual_rules != expected_rules:
            mismatches.append("style_rule_ids")
        if (
            meta.get("performance_evidence_scope") != "not_performance_evidence"
            and meta.get("primary_performance_rule_id") not in actual_rules
        ):
            mismatches.append("primary_performance_rule_id")
        expected_material_plan = {
            "category": meta.get("style_query_category"),
            "carrier": meta.get("style_query_carrier"),
            "primary_job": meta.get("primary_job"),
            "traffic_stage": meta.get("traffic_stage"),
            "business_objective": meta.get("business_objective"),
            "performance_evidence_scope": meta.get("performance_evidence_scope"),
            "primary_performance_rule_id": meta.get("primary_performance_rule_id"),
            "primary_performance_evidence_scope": meta.get(
                "performance_evidence_scope"
            ),
            "available_material_codes": sorted(
                self._contract_ids(meta.get("style_query_available_material_codes"))
            ),
            "required_material_codes": sorted(
                self._contract_ids(meta.get("style_query_required_material_codes"))
            ),
            "required_constraint_codes": sorted(
                self._contract_ids(meta.get("style_query_required_constraint_codes"))
            ),
            "active_constraint_codes": sorted(
                self._contract_ids(meta.get("style_query_active_constraint_codes"))
            ),
            "active_contraindication_codes": sorted(
                self._contract_ids(meta.get("style_query_active_contraindication_codes"))
            ),
        }
        normalized_material_plan = None
        if isinstance(material_plan, dict) and set(material_plan) == set(expected_material_plan):
            normalized_material_plan = {}
            for key, expected in expected_material_plan.items():
                value = material_plan.get(key)
                if isinstance(expected, list):
                    if not isinstance(value, list) or not all(
                        isinstance(item, str) for item in value
                    ):
                        normalized_material_plan = None
                        break
                    normalized_material_plan[key] = sorted(value)
                else:
                    normalized_material_plan[key] = value
        if normalized_material_plan != expected_material_plan:
            mismatches.append("material_plan_json")
        active_contraindications = set(
            expected_material_plan["active_contraindication_codes"]
        )
        checked_codes = {
            value
            for value in anti_patterns_checked or []
            if isinstance(value, str)
        } if isinstance(anti_patterns_checked, list) else set()
        if not active_contraindications.issubset(checked_codes):
            mismatches.append("anti_patterns_checked_json")
        if mismatches:
            self.error(
                "style_binding_receipt_mismatch",
                path.name,
                "published binding disagrees on: " + ", ".join(sorted(set(mismatches))),
            )

    def _check_first_party_outcome(self, path: Path, meta: dict[str, str]) -> None:
        if meta.get("performance_evidence_scope") != "first_party_traffic_validated":
            return
        raw_library_path = meta.get("style_library_path", "").strip()
        library_path = (self.run_dir / raw_library_path).resolve()
        if not library_path.is_file():
            self.error(
                "traffic_outcome_receipt_missing",
                path.name,
                "first-party outcome style library is missing",
            )
            return
        try:
            uri_path = quote(str(library_path), safe="/")
            con = sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA query_only = ON")
            foreign_key_violations = con.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_key_violations:
                self.error(
                    "traffic_outcome_receipt_invalid",
                    path.name,
                    "style library contains foreign-key violations",
                )
                return
            outcome_id = meta.get("traffic_outcome_checkpoint_id")
            checkpoint = con.execute(
                "SELECT * FROM draft_outcome_checkpoints WHERE outcome_checkpoint_id=?",
                (outcome_id,),
            ).fetchone()
            publication = con.execute(
                "SELECT * FROM draft_outcome_publications WHERE outcome_checkpoint_id=?",
                (outcome_id,),
            ).fetchone()
            if checkpoint is None or publication is None:
                self.error(
                    "traffic_outcome_receipt_missing",
                    path.name,
                    "no immutable draft outcome publication matches the checkpoint",
                )
                return
            experiment = con.execute(
                "SELECT * FROM draft_experiments WHERE experiment_id=?",
                (checkpoint["experiment_id"],),
            ).fetchone()
            experiment_publication = con.execute(
                "SELECT * FROM draft_experiment_publications WHERE experiment_id=?",
                (checkpoint["experiment_id"],),
            ).fetchone()
            assignment = con.execute(
                """
                SELECT * FROM draft_experiment_assignments
                WHERE experiment_id=? AND draft_binding_id=?
                """,
                (checkpoint["experiment_id"], checkpoint["draft_binding_id"]),
            ).fetchone()
            publish_event = con.execute(
                """
                SELECT * FROM draft_publish_events
                WHERE experiment_id=? AND draft_binding_id=?
                """,
                (checkpoint["experiment_id"], checkpoint["draft_binding_id"]),
            ).fetchone()
            performance_definition = con.execute(
                """
                SELECT * FROM performance_definitions
                WHERE performance_definition_id=? AND metric_name=?
                """,
                (
                    checkpoint["performance_definition_id"],
                    checkpoint["primary_metric_name"],
                ),
            ).fetchone()
            baseline_publication = con.execute(
                """
                SELECT * FROM baseline_snapshot_publications
                WHERE baseline_snapshot_id=?
                  AND library_account_id=?
                  AND performance_definition_id=?
                  AND metric_name=?
                  AND baseline_snapshot_sha256=?
                """,
                (
                    checkpoint["baseline_snapshot_id"],
                    checkpoint["library_account_id"],
                    checkpoint["performance_definition_id"],
                    checkpoint["primary_metric_name"],
                    checkpoint["baseline_snapshot_sha256"],
                ),
            ).fetchone()
            baseline_member_audit = con.execute(
                """
                SELECT
                    COUNT(*) AS included_count,
                    SUM(CASE WHEN metric.visibility_scope='first_party_analytics'
                                  AND metric.metric_name=?
                             THEN 0 ELSE 1 END) AS invalid_count
                FROM account_baseline_members AS member
                JOIN post_metrics AS metric
                  ON metric.post_metric_id=member.member_post_metric_id
                 AND metric.post_observation_id=member.member_post_observation_id
                 AND metric.metric_name=member.metric_name
                WHERE member.baseline_snapshot_id=?
                  AND member.inclusion_status='included'
                """,
                (
                    checkpoint["primary_metric_name"],
                    checkpoint["baseline_snapshot_id"],
                ),
            ).fetchone()
            metrics = con.execute(
                """
                SELECT * FROM draft_outcome_metrics
                WHERE outcome_checkpoint_id=?
                ORDER BY metric_ordinal, outcome_metric_id
                """,
                (outcome_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            self.error("traffic_outcome_receipt_invalid", path.name, str(exc))
            return
        finally:
            if "con" in locals():
                con.close()
        mismatches: list[str] = []
        exact_checkpoint = {
            "draft_binding_id": meta.get("draft_binding_id"),
            "library_account_id": meta.get("account_scope"),
            "visibility_scope": "first_party_analytics",
            "primary_metric_name": meta.get("traffic_primary_metric"),
            "primary_metric_status": "observed",
            "traffic_verdict": meta.get("traffic_verdict"),
        }
        if not scope_is_specific(meta.get("account_scope")):
            mismatches.append("account_scope")
        for field, expected in exact_checkpoint.items():
            if str(checkpoint[field]) != str(expected):
                mismatches.append(field)
        if not isinstance(checkpoint["checkpoint_hours"], int) or checkpoint["checkpoint_hours"] <= 0:
            mismatches.append("checkpoint_hours")
        if publication["draft_binding_id"] != meta.get("draft_binding_id"):
            mismatches.append("publication.draft_binding_id")
        if (
            publication["metric_set_sha256"] != checkpoint["metric_set_sha256"]
            or publication["metric_count"] != checkpoint["metric_count"]
            or publication["traffic_verdict"] != checkpoint["traffic_verdict"]
        ):
            mismatches.append("outcome_publication")
        if (
            experiment is None
            or experiment_publication is None
            or assignment is None
            or publish_event is None
        ):
            mismatches.append("experiment_publication")
        else:
            exact_experiment = {
                "library_account_id": meta.get("account_scope"),
                "business_objective": self.run.get("business_objective"),
                "visibility_scope": "first_party_analytics",
                "primary_metric_name": meta.get("traffic_primary_metric"),
            }
            for field, expected in exact_experiment.items():
                if str(experiment[field]) != str(expected):
                    mismatches.append(f"experiment.{field}")
            if experiment["status"] not in {"preregistered", "closed"}:
                mismatches.append("experiment.status")
            if assignment["actual_publish_at"] is not None:
                mismatches.append("assignment.actual_publish_at")
            expected_publish_event = {
                "library_account_id": meta.get("account_scope"),
                "surface": meta.get("traffic_observation_surface"),
            }
            for field, expected in expected_publish_event.items():
                if str(publish_event[field]) != str(expected):
                    mismatches.append(f"publish_event.{field}")
            if not scope_is_specific(str(publish_event["platform_post_id"])):
                mismatches.append("publish_event.platform_post_id")
            if not str(publish_event["publication_url"]).strip():
                mismatches.append("publish_event.publication_url")
            calculated_publish_event_sha = hashlib.sha256(
                json.dumps(
                    [
                        publish_event["publish_event_id"],
                        publish_event["experiment_id"],
                        publish_event["draft_binding_id"],
                        publish_event["library_account_id"],
                        publish_event["surface"],
                        publish_event["platform_post_id"],
                        publish_event["publication_url"],
                        publish_event["actual_publish_at"],
                    ],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            if publish_event["publish_event_sha256"] != calculated_publish_event_sha:
                mismatches.append("publish_event.publish_event_sha256")
            try:
                preregistered_at = parse_timestamp_utc(
                    experiment_publication["published_at"]
                )
                published_at = parse_timestamp_utc(
                    publish_event["actual_publish_at"]
                )
                observed_at = parse_timestamp_utc(checkpoint["observed_at"])
                elapsed_hours = (observed_at - published_at).total_seconds() / 3600
                if not (preregistered_at <= published_at <= observed_at):
                    mismatches.append("publish_event.actual_publish_at")
                checkpoint_hours = float(checkpoint["checkpoint_hours"])
                checkpoint_tolerance = min(2.0, checkpoint_hours * 0.1)
                if abs(elapsed_hours - checkpoint_hours) > checkpoint_tolerance:
                    mismatches.append("checkpoint.observed_at")
            except (TypeError, ValueError):
                mismatches.append("checkpoint.observed_at")
            try:
                held_constants = json.loads(experiment["held_constants_json"])
            except (TypeError, json.JSONDecodeError):
                held_constants = {}
            expected_constants = {
                "platform": meta.get("platform"),
                "account_scope": meta.get("account_scope"),
                "surface": meta.get("traffic_observation_surface"),
                "category": meta.get("style_query_category"),
                "carrier": meta.get("style_query_carrier"),
                "primary_job": meta.get("primary_job"),
                "traffic_stage": meta.get("traffic_stage"),
                "window_start": self.run.get("window_start"),
                "window_end": self.run.get("window_end"),
            }
            if not isinstance(held_constants, dict) or any(
                str(held_constants.get(field, "")) != str(expected)
                for field, expected in expected_constants.items()
            ):
                mismatches.append("experiment.held_constants_json")
        if performance_definition is None:
            mismatches.append("performance_definition")
        else:
            expected_definition = {
                "business_objective": "traffic_first",
                "primary_job": meta.get("primary_job"),
                "traffic_stage": meta.get("traffic_stage"),
                "metric_name": meta.get("traffic_primary_metric"),
            }
            for field, expected in expected_definition.items():
                if str(performance_definition[field]) != str(expected):
                    mismatches.append(f"performance_definition.{field}")
            if performance_definition["metric_name"] not in {"impressions", "reach"}:
                mismatches.append("performance_definition.metric_name")
        if baseline_publication is None:
            mismatches.append("baseline_snapshot_publication")
        if (
            baseline_member_audit is None
            or int(baseline_member_audit["included_count"] or 0) < 1
            or int(baseline_member_audit["invalid_count"] or 0) != 0
        ):
            mismatches.append("baseline_first_party_members")
        if checkpoint["metric_count"] != len(metrics):
            mismatches.append("metric_count")
        metric_hashes: list[str] = []
        for metric in metrics:
            metric_values = [
                metric["outcome_metric_id"], metric["outcome_checkpoint_id"],
                metric["experiment_id"], metric["draft_binding_id"],
                metric["metric_role"], metric["metric_name"],
                metric["metric_status"], metric["metric_value"],
                metric["numerator"], metric["denominator"],
                metric["denominator_metric_name"], metric["metric_unit"],
                metric["metric_ordinal"],
            ]
            calculated_metric_sha = hashlib.sha256(
                json.dumps(
                    metric_values,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            if metric["metric_sha256"] != calculated_metric_sha:
                mismatches.append(f"metric_sha256:{metric['outcome_metric_id']}")
            metric_hashes.append(calculated_metric_sha)
        calculated_metric_set_sha = hashlib.sha256(
            json.dumps(
                metric_hashes,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if checkpoint["metric_set_sha256"] != calculated_metric_set_sha:
            mismatches.append("metric_set_sha256")
        primary_metrics = [
            row for row in metrics
            if row["metric_role"] == "primary_exposure"
            and row["metric_name"] == meta.get("traffic_primary_metric")
            and row["metric_status"] == "observed"
            and row["metric_value"] is not None
        ]
        if len(primary_metrics) != 1:
            mismatches.append("primary_exposure_metric")
        receipt_payload = {
            "checkpoint": dict(checkpoint),
            "publication": dict(publication),
            "experiment": dict(experiment) if experiment is not None else None,
            "experiment_publication": (
                dict(experiment_publication)
                if experiment_publication is not None else None
            ),
            "assignment": dict(assignment) if assignment is not None else None,
            "publish_event": dict(publish_event) if publish_event is not None else None,
            "performance_definition": (
                dict(performance_definition)
                if performance_definition is not None else None
            ),
            "baseline_publication": (
                dict(baseline_publication) if baseline_publication is not None else None
            ),
            "baseline_member_audit": (
                dict(baseline_member_audit)
                if baseline_member_audit is not None else None
            ),
            "metrics": [dict(row) for row in metrics],
        }
        actual_receipt_sha = hashlib.sha256(
            json.dumps(
                receipt_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if actual_receipt_sha != meta.get("traffic_outcome_receipt_sha256"):
            mismatches.append("traffic_outcome_receipt_sha256")
        if mismatches:
            self.error(
                "traffic_outcome_receipt_mismatch",
                path.name,
                "published first-party outcome disagrees on: "
                + ", ".join(sorted(set(mismatches))),
            )

    def _check_trend_template_contract(
        self,
        path: Path,
        rendered_text: str,
        meta: dict[str, str],
        headings: set[str],
    ) -> None:
        requirement = self.run.get("trend_template_requirement", "none")
        has_section = "趋势模板绑定" in headings
        if (self._is_v2() or requirement == "draft") and not has_section:
            self.error(
                "trend_template_contract_missing",
                path.name,
                "v2 drafts require an explicit 趋势模板绑定 section; use template_contract_status=not_used when no trend template is used",
            )
            return
        if not has_section:
            return
        contract = parse_contract_block(markdown_section(rendered_text, "趋势模板绑定"))
        missing = sorted(TREND_TEMPLATE_CONTRACT_FIELDS - contract.keys())
        if missing:
            self.error(
                "trend_template_contract_mismatch",
                path.name,
                "趋势模板绑定 missing keys: " + ", ".join(missing),
            )
            return
        status = contract.get("template_contract_status", "")
        if status == "not_used":
            if requirement == "draft":
                self.error(
                    "trend_template_contract_mismatch",
                    path.name,
                    "trend_template_requirement=draft cannot use template_contract_status=not_used",
                )
            return
        if status != "bound_candidate":
            self.error(
                "trend_template_contract_mismatch",
                path.name,
                "template_contract_status must be not_used or bound_candidate",
            )
            return
        if requirement != "draft":
            self.error(
                "trend_template_contract_mismatch",
                path.name,
                "bound_candidate requires run.yaml trend_template_requirement=draft",
            )

        record_id = contract.get("candidate_record_id", "")
        candidate = next(
            (
                item
                for item in self.trend_candidates
                if item.get("candidate_record_id") == record_id
            ),
            None,
        )
        if candidate is None:
            self.error(
                "trend_template_contract_mismatch",
                path.name,
                f"unknown candidate_record_id: {record_id}",
            )
            return
        same_template = [
            item
            for item in self.trend_candidates
            if item.get("template_id") == candidate.get("template_id")
            and isinstance(item.get("candidate_version"), int)
        ]
        latest = max(same_template, key=lambda item: int(item["candidate_version"]))
        if latest.get("candidate_record_id") != record_id:
            self.error(
                "trend_template_stale_binding",
                path.name,
                "draft must bind the highest candidate_version for this template",
            )
        if candidate.get("record_sha256") != canonical_json_sha256(candidate, "record_sha256"):
            self.error(
                "trend_record_hash_mismatch",
                path.name,
                "bound trend candidate hash is invalid",
            )

        exact_pairs = {
            "template_id": candidate.get("template_id"),
            "family_id": candidate.get("family_id"),
            "candidate_version": str(candidate.get("candidate_version")),
            "replication_status": candidate.get("replication_status"),
            "lifecycle_phase": candidate.get("lifecycle_phase"),
            "last_refreshed_at": candidate.get("last_refreshed_at"),
            "decision": candidate.get("decision"),
        }
        mismatches = [
            key for key, expected in exact_pairs.items() if contract.get(key) != str(expected)
        ]
        if mismatches:
            self.error(
                "trend_template_contract_mismatch",
                path.name,
                "draft disagrees with candidate on: " + ", ".join(sorted(mismatches)),
            )
        if candidate.get("replication_status") != "replicated" or candidate.get(
            "lifecycle_phase"
        ) not in {"rising", "mature", "evergreen_carrier"} or candidate.get(
            "decision"
        ) not in {"shoot", "adapt"}:
            self.error(
                "trend_decision_not_eligible",
                path.name,
                "bound candidate is not eligible for production",
            )
        if candidate.get("rights_status") not in {"grammar_only", "authorized_assets"}:
            self.error("trend_rights_gate", path.name, "bound candidate rights are not cleared")
        if candidate.get("safety_status") != "passed":
            self.error("trend_safety_gate", path.name, "bound candidate safety is not passed")

        sample_fields = {
            "source_sample_ids": "source_sample_ids",
            "support_sample_ids": "support_sample_ids",
            "counterexample_sample_ids": "counterexample_sample_ids",
        }
        for contract_field, candidate_field in sample_fields.items():
            actual = set(split_ids(contract.get(contract_field, "")))
            expected = set(candidate.get(candidate_field, []))
            if actual != expected:
                self.error(
                    "trend_template_contract_mismatch",
                    path.name,
                    f"{contract_field} must exactly match the candidate",
                )

        scopes = {
            "style_query_category": "category_scopes",
            "style_query_carrier": "carrier_scopes",
            "primary_job": "primary_job_scopes",
            "traffic_stage": "traffic_stage_scopes",
        }
        for meta_field, candidate_field in scopes.items():
            allowed = candidate.get(candidate_field, [])
            if not isinstance(allowed, list) or meta.get(meta_field) not in allowed:
                self.error(
                    "trend_template_scope_mismatch",
                    path.name,
                    f"{meta_field} is outside the candidate's exact scope",
                )

        slot_map = candidate.get("slot_map", {})
        if isinstance(slot_map, dict):
            fixed = set(split_ids(contract.get("fixed_slots", "")))
            expected_fixed = set(str(value) for value in slot_map.get("fixed", []))
            replaced = set(split_ids(contract.get("replaced_slots", "")))
            replaceable = set(str(value) for value in slot_map.get("replaceable", []))
            if fixed != expected_fixed or not replaced or not replaced.issubset(replaceable):
                self.error(
                    "trend_slot_map",
                    path.name,
                    "fixed_slots must match and replaced_slots must be a non-empty subset of candidate slots",
                )
        contribution = contract.get("new_semantic_contribution", "")
        if contribution in {"", "none", "unknown", "待填写"}:
            self.error(
                "trend_slot_map",
                path.name,
                "bound template requires a substantive new_semantic_contribution",
            )
        try:
            material_map = json.loads(contract.get("material_evidence_map", ""))
        except json.JSONDecodeError:
            material_map = None
        required_materials = set(candidate.get("required_material_codes", []))
        if not isinstance(material_map, dict) or not required_materials.issubset(material_map):
            self.error(
                "trend_material_gate",
                path.name,
                "material_evidence_map must cover every required template material",
            )
        else:
            known_ids, _ = self._known_evidence_ids()
            evidence_types = self._evidence_id_types()
            allowed_types = {
                "source",
                "claim",
                "post",
                "authorized_material",
                "authorization",
            }
            bound_refs: set[str] = set()
            for code in sorted(required_materials):
                refs = material_map.get(code)
                if not isinstance(refs, list) or not refs or not all(
                    isinstance(value, str) and value.strip() for value in refs
                ):
                    self.error(
                        "trend_material_gate",
                        path.name,
                        f"{code} must map to a non-empty JSON string array",
                    )
                    continue
                unknown = sorted(set(refs) - known_ids)
                incompatible = sorted(
                    value
                    for value in refs
                    if not evidence_types.get(value, set()).intersection(allowed_types)
                )
                if unknown or incompatible:
                    self.error(
                        "trend_material_gate",
                        path.name,
                        f"{code} has unknown or incompatible evidence IDs: {sorted(set(unknown + incompatible))}",
                    )
                bound_refs.update(value for value in refs if value in known_ids)
            if candidate.get("rights_status") == "authorized_assets":
                required_assets = set(candidate.get("authorized_asset_ids", []))
                if not required_assets.issubset(bound_refs):
                    self.error(
                        "trend_material_gate",
                        path.name,
                        "bound draft must reference every authorized material ID declared by the candidate",
                    )

    def _check_drafts(self) -> None:
        drafts = self.run_dir / "drafts"
        if not drafts.is_dir():
            return
        topics = {
            row.get("topic_id", ""): row
            for row in self.rows.get("topics.csv", [])
            if row.get("topic_id", "")
        }
        authorizations = {
            row.get("authorization_id", ""): row
            for row in self.rows.get("authorization-log.csv", [])
            if row.get("authorization_id", "")
        }
        registry = self._registry()
        for path in sorted(drafts.glob("*.md")):
            try:
                text = path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError) as exc:
                self.error("unreadable_draft", path.name, str(exc))
                continue
            meta = parse_frontmatter(text)
            rendered_text = visible_markdown(text)
            required_meta = DRAFT_META | (V2_DRAFT_META if self._is_v2() else set())
            missing_meta = sorted(required_meta - meta.keys())
            if missing_meta:
                self.error(
                    "draft_contract",
                    path.name,
                    "missing frontmatter: " + ", ".join(missing_meta),
                )
            if self._is_v2():
                self._check_v2_draft_style_contract(path, meta)
                self._check_grounded_style_binding(path, meta)
                self._check_first_party_outcome(path, meta)
            if self.run.get("status") == "complete":
                for field in sorted(DRAFT_NONEMPTY_META):
                    if not meta.get(field, "").strip():
                        self.error(
                            "empty_draft_field",
                            path.name,
                            f"completed draft requires a non-empty {field}",
                        )
            truth_label = meta.get("truth_label", "")
            disclosure_text = meta.get("truth_disclosure_text", "").strip()
            disclosure_location = meta.get("truth_disclosure_location", "").strip()
            frontmatter_end = (
                rendered_text.find("\n---", 4) if rendered_text.startswith("---\n") else -1
            )
            visible_body = (
                rendered_text[frontmatter_end + 4 :]
                if frontmatter_end >= 0
                else rendered_text
            )
            first_screen = visible_body[:800]
            disclosure_patterns = TRUTH_DISCLOSURE_PATTERNS.get(truth_label, ())
            disclosure_conflicts = TRUTH_DISCLOSURE_CONFLICT_PATTERNS.get(
                truth_label, ()
            )
            marker_ok = bool(disclosure_patterns) and any(
                re.search(pattern, disclosure_text) for pattern in disclosure_patterns
            )
            conflict_found = any(
                re.search(pattern, disclosure_text) for pattern in disclosure_conflicts
            )
            if truth_label in TRUTH_LABELS and conflict_found:
                self.error(
                    "truth_disclosure_conflict",
                    path.name,
                    "truth disclosure contradicts the selected truth_label",
                )
            if truth_label in TRUTH_LABELS and not (
                marker_ok
                and not conflict_found
                and disclosure_location in VISIBLE_DISCLOSURE_LOCATIONS
                and disclosure_text
                and disclosure_text in first_screen
            ):
                self.error(
                    "truth_disclosure_missing",
                    path.name,
                    "truth label must be rendered with an accurate disclosure in the first screen/paragraph, not only stored in metadata",
                )
            heading_list = [
                match.group(1).strip()
                for match in re.finditer(
                    r"^##\s+(.+?)\s*$", rendered_text, flags=re.MULTILINE
                )
            ]
            headings = set(heading_list)
            duplicate_headings = sorted(
                heading for heading, count in Counter(heading_list).items() if count > 1
            )
            if duplicate_headings:
                self.error(
                    "duplicate_draft_section",
                    path.name,
                    "duplicate sections are forbidden: " + ", ".join(duplicate_headings),
                )
            required_headings = DRAFT_HEADINGS | (V2_DRAFT_HEADINGS if self._is_v2() else set())
            missing_headings = sorted(required_headings - headings)
            if missing_headings:
                self.error(
                    "draft_contract",
                    path.name,
                    "missing sections: " + ", ".join(missing_headings),
                )
            if self.run.get("status") == "complete":
                for heading in sorted(required_headings & headings):
                    body = markdown_section(rendered_text, heading)
                    if not re.sub(r"[#>*_`\-\s]", "", body):
                        self.error(
                            "empty_draft_section",
                            path.name,
                            f"completed draft section has no substantive content: {heading}",
                        )
            if self._is_v2():
                self._check_v2_mechanism_contract(path, rendered_text, meta, headings)
                self._check_trend_template_contract(path, rendered_text, meta, headings)
                self._check_v2_visual_contract(path, rendered_text, meta, headings)
            cta_contract: dict[str, str] = {}
            if "CTA 与披露" in headings:
                cta_contract = parse_contract_block(
                    markdown_section(rendered_text, "CTA 与披露")
                )
                required_contract = {
                    "cta_type",
                    "cta_copy",
                    "commercial_relationship",
                    "disclosure_text",
                    "disclosure_location",
                    "eligibility_ids",
                    "platform",
                    "account_scope",
                    "surfaces",
                }
                missing_contract = sorted(required_contract - cta_contract.keys())
                if missing_contract:
                    self.error(
                        "cta_contract_mismatch",
                        path.name,
                        "CTA 与披露 missing keys: " + ", ".join(missing_contract),
                    )
                empty_contract = sorted(
                    key for key in required_contract if key in cta_contract and not cta_contract[key]
                )
                if empty_contract:
                    self.error(
                        "cta_contract_mismatch",
                        path.name,
                        "CTA 与披露 has empty values: " + ", ".join(empty_contract),
                    )
                for field in (
                    "cta_type",
                    "commercial_relationship",
                    "disclosure_text",
                    "disclosure_location",
                    "eligibility_ids",
                    "platform",
                    "account_scope",
                    "surfaces",
                ):
                    if field in cta_contract and normalize_none(cta_contract[field]) != normalize_none(
                        meta.get(field)
                    ):
                        self.error(
                            "cta_contract_mismatch",
                            path.name,
                            f"CTA 与披露 {field} does not match frontmatter",
                        )
                contract_cta = normalize_none(cta_contract.get("cta_type"))
                contract_copy = normalize_none(cta_contract.get("cta_copy"))
                if (contract_cta == "none") != (contract_copy == "none"):
                    self.error(
                        "cta_contract_mismatch",
                        path.name,
                        "cta_copy must be none exactly when cta_type is none",
                    )
            topic_id = meta.get("topic_id", "")
            if topic_id and topic_id not in topics:
                self.error("dangling_reference", path.name, f"unknown topic_id {topic_id}")
            elif topic_id:
                topic = topics[topic_id]
                mismatches = [
                    field
                    for field in ("primary_job", "lifecycle")
                    if meta.get(field, "") != topic.get(field, "")
                ]
                if mismatches:
                    self.error(
                        "draft_topic_mismatch",
                        path.name,
                        "draft and topic disagree on: " + ", ".join(mismatches),
                    )
            primary_job = meta.get("primary_job", "")
            allowed_primary_jobs = (
                self._v2_codes("primary_job") if self._is_v2() else PRIMARY_JOBS
            )
            if primary_job and primary_job not in allowed_primary_jobs:
                self.error("invalid_enum", path.name, f"invalid primary_job: {primary_job}")
            lifecycle = meta.get("lifecycle", "")
            if lifecycle and lifecycle not in LIFECYCLES:
                self.error("invalid_enum", path.name, f"invalid lifecycle: {lifecycle}")
            if truth_label and truth_label not in TRUTH_LABELS:
                self.error(
                    "invalid_truth_label",
                    path.name,
                    f"invalid truth_label: {truth_label}",
                )
            relationship = meta.get("commercial_relationship", "")
            if relationship and relationship not in COMMERCIAL_RELATIONSHIPS:
                self.error(
                    "invalid_enum",
                    path.name,
                    f"invalid commercial_relationship: {relationship}",
                )
            if relationship and relationship != "none":
                commercial_disclosure = meta.get("disclosure_text", "").strip()
                commercial_location = meta.get("disclosure_location", "").strip()
                published_copy = markdown_section(rendered_text, "成稿")
                disclosure_patterns = COMMERCIAL_DISCLOSURE_PATTERNS.get(
                    relationship, ()
                )
                commercial_marker_ok = bool(disclosure_patterns) and any(
                    re.search(pattern, commercial_disclosure)
                    for pattern in disclosure_patterns
                )
                commercial_conflict = any(
                    re.search(pattern, commercial_disclosure)
                    for pattern in COMMERCIAL_DISCLOSURE_CONFLICT_PATTERNS.get(
                        relationship, ()
                    )
                )
                if commercial_conflict:
                    self.error(
                        "commercial_disclosure_conflict",
                        path.name,
                        "commercial disclosure contradicts the declared commercial_relationship",
                    )
                location_ok = False
                if commercial_location in VISIBLE_DISCLOSURE_LOCATIONS:
                    location_ok = commercial_disclosure in published_copy[:800]
                elif commercial_location in {"CTA前", "正文CTA前"}:
                    cta_copy = cta_contract.get("cta_copy", "").strip()
                    location_ok = (
                        normalize_none(cta_copy) != "none"
                        and commercial_disclosure in published_copy
                        and cta_copy in published_copy
                        and published_copy.index(commercial_disclosure)
                        < published_copy.index(cta_copy)
                    )
                if (
                    commercial_disclosure.lower() in {"", "none"}
                    or not commercial_marker_ok
                    or commercial_conflict
                    or commercial_location not in VISIBLE_COMMERCIAL_DISCLOSURE_LOCATIONS
                    or commercial_disclosure not in published_copy
                    or not location_ok
                ):
                    self.error(
                        "missing_commercial_disclosure",
                        path.name,
                        "commercial relationship requires exact disclosure_text in the visible 成稿 section and a controlled disclosure_location",
                    )
            cta_type = meta.get("cta_type", "")
            if cta_type and cta_type not in CTA_TYPES:
                self.error("invalid_enum", path.name, f"invalid cta_type: {cta_type}")
            if cta_type in COMMERCIAL_CTA_TYPES and relationship in {"", "none"}:
                self.error(
                    "commercial_cta_without_relationship",
                    path.name,
                    "commercial CTA requires the real commercial relationship and disclosure",
                )
            commercial_job = "conversion" if self._is_v2() else "commercial_conversion"
            if cta_type in COMMERCIAL_CTA_TYPES and primary_job != commercial_job:
                self.error(
                    "commercial_cta_job_mismatch",
                    path.name,
                    f"commercial CTA requires primary_job={commercial_job}",
                )
            draft_status = meta.get("status", "")
            if draft_status and draft_status not in DRAFT_STATUSES:
                self.error("invalid_enum", path.name, f"invalid draft status: {draft_status}")
            if self.run.get("status") == "complete":
                if draft_status != "ready":
                    self.error(
                        "review_not_passed",
                        path.name,
                        "completed draft run requires draft status ready",
                    )
            if draft_status == "ready" or self.run.get("status") == "complete":
                for heading in ("合规审校", "创意审校"):
                    review = parse_contract_block(markdown_section(rendered_text, heading))
                    if review.get("review_status") != "PASS":
                        self.error(
                            "review_not_passed",
                            path.name,
                            f"{heading} requires review_status: PASS",
                        )
            self._check_draft_authorization(path, meta, authorizations)
            self._check_draft_eligibility(path, meta, registry)


def format_text(
    issues: Iterable[Issue],
    strict: bool,
    status: str = "unknown",
    legacy_contract: bool = False,
) -> tuple[str, int]:
    issues = list(issues)
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    lines = ["redbook-writing run validator"]
    for issue in issues:
        lines.append(
            f"[{issue.severity.upper()}] {issue.code} {issue.location}: {issue.message}"
        )
    failed = bool(errors or (strict and warnings))
    if failed:
        verdict = "INVALID"
    elif legacy_contract:
        verdict = f"VALID_LEGACY_{status.upper()}"
    else:
        verdict = f"VALID_{status.upper()}"
    lines.append(f"{verdict}: {len(errors)} error(s), {len(warnings)} warning(s)")
    return "\n".join(lines) + "\n", 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a redbook-writing run directory and its evidence/CTA contracts."
    )
    parser.add_argument("run_dir", type=Path, help="Path to research/xiaohongshu/<run>")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings (for example stale current rules) as failures.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--allow-legacy-contract",
        action="store_true",
        help=(
            "Inspect a pre-v2 run that has no run_contract_version. "
            "Legacy runs never receive a current VALID_COMPLETE verdict."
        ),
    )
    args = parser.parse_args(argv)

    validator = RunValidator(
        args.run_dir.expanduser().resolve(),
        strict=args.strict,
        allow_legacy_contract=args.allow_legacy_contract,
    )
    issues = validator.validate()
    run_status = validator.run.get("status", "unknown")
    text_output, exit_code = format_text(
        issues,
        args.strict,
        run_status,
        legacy_contract=validator.legacy_contract,
    )
    if args.json:
        payload = {
            "valid": exit_code == 0,
            "strict": args.strict,
            "status": run_status,
            "complete": (
                run_status == "complete"
                and exit_code == 0
                and not validator.legacy_contract
            ),
            "contract_version": "legacy" if validator.legacy_contract else "2",
            "run_dir": str(validator.run_dir),
            "errors": sum(issue.severity == "error" for issue in issues),
            "warnings": sum(issue.severity == "warning" for issue in issues),
            "issues": [asdict(issue) for issue in issues],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(text_output)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
