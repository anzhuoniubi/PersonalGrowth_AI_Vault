#!/usr/bin/env python3
"""Select evidence/attention skeletons without inventing materials or aesthetics."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote


DEFAULT_LIBRARY = (
    Path(__file__).resolve().parents[1]
    / "assets"
    / "visual-direction-cards-v1.json"
)


class ContractError(ValueError):
    """Raised when a packaged or run-supplied contract is malformed."""


def emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"status: {payload['status']}")
    if payload.get("message"):
        print(payload["message"])
    for gap in payload.get("prototype_gaps", []):
        print(f"\n[{gap['card_id']}] {gap['name']}")
        if gap.get("missing_materials"):
            print("missing_materials: " + ", ".join(gap["missing_materials"]))
        if gap.get("active_contraindications"):
            print(
                "active_contraindications: "
                + ", ".join(gap["active_contraindications"])
            )
    for match in payload.get("matches", []):
        print(f"\n[{match['card_id']}] {match['name']}")
        print("attention: " + " → ".join(match["attention_path"]["sequence"]))
        print("carrier_plan: " + match["carrier_role_plan"]["output_shape"])
        print("aesthetics: " + match["aesthetic_control"]["source"])


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"{label} cannot be read as JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ContractError(f"{label} must be a JSON object")
    return payload


def load_library(path: Path) -> dict[str, Any]:
    payload = load_json(path, "visual direction library")
    if payload.get("schema_version") != "1.1.0":
        raise ContractError("unsupported visual direction library schema")
    cards = payload.get("cards")
    if not isinstance(cards, list) or not cards:
        raise ContractError("visual direction library cards must be non-empty")

    required_top = {
        "carrier_taxonomy",
        "primary_job_taxonomy",
        "asset_manifest_contract",
        "style_binding_contract",
    }
    if required_top - set(payload):
        raise ContractError("visual direction library missing machine contracts")
    asset_contract = payload["asset_manifest_contract"]
    required_asset_fields = {
        "asset_id",
        "asset_path",
        "material_codes",
        "sha256",
        "media_dimensions",
        "rights_basis",
        "authorization_ref",
        "license_ref",
        "transform_history",
        "privacy_review",
        "commercial_disclosure",
        "expires_at",
    }
    if set(asset_contract.get("required_fields", [])) != required_asset_fields:
        raise ContractError("asset manifest contract does not fail closed")
    if asset_contract.get("locator_contract", {}).get("mode") != "local_file_only":
        raise ContractError("unsupported asset locator mode")
    if not asset_contract.get("media_dimensions_contract", {}).get(
        "required_for_extensions"
    ):
        raise ContractError("asset dimension verification contract missing")
    style_contract = payload["style_binding_contract"]
    if style_contract.get("source") != "sqlite_publication_reconciliation_only":
        raise ContractError("standalone style binding is not allowed")
    if set(style_contract.get("exact_match_fields", [])) != {
        "category",
        "primary_job",
        "carrier",
    }:
        raise ContractError("style binding exact-match contract drift")

    card_ids = {card.get("card_id") for card in cards if isinstance(card, dict)}
    if None in card_ids or len(card_ids) != len(cards):
        raise ContractError("card_id values must be present and unique")

    carriers = set(payload["carrier_taxonomy"])
    jobs = set(payload["primary_job_taxonomy"])
    allowed_eligibility = set(payload["selection_eligibility_taxonomy"])
    null_behaviors = {
        "block_selection",
        "omit_clause",
        "render_as_not_applicable",
        "require_human_review",
    }
    required_fields = {
        "maturity",
        "selection_eligibility",
        "decision_predicate",
        "not_for",
        "nearest_alternative",
        "carrier_role_plans",
        "material_count_gates",
        "prompt_variables",
        "prompt_template",
    }
    for card in cards:
        card_id = card.get("card_id", "unknown")
        missing = required_fields - set(card)
        if missing:
            raise ContractError(f"{card_id} missing fields: {', '.join(sorted(missing))}")
        if card.get("performance_evidence_status") != "candidate_only":
            raise ContractError(f"{card_id} is not candidate_only")
        if card.get("performance_evidence_scope") != "not_performance_evidence":
            raise ContractError(f"{card_id} overstates performance evidence")
        if card.get("starter_eligible") is not False:
            raise ContractError(f"{card_id} cannot be starter eligible")
        if card.get("maturity") != "prototype":
            raise ContractError(f"{card_id} has unsupported maturity")
        if card.get("selection_eligibility") not in allowed_eligibility:
            raise ContractError(f"{card_id} has invalid selection_eligibility")
        if card.get("aesthetic_authority") != "published_style_binding_only":
            raise ContractError(f"{card_id} lets candidate guidance control aesthetics")

        suitable = card.get("suitable", {})
        card_carriers = set(suitable.get("carriers", []))
        card_jobs = set(suitable.get("primary_jobs", []))
        if not card_carriers or card_carriers - carriers:
            raise ContractError(f"{card_id} has unknown or empty carrier fit")
        if not card_jobs or card_jobs - jobs:
            raise ContractError(f"{card_id} has unknown or empty primary_job fit")
        if set(card["carrier_role_plans"]) != card_carriers:
            raise ContractError(f"{card_id} carrier role plan drift")
        if set(card["material_count_gates"]) != card_carriers:
            raise ContractError(f"{card_id} material count gate drift")

        variables: dict[str, dict[str, Any]] = {}
        for variable in card["prompt_variables"]:
            if not isinstance(variable, dict):
                raise ContractError(f"{card_id} has untyped prompt variable")
            if not {"name", "type", "required", "null_behavior"}.issubset(variable):
                raise ContractError(f"{card_id} has incomplete prompt variable")
            if variable["name"] in variables:
                raise ContractError(f"{card_id} has duplicate prompt variable")
            if variable["null_behavior"] not in null_behaviors:
                raise ContractError(f"{card_id} has invalid null behavior")
            if variable["required"] and variable["null_behavior"] != "block_selection":
                raise ContractError(f"{card_id} required variable does not fail closed")
            variables[variable["name"]] = variable
        if "asset_manifest_refs" not in variables:
            raise ContractError(f"{card_id} does not require asset_manifest_refs")

        proof_names = {
            role["required_proof"] for role in card.get("page_roles", [])
        }
        for plan in card["carrier_role_plans"].values():
            roles = plan.get("roles")
            if not isinstance(roles, list) or not roles:
                raise ContractError(f"{card_id} has empty carrier roles")
            merge = plan.get("single_image_merge", {})
            if plan.get("output_shape") == "single_image":
                if merge.get("allowed") is not True or not merge.get("merge_rule"):
                    raise ContractError(f"{card_id} lacks single-image merge rule")
            elif merge.get("allowed") is not False:
                raise ContractError(f"{card_id} wrongly permits single-image merge")
            proof_names.update(role["required_proof"] for role in roles)
        for proof_name in proof_names:
            variable = variables.get(proof_name)
            if not variable or not variable["required"]:
                raise ContractError(f"{card_id} proof {proof_name} is not required")

        placeholders = set(re.findall(r"\{([A-Za-z0-9_]+)\}", card["prompt_template"]))
        undeclared = placeholders - set(variables)
        if undeclared:
            raise ContractError(
                f"{card_id} prompt placeholders undeclared: {', '.join(sorted(undeclared))}"
            )
        if "asset_manifest_refs" not in placeholders:
            raise ContractError(f"{card_id} prompt does not bind asset manifest")
        for carrier, gates in card["material_count_gates"].items():
            if not isinstance(gates, list) or not gates:
                raise ContractError(f"{card_id}/{carrier} has no material count gates")
            for gate in gates:
                if (
                    not isinstance(gate.get("min_distinct_asset_refs"), int)
                    or gate["min_distinct_asset_refs"] < 1
                    or not gate.get("material_code")
                ):
                    raise ContractError(f"{card_id}/{carrier} has invalid count gate")
        for alternative in card["nearest_alternative"]:
            if alternative.get("card_id") not in card_ids or not alternative.get("when"):
                raise ContractError(f"{card_id} has invalid nearest alternative")

    raw = json.dumps(payload, ensure_ascii=False)
    if re.search(r"\d+\s*%|\d+\s*％", raw):
        raise ContractError("candidate library contains unsupported fixed ratios")
    if re.search(r"\d+\s*[—-]\s*\d+\s*字|\d+\s*字(?:内|以下|以上)", raw):
        raise ContractError("candidate library contains unsupported word limits")
    return payload


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_row_sha256(*values: object) -> str:
    normalized = [float(value) if isinstance(value, float) else value for value in values]
    return hashlib.sha256(canonical_json(normalized).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_is_below(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def jpeg_dimensions(path: Path) -> tuple[int, int]:
    sof_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    with path.open("rb") as handle:
        if handle.read(2) != b"\xff\xd8":
            raise ContractError(f"asset {path.name} is not a valid JPEG")
        while True:
            marker_start = handle.read(1)
            if not marker_start:
                break
            if marker_start != b"\xff":
                continue
            marker = handle.read(1)
            while marker == b"\xff":
                marker = handle.read(1)
            if not marker:
                break
            marker_value = marker[0]
            if marker_value in {0xD8, 0xD9}:
                continue
            length_bytes = handle.read(2)
            if len(length_bytes) != 2:
                break
            segment_length = struct.unpack(">H", length_bytes)[0]
            if segment_length < 2:
                break
            if marker_value in sof_markers:
                body = handle.read(5)
                if len(body) != 5:
                    break
                height, width = struct.unpack(">HH", body[1:])
                return width, height
            handle.seek(segment_length - 2, 1)
    raise ContractError(f"asset {path.name} JPEG dimensions cannot be read")


def webp_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ContractError(f"asset {path.name} is not a valid WebP")
    chunk = data[12:16]
    if chunk == b"VP8X":
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    if chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8 ":
        marker = data.find(b"\x9d\x01\x2a", 20)
        if marker >= 0 and len(data) >= marker + 7:
            width = int.from_bytes(data[marker + 3 : marker + 5], "little") & 0x3FFF
            height = int.from_bytes(data[marker + 5 : marker + 7], "little") & 0x3FFF
            return width, height
    raise ContractError(f"asset {path.name} WebP dimensions cannot be read")


def image_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(32)
    if header[:8] == b"\x89PNG\r\n\x1a\n":
        if len(header) < 24:
            raise ContractError(f"asset {path.name} is not a valid PNG")
        return struct.unpack(">II", header[16:24])
    if header[:6] in {b"GIF87a", b"GIF89a"}:
        if len(header) < 10:
            raise ContractError(f"asset {path.name} is not a valid GIF")
        return struct.unpack("<HH", header[6:10])
    if header[:2] == b"\xff\xd8":
        return jpeg_dimensions(path)
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return webp_dimensions(path)
    raise ContractError(f"asset {path.name} image dimensions cannot be read")


def detect_visual_kind(path: Path, contract: dict[str, Any]) -> str | None:
    with path.open("rb") as handle:
        header = handle.read(32)
    if (
        header[:8] == b"\x89PNG\r\n\x1a\n"
        or header[:6] in {b"GIF87a", b"GIF89a"}
        or header[:2] == b"\xff\xd8"
        or (header[:4] == b"RIFF" and header[8:12] == b"WEBP")
    ):
        return "image"
    if header[:4] == b"\x1a\x45\xdf\xa3" or header[4:8] == b"ftyp":
        return "video"
    suffix = path.suffix.lower()
    required_extensions = set(
        contract["media_dimensions_contract"]["required_for_extensions"]
    )
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        return "image"
    if suffix in required_extensions:
        return "video"
    return None


def video_dimensions(path: Path) -> tuple[int, int]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise ContractError(
            f"asset {path.name} requires ffprobe for dimension verification"
        )
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ContractError(f"asset {path.name} video dimensions cannot be read")
    try:
        streams = json.loads(result.stdout).get("streams", [])
        width = int(streams[0]["width"])
        height = int(streams[0]["height"])
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ContractError(
            f"asset {path.name} video dimensions cannot be read"
        ) from exc
    return width, height


def validate_dimensions(
    asset: dict[str, Any], located_path: Path, contract: dict[str, Any]
) -> None:
    declared = asset.get("media_dimensions")
    visual_kind = detect_visual_kind(located_path, contract)
    if visual_kind is None:
        if declared is not None:
            raise ContractError(
                f"asset {asset['asset_id']} declares unverifiable media_dimensions"
            )
        return
    if not isinstance(declared, dict) or set(declared) != {"width_px", "height_px"}:
        raise ContractError(
            f"asset {asset['asset_id']} requires width_px/height_px media_dimensions"
        )
    if any(
        not isinstance(declared[field], int) or declared[field] < 1
        for field in ("width_px", "height_px")
    ):
        raise ContractError(f"asset {asset['asset_id']} has invalid media_dimensions")
    if visual_kind == "image":
        actual_width, actual_height = image_dimensions(located_path)
    elif visual_kind == "video":
        actual_width, actual_height = video_dimensions(located_path)
    else:
        raise ContractError(f"asset {asset['asset_id']} dimensions cannot be verified")
    if (declared["width_px"], declared["height_px"]) != (
        actual_width,
        actual_height,
    ):
        raise ContractError(
            f"asset {asset['asset_id']} dimensions mismatch: "
            f"declared={declared['width_px']}x{declared['height_px']} "
            f"actual={actual_width}x{actual_height}"
        )


def validate_asset_manifest(
    payload: dict[str, Any], contract: dict[str, Any], manifest_root: Path
) -> tuple[list[dict[str, Any]], dict[str, set[str]]]:
    assets = payload.get(contract["container_field"])
    if not isinstance(assets, list) or not assets:
        raise ContractError("asset_manifest_refs must be a non-empty array")
    required_fields = set(contract["required_fields"])
    allowed_rights = set(contract["rights_basis_allowed"])
    allowed_privacy = set(contract["privacy_review_allowed"])
    allowed_commercial = set(contract["commercial_disclosure_allowed"])
    ids: set[str] = set()
    material_assets: dict[str, set[str]] = defaultdict(set)
    try:
        resolved_root = manifest_root.resolve(strict=True)
    except OSError as exc:
        raise ContractError("asset manifest root does not exist") from exc

    for index, asset in enumerate(assets):
        if not isinstance(asset, dict):
            raise ContractError(f"asset_manifest_refs[{index}] must be an object")
        missing = required_fields - set(asset)
        if missing:
            raise ContractError(
                f"asset_manifest_refs[{index}] missing " + ", ".join(sorted(missing))
            )
        asset_id = asset.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id.strip() or asset_id in ids:
            raise ContractError(f"asset_manifest_refs[{index}] has invalid/duplicate asset_id")
        ids.add(asset_id)
        asset_path = asset.get("asset_path")
        if not isinstance(asset_path, str) or not asset_path.strip():
            raise ContractError(f"asset {asset_id} has invalid asset_path")
        relative_path = Path(asset_path)
        if relative_path.is_absolute():
            raise ContractError(f"asset {asset_id} asset_path must be relative")
        if ".." in relative_path.parts:
            raise ContractError(f"asset {asset_id} asset_path contains path traversal")
        try:
            located_path = (resolved_root / relative_path).resolve(strict=True)
        except OSError as exc:
            raise ContractError(f"asset {asset_id} file does not exist") from exc
        if not path_is_below(located_path, resolved_root):
            raise ContractError(f"asset {asset_id} resolves outside manifest root")
        if not located_path.is_file():
            raise ContractError(f"asset {asset_id} is not a regular file")
        codes = asset.get("material_codes")
        if (
            not isinstance(codes, list)
            or not codes
            or any(not isinstance(code, str) or not code.strip() for code in codes)
        ):
            raise ContractError(f"asset {asset_id} has invalid material_codes")
        if not isinstance(asset.get("sha256"), str) or not re.fullmatch(
            r"[0-9a-f]{64}", asset["sha256"]
        ):
            raise ContractError(f"asset {asset_id} has invalid sha256")
        actual_sha256 = file_sha256(located_path)
        if actual_sha256 != asset["sha256"]:
            raise ContractError(
                f"asset {asset_id} sha256 mismatch: "
                f"declared={asset['sha256']} actual={actual_sha256}"
            )
        validate_dimensions(asset, located_path, contract)
        rights = asset.get("rights_basis")
        if rights not in allowed_rights:
            raise ContractError(f"asset {asset_id} has invalid rights_basis")
        if rights == "written_permission" and not asset.get("authorization_ref"):
            raise ContractError(f"asset {asset_id} requires authorization_ref")
        if rights == "licensed" and not asset.get("license_ref"):
            raise ContractError(f"asset {asset_id} requires license_ref")
        for nullable_field in ("authorization_ref", "license_ref"):
            value = asset.get(nullable_field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ContractError(f"asset {asset_id} has invalid {nullable_field}")
        if not isinstance(asset.get("transform_history"), list):
            raise ContractError(f"asset {asset_id} has invalid transform_history")
        if asset.get("privacy_review") not in allowed_privacy:
            raise ContractError(f"asset {asset_id} has invalid privacy_review")
        if asset.get("commercial_disclosure") not in allowed_commercial:
            raise ContractError(f"asset {asset_id} has invalid commercial_disclosure")
        expires_at = asset.get("expires_at")
        if expires_at is not None:
            if not isinstance(expires_at, str):
                raise ContractError(f"asset {asset_id} has invalid expires_at")
            try:
                expiry = date.fromisoformat(expires_at[:10])
            except ValueError as exc:
                raise ContractError(f"asset {asset_id} has invalid expires_at") from exc
            if expiry < date.today():
                raise ContractError(f"asset {asset_id} receipt is expired")
        for code in codes:
            material_assets[code].add(asset_id)
    return assets, material_assets


def parse_json_text(value: Any, field: str) -> Any:
    if not isinstance(value, str):
        raise ContractError(f"style binding {field} is not JSON text")
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ContractError(f"style binding {field} is invalid JSON") from exc


def load_published_style_binding(
    db_path: Path,
    draft_binding_id: str,
    *,
    category: str,
    job: str,
    carrier: str,
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Reconcile one published binding and its aesthetic rules from SQLite."""

    if not draft_binding_id.strip():
        raise ContractError("draft_binding_id is required")
    try:
        resolved_db = db_path.resolve(strict=True)
    except OSError as exc:
        raise ContractError("style library does not exist") from exc
    if not resolved_db.is_file():
        raise ContractError("style library is not a regular SQLite file")
    uri = f"file:{quote(str(resolved_db), safe='/')}?mode=ro"
    try:
        con = sqlite3.connect(uri, uri=True)
        con.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        raise ContractError("style library cannot be opened read-only") from exc
    try:
        if con.execute("PRAGMA user_version").fetchone()[0] != 2:
            raise ContractError("style library schema_version mismatch")
        required_tables = {
            "style_archetypes",
            "archetype_publications",
            "archetype_rules",
            "archetype_rule_publications",
            "draft_style_bindings",
            "draft_binding_publications",
        }
        tables = {
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_schema WHERE type='table'"
            ).fetchall()
        }
        if required_tables - tables:
            raise ContractError("style library is missing publication tables")
        con.execute("BEGIN")
        row = con.execute(
            """
            SELECT
                binding.draft_binding_id,
                binding.draft_id,
                binding.binding_source,
                binding.archetype_id,
                binding.binding_role,
                binding.archetype_version,
                binding.archetype_snapshot_sha256,
                binding.starter_pack_id,
                binding.starter_pack_version,
                binding.starter_pack_sha256,
                binding.starter_prompt_id,
                binding.selected_rule_ids,
                binding.reference_library_post_ids,
                binding.counterexample_library_post_ids,
                binding.material_plan_json,
                binding.intentional_deviations_json,
                binding.anti_patterns_checked_json,
                binding.review_status,
                publication.binding_sha256,
                publication.published_at AS binding_published_at,
                archetype.name AS archetype_name,
                archetype.category_scope,
                archetype.carrier AS archetype_carrier,
                archetype.primary_job_scope,
                archetype.audience_state,
                archetype.description AS archetype_description,
                archetype.production_cost,
                archetype.confidence,
                archetype.status AS archetype_status,
                archetype.current_version,
                archetype.snapshot_sha256,
                archetype.taxonomy_version,
                archetype_publication.published_at AS archetype_published_at
            FROM draft_style_bindings AS binding
            JOIN draft_binding_publications AS publication
              ON publication.draft_binding_id = binding.draft_binding_id
             AND publication.draft_id = binding.draft_id
            JOIN style_archetypes AS archetype
              ON archetype.archetype_id = binding.archetype_id
             AND archetype.current_version = binding.archetype_version
             AND archetype.snapshot_sha256 = binding.archetype_snapshot_sha256
            JOIN archetype_publications AS archetype_publication
              ON archetype_publication.archetype_id = archetype.archetype_id
             AND archetype_publication.archetype_version = archetype.current_version
             AND archetype_publication.archetype_snapshot_sha256 = archetype.snapshot_sha256
            WHERE binding.draft_binding_id = ?
            """,
            (draft_binding_id,),
        ).fetchone()
        if row is None:
            raise ContractError("published draft binding not found")
        if row["binding_source"] != "library":
            raise ContractError(
                "starter-pack binding cannot supply exact category aesthetic rules"
            )
        if row["binding_role"] != "primary" or row["review_status"] != "PASS":
            raise ContractError("style binding is not a reviewed primary binding")
        if row["archetype_status"] not in {"supported", "reusable"}:
            raise ContractError("style binding archetype is not supported/reusable")
        exact_values = {
            "category": (row["category_scope"], category),
            "primary_job": (row["primary_job_scope"], job),
            "carrier": (row["archetype_carrier"], carrier),
        }
        mismatches = [
            field
            for field, (actual, expected) in exact_values.items()
            if actual != expected
        ]
        if mismatches:
            raise ContractError(
                "style binding does not exactly match " + "/".join(mismatches)
            )

        expected_archetype_hash = canonical_row_sha256(
            row["archetype_id"],
            row["archetype_name"],
            row["category_scope"],
            row["archetype_carrier"],
            row["primary_job_scope"],
            row["audience_state"],
            row["archetype_description"],
            row["production_cost"],
            row["confidence"],
            row["archetype_status"],
            row["current_version"],
            row["taxonomy_version"],
        )
        if expected_archetype_hash != row["snapshot_sha256"]:
            raise ContractError("archetype publication hash mismatch")

        json_fields = (
            "selected_rule_ids",
            "reference_library_post_ids",
            "counterexample_library_post_ids",
            "material_plan_json",
            "intentional_deviations_json",
            "anti_patterns_checked_json",
        )
        parsed = {field: parse_json_text(row[field], field) for field in json_fields}
        selected_rule_ids = parsed["selected_rule_ids"]
        if (
            not isinstance(selected_rule_ids, list)
            or not selected_rule_ids
            or any(not isinstance(rule_id, str) for rule_id in selected_rule_ids)
            or len(set(selected_rule_ids)) != len(selected_rule_ids)
        ):
            raise ContractError("style binding selected_rule_ids are invalid")
        expected_binding_hash = canonical_row_sha256(
            row["draft_binding_id"],
            row["draft_id"],
            row["binding_source"],
            row["archetype_id"],
            row["archetype_version"],
            row["archetype_snapshot_sha256"],
            row["starter_pack_id"],
            row["starter_pack_version"],
            row["starter_pack_sha256"],
            row["starter_prompt_id"],
            canonical_json(parsed["selected_rule_ids"]),
            canonical_json(parsed["reference_library_post_ids"]),
            canonical_json(parsed["counterexample_library_post_ids"]),
            canonical_json(parsed["material_plan_json"]),
            canonical_json(parsed["intentional_deviations_json"]),
            canonical_json(parsed["anti_patterns_checked_json"]),
            row["review_status"],
        )
        if expected_binding_hash != row["binding_sha256"]:
            raise ContractError("binding publication hash mismatch")

        placeholders = ",".join("?" for _ in selected_rule_ids)
        rule_rows = con.execute(
            f"""
            SELECT
                rule.rule_id,
                rule.archetype_id,
                rule.archetype_version,
                rule.rule_type,
                rule.rule_payload_json,
                rule.applicability_scope,
                rule.status,
                publication.archetype_snapshot_sha256,
                publication.rule_sha256,
                publication.evidence_set_sha256,
                publication.evidence_count,
                publication.published_at
            FROM archetype_rules AS rule
            JOIN archetype_rule_publications AS publication
              ON publication.rule_id = rule.rule_id
             AND publication.archetype_id = rule.archetype_id
             AND publication.archetype_version = rule.archetype_version
            WHERE rule.rule_id IN ({placeholders})
            """,
            tuple(selected_rule_ids),
        ).fetchall()
        rules_by_id = {rule["rule_id"]: rule for rule in rule_rows}
        if set(rules_by_id) != set(selected_rule_ids):
            raise ContractError("style binding references unpublished rule")
        aesthetic_fields = contract["aesthetic_fields_required"]
        aesthetic_contract: dict[str, list[dict[str, Any]]] = {
            field: [] for field in aesthetic_fields
        }
        rule_receipts = []
        for rule_id in selected_rule_ids:
            rule = rules_by_id[rule_id]
            if (
                rule["archetype_id"] != row["archetype_id"]
                or rule["archetype_version"] != row["archetype_version"]
                or rule["archetype_snapshot_sha256"]
                != row["archetype_snapshot_sha256"]
                or rule["status"] != "active"
            ):
                raise ContractError("published rule does not match binding snapshot")
            payload = parse_json_text(rule["rule_payload_json"], "rule_payload_json")
            if not isinstance(payload, dict):
                raise ContractError("published rule payload must be an object")
            expected_rule_hash = canonical_row_sha256(
                rule["rule_id"],
                rule["archetype_id"],
                rule["archetype_version"],
                rule["rule_type"],
                canonical_json(payload),
                rule["applicability_scope"],
                rule["status"],
            )
            if expected_rule_hash != rule["rule_sha256"]:
                raise ContractError(f"published rule hash mismatch: {rule_id}")
            for field in aesthetic_fields:
                if field in payload and payload[field] not in (None, "", [], {}):
                    aesthetic_contract[field].append(
                        {"rule_id": rule_id, "value": payload[field]}
                    )
            rule_receipts.append(
                {
                    "rule_id": rule_id,
                    "rule_type": rule["rule_type"],
                    "rule_sha256": rule["rule_sha256"],
                    "evidence_set_sha256": rule["evidence_set_sha256"],
                    "evidence_count": rule["evidence_count"],
                    "published_at": rule["published_at"],
                }
            )
        missing_aesthetics = [
            field for field, receipts in aesthetic_contract.items() if not receipts
        ]
        if missing_aesthetics:
            raise ContractError(
                "published style rules missing aesthetic fields: "
                + ", ".join(missing_aesthetics)
            )
        return {
            "binding_id": row["draft_binding_id"],
            "binding_sha256": row["binding_sha256"],
            "status": "published",
            "category": row["category_scope"],
            "primary_job": row["primary_job_scope"],
            "carrier": row["archetype_carrier"],
            "snapshot_id": row["archetype_snapshot_sha256"],
            "style_rule_ids": selected_rule_ids,
            "aesthetic_contract": aesthetic_contract,
            "rule_publication_receipts": rule_receipts,
            "binding_published_at": row["binding_published_at"],
            "archetype_published_at": row["archetype_published_at"],
        }
    except sqlite3.Error as exc:
        raise ContractError(f"style library reconciliation failed: {exc}") from exc
    finally:
        con.close()


def card_gap(
    card: dict[str, Any], carrier: str, material_assets: dict[str, set[str]],
    active_contraindications: set[str]
) -> dict[str, Any]:
    required = set(card["suitable"]["required_materials"])
    available = {code for code, asset_ids in material_assets.items() if asset_ids}
    missing = sorted(required - available)
    count_gaps = []
    for gate in card["material_count_gates"][carrier]:
        actual = len(material_assets.get(gate["material_code"], set()))
        if actual < gate["min_distinct_asset_refs"]:
            count_gaps.append(
                {
                    "material_code": gate["material_code"],
                    "required": gate["min_distinct_asset_refs"],
                    "actual": actual,
                    "reason": gate["reason"],
                }
            )
    contraindications = sorted(
        set(card["suitable"]["contraindications"]) & active_contraindications
    )
    return {
        "card_id": card["card_id"],
        "name": card["name"],
        "missing_materials": missing,
        "material_count_gaps": count_gaps,
        "active_contraindications": contraindications,
        "nearest_alternative": card["nearest_alternative"],
    }


def selected_card(
    card: dict[str, Any], carrier: str, material_assets: dict[str, set[str]],
    binding: dict[str, Any] | None, mode: str
) -> dict[str, Any]:
    material_receipts = {
        code: sorted(material_assets[code])
        for code in card["suitable"]["required_materials"]
    }
    aesthetic_control = (
        {
            "source": "published_style_binding",
            "binding_id": binding["binding_id"],
            "binding_sha256": binding["binding_sha256"],
            "category": binding["category"],
            "primary_job": binding["primary_job"],
            "carrier": binding["carrier"],
            "snapshot_id": binding["snapshot_id"],
            "style_rule_ids": binding["style_rule_ids"],
            "aesthetic_contract": binding["aesthetic_contract"],
            "rule_publication_receipts": binding["rule_publication_receipts"],
        }
        if binding
        else {
            "source": "unbound_exploration",
            "binding_id": None,
            "aesthetic_contract": None,
        }
    )
    return {
        "card_id": card["card_id"],
        "name": card["name"],
        "maturity": card["maturity"],
        "selection_eligibility": card["selection_eligibility"],
        "performance_evidence_status": card["performance_evidence_status"],
        "performance_evidence_scope": card["performance_evidence_scope"],
        "query_fit": {"primary_job": "exact", "carrier": "exact"},
        "material_receipts": material_receipts,
        "attention_path": card["attention_path"],
        "cover_job": card["cover"]["job"],
        "carrier_role_plan": card["carrier_role_plans"][carrier],
        "image_caption_division": card["image_caption_division"],
        "prompt_variables": card["prompt_variables"],
        "prompt_template": card["prompt_template"],
        "negative_prompt": card["negative_prompt"],
        "anti_ppt_check": card["anti_ppt_check"],
        "failure_conditions": card["failure_conditions"],
        "rights": card["rights"],
        "aesthetic_control": aesthetic_control,
        "direction_card_controls": [
            "attention_path",
            "proof_order",
            "carrier_role_plan",
            "image_caption_division",
            "truth_and_rights_boundaries",
        ],
        "direction_card_controls_aesthetics": False,
        "sole_direction_allowed": mode == "exploration",
        "output_ceiling": (
            "prototype_only" if mode == "exploration" else "rendered_needs_review"
        ),
    }


def select(
    library: dict[str, Any],
    category: str,
    job: str,
    carrier: str,
    manifest: dict[str, Any] | None,
    manifest_root: Path | None,
    style_library: Path | None,
    draft_binding_id: str | None,
    active_contraindications: set[str],
    mode: str,
    limit: int,
) -> tuple[dict[str, Any], int]:
    invalid = []
    if not category.strip():
        invalid.append("category=<empty>")
    if job not in library["primary_job_taxonomy"]:
        invalid.append(f"primary_job={job}")
    if carrier not in library["carrier_taxonomy"]:
        invalid.append(f"carrier={carrier}")
    unknown_contraindications = active_contraindications - set(
        library["contraindication_taxonomy"]
    )
    invalid.extend(
        f"contraindication={value}" for value in sorted(unknown_contraindications)
    )
    if invalid:
        return {
            "status": "invalid_query",
            "message": "invalid taxonomy value(s): " + ", ".join(invalid),
            "matches": [],
        }, 2

    query = {
        "category": category,
        "primary_job": job,
        "carrier": carrier,
        "mode": mode,
        "active_contraindications": sorted(active_contraindications),
    }
    if manifest is None or manifest_root is None:
        return {
            "status": "prototype_gap",
            "message": "asset_manifest_refs are required; no direction is inferred.",
            "query": query,
            "missing_requirements": ["asset_manifest_refs"],
            "matches": [],
        }, 2
    try:
        _, material_assets = validate_asset_manifest(
            manifest, library["asset_manifest_contract"], manifest_root
        )
    except ContractError as exc:
        return {
            "status": "invalid_asset_manifest",
            "message": str(exc),
            "query": query,
            "matches": [],
        }, 2

    structural = [
        card
        for card in library["cards"]
        if job in card["suitable"]["primary_jobs"]
        and carrier in card["suitable"]["carriers"]
    ]
    if not structural:
        alternatives = [
            {
                "card_id": card["card_id"],
                "name": card["name"],
                "matching_jobs": sorted(set(card["suitable"]["primary_jobs"]) & {job}),
                "matching_carriers": sorted(set(card["suitable"]["carriers"]) & {carrier}),
                "nearest_alternative": card["nearest_alternative"],
            }
            for card in library["cards"]
            if job in card["suitable"]["primary_jobs"]
            or carrier in card["suitable"]["carriers"]
        ]
        return {
            "status": "no_eligible_card",
            "message": "No card exactly matches both primary_job and carrier.",
            "query": query,
            "prototype_gaps": alternatives,
            "matches": [],
        }, 2

    gaps = [
        card_gap(card, carrier, material_assets, active_contraindications)
        for card in structural
    ]
    eligible = [
        card
        for card, gap in zip(structural, gaps)
        if not gap["missing_materials"]
        and not gap["material_count_gaps"]
        and not gap["active_contraindications"]
    ]
    if not eligible:
        return {
            "status": "no_eligible_card",
            "message": "Exact candidates exist, but materials/count gates/contraindications fail.",
            "query": query,
            "prototype_gaps": gaps,
            "matches": [],
        }, 2

    if mode == "production":
        if style_library is None or not draft_binding_id:
            return {
                "status": "prototype_gap",
                "message": "Production aesthetics require a reconciled SQLite publication.",
                "query": query,
                "missing_requirements": [
                    "published_style_binding",
                    "style_library_sqlite",
                    "published_draft_binding_id",
                ],
                "prototype_candidates": [card["card_id"] for card in eligible],
                "matches": [],
            }, 2
        try:
            validated_binding = load_published_style_binding(
                style_library,
                draft_binding_id,
                category=category,
                job=job,
                carrier=carrier,
                contract=library["style_binding_contract"],
            )
        except ContractError as exc:
            return {
                "status": "prototype_gap",
                "message": str(exc),
                "query": query,
                "missing_requirements": ["exact_published_style_binding"],
                "prototype_candidates": [card["card_id"] for card in eligible],
                "matches": [],
            }, 2
        non_series = [
            card
            for card in eligible
            if card["selection_eligibility"] != "series_modifier_only"
        ]
        if not non_series:
            return {
                "status": "prototype_gap",
                "message": "A series modifier cannot be the sole production direction.",
                "query": query,
                "missing_requirements": ["base_direction_card"],
                "prototype_candidates": [card["card_id"] for card in eligible],
                "matches": [],
            }, 2
        ordered = non_series + [
            card for card in eligible if card not in non_series
        ]
        matches = [
            selected_card(card, carrier, material_assets, validated_binding, mode)
            for card in ordered[:limit]
        ]
        return {
            "status": "matched",
            "message": (
                "Direction cards control evidence/attention only; "
                "binding controls aesthetics."
            ),
            "query": query,
            "matches": matches,
        }, 0

    matches = [
        selected_card(card, carrier, material_assets, None, mode)
        for card in eligible[:limit]
    ]
    return {
        "status": "matched_exploration",
        "message": (
            "Explicit exploration may use one candidate direction, but it remains "
            "prototype_only and cannot become ready."
        ),
        "query": query,
        "matches": matches,
    }, 0


def select_from_paths(
    *,
    category: str,
    job: str,
    carrier: str,
    asset_manifest_path: Path | None,
    style_library_path: Path | None,
    draft_binding_id: str | None,
    active_contraindications: set[str] | None = None,
    mode: str = "production",
    limit: int = 2,
    library_path: Path = DEFAULT_LIBRARY,
) -> tuple[dict[str, Any], int]:
    """Callable fail-closed API; derive the asset root from the manifest path."""

    library = load_library(library_path)
    manifest = (
        load_json(asset_manifest_path, "asset manifest")
        if asset_manifest_path
        else None
    )
    manifest_root = asset_manifest_path.resolve().parent if asset_manifest_path else None
    return select(
        library=library,
        category=category,
        job=job,
        carrier=carrier,
        manifest=manifest,
        manifest_root=manifest_root,
        style_library=style_library_path,
        draft_binding_id=draft_binding_id,
        active_contraindications=active_contraindications or set(),
        mode=mode,
        limit=limit,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select Xiaohongshu visual evidence/attention skeletons."
    )
    parser.add_argument("--category", required=True, help="Exact category scope")
    parser.add_argument("--job", required=True, help="Exact primary_job taxonomy value")
    parser.add_argument("--carrier", required=True, help="Exact carrier taxonomy value")
    parser.add_argument(
        "--asset-manifest", type=Path, help="JSON object containing asset_manifest_refs"
    )
    parser.add_argument(
        "--style-library", type=Path, help="Version-2 style-library SQLite database"
    )
    parser.add_argument(
        "--draft-binding-id", help="Published draft_style_bindings identifier"
    )
    parser.add_argument(
        "--contraindication", action="append", default=[],
        help="Active contraindication code; repeat as needed",
    )
    parser.add_argument(
        "--mode", choices=("production", "exploration"), default="production"
    )
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY)
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.limit < 1:
        emit(
            {"status": "invalid_query", "message": "limit must be >= 1", "matches": []},
            args.json,
        )
        return 2
    try:
        payload, code = select_from_paths(
            category=args.category,
            job=args.job,
            carrier=args.carrier,
            asset_manifest_path=args.asset_manifest,
            style_library_path=args.style_library,
            draft_binding_id=args.draft_binding_id,
            active_contraindications=set(args.contraindication),
            mode=args.mode,
            limit=args.limit,
            library_path=args.library,
        )
    except ContractError as exc:
        emit(
            {"status": "invalid_contract", "message": str(exc), "matches": []},
            args.json,
        )
        return 2
    emit(payload, args.json)
    return code


if __name__ == "__main__":
    sys.exit(main())
