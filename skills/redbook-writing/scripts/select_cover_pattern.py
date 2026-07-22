#!/usr/bin/env python3
"""Select a native Xiaohongshu cover carrier without inventing visual evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_ASSET = Path(__file__).resolve().parents[1] / "assets" / "cover-patterns-v1.json"


class ContractError(ValueError):
    pass


def parse_csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def load_library(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cover pattern library cannot be read: {exc}") from exc
    if payload.get("schema_version") != "1.0.0":
        raise ContractError("unsupported cover pattern library schema")
    patterns = payload.get("patterns")
    if not isinstance(patterns, list) or not patterns:
        raise ContractError("cover pattern library must contain patterns")
    ids = [pattern.get("pattern_id") for pattern in patterns]
    if None in ids or len(ids) != len(set(ids)):
        raise ContractError("pattern_id values must be present and unique")
    for pattern in patterns:
        if pattern.get("claim_ceiling") != "task_fit":
            raise ContractError(f"{pattern.get('pattern_id')} overstates evidence")
        options = pattern.get("required_materials_any")
        if not isinstance(options, list) or not options or not all(option for option in options):
            raise ContractError(f"{pattern.get('pattern_id')} lacks material gates")
    return payload


def active_contraindications(visual_evidence_role: str) -> set[str]:
    if visual_evidence_role != "primary":
        return set()
    return {
        "real_scene_is_primary_evidence",
        "result_difference_is_primary_evidence",
        "exact_ui_path_is_primary_evidence",
    }


def material_gap(pattern: dict[str, Any], materials: set[str]) -> set[str]:
    options = [set(option) for option in pattern["required_materials_any"]]
    if any(option <= materials for option in options):
        return set()
    return min((option - materials for option in options), key=len)


def select_pattern(
    library: dict[str, Any],
    *,
    job: str,
    carrier: str,
    materials: set[str],
    visual_evidence_role: str,
    pattern_id: str | None = None,
) -> tuple[int, dict[str, Any]]:
    patterns: list[dict[str, Any]] = library["patterns"]
    active = active_contraindications(visual_evidence_role)

    if pattern_id:
        exact = [pattern for pattern in patterns if pattern["pattern_id"] == pattern_id]
        if not exact:
            return 2, {"status": "invalid_query", "reason": f"unknown pattern_id: {pattern_id}"}
        pattern = exact[0]
        conflicts = sorted(active & set(pattern["contraindications"]))
        if conflicts or (visual_evidence_role == "primary" and pattern["family"] == "text_dominant_native_card"):
            return 2, {
                "status": "contraindicated",
                "pattern_id": pattern_id,
                "active_contraindications": conflicts or ["primary_visual_proof_overrides_text_card"],
                "claim_ceiling": library["claim_ceiling"],
            }
        if job not in pattern["jobs"] or carrier not in pattern["carriers"]:
            return 2, {"status": "needs_research", "reason": "explicit pattern does not exact-match job and carrier"}
        gap = material_gap(pattern, materials)
        if gap:
            return 2, {"status": "needs_materials", "missing_materials": sorted(gap), "pattern_id": pattern_id}
        return 0, {"status": "matched", "selected_pattern": pattern, "rejected_patterns": [], "claim_ceiling": library["claim_ceiling"], "output_state_ceiling": library["output_state_ceiling"]}

    scoped = [pattern for pattern in patterns if job in pattern["jobs"] and carrier in pattern["carriers"]]
    if not scoped:
        return 2, {"status": "needs_research", "reason": "no exact job/carrier cover pattern", "job": job, "carrier": carrier}

    eligible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    missing_union: set[str] = set()
    for pattern in scoped:
        conflicts = sorted(active & set(pattern["contraindications"]))
        if visual_evidence_role == "primary" and pattern["family"] == "text_dominant_native_card" and not conflicts:
            conflicts = ["primary_visual_proof_overrides_text_card"]
        if conflicts:
            rejected.append({"pattern_id": pattern["pattern_id"], "reason": "contraindicated", "active_contraindications": conflicts})
            continue
        gap = material_gap(pattern, materials)
        if gap:
            missing_union.update(gap)
            rejected.append({"pattern_id": pattern["pattern_id"], "reason": "missing_materials", "missing_materials": sorted(gap)})
            continue
        eligible.append(pattern)

    if not eligible:
        status = "needs_materials" if missing_union else "contraindicated"
        payload: dict[str, Any] = {"status": status, "rejected_patterns": rejected, "claim_ceiling": library["claim_ceiling"]}
        if missing_union:
            payload["missing_materials"] = sorted(missing_union)
        return 2, payload

    def score(pattern: dict[str, Any]) -> tuple[int, int, str]:
        is_text = pattern["family"] == "text_dominant_native_card"
        route_penalty = 0
        if visual_evidence_role in {"none", "supporting"}:
            route_penalty = 0 if is_text else 20
        elif visual_evidence_role == "primary":
            route_penalty = 0 if not is_text else 100
        return (route_penalty, int(pattern["priority_policy"]["rank"]), pattern["pattern_id"])

    selected = sorted(eligible, key=score)[0]
    for pattern in eligible:
        if pattern["pattern_id"] != selected["pattern_id"]:
            rejected.append({"pattern_id": pattern["pattern_id"], "reason": "lower_task_priority"})
    return 0, {
        "status": "matched",
        "selected_pattern": selected,
        "rejected_patterns": rejected,
        "claim_ceiling": library["claim_ceiling"],
        "output_state_ceiling": library["output_state_ceiling"],
        "performance_evidence": "not_performance_evidence",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", type=Path, default=DEFAULT_ASSET)
    parser.add_argument("--job", required=True)
    parser.add_argument("--carrier", required=True)
    parser.add_argument("--materials", default="")
    parser.add_argument("--visual-evidence-role", choices=["none", "supporting", "primary"], required=True)
    parser.add_argument("--pattern-id")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        library = load_library(args.asset)
        code, payload = select_pattern(
            library,
            job=args.job,
            carrier=args.carrier,
            materials=parse_csv(args.materials),
            visual_evidence_role=args.visual_evidence_role,
            pattern_id=args.pattern_id,
        )
    except ContractError as exc:
        code, payload = 2, {"status": "invalid_contract", "reason": str(exc)}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
