#!/usr/bin/env python3
"""Select bounded Xiaohongshu traffic-mechanism cards from the packaged library."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_LIBRARY = Path(__file__).resolve().parents[1] / "assets" / "traffic-mechanisms-v1.json"


def emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"status: {payload['status']}")
    if payload.get("message"):
        print(payload["message"])
    if payload.get("missing_material_codes"):
        print("missing_materials: " + ", ".join(payload["missing_material_codes"]))
    if payload.get("forbidden_material_codes"):
        print("forbidden_materials: " + ", ".join(payload["forbidden_material_codes"]))
    for match in payload.get("matches", []):
        print(
            f"\n[{match['selection_slot']}] {match['mechanism_id']}  "
            f"{match['name']}  score={match['selection_score']}"
        )
        print(match["one_line_formula"])
        print("inputs: " + "；".join(match["inputs"]))
        print("failure: " + "；".join(match["failure_conditions"]))


def load_library(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("schema_version") != "1.0.0" or not isinstance(
        payload.get("mechanisms"), list
    ):
        raise ValueError("unsupported or malformed mechanism library")
    required_fields = {
        "mechanism_id",
        "mechanism_kind",
        "required_material_codes",
        "forbidden_material_codes",
        "requires",
        "conflicts_with",
        "activation",
        "priority",
        "source_refs",
    }
    allowed_kinds = set(payload.get("mechanism_kind_taxonomy", []))
    allowed_materials = set(payload.get("material_code_taxonomy", []))
    allowed_forbidden = set(payload.get("forbidden_material_code_taxonomy", []))
    allowed_carriers = set(payload.get("carrier_taxonomy", []))
    mechanism_ids = {
        card.get("mechanism_id")
        for card in payload["mechanisms"]
        if isinstance(card, dict)
    }
    if None in mechanism_ids or len(mechanism_ids) != len(payload["mechanisms"]):
        raise ValueError("mechanism_id values must be present and unique")
    for card in payload["mechanisms"]:
        missing_fields = required_fields - set(card)
        if missing_fields:
            raise ValueError(
                f"{card.get('mechanism_id', 'unknown')} missing fields: "
                + ", ".join(sorted(missing_fields))
            )
        if card["mechanism_kind"] not in allowed_kinds:
            raise ValueError(f"unknown mechanism_kind in {card['mechanism_id']}")
        if not isinstance(card["priority"], int) or not 0 <= card["priority"] <= 100:
            raise ValueError(f"invalid priority in {card['mechanism_id']}")
        if set(card["required_material_codes"]) - allowed_materials:
            raise ValueError(f"unknown required material in {card['mechanism_id']}")
        if set(card["forbidden_material_codes"]) - allowed_forbidden:
            raise ValueError(f"unknown forbidden material in {card['mechanism_id']}")
        if (set(card["requires"]) | set(card["conflicts_with"])) - mechanism_ids:
            raise ValueError(f"unknown mechanism relation in {card['mechanism_id']}")
        if card["mechanism_id"] in set(card["requires"]) | set(card["conflicts_with"]):
            raise ValueError(f"self relation in {card['mechanism_id']}")
        carrier_values = set(card["carrier_task_fit"].get("preferred", [])) | set(
            card["carrier_task_fit"].get("compatible", [])
        )
        if carrier_values - allowed_carriers:
            raise ValueError(f"unknown carrier in {card['mechanism_id']}")
        expected_stages = {
            card["traffic_stage"]["primary"],
            *card["traffic_stage"]["secondary"],
        }
        if set(card["activation"].get("eligible_traffic_stages", [])) != expected_stages:
            raise ValueError(f"activation stage drift in {card['mechanism_id']}")
        if set(card["activation"].get("eligible_primary_jobs", [])) != set(
            card["primary_jobs"]
        ):
            raise ValueError(f"activation job drift in {card['mechanism_id']}")
        for ref in card["source_refs"]:
            if not {"ref", "evidence_layer", "scope", "limitation"}.issubset(ref):
                raise ValueError(f"incomplete source ref in {card['mechanism_id']}")
            if "/" in ref["ref"].split(":", 1)[-1]:
                raise ValueError(f"composite source ref in {card['mechanism_id']}")
        ref_ids = {ref["ref"] for ref in card["source_refs"]}
        if set(card.get("subrecipe_refs", [])) - ref_ids:
            raise ValueError(f"unresolved subrecipe ref in {card['mechanism_id']}")
    cards_by_id = {card["mechanism_id"]: card for card in payload["mechanisms"]}
    for card in payload["mechanisms"]:
        for conflict_id in card["conflicts_with"]:
            if card["mechanism_id"] not in cards_by_id[conflict_id]["conflicts_with"]:
                raise ValueError(
                    f"asymmetric conflict {card['mechanism_id']} <-> {conflict_id}"
                )
    for carrier, contract in payload.get("carrier_truth_conditions", {}).items():
        if carrier not in allowed_carriers:
            raise ValueError(f"truth contract for unknown carrier {carrier}")
        truth_materials = set(contract.get("required_all_material_codes", [])) | set(
            contract.get("required_any_material_codes", [])
        )
        if truth_materials - allowed_materials:
            raise ValueError(f"unknown truth material for carrier {carrier}")
        if set(contract.get("forbidden_material_codes", [])) - allowed_forbidden:
            raise ValueError(f"unknown truth contraindication for carrier {carrier}")
    return payload


SLOT_KINDS = {
    "content": {"content"},
    "carrier_or_truth": {"carrier_router", "truth_gate"},
    "learning_or_governance": {"feedback", "measurement", "governance"},
}


def score_card(
    card: dict[str, Any], stage: str, job: str, carrier: str | None
) -> float:
    traffic = card["traffic_stage"]
    score: float = 4 if traffic["primary"] == stage else 2
    if job not in card["activation"]["eligible_primary_jobs"]:
        return -1
    score += 4
    if carrier:
        fit = card["carrier_task_fit"]
        if carrier in fit["preferred"]:
            score += 3
        elif carrier in fit["compatible"]:
            score += 1
        else:
            return -1
    score += card["priority"] / 100
    return score


def parse_materials(csv_values: list[str], repeated_values: list[str]) -> set[str]:
    materials = {value.strip() for value in repeated_values if value.strip()}
    for csv_value in csv_values:
        materials.update(value.strip() for value in csv_value.split(",") if value.strip())
    return materials


def material_gaps(
    card: dict[str, Any], materials: set[str]
) -> tuple[set[str], set[str]]:
    missing = set(card["required_material_codes"]) - materials
    forbidden = set(card["forbidden_material_codes"]) & materials
    return missing, forbidden


def carrier_truth_gaps(
    library: dict[str, Any], carrier: str | None, materials: set[str]
) -> tuple[set[str], set[str]]:
    if not carrier:
        return set(), set()
    contract = library.get("carrier_truth_conditions", {}).get(carrier)
    if not contract:
        return set(), set()
    missing = set(contract.get("required_all_material_codes", [])) - materials
    any_codes = set(contract.get("required_any_material_codes", []))
    if any_codes and not any_codes.intersection(materials):
        missing.add(contract["missing_material_code"])
    forbidden = set(contract.get("forbidden_material_codes", [])) & materials
    return missing, forbidden


def card_slot(card: dict[str, Any]) -> str:
    for slot, kinds in SLOT_KINDS.items():
        if card["mechanism_kind"] in kinds:
            return slot
    raise ValueError(f"unknown mechanism_kind for {card['mechanism_id']}")


def cards_conflict(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        right["mechanism_id"] in left["conflicts_with"]
        or left["mechanism_id"] in right["conflicts_with"]
    )


def selected_payload(card: dict[str, Any], score: float, slot: str) -> dict[str, Any]:
    selected = {
        key: card[key]
        for key in (
            "mechanism_id",
            "name",
            "mechanism_kind",
            "one_line_formula",
            "traffic_stage",
            "primary_jobs",
            "carrier_task_fit",
            "required_material_codes",
            "forbidden_material_codes",
            "requires",
            "conflicts_with",
            "activation",
            "priority",
            "inputs",
            "actions",
            "metrics",
            "failure_conditions",
            "anti_cargo_cult",
            "source_refs",
        )
    }
    if card.get("subrecipe_refs"):
        selected["subrecipe_refs"] = card["subrecipe_refs"]
    selected["selection_slot"] = slot
    selected["selection_score"] = round(score, 2)
    return selected


def select(
    library: dict[str, Any],
    stage: str,
    job: str,
    carrier: str | None,
    materials: set[str],
    limit: int,
) -> tuple[dict[str, Any], int]:
    invalid: list[str] = []
    if stage not in library["traffic_stage_taxonomy"]:
        invalid.append(f"traffic_stage={stage}")
    if job not in library["primary_job_taxonomy"]:
        invalid.append(f"primary_job={job}")
    if carrier and carrier not in library["carrier_taxonomy"]:
        invalid.append(f"carrier={carrier}")
    known_materials = set(library.get("material_code_taxonomy", [])) | set(
        library.get("forbidden_material_code_taxonomy", [])
    )
    unknown_materials = sorted(materials - known_materials)
    if unknown_materials:
        invalid.extend(f"material={value}" for value in unknown_materials)
    if invalid:
        return (
            {
                "status": "invalid_query",
                "message": "invalid taxonomy value(s): " + ", ".join(invalid),
                "matches": [],
            },
            2,
        )

    carrier_missing, carrier_forbidden = carrier_truth_gaps(library, carrier, materials)
    if carrier_missing or carrier_forbidden:
        return (
            {
                "status": "needs_materials",
                "message": "Carrier truth conditions are not satisfied.",
                "query": {
                    "traffic_stage": stage,
                    "primary_job": job,
                    "carrier": carrier,
                    "materials": sorted(materials),
                },
                "missing_material_codes": sorted(carrier_missing),
                "forbidden_material_codes": sorted(carrier_forbidden),
                "matches": [],
            },
            2,
        )

    structural: dict[str, list[tuple[float, dict[str, Any]]]] = {
        slot: [] for slot in SLOT_KINDS
    }
    eligible: dict[str, list[tuple[float, dict[str, Any]]]] = {
        slot: [] for slot in SLOT_KINDS
    }
    for card in library["mechanisms"]:
        stages = card["activation"]["eligible_traffic_stages"]
        if stage not in stages:
            continue
        score = score_card(card, stage, job, carrier)
        if score >= 0:
            slot = card_slot(card)
            structural[slot].append((score, card))
            missing, forbidden = material_gaps(card, materials)
            if not missing and not forbidden:
                eligible[slot].append((score, card))

    for pool in (*structural.values(), *eligible.values()):
        pool.sort(key=lambda item: (-item[0], item[1]["mechanism_id"]))

    empty_structural = [slot for slot, pool in structural.items() if not pool]
    if empty_structural:
        return (
            {
                "status": "needs_research",
                "message": (
                    "No complete three-slot task-fit set. Keep the same primary job and "
                    "carrier; collect a current comparable mechanism for the missing slot(s)."
                ),
                "query": {
                    "traffic_stage": stage,
                    "primary_job": job,
                    "carrier": carrier,
                    "materials": sorted(materials),
                },
                "missing_selection_slots": empty_structural,
                "matches": [],
            },
            2,
        )

    empty_eligible = [slot for slot, pool in eligible.items() if not pool]
    if empty_eligible:
        missing_codes: set[str] = set()
        forbidden_codes: set[str] = set()
        candidates: list[dict[str, Any]] = []
        for slot in empty_eligible:
            score, card = structural[slot][0]
            missing, forbidden = material_gaps(card, materials)
            missing_codes.update(missing)
            forbidden_codes.update(forbidden)
            candidates.append(
                {
                    "selection_slot": slot,
                    "mechanism_id": card["mechanism_id"],
                    "name": card["name"],
                    "missing_material_codes": sorted(missing),
                    "forbidden_material_codes": sorted(forbidden),
                    "selection_score_without_material_gate": round(score, 2),
                }
            )
        return (
            {
                "status": "needs_materials",
                "message": (
                    "Task-fit cards exist, but the available material set cannot satisfy "
                    "all three selection slots. Supply or verify materials; do not replace "
                    "the task with generic governance advice."
                ),
                "query": {
                    "traffic_stage": stage,
                    "primary_job": job,
                    "carrier": carrier,
                    "materials": sorted(materials),
                },
                "missing_material_codes": sorted(missing_codes),
                "forbidden_material_codes": sorted(forbidden_codes),
                "gap_candidates": candidates,
                "matches": [],
            },
            2,
        )

    chosen: dict[str, tuple[float, dict[str, Any]]] = {
        slot: pool[0] for slot, pool in eligible.items()
    }
    chosen_ids = {card["mechanism_id"] for _, card in chosen.values()}
    for slot, (_, card) in list(chosen.items()):
        for required_id in card["requires"]:
            if required_id in chosen_ids:
                continue
            required_card = next(
                (
                    item
                    for pool in eligible.values()
                    for item in pool
                    if item[1]["mechanism_id"] == required_id
                ),
                None,
            )
            if required_card is None:
                structural_required = next(
                    (
                        item
                        for pool in structural.values()
                        for item in pool
                        if item[1]["mechanism_id"] == required_id
                    ),
                    None,
                )
                if structural_required is not None:
                    missing, forbidden = material_gaps(
                        structural_required[1], materials
                    )
                    return (
                        {
                            "status": "needs_materials",
                            "message": (
                                f"Selected mechanism {card['mechanism_id']} requires "
                                f"{required_id}, but its material gate is not satisfied."
                            ),
                            "query": {
                                "traffic_stage": stage,
                                "primary_job": job,
                                "carrier": carrier,
                                "materials": sorted(materials),
                            },
                            "missing_material_codes": sorted(missing),
                            "forbidden_material_codes": sorted(forbidden),
                            "required_by": card["mechanism_id"],
                            "required_mechanism_id": required_id,
                            "matches": [],
                        },
                        2,
                    )
                return (
                    {
                        "status": "needs_research",
                        "message": f"Required mechanism {required_id} is not task-fit.",
                        "query": {
                            "traffic_stage": stage,
                            "primary_job": job,
                            "carrier": carrier,
                            "materials": sorted(materials),
                        },
                        "matches": [],
                    },
                    2,
                )
            required_slot = card_slot(required_card[1])
            chosen[required_slot] = required_card
            chosen_ids = {item[1]["mechanism_id"] for item in chosen.values()}

    ordered_slots = ["content", "carrier_or_truth", "learning_or_governance"]
    # Preserve the primary content path first; resolve conflicts from governance back inward.
    for slot in reversed(ordered_slots):
        current_score, current_card = chosen[slot]
        others = [card for other_slot, (_, card) in chosen.items() if other_slot != slot]
        if not any(cards_conflict(current_card, other) for other in others):
            continue
        replacement = next(
            (
                candidate
                for candidate in eligible[slot]
                if not any(cards_conflict(candidate[1], other) for other in others)
                and set(candidate[1]["requires"]).issubset(
                    {other["mechanism_id"] for other in others}
                )
            ),
            None,
        )
        if replacement is None:
            return (
                {
                    "status": "needs_research",
                    "message": (
                        f"No non-conflicting mechanism remains for selection slot {slot}."
                    ),
                    "query": {
                        "traffic_stage": stage,
                        "primary_job": job,
                        "carrier": carrier,
                        "materials": sorted(materials),
                    },
                    "conflicting_mechanism_ids": sorted(
                        {
                            current_card["mechanism_id"],
                            *(
                                other["mechanism_id"]
                                for other in others
                                if cards_conflict(current_card, other)
                            ),
                        }
                    ),
                    "matches": [],
                },
                2,
            )
        chosen[slot] = replacement

    matches = [
        selected_payload(card, score, slot)
        for slot in ordered_slots[:limit]
        for score, card in [chosen[slot]]
    ]
    return (
        {
            "status": "matched",
            "library_id": library["library_id"],
            "snapshot_date": library["snapshot_date"],
            "query": {
                "traffic_stage": stage,
                "primary_job": job,
                "carrier": carrier,
                "materials": sorted(materials),
            },
            "selection_contract": "one content + one carrier/truth + one feedback/measurement/governance",
            "warning": library["non_guarantee"],
            "matches": matches,
        },
        0,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Select task-fit mechanism cards; output is not a viral prediction."
    )
    parser.add_argument("--stage", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--carrier")
    parser.add_argument(
        "--materials",
        action="append",
        default=[],
        help="Comma-separated available/verified material codes; may be repeated.",
    )
    parser.add_argument(
        "--material",
        action="append",
        default=[],
        help="One available/verified material code; may be repeated.",
    )
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.limit < 3:
        emit({"status": "invalid_query", "message": "limit must be >= 3", "matches": []}, args.json)
        return 2
    try:
        library = load_library(args.library.expanduser().resolve())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        emit({"status": "library_error", "message": str(exc), "matches": []}, args.json)
        return 2
    materials = parse_materials(args.materials, args.material)
    payload, exit_code = select(
        library, args.stage, args.job, args.carrier, materials, args.limit
    )
    emit(payload, args.json)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
