#!/usr/bin/env python3
"""Select one exact, evidence-bounded aesthetic overlay for prototype exploration."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSET_PATH = SKILL_ROOT / "assets" / "aesthetic-exploration-prompts-v1.json"


class ContractError(ValueError):
    pass


def split_codes(value: str) -> set[str]:
    return {
        item.strip()
        for item in value.split(",")
        if item.strip() and item.strip().lower() != "none"
    }


def parse_counts(materials: set[str], value: str) -> dict[str, int]:
    counts = {code: 1 for code in materials}
    for item in split_codes(value):
        if "=" not in item:
            raise ContractError(f"invalid material count {item!r}; use code=integer")
        code, raw_count = (part.strip() for part in item.split("=", 1))
        try:
            count = int(raw_count)
        except ValueError as exc:
            raise ContractError(f"invalid material count for {code}") from exc
        if not code or count < 0:
            raise ContractError(f"invalid material count for {code}")
        counts[code] = count
    return counts


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_observation_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ContractError(f"invalid observation JSONL line {line_number}") from exc
            observation_id = record.get("observation_id")
            if not isinstance(observation_id, str) or not observation_id:
                raise ContractError(f"missing observation_id on line {line_number}")
            ids.add(observation_id)
    return ids


def verify_sources(library: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
    snapshots = library.get("source_snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        raise ContractError("source_snapshots are required")
    audit_json: dict[str, Any] | None = None
    observation_ids: set[str] = set()
    for snapshot in snapshots:
        required = {"snapshot_id", "path", "sha256", "captured_at", "review_by"}
        if set(snapshot) != required:
            raise ContractError("source snapshot fields are not exact")
        source_path = SKILL_ROOT / snapshot["path"]
        if not source_path.is_file():
            raise ContractError(f"source snapshot missing: {snapshot['path']}")
        if sha256_file(source_path) != snapshot["sha256"]:
            raise ContractError(f"source snapshot hash mismatch: {snapshot['snapshot_id']}")
        try:
            review_by = date.fromisoformat(snapshot["review_by"])
        except (TypeError, ValueError) as exc:
            raise ContractError(f"invalid review_by: {snapshot['snapshot_id']}") from exc
        if review_by < date.today():
            raise ContractError(f"source snapshot is stale: {snapshot['snapshot_id']}")
        if snapshot["snapshot_id"] == "SRC-AESTHETIC-CLAIMS-V1":
            audit_json = load_json(source_path)
        if snapshot["snapshot_id"] == "SRC-AESTHETIC-OBS-V1":
            observation_ids = load_observation_ids(source_path)
    if audit_json is None or not observation_ids:
        raise ContractError("required audit or observation snapshot is absent")
    return audit_json, observation_ids


def verify_library(path: Path) -> dict[str, Any]:
    library = load_json(path)
    if library.get("status") != "curated_exploration":
        raise ContractError("library status must remain curated_exploration")
    if library.get("performance_evidence_status") != "candidate_only":
        raise ContractError("library must remain candidate_only")
    if library.get("performance_evidence_scope") != "not_performance_evidence":
        raise ContractError("library must remain not_performance_evidence")
    if library.get("output_ceiling") != "prototype_only":
        raise ContractError("library output ceiling must remain prototype_only")
    if library.get("starter_eligible") is not False:
        raise ContractError("library cannot be starter eligible")
    audit, observation_ids = verify_sources(library)
    claim_by_id = {claim.get("claim_id"): claim for claim in audit.get("claims", [])}
    if None in claim_by_id or not claim_by_id:
        raise ContractError("audit claim ledger is missing")
    source_ids = {source.get("source_id") for source in audit.get("sources", [])}
    for claim_id, claim in claim_by_id.items():
        if claim.get("source_id") not in source_ids:
            raise ContractError(f"{claim_id} references an unknown public source")
        expected_claim_sha = hashlib.sha256(str(claim.get("claim", "")).encode()).hexdigest()
        if claim.get("claim_text_sha256") != expected_claim_sha:
            raise ContractError(f"{claim_id} claim text hash mismatch")
        if not {"performance_tier", "style_ready_evidence", "traffic_causality"}.issubset(
            set(claim.get("prohibited_use_codes", []))
        ):
            raise ContractError(f"{claim_id} lacks performance boundaries")
    prompt_ids: set[str] = set()
    cell_ids: set[str] = set()
    allowed_prompt_roles = {"task_fit", "series_identity_only", "anti_pattern"}
    allowed_selection = {"exploration_selectable", "research_lead_only", "disabled"}
    for prompt in library.get("prompts", []):
        prompt_id = prompt.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id or prompt_id in prompt_ids:
            raise ContractError("prompt IDs must be unique and non-empty")
        prompt_ids.add(prompt_id)
        if prompt.get("prompt_role") not in allowed_prompt_roles:
            raise ContractError(f"{prompt_id} has invalid prompt_role")
        if prompt.get("selection_status") not in allowed_selection:
            raise ContractError(f"{prompt_id} has invalid selection_status")
        if prompt.get("performance_evidence_scope") != "not_performance_evidence":
            raise ContractError(f"{prompt_id} claims performance evidence")
        if prompt.get("output_ceiling") not in {"prototype_only", "brief_only"}:
            raise ContractError(f"{prompt_id} has invalid output ceiling")
        expected_prompt_sha = hashlib.sha256(prompt.get("prompt_template", "").encode()).hexdigest()
        if prompt.get("prompt_sha256") != expected_prompt_sha:
            raise ContractError(f"{prompt_id} prompt hash mismatch")
        compatible = set(prompt.get("compatible_direction_card_ids", []))
        if not compatible:
            raise ContractError(f"{prompt_id} has no compatible direction cards")
        for cell in prompt.get("scope_cells", []):
            required_cell_fields = {
                "cell_id", "category_code", "primary_job", "carrier", "direction_card_id",
                "required_material_codes", "material_count_gates", "required_constraint_codes",
                "contraindication_codes", "observation_refs", "public_source_refs", "claim_refs",
                "counterexample_refs", "cell_status",
            }
            if set(cell) != required_cell_fields:
                raise ContractError(f"{prompt_id} scope cell fields are not exact")
            cell_id = cell["cell_id"]
            if not isinstance(cell_id, str) or not cell_id or cell_id in cell_ids:
                raise ContractError("scope cell IDs must be unique and non-empty")
            cell_ids.add(cell_id)
            if cell["direction_card_id"] not in compatible:
                raise ContractError(f"{cell_id} uses an incompatible direction card")
            if set(cell["material_count_gates"]) != set(cell["required_material_codes"]):
                raise ContractError(f"{cell_id} material gates do not match required codes")
            if not cell["required_constraint_codes"] or not cell["observation_refs"]:
                raise ContractError(f"{cell_id} lacks constraints or observations")
            for ref in cell["observation_refs"]:
                if ref.get("id") not in observation_ids:
                    raise ContractError(f"{cell_id} references an unknown observation")
                if ref.get("role") not in {"task_fit", "series_constant", "boundary", "research_lead", "anti_pattern"}:
                    raise ContractError(f"{cell_id} has invalid observation role")
                if not ref.get("limitations"):
                    raise ContractError(f"{cell_id} observation lacks limitations")
            for ref in cell["claim_refs"]:
                claim = claim_by_id.get(ref.get("id"))
                if claim is None:
                    raise ContractError(f"{cell_id} references an unknown claim")
                if ref.get("allowed_use_code") not in claim.get("allowed_use_codes", []):
                    raise ContractError(f"{cell_id} claim use is outside its ledger scope")
                prohibited = set(ref.get("explicitly_not_supporting", []))
                if prohibited != {"aesthetic_effect", "performance_tier", "traffic_causality"}:
                    raise ContractError(f"{cell_id} claim boundary is incomplete")
    expected = library.get("self_check", {}).get("prompt_count")
    if expected != len(prompt_ids):
        raise ContractError("self_check prompt_count mismatch")
    if library.get("self_check", {}).get("scope_cell_count") != len(cell_ids):
        raise ContractError("self_check scope_cell_count mismatch")
    return library


def exact_tuple(cell: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        cell["category_code"],
        cell["primary_job"],
        cell["carrier"],
        cell["direction_card_id"],
    )


def select(args: argparse.Namespace, library: dict[str, Any]) -> dict[str, Any]:
    if args.mode != "explicit_exploration":
        return {
            "status": "binding_controls_aesthetics" if args.mode in {"production", "grounded", "rendered"} else "invalid_query",
            "reason": "aesthetic overlays are only available in explicit_exploration mode",
            "output_state": "brief_only",
        }
    if args.requested_output_state in {"ready", "viral", "performance_rule", "traffic_validated"}:
        return {
            "status": "forbidden_output_state",
            "reason": "this library can never emit ready, viral, performance_rule, or traffic_validated",
            "output_state": "brief_only",
        }
    if args.published_binding_status == "published":
        return {
            "status": "binding_controls_aesthetics",
            "reason": "the exact published style binding is the only production aesthetic authority",
            "output_state": "use_published_binding",
        }
    reset_changes = split_codes(args.reset_changes)
    if args.holistic_rejections >= 2 and len(reset_changes & {"target_sample", "prompt_module", "real_materials"}) < 2:
        return {
            "status": "reset_required_after_two_rejections",
            "reason": "after two holistic rejections, change at least two of target_sample, prompt_module, real_materials",
            "output_state": "brief_only",
        }
    if args.rights_provenance_status != "passed":
        return {
            "status": "rights_or_provenance_blocked",
            "reason": "rights, privacy, disclosure, or provenance receipts are not closed",
            "output_state": "brief_only",
        }

    requested = (args.category_code, args.primary_job, args.carrier, args.direction_card_id)
    exact_matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    analogue_matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for prompt in library["prompts"]:
        if args.prompt_id and prompt["prompt_id"] != args.prompt_id:
            continue
        for cell in prompt["scope_cells"]:
            if exact_tuple(cell) == requested:
                exact_matches.append((prompt, cell))
        for cell in prompt.get("analogue_cells_requires_review", []):
            analogue_tuple = (
                cell["category_code"], cell["primary_job"], cell["carrier"], cell["direction_card_id"]
            )
            if analogue_tuple == requested:
                analogue_matches.append((prompt, cell))

    all_prompt_ids = {prompt["prompt_id"] for prompt in library["prompts"]}
    if args.prompt_id and args.prompt_id not in all_prompt_ids:
        return {"status": "invalid_query", "reason": f"unknown prompt_id: {args.prompt_id}", "output_state": "brief_only"}
    if not exact_matches:
        if analogue_matches:
            return {
                "status": "analogue_review_required",
                "reason": "this tuple is only an analogue lead; record transfer rationale and build a local exact scope cell before generation",
                "candidates": [
                    {"prompt_id": prompt["prompt_id"], "analogue": cell}
                    for prompt, cell in analogue_matches
                ],
                "output_state": "brief_only",
            }
        return {
            "status": "no_exact_scope_cell",
            "reason": "no observed exact category × primary_job × carrier × direction card cell exists",
            "output_state": "prototype_gap/brief_only",
        }
    if len(exact_matches) > 1 and not args.prompt_id:
        return {
            "status": "invalid_query",
            "reason": "multiple prompt modules share this exact tuple; select one prompt_id and record rejected candidates",
            "candidates": [
                {"prompt_id": prompt["prompt_id"], "cell_id": cell["cell_id"]}
                for prompt, cell in exact_matches
            ],
            "output_state": "brief_only",
        }

    prompt, cell = exact_matches[0]
    if prompt["selection_status"] == "research_lead_only" or cell["cell_status"] == "research_lead_only":
        return {
            "status": "research_lead_only",
            "reason": "the observation is not stable enough for a visual prototype; collect the listed evidence gap first",
            "prompt_id": prompt["prompt_id"],
            "cell_id": cell["cell_id"],
            "output_state": "brief_only",
        }
    if args.direction_card_id not in prompt["compatible_direction_card_ids"]:
        return {
            "status": "incompatible_direction",
            "reason": "the selected visual direction card is outside this prompt's evidence scope",
            "output_state": "brief_only",
        }

    materials = split_codes(args.materials)
    constraints = split_codes(args.constraints)
    contraindications = split_codes(args.contraindications)
    try:
        material_counts = parse_counts(materials, args.material_counts)
    except ContractError as exc:
        return {"status": "invalid_query", "reason": str(exc), "output_state": "brief_only"}
    missing_materials = [
        code for code in cell["required_material_codes"]
        if material_counts.get(code, 0) < int(cell["material_count_gates"][code])
    ]
    missing_constraints = sorted(set(cell["required_constraint_codes"]) - constraints)
    if missing_materials or missing_constraints:
        return {
            "status": "needs_materials",
            "reason": "manifest-backed material count or required constraint gate failed",
            "missing_materials": missing_materials,
            "missing_constraints": missing_constraints,
            "required_material_count_gates": cell["material_count_gates"],
            "output_state": "brief_only",
        }
    active = sorted(set(cell["contraindication_codes"]) & contraindications)
    if active:
        return {
            "status": "contraindication_blocked",
            "reason": "one or more active contraindications block this prompt",
            "active_contraindications": active,
            "output_state": "brief_only",
        }

    rejected = split_codes(args.rejected_prompt_ids)
    if prompt["prompt_id"] in rejected:
        return {"status": "invalid_query", "reason": "selected prompt also appears in rejected_prompt_ids", "output_state": "brief_only"}
    return {
        "status": "matched_exploration",
        "performance_evidence_status": "candidate_only",
        "performance_evidence_scope": "not_performance_evidence",
        "output_state": "prototype_only",
        "starter_eligible": False,
        "prompt_id": prompt["prompt_id"],
        "prompt_sha256": prompt["prompt_sha256"],
        "cell_id": cell["cell_id"],
        "category_code": cell["category_code"],
        "primary_job": cell["primary_job"],
        "carrier": cell["carrier"],
        "direction_card_id": cell["direction_card_id"],
        "source_snapshot_hashes": {
            item["snapshot_id"]: item["sha256"] for item in library["source_snapshots"]
        },
        "observation_refs": cell["observation_refs"],
        "claim_refs": cell["claim_refs"],
        "counterexample_refs": cell["counterexample_refs"],
        "asset_manifest_refs": sorted(materials),
        "rights_provenance_status": args.rights_provenance_status,
        "selection_reason": args.selection_reason,
        "rejected_prompt_ids": sorted(rejected),
        "aesthetic_directives": prompt["aesthetic_directives"],
        "prompt": f"{library['global_prompt_prefix']}\n\n本次 exact scope 方向：{prompt['prompt_template']}",
        "negative_prompt": library["global_negative_prompt"] + prompt["negative_prompt"],
        "review_checks": prompt["review_checks"],
        "limitations": [ref["limitations"] for ref in cell["observation_refs"]],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category-code", "--category", dest="category_code", required=True)
    parser.add_argument("--primary-job", required=True)
    parser.add_argument("--carrier", required=True)
    parser.add_argument("--direction-card-id", required=True)
    parser.add_argument("--materials", default="none", help="comma-separated manifest-backed material codes")
    parser.add_argument("--material-counts", default="none", help="comma-separated code=integer counts")
    parser.add_argument("--constraints", default="none", help="comma-separated passed constraint codes")
    parser.add_argument("--contraindications", default="none", help="comma-separated active contraindication codes")
    parser.add_argument("--prompt-id")
    parser.add_argument("--mode", choices=("explicit_exploration", "production", "grounded", "rendered"), default="explicit_exploration")
    parser.add_argument("--requested-output-state", default="prototype_only")
    parser.add_argument("--published-binding-status", choices=("none", "published"), default="none")
    parser.add_argument("--rights-provenance-status", choices=("passed", "blocked", "unknown"), default="unknown")
    parser.add_argument("--holistic-rejections", type=int, default=0)
    parser.add_argument("--reset-changes", default="none")
    parser.add_argument("--selection-reason", default="exact scope cell and material gates matched")
    parser.add_argument("--rejected-prompt-ids", default="none")
    parser.add_argument("--asset", type=Path, default=ASSET_PATH)
    parser.add_argument("--pretty", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        library = verify_library(args.asset)
        result = select(args, library)
    except (OSError, json.JSONDecodeError, ContractError) as exc:
        result = {
            "status": "stale_or_tampered_evidence",
            "reason": str(exc),
            "output_state": "prototype_gap/brief_only",
        }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result.get("status") == "matched_exploration" else 2


if __name__ == "__main__":
    raise SystemExit(main())
