#!/usr/bin/env python3
"""Initialize and access the local multimodal style library."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import date
from statistics import median
from pathlib import Path
from typing import Sequence
from urllib.parse import quote


SCHEMA_VERSION = 2
SCHEMA_REVISION = "2.2-qualified-promotion"
ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
LEGACY_SCHEMA_PATH = ASSETS_DIR / "style-library-schema.sql"
LEGACY_TAXONOMY_PATH = ASSETS_DIR / "style-taxonomy-v1.json"
SCHEMA_PATH = ASSETS_DIR / "style-library-schema-v2.sql"
TAXONOMY_PATH = ASSETS_DIR / "style-taxonomy-v2.json"

TAXONOMY_KEYS = frozenset(
    {
        "taxonomy_version",
        "primary_job",
        "traffic_stage",
        "material_code",
        "production_constraint_code",
        "contraindication_code",
        "motive_code",
        "distribution_mode",
        "model_lifecycle_stage",
        "reviewer_independence_status",
        "asset_origin_code",
        "rights_basis_code",
        "authorization_status",
        "delivery_surface",
        "production_gate_status",
        "account_capability_code",
        "visual_feedback_reason_code",
        "carrier",
        "slide_role",
        "composition",
        "dominant_material",
        "background_type",
        "subject_presence",
        "layout_structure",
        "text_density",
        "hierarchy_levels",
        "alignment",
        "spacing_pattern",
        "font_feel",
        "decoration_types",
        "annotation_style",
        "imperfection_signals",
        "image_text_relationship",
        "text_surface",
        "point_of_view",
        "audience_address",
        "register",
        "sentence_length_pattern",
        "line_break_pattern",
        "punctuation_pattern",
        "emoji_pattern",
        "hook_move",
        "narrative_moves",
        "evidence_move",
        "payoff_move",
        "cta_move",
        "image_caption_division",
        "rule_type",
    }
)

OPEN_ENDED_TAXONOMY_KEYS = frozenset(
    {
        "carrier",
        "composition",
        "dominant_material",
        "background_type",
        "subject_presence",
        "layout_structure",
        "alignment",
        "spacing_pattern",
        "font_feel",
        "decoration_types",
        "annotation_style",
        "imperfection_signals",
        "image_text_relationship",
        "text_surface",
        "point_of_view",
        "audience_address",
        "register",
        "sentence_length_pattern",
        "line_break_pattern",
        "punctuation_pattern",
        "emoji_pattern",
        "hook_move",
        "narrative_moves",
        "evidence_move",
        "payoff_move",
        "cta_move",
        "image_caption_division",
        "material_code",
        "production_constraint_code",
        "contraindication_code",
        "motive_code",
        "distribution_mode",
        "asset_origin_code",
        "rights_basis_code",
        "delivery_surface",
        "account_capability_code",
        "visual_feedback_reason_code",
    }
)

REQUIRED_PRIMARY_JOBS = frozenset(
    {
        "feed_stop",
        "search_answer",
        "explain",
        "trust_build",
        "decision_support",
        "relationship_build",
        "conversion",
        "authority_statement",
    }
)

TRAFFIC_STAGES = frozenset(
    {
        "feed_stop",
        "read_through",
        "save_share",
        "comment_cocreation",
        "profile_follow",
    }
)

LEDGER_TOP_LEVEL_KEYS = frozenset(
    {
        "observation_id", "capture_date", "review_by", "surface",
        "query_context", "query_fingerprint", "source_url", "platform_note_id",
        "note_id_status", "library_post_id", "library_account_id",
        "taxonomy_version", "carrier", "primary_job", "material_codes",
        "production_constraint_codes", "contraindication_codes", "mechanism",
        "page_observations", "performance_recomputability", "derived_tier",
        "baseline_multiple", "performance_receipt", "visible_metrics",
        "asset_sha256s", "visual_observation_ids", "copy_observation_ids",
        "evidence_role", "counterexample_or_boundary_ids", "starter_eligible",
        "qualification_status", "limitations", "taxonomy_notes",
    }
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_row_sha256_v2(*values: object) -> str:
    """Hash one ordered row; used by publication triggers and finalizers."""

    normalized = [float(value) if isinstance(value, float) else value for value in values]
    return _sha256_text(_canonical_json(normalized))


def _canonicalize_json_text_v2(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("canonical_json_requires_text")
    return _canonical_json(json.loads(value))


def _performance_computation_sha256_v2(
    post_observation_id: object,
    baseline_snapshot_id: object,
    baseline_snapshot_sha256: object,
    definition_sha256: object,
    metric_name: object,
    target_metric_value: object,
    median_value: object,
    multiple: object,
    performance_tier: object,
) -> str:
    """Hash the exact recomputable inputs used by a tier publication."""

    computation = {
        "post_observation_id": str(post_observation_id),
        "baseline_snapshot_id": str(baseline_snapshot_id),
        "baseline_snapshot_sha256": str(baseline_snapshot_sha256),
        "definition_sha256": str(definition_sha256),
        "metric_name": str(metric_name),
        "target_metric_value": float(target_metric_value),
        "median_value": float(median_value),
        "multiple": float(multiple),
        "performance_tier": str(performance_tier),
    }
    return _sha256_text(_canonical_json(computation))


class StyleLibraryError(RuntimeError):
    """Raised when the local style library contract cannot be satisfied."""


class _CanonicalSha256AggregateV2:
    """Hash an ordered sequence using the documented compact JSON encoding."""

    def __init__(self) -> None:
        self._values: list[object] = []

    def step(self, value: object) -> None:
        self._values.append(value)

    def finalize(self) -> str:
        encoded = json.dumps(
            self._values,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class _MedianAggregateV2:
    """Return the numeric median while ignoring unavailable (NULL) values."""

    def __init__(self) -> None:
        self._values: list[float] = []

    def step(self, value: object) -> None:
        if value is not None:
            self._values.append(float(value))

    def finalize(self) -> float | None:
        if not self._values:
            return None
        return float(median(self._values))


def _configure_connection(con: sqlite3.Connection) -> None:
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA recursive_triggers = ON")
    con.create_aggregate(
        "canonical_sha256_agg_v2", 1, _CanonicalSha256AggregateV2
    )
    con.create_aggregate("median_agg_v2", 1, _MedianAggregateV2)
    con.create_function(
        "performance_computation_sha256_v2",
        9,
        _performance_computation_sha256_v2,
        deterministic=True,
    )
    con.create_function(
        "canonical_row_sha256_v2",
        -1,
        _canonical_row_sha256_v2,
        deterministic=True,
    )
    con.create_function(
        "canonical_json_v2",
        1,
        _canonicalize_json_text_v2,
        deterministic=True,
    )


def connect_db(db_path: Path) -> sqlite3.Connection:
    """Open a configured v2 connection; legacy databases fail closed."""

    con = sqlite3.connect(Path(db_path))
    _configure_connection(con)
    try:
        version = con.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.Error as exc:
        con.close()
        raise StyleLibraryError("schema_preflight_failed") from exc
    if version == 1:
        con.close()
        raise StyleLibraryError("schema_upgrade_required")
    if version != SCHEMA_VERSION:
        con.close()
        raise StyleLibraryError("schema_version_mismatch")
    try:
        revision = con.execute(
            "SELECT schema_revision FROM style_schema_metadata WHERE singleton=1"
        ).fetchone()
    except sqlite3.Error as exc:
        con.close()
        raise StyleLibraryError("schema_v2_revision_mismatch") from exc
    if revision is None or revision[0] != SCHEMA_REVISION:
        con.close()
        raise StyleLibraryError("schema_v2_revision_mismatch")
    if con.execute("PRAGMA foreign_key_check").fetchone() is not None:
        con.close()
        raise StyleLibraryError("schema_foreign_key_violation")
    return con


def _normalized_schema_objects(
    con: sqlite3.Connection,
) -> dict[str, tuple[str, str, str]]:
    objects: dict[str, tuple[str, str, str]] = {}
    rows = con.execute(
        """
        SELECT type, name, tbl_name, sql
        FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%'
          AND type IN ('table', 'index', 'trigger', 'view')
        """
    )
    for object_type, name, table_name, sql in rows:
        normalized_sql = " ".join((sql or "").split())
        objects[name] = (object_type, table_name, normalized_sql)
    return objects


def _execute_sql_script(con: sqlite3.Connection, schema_sql: str) -> None:
    """Execute complete SQLite statements without executescript auto-commits."""

    pending = ""
    for line in schema_sql.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            statement = pending.strip()
            pending = ""
            if statement:
                con.execute(statement)
    if pending.strip():
        raise StyleLibraryError("schema_sql_incomplete")


def _validate_schema(
    con: sqlite3.Connection, schema_sql: str, error_code: str
) -> None:
    expected = sqlite3.connect(":memory:")
    _configure_connection(expected)
    try:
        _execute_sql_script(expected, schema_sql)
        expected_objects = _normalized_schema_objects(expected)
    finally:
        expected.close()

    actual_objects = _normalized_schema_objects(con)
    if actual_objects != expected_objects:
        raise StyleLibraryError(error_code)


def _open_read_only(db_path: Path) -> sqlite3.Connection:
    uri_path = quote(str(db_path.resolve()), safe="/")
    con = sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True)
    _configure_connection(con)
    return con


def _preflight_existing_database(db_path: Path) -> int:
    """Inspect an existing file read-only before any initialization write."""

    try:
        con = _open_read_only(db_path)
        try:
            version = con.execute("PRAGMA user_version").fetchone()[0]
            integrity = con.execute("PRAGMA quick_check").fetchone()[0]
            if integrity != "ok":
                raise StyleLibraryError("schema_preflight_failed")
            objects = _normalized_schema_objects(con)
            if version == 0:
                if objects:
                    raise StyleLibraryError("unversioned_database_not_empty")
                return 0
            if version == 1:
                legacy_sql = LEGACY_SCHEMA_PATH.read_text(encoding="utf-8")
                _validate_schema(con, legacy_sql, "schema_v1_invalid")
                raise StyleLibraryError("schema_upgrade_required")
            if version == SCHEMA_VERSION:
                try:
                    revision = con.execute(
                        "SELECT schema_revision FROM style_schema_metadata "
                        "WHERE singleton=1"
                    ).fetchone()
                except sqlite3.Error as exc:
                    raise StyleLibraryError(
                        "schema_v2_revision_mismatch"
                    ) from exc
                if revision is None or revision[0] != SCHEMA_REVISION:
                    raise StyleLibraryError("schema_v2_revision_mismatch")
                schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
                _validate_schema(con, schema_sql, "schema_v2_revision_mismatch")
                if con.execute("PRAGMA foreign_key_check").fetchone() is not None:
                    raise StyleLibraryError("schema_foreign_key_violation")
                return version
            if version > SCHEMA_VERSION:
                raise StyleLibraryError("schema_version_unsupported")
            raise StyleLibraryError("schema_version_unsupported")
        finally:
            con.close()
    except StyleLibraryError:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise StyleLibraryError("schema_preflight_failed") from exc


def init_db(db_path: Path) -> dict[str, object]:
    """Create v2 only in a genuinely empty v0 file, after read-only preflight."""

    # Fail before touching the database when the active vocabulary is absent,
    # malformed, or not exactly v2.
    load_taxonomy()
    db_path = Path(db_path)
    con: sqlite3.Connection | None = None
    existed_before = db_path.exists()
    before_bytes = db_path.read_bytes() if existed_before and db_path.is_file() else None
    write_started = False
    try:
        if existed_before:
            version = _preflight_existing_database(db_path)
            if version == SCHEMA_VERSION:
                return {
                    "status": "ok",
                    "schema_version": version,
                    "schema_revision": SCHEMA_REVISION,
                    "db": str(db_path),
                }

        db_path.parent.mkdir(parents=True, exist_ok=True)
        write_started = True
        con = sqlite3.connect(db_path)
        _configure_connection(con)
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        con.execute("BEGIN IMMEDIATE")
        _execute_sql_script(con, schema_sql)
        con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        con.commit()
        version = con.execute("PRAGMA user_version").fetchone()[0]
        _validate_schema(con, schema_sql, "schema_v2_invalid")
        if con.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise StyleLibraryError("schema_v2_invalid")
    except StyleLibraryError:
        if con is not None and con.in_transaction:
            con.rollback()
        if con is not None:
            con.close()
            con = None
        if write_started and existed_before and before_bytes is not None:
            db_path.write_bytes(before_bytes)
        elif write_started and not existed_before:
            db_path.unlink(missing_ok=True)
        raise
    except (OSError, sqlite3.Error) as exc:
        if con is not None and con.in_transaction:
            con.rollback()
        if con is not None:
            con.close()
            con = None
        if write_started and existed_before and before_bytes is not None:
            db_path.write_bytes(before_bytes)
        elif write_started and not existed_before:
            db_path.unlink(missing_ok=True)
        raise StyleLibraryError("schema_initialization_failed") from exc
    finally:
        if con is not None:
            con.close()

    if version != SCHEMA_VERSION:
        if existed_before and before_bytes is not None:
            db_path.write_bytes(before_bytes)
        elif not existed_before:
            db_path.unlink(missing_ok=True)
        raise StyleLibraryError("schema_version_mismatch")

    return {
        "status": "ok",
        "schema_version": version,
        "schema_revision": SCHEMA_REVISION,
        "db": str(db_path),
    }


def load_taxonomy() -> dict[str, object]:
    """Load the exact v2 controlled vocabulary contract."""

    try:
        data = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StyleLibraryError("taxonomy_load_failed") from exc

    if not isinstance(data, dict):
        raise StyleLibraryError("taxonomy_invalid")
    if set(data) != TAXONOMY_KEYS:
        raise StyleLibraryError("taxonomy_invalid")
    version = data.get("taxonomy_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        raise StyleLibraryError("taxonomy_version_mismatch")

    for key in TAXONOMY_KEYS - {"taxonomy_version"}:
        values = data[key]
        if not isinstance(values, list) or not values:
            raise StyleLibraryError("taxonomy_invalid")
        if any(type(value) is not str or not value.strip() for value in values):
            raise StyleLibraryError("taxonomy_invalid")
        if len(values) != len(set(values)):
            raise StyleLibraryError("taxonomy_invalid")

    for key in OPEN_ENDED_TAXONOMY_KEYS:
        values = data[key]
        if "unknown" not in values or "other" not in values:
            raise StyleLibraryError("taxonomy_invalid")
    if "other" not in data["slide_role"]:
        raise StyleLibraryError("taxonomy_invalid")
    for key in ("text_density", "hierarchy_levels"):
        if "unknown" not in data[key]:
            raise StyleLibraryError("taxonomy_invalid")
    if not REQUIRED_PRIMARY_JOBS.issubset(data["primary_job"]):
        raise StyleLibraryError("taxonomy_invalid")
    if set(data["traffic_stage"]) != TRAFFIC_STAGES:
        raise StyleLibraryError("taxonomy_invalid")
    return data


def _table_count(con: sqlite3.Connection, table: str) -> int:
    exists = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if exists is None:
        return 0
    return int(con.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])


def _published_rule_readiness(
    con: sqlite3.Connection, taxonomy: dict[str, object]
) -> tuple[int, dict[str, int]]:
    """Count only currently usable, independently qualified rule bundles."""

    counts = {stage: 0 for stage in sorted(TRAFFIC_STAGES)}
    qualified = 0
    rows = con.execute(
        """
        SELECT archetype.*
        FROM style_archetypes AS archetype
        JOIN qualified_style_publications AS qualification
          ON qualification.archetype_id=archetype.archetype_id
         AND qualification.archetype_version=archetype.current_version
         AND qualification.archetype_snapshot_sha256=archetype.snapshot_sha256
        WHERE archetype.status IN ('supported','reusable')
        ORDER BY archetype.archetype_id
        """
    ).fetchall()
    for archetype in rows:
        try:
            bundle = _load_current_qualified_bundle(con, archetype, taxonomy)
        except (json.JSONDecodeError, StyleLibraryError):
            continue
        for rule in bundle["rules"]:
            qualified += 1
            stage = rule["payload"]["traffic_stage"]
            if stage in counts:
                counts[str(stage)] += 1
    return qualified, counts


def status_db(db_path: Path) -> dict[str, object]:
    """Report what exists without upgrading unverified observations to evidence."""

    taxonomy = load_taxonomy()
    con = connect_db(db_path)
    try:
        ledger_n = _table_count(con, "sanitized_style_ledger_entries")
        qualified_n, stage_counts = _published_rule_readiness(con, taxonomy)
        counts = {
            "sanitized_ledger_entries": ledger_n,
            "qualified_style_rules": qualified_n,
            "published_baselines": _table_count(
                con, "baseline_snapshot_publications"
            ),
            "published_performance_receipts": _table_count(
                con, "post_performance_publications"
            ),
            "published_archetype_snapshots": _table_count(
                con, "archetype_publications"
            ),
            "published_rule_receipts": _table_count(
                con, "archetype_rule_publications"
            ),
            "draft_bindings": _table_count(con, "draft_style_bindings"),
            "published_binding_receipts": _table_count(
                con, "draft_binding_publications"
            ),
            "style_assets": _table_count(con, "style_assets"),
        }
    finally:
        con.close()
    return {
        "status": "ok",
        "schema_version": SCHEMA_VERSION,
        "schema_revision": SCHEMA_REVISION,
        "taxonomy_version": taxonomy["taxonomy_version"],
        "counts": counts,
        "traffic_stage_qualified_counts": stage_counts,
        "release_readiness": {
            "state": "ready_to_bind" if qualified_n else "needs_style_research",
            "reason_codes": [] if qualified_n else [
                    "no_published_qualified_rule",
                    "sanitized_ledger_is_candidate_only",
                ],
            "checkpoint": None if qualified_n else (
                "publish a reviewed exact-scope rule bundle with hashed pages, "
                "typed copy/visual evidence, and counterevidence"
            ),
            "performance_claim_boundary": (
                "qualified_style_rules is an evidence-bound style count, not "
                "a count of first-party traffic-validated rules"
            ),
        },
    }


def _require_code_list(
    record: dict[str, object], key: str, allowed: set[str] | frozenset[str]
) -> list[str]:
    values = record.get(key)
    if (
        not isinstance(values, list)
        or not values
        or any(type(item) is not str or item not in allowed for item in values)
        or len(values) != len(set(values))
    ):
        raise StyleLibraryError("ledger_taxonomy_invalid")
    return sorted(values)


def _validate_ledger_record(
    record: object, taxonomy: dict[str, object]
) -> dict[str, object]:
    if not isinstance(record, dict) or not set(record).issubset(LEDGER_TOP_LEVEL_KEYS):
        raise StyleLibraryError("ledger_record_invalid")
    required = LEDGER_TOP_LEVEL_KEYS - {"taxonomy_notes"}
    if not required.issubset(record):
        raise StyleLibraryError("ledger_record_invalid")
    observation_id = record.get("observation_id")
    if (
        type(observation_id) is not str
        or len(observation_id) != 9
        or not observation_id.startswith("O-XHS-")
        or not observation_id[6:].isdigit()
        or not 1 <= int(observation_id[6:]) <= 12
    ):
        raise StyleLibraryError("ledger_observation_id_out_of_scope")
    if record.get("taxonomy_version") != SCHEMA_VERSION:
        raise StyleLibraryError("ledger_taxonomy_invalid")
    if record.get("carrier") not in taxonomy["carrier"]:
        raise StyleLibraryError("ledger_taxonomy_invalid")
    if record.get("primary_job") not in taxonomy["primary_job"]:
        raise StyleLibraryError("ledger_taxonomy_invalid")
    material_codes = _require_code_list(
        record, "material_codes", set(taxonomy["material_code"])
    )
    constraint_codes = _require_code_list(
        record,
        "production_constraint_codes",
        set(taxonomy["production_constraint_code"]),
    )
    contraindication_codes = _require_code_list(
        record, "contraindication_codes", set(taxonomy["contraindication_code"])
    )
    mechanism = record.get("mechanism")
    metrics = record.get("visible_metrics")
    pages = record.get("page_observations")
    if (
        not isinstance(mechanism, dict)
        or mechanism.get("claim_kind") not in {"task_fit", "series_constant"}
        or mechanism.get("performance_evidence_scope")
        not in {"not_performance_evidence", "public_proxy_association"}
        or not isinstance(metrics, dict)
        or metrics.get("visibility_scope") != "public_proxy"
        or metrics.get("traffic_verdict") not in {"unavailable", "not_applicable"}
        or not isinstance(pages, list)
        or not pages
    ):
        raise StyleLibraryError("ledger_record_invalid")
    forbidden = (
        record.get("performance_receipt") is not None
        or record.get("asset_sha256s") != []
        or record.get("visual_observation_ids") != []
        or record.get("copy_observation_ids") != []
        or any(
            not isinstance(page, dict)
            or page.get("asset_sha256") is not None
            or page.get("capture_status") != "observed_unhashed"
            for page in pages
        )
    )
    if forbidden:
        raise StyleLibraryError("ledger_forbidden_evidence_claim")
    if (
        record.get("qualification_status") != "ineligible_unverified"
        or record.get("performance_recomputability") != "unverified"
        or record.get("derived_tier") != "unknown"
        or record.get("starter_eligible") is not False
    ):
        raise StyleLibraryError("ledger_qualification_forgery")
    for key in (
        "library_post_id", "library_account_id", "capture_date", "review_by",
        "query_fingerprint", "evidence_role",
    ):
        if type(record.get(key)) is not str or not str(record[key]).strip():
            raise StyleLibraryError("ledger_record_invalid")
    normalized = dict(record)
    normalized["material_codes"] = material_codes
    normalized["production_constraint_codes"] = constraint_codes
    normalized["contraindication_codes"] = contraindication_codes
    return normalized


def ingest_ledger(db_path: Path, jsonl_path: Path) -> dict[str, object]:
    """Import only sanitized O-XHS-001..012 candidate rows, never evidence assets."""

    taxonomy = load_taxonomy()
    try:
        raw = Path(jsonl_path).read_bytes()
        records = [
            _validate_ledger_record(json.loads(line), taxonomy)
            for line in raw.decode("utf-8").splitlines()
            if line.strip()
        ]
    except StyleLibraryError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StyleLibraryError("ledger_load_failed") from exc
    if not records:
        raise StyleLibraryError("ledger_empty")
    ids = [str(record["observation_id"]) for record in records]
    if len(ids) != len(set(ids)):
        raise StyleLibraryError("ledger_duplicate_observation_id")
    records = sorted(records, key=lambda record: record["observation_id"])
    canonical_records = [_canonical_json(record) for record in records]
    record_hashes = [_sha256_text(payload) for payload in canonical_records]
    bundle_sha = _sha256_text(_canonical_json(record_hashes))
    source_sha = hashlib.sha256(raw).hexdigest()
    rows = sorted(
        zip(records, canonical_records, record_hashes),
        key=lambda item: item[0]["observation_id"],
    )
    con = connect_db(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        receipt = con.execute(
            "SELECT record_count,source_file_sha256 FROM sanitized_ledger_ingests "
            "WHERE input_bundle_sha256=?",
            (bundle_sha,),
        ).fetchone()
        if receipt is not None:
            stored_count = con.execute(
                "SELECT count(*) FROM sanitized_style_ledger_entries "
                "WHERE input_bundle_sha256=?",
                (bundle_sha,),
            ).fetchone()[0]
            if int(receipt["record_count"]) != len(rows) or stored_count != len(rows):
                raise StyleLibraryError("ledger_receipt_mismatch")
            con.rollback()
            return {
                "status": "idempotent",
                "record_count": len(rows),
                "input_bundle_sha256": bundle_sha,
            }
        placeholders = ",".join("?" for _ in ids)
        if con.execute(
            f"SELECT 1 FROM sanitized_style_ledger_entries "
            f"WHERE observation_id IN ({placeholders}) LIMIT 1",
            ids,
        ).fetchone() is not None:
            raise StyleLibraryError("ledger_duplicate_conflict")
        con.execute(
            "INSERT INTO sanitized_ledger_ingests("
            "input_bundle_sha256,source_file_sha256,record_count) VALUES (?,?,?)",
            (bundle_sha, source_sha, len(rows)),
        )
        for record, canonical, record_sha in rows:
            mechanism = record["mechanism"]
            metrics = record["visible_metrics"]
            con.execute(
                """
                INSERT INTO sanitized_style_ledger_entries(
                    observation_id,input_bundle_sha256,library_post_id,
                    library_account_id,capture_date,review_by,query_fingerprint,
                    carrier,primary_job,traffic_stage,material_codes_json,
                    production_constraint_codes_json,contraindication_codes_json,
                    claim_kind,performance_evidence_scope,evidence_role,
                    qualification_status,performance_recomputability,derived_tier,
                    starter_eligible,visibility_scope,traffic_verdict,
                    record_sha256,record_json
                ) VALUES (?,?,?,?,?,?,?,?,?,NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record["observation_id"], bundle_sha, record["library_post_id"],
                    record["library_account_id"], record["capture_date"],
                    record["review_by"], record["query_fingerprint"],
                    record["carrier"], record["primary_job"],
                    _canonical_json(record["material_codes"]),
                    _canonical_json(record["production_constraint_codes"]),
                    _canonical_json(record["contraindication_codes"]),
                    mechanism["claim_kind"], mechanism["performance_evidence_scope"],
                    record["evidence_role"], record["qualification_status"],
                    record["performance_recomputability"], record["derived_tier"],
                    0, metrics["visibility_scope"], metrics["traffic_verdict"],
                    record_sha, canonical,
                ),
            )
        con.commit()
    except StyleLibraryError:
        con.rollback()
        raise
    except sqlite3.Error as exc:
        con.rollback()
        raise StyleLibraryError("ledger_ingest_failed") from exc
    finally:
        con.close()
    return {
        "status": "imported",
        "record_count": len(rows),
        "input_bundle_sha256": bundle_sha,
    }


RULE_PAYLOAD_KEYS = frozenset(
    {
        "claim_kind",
        "performance_evidence_scope",
        "traffic_stage",
        "required_material_codes",
        "required_constraint_codes",
        "contraindication_codes",
        "prohibited_claims",
        "selection_requirement",
        "dependency_rule_ids",
        "instruction",
    }
)
RULE_CLAIM_KINDS = frozenset(
    {
        "task_fit",
        "series_constant",
        "contrastive_performance_hypothesis",
        "anti_pattern",
    }
)
NON_TRAFFIC_PERFORMANCE_SCOPES = frozenset(
    {"not_performance_evidence", "public_proxy_association"}
)
VISUAL_RULE_TYPES = frozenset({"cover", "rhythm", "visual", "material"})


def _require_text(value: object, error_code: str) -> str:
    if type(value) is not str or not value.strip():
        raise StyleLibraryError(error_code)
    return value.strip()


def _require_string_list(
    value: object,
    error_code: str,
    *,
    allow_empty: bool = False,
) -> list[str]:
    if (
        not isinstance(value, list)
        or (not allow_empty and not value)
        or any(type(item) is not str or not item.strip() for item in value)
    ):
        raise StyleLibraryError(error_code)
    normalized = sorted(item.strip() for item in value)
    if len(normalized) != len(set(normalized)):
        raise StyleLibraryError(error_code)
    return normalized


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _load_json_record(path: Path, error_code: str) -> dict[str, object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StyleLibraryError(error_code) from exc
    if not isinstance(value, dict):
        raise StyleLibraryError(error_code)
    return value


def _normalize_rule_payload(
    payload: object, taxonomy: dict[str, object]
) -> dict[str, object]:
    if (
        not isinstance(payload, dict)
        or set(payload) != RULE_PAYLOAD_KEYS
        or payload.get("claim_kind") not in RULE_CLAIM_KINDS
    ):
        raise StyleLibraryError("candidate_rule_payload_invalid")
    scope = payload.get("performance_evidence_scope")
    if scope == "first_party_traffic_validated":
        # v2 has immutable outcome receipts, but no rule-to-outcome publication
        # edge.  Accepting this string would turn a payload claim into evidence.
        raise StyleLibraryError("performance_scope_unsupported_by_schema")
    if scope not in NON_TRAFFIC_PERFORMANCE_SCOPES:
        raise StyleLibraryError("candidate_rule_payload_invalid")
    if (
        scope == "public_proxy_association"
        and payload.get("claim_kind") != "contrastive_performance_hypothesis"
    ):
        raise StyleLibraryError("candidate_rule_payload_invalid")
    if (
        scope == "not_performance_evidence"
        and payload.get("claim_kind") == "contrastive_performance_hypothesis"
    ):
        raise StyleLibraryError("candidate_rule_payload_invalid")
    traffic_stage = payload.get("traffic_stage")
    if traffic_stage not in taxonomy["traffic_stage"]:
        raise StyleLibraryError("candidate_rule_payload_invalid")
    selection_requirement = payload.get("selection_requirement")
    if selection_requirement not in {"required", "optional"}:
        raise StyleLibraryError("candidate_rule_payload_invalid")
    dependency_rule_ids = _require_string_list(
        payload.get("dependency_rule_ids"),
        "candidate_rule_payload_invalid",
        allow_empty=True,
    )
    material_codes = _require_string_list(
        payload.get("required_material_codes"),
        "candidate_rule_payload_invalid",
    )
    constraint_codes = _require_string_list(
        payload.get("required_constraint_codes"),
        "candidate_rule_payload_invalid",
        allow_empty=True,
    )
    contraindication_codes = _require_string_list(
        payload.get("contraindication_codes"),
        "candidate_rule_payload_invalid",
        allow_empty=True,
    )
    if not set(material_codes).issubset(taxonomy["material_code"]):
        raise StyleLibraryError("candidate_rule_payload_invalid")
    if not set(constraint_codes).issubset(taxonomy["production_constraint_code"]):
        raise StyleLibraryError("candidate_rule_payload_invalid")
    if not set(contraindication_codes).issubset(taxonomy["contraindication_code"]):
        raise StyleLibraryError("candidate_rule_payload_invalid")
    prohibited_claims = _require_string_list(
        payload.get("prohibited_claims"),
        "candidate_rule_payload_invalid",
    )
    if scope != "first_party_traffic_validated" and not {
        "traffic_causality",
        "guaranteed_viral",
    }.issubset(prohibited_claims):
        raise StyleLibraryError("candidate_rule_payload_invalid")
    instruction = _require_text(
        payload.get("instruction"), "candidate_rule_payload_invalid"
    )
    return {
        "claim_kind": payload["claim_kind"],
        "performance_evidence_scope": scope,
        "traffic_stage": traffic_stage,
        "required_material_codes": material_codes,
        "required_constraint_codes": constraint_codes,
        "contraindication_codes": contraindication_codes,
        "prohibited_claims": prohibited_claims,
        "selection_requirement": selection_requirement,
        "dependency_rule_ids": dependency_rule_ids,
        "instruction": instruction,
    }


def _database_root(con: sqlite3.Connection) -> Path:
    row = next(
        (row for row in con.execute("PRAGMA database_list") if row[1] == "main"),
        None,
    )
    if row is None or not str(row[2] or "").strip():
        raise StyleLibraryError("candidate_source_asset_unverifiable")
    return Path(str(row[2])).resolve().parent


def _verify_asset_file(con: sqlite3.Connection, row: sqlite3.Row) -> None:
    asset_path = str(row["asset_path"] or "")
    if not asset_path:
        raise StyleLibraryError("candidate_source_asset_unverifiable")
    root = _database_root(con)
    try:
        path = (root / asset_path).resolve(strict=True)
        path.relative_to(root)
        data = path.read_bytes()
    except (OSError, ValueError) as exc:
        raise StyleLibraryError("candidate_source_asset_unverifiable") from exc
    if hashlib.sha256(data).hexdigest() != row["asset_sha256"]:
        raise StyleLibraryError("candidate_source_asset_hash_mismatch")
    mime = row["mime_type"]
    if mime in {"image/png", "image/jpeg", "image/webp"}:
        try:
            from PIL import Image
        except ImportError as exc:
            raise StyleLibraryError("image_decoder_dependency_missing") from exc
        expected_format = {
            "image/png": "PNG",
            "image/jpeg": "JPEG",
            "image/webp": "WEBP",
        }[mime]
        try:
            with Image.open(path) as image:
                if image.format != expected_format:
                    raise StyleLibraryError(
                        "candidate_source_asset_mime_mismatch"
                    )
                image.verify()
            with Image.open(path) as decoded:
                decoded.load()
                dimensions = decoded.size
                decoded_format = decoded.format
        except StyleLibraryError:
            raise
        except (OSError, ValueError) as exc:
            raise StyleLibraryError("candidate_source_asset_decode_failed") from exc
        if decoded_format != expected_format:
            raise StyleLibraryError("candidate_source_asset_mime_mismatch")
        if dimensions != (row["width"], row["height"]):
            raise StyleLibraryError("candidate_source_asset_dimensions_mismatch")
    elif mime == "text/plain":
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StyleLibraryError("candidate_source_asset_mime_mismatch") from exc
        if row["width"] is not None or row["height"] is not None:
            raise StyleLibraryError("candidate_source_asset_dimensions_mismatch")
    else:
        raise StyleLibraryError("candidate_source_asset_mime_unsupported")


def _typed_evidence_target(
    con: sqlite3.Connection,
    observation_type: str,
    observation_id: str,
    post_observation_id: str | None = None,
) -> dict[str, object]:
    if observation_type == "visual":
        row = con.execute(
            """
            SELECT visual.observation_sha256 AS target_sha256,
                   visual.library_post_id,post.library_account_id,post.category,
                   post.cluster_id,post.status AS post_status,
                   asset.asset_id,asset.asset_sha256,asset.asset_path,
                   asset.mime_type,asset.width,asset.height,asset.access_status,
                   asset.copyright_notes
            FROM visual_observations AS visual
            JOIN style_slides AS slide
              ON slide.slide_id=visual.slide_id
             AND slide.library_post_id=visual.library_post_id
            JOIN style_posts AS post
              ON post.library_post_id=visual.library_post_id
            JOIN style_assets AS asset ON asset.asset_id=slide.asset_id
            WHERE visual.visual_observation_id=?
            """,
            (observation_id,),
        ).fetchone()
    elif observation_type == "copy":
        row = con.execute(
            """
            SELECT copy.observation_sha256 AS target_sha256,
                   copy.library_post_id,post.library_account_id,post.category,
                   post.cluster_id,post.status AS post_status,
                   asset.asset_id,asset.asset_sha256,asset.asset_path,
                   asset.mime_type,asset.width,asset.height,asset.access_status,
                   asset.copyright_notes
            FROM copy_observations AS copy
            JOIN style_posts AS post
              ON post.library_post_id=copy.library_post_id
            LEFT JOIN style_slides AS slide
              ON slide.slide_id=copy.slide_id
             AND slide.library_post_id=copy.library_post_id
            JOIN style_assets AS asset
              ON asset.asset_id=CASE
                  WHEN copy.slide_id IS NULL THEN post.caption_asset_id
                  ELSE slide.asset_id
              END
            WHERE copy.observation_id=?
            """,
            (observation_id,),
        ).fetchone()
    elif observation_type == "post_metric":
        row = con.execute(
            """
            SELECT performance.performance_computation_sha256 AS target_sha256,
                   observation.library_post_id,post.library_account_id,
                   post.category,post.cluster_id,post.status AS post_status,
                   observation.post_observation_id,
                   NULL AS asset_id,NULL AS asset_sha256,NULL AS asset_path,
                   NULL AS mime_type,NULL AS width,NULL AS height,
                   'available' AS access_status,
                   'immutable performance receipt' AS copyright_notes,
                   observation.source_csv_sha256,
                   performance.performance_computation_sha256,
                   performance.performance_tier,performance.visibility_scope,
                   performance.traffic_verdict,
                   definition.primary_job AS performance_primary_job,
                   definition.traffic_stage AS performance_traffic_stage,
                   definition.business_objective AS performance_business_objective
            FROM post_metrics AS metric
            JOIN style_post_observations AS observation
              ON observation.post_observation_id=metric.post_observation_id
            JOIN style_posts AS post
              ON post.library_post_id=observation.library_post_id
            JOIN post_performance_publications AS performance
              ON performance.target_post_metric_id=metric.post_metric_id
            JOIN performance_definitions AS definition
              ON definition.performance_definition_id=
                 performance.performance_definition_id
             AND definition.metric_name=performance.metric_name
            WHERE metric.post_metric_id=?
            """,
            (observation_id,),
        ).fetchone()
        if row is not None and post_observation_id not in {
            None, row["post_observation_id"]
        }:
            raise StyleLibraryError("candidate_evidence_post_observation_mismatch")
    else:
        raise StyleLibraryError("candidate_evidence_type_invalid")
    if row is None:
        raise StyleLibraryError("candidate_evidence_observation_missing")
    result = dict(row)
    if not _is_sha256(result["target_sha256"]):
        raise StyleLibraryError("candidate_evidence_hash_invalid")
    if result["post_status"] != "active":
        raise StyleLibraryError("candidate_evidence_post_unavailable")
    if observation_type in {"visual", "copy"}:
        if (
            not _is_sha256(result["asset_sha256"])
            or result["access_status"] != "available"
            or not str(result["copyright_notes"] or "").strip()
        ):
            raise StyleLibraryError("candidate_source_asset_unverifiable")
        _verify_asset_file(con, row)
        if post_observation_id is None:
            link = con.execute(
                """
                SELECT post_observation_id FROM feature_observation_links
                WHERE observation_type=? AND observation_id=?
                """,
                (observation_type, observation_id),
            ).fetchone()
            if link is None:
                raise StyleLibraryError("candidate_evidence_feature_link_missing")
            post_observation_id = str(link["post_observation_id"])
        performance = con.execute(
            """
            SELECT observation.post_observation_id,observation.source_csv_sha256,
                   performance.performance_computation_sha256,
                   performance.performance_tier,performance.visibility_scope,
                   performance.traffic_verdict,
                   definition.primary_job AS performance_primary_job,
                   definition.traffic_stage AS performance_traffic_stage,
                   definition.business_objective AS performance_business_objective
            FROM style_post_observations AS observation
            JOIN post_performance_publications AS performance
              ON performance.post_observation_id=observation.post_observation_id
            JOIN performance_definitions AS definition
              ON definition.performance_definition_id=
                 performance.performance_definition_id
             AND definition.metric_name=performance.metric_name
            WHERE observation.post_observation_id=?
              AND observation.library_post_id=?
              AND observation.observation_state='complete'
            """,
            (post_observation_id, result["library_post_id"]),
        ).fetchone()
        if performance is None:
            raise StyleLibraryError("candidate_performance_receipt_missing")
        result.update(dict(performance))
    return result


def _ensure_feature_link(
    con: sqlite3.Connection,
    observation_type: str,
    observation_id: str,
    target: dict[str, object],
) -> dict[str, object]:
    capture_sha = _canonical_row_sha256_v2(
        observation_type,
        observation_id,
        target["post_observation_id"],
        target["library_post_id"],
        target["target_sha256"],
        target["asset_sha256"],
        target["source_csv_sha256"],
    )
    feature_link_id = f"FL-{capture_sha[:24]}"
    link_sha = _canonical_row_sha256_v2(
        feature_link_id,
        observation_type,
        observation_id,
        target["post_observation_id"],
        target["library_post_id"],
        target["target_sha256"],
        target["asset_sha256"],
        target["source_csv_sha256"],
        target["performance_computation_sha256"],
        capture_sha,
    )
    values = (
        feature_link_id,
        observation_type,
        observation_id,
        target["post_observation_id"],
        target["library_post_id"],
        target["target_sha256"],
        target["asset_sha256"],
        target["source_csv_sha256"],
        target["performance_computation_sha256"],
        capture_sha,
        link_sha,
    )
    con.execute(
        """
        INSERT OR IGNORE INTO feature_observation_links(
            feature_link_id,observation_type,observation_id,
            post_observation_id,library_post_id,feature_observation_sha256,
            source_asset_sha256,source_csv_sha256,
            performance_computation_sha256,capture_bundle_sha256,
            feature_link_sha256
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        values,
    )
    row = con.execute(
        """
        SELECT feature_link_id,observation_type,observation_id,
               post_observation_id,library_post_id,feature_observation_sha256,
               source_asset_sha256,source_csv_sha256,
               performance_computation_sha256,capture_bundle_sha256,
               feature_link_sha256
        FROM feature_observation_links
        WHERE observation_type=? AND observation_id=?
        """,
        (observation_type, observation_id),
    ).fetchone()
    if row is None or tuple(row) != values:
        raise StyleLibraryError("candidate_feature_link_conflict")
    return dict(row)


def _validate_rule_evidence(
    con: sqlite3.Connection,
    *,
    rule: dict[str, object],
    category: str,
    primary_job: str,
    taxonomy: dict[str, object],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    payload = _normalize_rule_payload(rule.get("payload"), taxonomy)
    evidence = rule.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise StyleLibraryError("candidate_evidence_missing")
    normalized: list[dict[str, object]] = []
    evidence_ids: set[str] = set()
    target_keys: set[tuple[str, str]] = set()
    support_posts: set[str] = set()
    counter_posts: set[str] = set()
    matching_type = "copy" if rule.get("rule_type") == "copy" else "visual"
    matching_support: list[dict[str, object]] = []
    matching_counter: list[dict[str, object]] = []
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {
            "rule_evidence_id",
            "observation_type",
            "observation_id",
            "post_observation_id",
            "evidence_role",
            "limitations",
        }:
            raise StyleLibraryError("candidate_evidence_invalid")
        evidence_id = _require_text(
            item.get("rule_evidence_id"), "candidate_evidence_invalid"
        )
        observation_type = _require_text(
            item.get("observation_type"), "candidate_evidence_invalid"
        )
        if observation_type not in {"visual", "copy"}:
            raise StyleLibraryError("candidate_evidence_type_invalid")
        observation_id = _require_text(
            item.get("observation_id"), "candidate_evidence_invalid"
        )
        post_observation_id = _require_text(
            item.get("post_observation_id"), "candidate_evidence_invalid"
        )
        role = item.get("evidence_role")
        if role not in {"support", "counterexample", "boundary"}:
            raise StyleLibraryError("candidate_evidence_invalid")
        limitations = _require_text(
            item.get("limitations"), "candidate_evidence_invalid"
        )
        if evidence_id in evidence_ids or (observation_type, observation_id) in target_keys:
            raise StyleLibraryError("candidate_evidence_duplicate")
        target = _typed_evidence_target(
            con, observation_type, observation_id, post_observation_id
        )
        if target["category"] != category:
            raise StyleLibraryError("candidate_evidence_category_mismatch")
        if (
            target["performance_primary_job"] != primary_job
            or target["performance_traffic_stage"] != payload["traffic_stage"]
            or target["performance_business_objective"] != "engagement_proxy"
        ):
            raise StyleLibraryError("candidate_performance_scope_mismatch")
        evidence_ids.add(evidence_id)
        target_keys.add((observation_type, observation_id))
        if role == "support":
            support_posts.add(target["library_post_id"])
            if observation_type == matching_type:
                matching_support.append(target)
        else:
            counter_posts.add(target["library_post_id"])
            if observation_type == matching_type:
                matching_counter.append(target)
        link = (
            _ensure_feature_link(con, observation_type, observation_id, target)
            if observation_type in {"visual", "copy"}
            else None
        )
        normalized.append(
            {
                "rule_evidence_id": evidence_id,
                "observation_type": observation_type,
                "observation_id": observation_id,
                "post_observation_id": post_observation_id,
                "evidence_role": role,
                "limitations": limitations,
                "library_post_id": target["library_post_id"],
                "library_account_id": target["library_account_id"],
                "cluster_id": target["cluster_id"],
                "performance_tier": target["performance_tier"],
                "feature_link_sha256": (
                    link["feature_link_sha256"] if link is not None else None
                ),
            }
        )
    if not support_posts or not counter_posts:
        raise StyleLibraryError("candidate_counterevidence_missing")
    if support_posts & counter_posts:
        raise StyleLibraryError("candidate_contrast_not_independent")
    if not matching_support or not matching_counter:
        raise StyleLibraryError("candidate_matching_type_contrast_missing")
    if payload["performance_evidence_scope"] == "public_proxy_association":
        if any(
            row["visibility_scope"] != "public_proxy"
            or row["traffic_verdict"] != "not_applicable"
            for row in matching_support + matching_counter
        ):
            raise StyleLibraryError("public_proxy_contrast_receipt_invalid")
        high_support = [
            row for row in matching_support if row["performance_tier"] == "high"
        ]
        if len({row["library_account_id"] for row in high_support}) < 2:
            raise StyleLibraryError("public_proxy_high_support_missing")
        if len(
            {
                row["cluster_id"]
                for row in high_support
                if str(row["cluster_id"] or "").strip()
            }
        ) < 2:
            raise StyleLibraryError("public_proxy_independent_cluster_missing")
        if not any(row["performance_tier"] in {"ordinary", "low"}
                   for row in matching_counter):
            raise StyleLibraryError("public_proxy_control_missing")
    return payload, normalized


def _candidate_snapshot_sha(record: dict[str, object]) -> str:
    return _canonical_row_sha256_v2(
        record["archetype_id"],
        record["name"],
        record["category"],
        record["carrier"],
        record["primary_job"],
        record["audience_state"],
        record["description"],
        record["production_cost"],
        record["confidence"],
        "candidate",
        record["archetype_version"],
        SCHEMA_VERSION,
    )


def create_archetype_candidate(
    db_path: Path, record: dict[str, object]
) -> dict[str, object]:
    """Create a candidate only from typed, hashed page/copy observations."""

    taxonomy = load_taxonomy()
    required = {
        "archetype_id",
        "name",
        "category",
        "carrier",
        "primary_job",
        "audience_state",
        "description",
        "production_cost",
        "confidence",
        "archetype_version",
        "rules",
    }
    if not isinstance(record, dict) or set(record) != required:
        raise StyleLibraryError("candidate_record_invalid")
    normalized: dict[str, object] = {
        key: _require_text(record.get(key), "candidate_record_invalid")
        for key in (
            "archetype_id",
            "name",
            "category",
            "audience_state",
            "description",
            "production_cost",
        )
    }
    carrier = record.get("carrier")
    primary_job = record.get("primary_job")
    version = record.get("archetype_version")
    confidence = record.get("confidence")
    if carrier not in taxonomy["carrier"] or carrier in {"unknown", "other"}:
        raise StyleLibraryError("candidate_scope_invalid")
    if primary_job not in taxonomy["primary_job"]:
        raise StyleLibraryError("candidate_scope_invalid")
    if type(version) is not int or version < 1:
        raise StyleLibraryError("candidate_record_invalid")
    if type(confidence) not in {int, float} or not 0 <= float(confidence) <= 1:
        raise StyleLibraryError("candidate_record_invalid")
    normalized.update(
        {
            "carrier": carrier,
            "primary_job": primary_job,
            "archetype_version": version,
            "confidence": float(confidence),
        }
    )
    rules = record.get("rules")
    if not isinstance(rules, list) or not rules:
        raise StyleLibraryError("candidate_rules_missing")
    con = connect_db(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        normalized_rules: list[dict[str, object]] = []
        rule_ids: set[str] = set()
        for rule in rules:
            if not isinstance(rule, dict) or set(rule) != {
                "rule_id",
                "rule_type",
                "applicability_scope",
                "payload",
                "evidence",
            }:
                raise StyleLibraryError("candidate_rule_invalid")
            rule_id = _require_text(rule.get("rule_id"), "candidate_rule_invalid")
            rule_type = rule.get("rule_type")
            if rule_id in rule_ids or rule_type not in taxonomy["rule_type"]:
                raise StyleLibraryError("candidate_rule_invalid")
            applicability = _require_text(
                rule.get("applicability_scope"), "candidate_rule_invalid"
            )
            expected_scope = (
                f"{normalized['category']}×{normalized['carrier']}"
                f"×{normalized['primary_job']}"
            )
            if applicability != expected_scope:
                raise StyleLibraryError("candidate_rule_scope_mismatch")
            payload, evidence_rows = _validate_rule_evidence(
                con,
                rule=rule,
                category=str(normalized["category"]),
                primary_job=str(normalized["primary_job"]),
                taxonomy=taxonomy,
            )
            rule_ids.add(rule_id)
            normalized_rules.append(
                {
                    "rule_id": rule_id,
                    "rule_type": rule_type,
                    "applicability_scope": applicability,
                    "payload": payload,
                    "evidence": evidence_rows,
                }
            )
        rule_types = {str(rule["rule_type"]) for rule in normalized_rules}
        if "copy" not in rule_types or not (rule_types & VISUAL_RULE_TYPES):
            raise StyleLibraryError("candidate_multimodal_coverage_missing")
        dependency_map = {
            str(rule["rule_id"]): list(rule["payload"]["dependency_rule_ids"])
            for rule in normalized_rules
        }
        if any(
            dependency == rule_id or dependency not in rule_ids
            for rule_id, dependencies in dependency_map.items()
            for dependency in dependencies
        ):
            raise StyleLibraryError("candidate_rule_dependency_invalid")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(rule_id: str) -> None:
            if rule_id in visiting:
                raise StyleLibraryError("candidate_rule_dependency_cycle")
            if rule_id in visited:
                return
            visiting.add(rule_id)
            for dependency in dependency_map[rule_id]:
                visit(dependency)
            visiting.remove(rule_id)
            visited.add(rule_id)

        for rule_id in sorted(rule_ids):
            visit(rule_id)
        snapshot_sha = _candidate_snapshot_sha(normalized)
        con.execute(
            """
            INSERT INTO style_archetypes(
                archetype_id,name,category_scope,carrier,primary_job_scope,
                audience_state,description,production_cost,confidence,status,
                current_version,snapshot_sha256,taxonomy_version
            ) VALUES (?,?,?,?,?,?,?,?,?,'candidate',?,?,2)
            """,
            (
                normalized["archetype_id"],
                normalized["name"],
                normalized["category"],
                normalized["carrier"],
                normalized["primary_job"],
                normalized["audience_state"],
                normalized["description"],
                normalized["production_cost"],
                normalized["confidence"],
                normalized["archetype_version"],
                snapshot_sha,
            ),
        )
        for rule in normalized_rules:
            con.execute(
                """
                INSERT INTO archetype_rules(
                    rule_id,archetype_id,archetype_version,rule_type,
                    rule_payload_json,applicability_scope,status
                ) VALUES (?,?,?,?,?,?,'active')
                """,
                (
                    rule["rule_id"],
                    normalized["archetype_id"],
                    normalized["archetype_version"],
                    rule["rule_type"],
                    _canonical_json(rule["payload"]),
                    rule["applicability_scope"],
                ),
            )
            for evidence in rule["evidence"]:
                con.execute(
                    """
                    INSERT INTO rule_evidence(
                        rule_evidence_id,rule_id,observation_type,
                        observation_id,evidence_role,limitations
                    ) VALUES (?,?,?,?,?,?)
                    """,
                    (
                        evidence["rule_evidence_id"],
                        rule["rule_id"],
                        evidence["observation_type"],
                        evidence["observation_id"],
                        evidence["evidence_role"],
                        evidence["limitations"],
                    ),
                )
        con.commit()
        return {
            "status": "candidate_created",
            "archetype_id": normalized["archetype_id"],
            "archetype_version": normalized["archetype_version"],
            "category": normalized["category"],
            "carrier": normalized["carrier"],
            "primary_job": normalized["primary_job"],
            "candidate_snapshot_sha256": snapshot_sha,
            "rule_ids": sorted(rule_ids),
            "performance_claim_boundary": (
                "no first-party traffic claim; task-fit or public-proxy association only"
            ),
        }
    except StyleLibraryError:
        if con.in_transaction:
            con.rollback()
        raise
    except sqlite3.Error as exc:
        if con.in_transaction:
            con.rollback()
        raise StyleLibraryError("candidate_ingest_failed") from exc
    finally:
        con.close()


def _normalize_review_record(record: object) -> dict[str, object]:
    required = {
        "archetype_id",
        "archetype_version",
        "category",
        "carrier",
        "primary_job",
        "selected_rule_ids",
        "decision",
        "target_status",
        "content_owner_id",
        "reviewer_ids",
        "reviewer_independence_status",
        "reviewed_at",
        "limitations",
    }
    if not isinstance(record, dict) or set(record) != required:
        raise StyleLibraryError("archetype_review_record_invalid")
    normalized: dict[str, object] = {
        key: _require_text(record.get(key), "archetype_review_record_invalid")
        for key in (
            "archetype_id",
            "category",
            "carrier",
            "primary_job",
            "content_owner_id",
            "reviewed_at",
        )
    }
    version = record.get("archetype_version")
    if type(version) is not int or version < 1:
        raise StyleLibraryError("archetype_review_record_invalid")
    if record.get("decision") != "PASS":
        raise StyleLibraryError("archetype_review_not_pass")
    if record.get("target_status") != "supported":
        raise StyleLibraryError("archetype_review_target_invalid")
    if record.get("reviewer_independence_status") != "independent":
        raise StyleLibraryError("reviewer_not_independent")
    reviewer_ids = _require_string_list(
        record.get("reviewer_ids"), "archetype_review_record_invalid"
    )
    if normalized["content_owner_id"] in reviewer_ids:
        raise StyleLibraryError("reviewer_not_independent")
    try:
        reviewed_on = date.fromisoformat(str(normalized["reviewed_at"]))
    except ValueError as exc:
        raise StyleLibraryError("archetype_review_date_invalid") from exc
    if reviewed_on > date.today():
        raise StyleLibraryError("archetype_review_date_invalid")
    normalized.update(
        {
            "archetype_version": version,
            "selected_rule_ids": _require_string_list(
                record.get("selected_rule_ids"),
                "archetype_review_record_invalid",
            ),
            "decision": "PASS",
            "target_status": record["target_status"],
            "reviewer_ids": reviewer_ids,
            "reviewer_independence_status": "independent",
            "limitations": _require_string_list(
                record.get("limitations"),
                "archetype_review_record_invalid",
            ),
        }
    )
    return normalized


def _read_rule_evidence_for_publication(
    con: sqlite3.Connection, rule_id: str
) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT evidence.rule_id,evidence.rule_evidence_id,evidence.observation_type,
               evidence.observation_id,evidence.evidence_role,
               evidence.limitations,
               CASE evidence.observation_type
                   WHEN 'visual' THEN visual.observation_sha256
                   WHEN 'copy' THEN copy.observation_sha256
                   WHEN 'post_metric' THEN
                       performance.performance_computation_sha256
               END AS target_sha256,
               CASE evidence.observation_type
                   WHEN 'visual' THEN visual.library_post_id
                   WHEN 'copy' THEN copy.library_post_id
                   WHEN 'post_metric' THEN metric_observation.library_post_id
               END AS library_post_id,
               feature.feature_link_sha256,feature.post_observation_id,
               feature.source_asset_sha256,feature.source_csv_sha256,
               feature.performance_computation_sha256,
               linked_performance.performance_tier,
               linked_performance.visibility_scope,
               linked_performance.traffic_verdict,
               linked_definition.primary_job AS performance_primary_job,
               linked_definition.traffic_stage AS performance_traffic_stage,
               linked_definition.business_objective AS performance_business_objective,
               linked_post.library_account_id,linked_post.cluster_id,
               linked_post.status AS post_status
        FROM rule_evidence AS evidence
        LEFT JOIN visual_observations AS visual
          ON evidence.observation_type='visual'
         AND visual.visual_observation_id=evidence.observation_id
        LEFT JOIN copy_observations AS copy
          ON evidence.observation_type='copy'
         AND copy.observation_id=evidence.observation_id
        LEFT JOIN post_metrics AS metric
          ON evidence.observation_type='post_metric'
         AND metric.post_metric_id=evidence.observation_id
        LEFT JOIN style_post_observations AS metric_observation
          ON metric_observation.post_observation_id=metric.post_observation_id
        LEFT JOIN post_performance_publications AS performance
          ON performance.target_post_metric_id=metric.post_metric_id
        LEFT JOIN feature_observation_links AS feature
          ON evidence.observation_type IN ('visual','copy')
         AND feature.observation_type=evidence.observation_type
         AND feature.observation_id=evidence.observation_id
        LEFT JOIN post_performance_publications AS linked_performance
          ON linked_performance.post_observation_id=feature.post_observation_id
        LEFT JOIN performance_definitions AS linked_definition
          ON linked_definition.performance_definition_id=
             linked_performance.performance_definition_id
         AND linked_definition.metric_name=linked_performance.metric_name
        LEFT JOIN style_posts AS linked_post
          ON linked_post.library_post_id=feature.library_post_id
        WHERE evidence.rule_id=?
        ORDER BY evidence.rule_evidence_id
        """,
        (rule_id,),
    ).fetchall()


def _ordered_bundle_sha(values: Sequence[str]) -> str:
    return _sha256_text(_canonical_json(list(values)))


def _rule_sha(rule: sqlite3.Row) -> str:
    return _canonical_row_sha256_v2(
        rule["rule_id"],
        rule["archetype_id"],
        rule["archetype_version"],
        rule["rule_type"],
        _canonical_json(json.loads(rule["rule_payload_json"])),
        rule["applicability_scope"],
        rule["status"],
    )


def _rule_bundle_sha(
    reviewed_rules: Sequence[tuple[sqlite3.Row, list[sqlite3.Row]]]
) -> str:
    return _ordered_bundle_sha(
        [
            f"{rule['rule_id']}|{_rule_sha(rule)}"
            for rule, _ in sorted(reviewed_rules, key=lambda item: item[0]["rule_id"])
        ]
    )


def _evidence_bundle_sha(
    reviewed_rules: Sequence[tuple[sqlite3.Row, list[sqlite3.Row]]]
) -> str:
    preimages: list[tuple[str, str, str]] = []
    for rule, evidence_rows in reviewed_rules:
        for row in evidence_rows:
            proof_sha = (
                row["feature_link_sha256"]
                if row["observation_type"] in {"visual", "copy"}
                else row["target_sha256"]
            )
            preimage = "|".join(
                    str(value)
                    for value in (
                        rule["rule_id"],
                        row["rule_evidence_id"],
                        row["observation_type"],
                        row["observation_id"],
                        row["evidence_role"],
                        row["limitations"],
                        proof_sha,
                    )
                )
            preimages.append(
                (str(rule["rule_id"]), str(row["rule_evidence_id"]), preimage)
            )
    return _ordered_bundle_sha(
        [item[2] for item in sorted(preimages, key=lambda item: item[:2])]
    )


def _feature_link_set_sha(
    reviewed_rules: Sequence[tuple[sqlite3.Row, list[sqlite3.Row]]]
) -> str:
    return _ordered_bundle_sha(
        [
            item[2]
            for item in sorted(
                (
                    str(rule["rule_id"]),
                    str(row["rule_evidence_id"]),
                    f"{rule['rule_id']}|{row['rule_evidence_id']}|"
                    f"{row['feature_link_sha256']}",
                )
                for rule, rows in reviewed_rules
                for row in rows
                if row["observation_type"] in {"visual", "copy"}
            )
        ]
    )


def _selected_asset_bundle_sha(
    reviewed_rules: Sequence[tuple[sqlite3.Row, list[sqlite3.Row]]]
) -> str:
    return _ordered_bundle_sha(
        [
            item[2]
            for item in sorted(
                (
                    str(rule["rule_id"]),
                    str(row["rule_evidence_id"]),
                    f"{rule['rule_id']}|{row['rule_evidence_id']}|"
                    f"{row['source_asset_sha256']}",
                )
                for rule, rows in reviewed_rules
                for row in rows
                if row["observation_type"] in {"visual", "copy"}
            )
        ]
    )


def _published_rule_evidence_is_current(
    con: sqlite3.Connection, rule_id: str, category: str
) -> bool:
    evidence = _read_rule_evidence_for_publication(con, rule_id)
    support_posts: set[str] = set()
    counter_posts: set[str] = set()
    if not evidence:
        return False
    try:
        for row in evidence:
            target = _typed_evidence_target(
                con,
                row["observation_type"],
                row["observation_id"],
                row["post_observation_id"],
            )
            if (
                target["target_sha256"] != row["target_sha256"]
                or target["category"] != category
                or row["feature_link_sha256"] is None
                or target["asset_sha256"] != row["source_asset_sha256"]
                or target["source_csv_sha256"] != row["source_csv_sha256"]
                or target["performance_computation_sha256"]
                != row["performance_computation_sha256"]
                or target["performance_tier"] != row["performance_tier"]
                or target["performance_primary_job"]
                != row["performance_primary_job"]
                or target["performance_traffic_stage"]
                != row["performance_traffic_stage"]
                or target["performance_business_objective"]
                != row["performance_business_objective"]
                or target["library_account_id"] != row["library_account_id"]
                or target["cluster_id"] != row["cluster_id"]
            ):
                return False
            if row["evidence_role"] == "support":
                support_posts.add(row["library_post_id"])
            elif row["evidence_role"] in {"counterexample", "boundary"}:
                counter_posts.add(row["library_post_id"])
    except StyleLibraryError:
        return False
    return bool(
        support_posts
        and counter_posts
        and not (support_posts & counter_posts)
    )


def _audit_reviewed_archetype(
    con: sqlite3.Connection,
    review: dict[str, object],
    *,
    require_candidate: bool = False,
) -> tuple[sqlite3.Row, list[tuple[sqlite3.Row, list[sqlite3.Row]]]]:
    taxonomy = load_taxonomy()
    archetype = con.execute(
        "SELECT * FROM style_archetypes WHERE archetype_id=?",
        (review["archetype_id"],),
    ).fetchone()
    if archetype is None:
        raise StyleLibraryError("archetype_not_found")
    allowed_statuses = {"candidate"} if require_candidate else {
        "candidate", review["target_status"]
    }
    if archetype["status"] not in allowed_statuses:
        raise StyleLibraryError("archetype_not_promotable")
    if archetype["status"] == "candidate" and archetype["snapshot_sha256"] != (
        _canonical_row_sha256_v2(
            archetype["archetype_id"],
            archetype["name"],
            archetype["category_scope"],
            archetype["carrier"],
            archetype["primary_job_scope"],
            archetype["audience_state"],
            archetype["description"],
            archetype["production_cost"],
            archetype["confidence"],
            "candidate",
            archetype["current_version"],
            archetype["taxonomy_version"],
        )
    ):
        raise StyleLibraryError("archetype_candidate_snapshot_stale")
    exact = {
        "current_version": review["archetype_version"],
        "category_scope": review["category"],
        "carrier": review["carrier"],
        "primary_job_scope": review["primary_job"],
    }
    if any(archetype[key] != value for key, value in exact.items()):
        raise StyleLibraryError("archetype_review_scope_mismatch")
    all_rules = con.execute(
        """
        SELECT * FROM archetype_rules
        WHERE archetype_id=? AND archetype_version=? AND status='active'
        ORDER BY rule_id
        """,
        (archetype["archetype_id"], archetype["current_version"]),
    ).fetchall()
    if [row["rule_id"] for row in all_rules] != review["selected_rule_ids"]:
        raise StyleLibraryError("archetype_review_rule_set_not_closed")
    reviewed_rules: list[tuple[sqlite3.Row, list[sqlite3.Row]]] = []
    rule_types: set[str] = set()
    bundle_support_posts: set[str] = set()
    bundle_counter_posts: set[str] = set()
    selected_ids = set(review["selected_rule_ids"])
    for rule in all_rules:
        payload = _normalize_rule_payload(
            json.loads(rule["rule_payload_json"]), taxonomy
        )
        if (
            payload["claim_kind"] != "contrastive_performance_hypothesis"
            or payload["performance_evidence_scope"]
            != "public_proxy_association"
        ):
            raise StyleLibraryError("archetype_review_performance_gate_failed")
        if not set(payload["dependency_rule_ids"]).issubset(selected_ids):
            raise StyleLibraryError("archetype_review_dependency_missing")
        evidence = _read_rule_evidence_for_publication(con, rule["rule_id"])
        matching_type = "copy" if rule["rule_type"] == "copy" else "visual"
        matching_support: list[sqlite3.Row] = []
        matching_counter: list[sqlite3.Row] = []
        for evidence_row in evidence:
            target = _typed_evidence_target(
                con,
                evidence_row["observation_type"],
                evidence_row["observation_id"],
                evidence_row["post_observation_id"],
            )
            if (
                target["target_sha256"] != evidence_row["target_sha256"]
                or target["category"] != archetype["category_scope"]
                or target["asset_sha256"]
                != evidence_row["source_asset_sha256"]
                or target["source_csv_sha256"]
                != evidence_row["source_csv_sha256"]
                or target["performance_computation_sha256"]
                != evidence_row["performance_computation_sha256"]
                or target["performance_primary_job"]
                != archetype["primary_job_scope"]
                or target["performance_traffic_stage"]
                != payload["traffic_stage"]
                or target["performance_business_objective"]
                != "engagement_proxy"
                or not _is_sha256(evidence_row["feature_link_sha256"])
            ):
                raise StyleLibraryError("archetype_review_evidence_gate_failed")
            if evidence_row["observation_type"] == matching_type:
                if evidence_row["evidence_role"] == "support":
                    matching_support.append(evidence_row)
                elif evidence_row["evidence_role"] in {
                    "counterexample", "boundary"
                }:
                    matching_counter.append(evidence_row)
        support_posts = {
            row["library_post_id"]
            for row in evidence
            if row["evidence_role"] == "support"
        }
        counter_posts = {
            row["library_post_id"]
            for row in evidence
            if row["evidence_role"] in {"counterexample", "boundary"}
        }
        if (
            not evidence
            or any(not _is_sha256(row["target_sha256"]) for row in evidence)
            or not support_posts
            or not counter_posts
            or support_posts & counter_posts
        ):
            raise StyleLibraryError("archetype_review_evidence_gate_failed")
        if (
            len(
                {
                    row["library_account_id"]
                    for row in matching_support
                    if row["performance_tier"] == "high"
                    and row["visibility_scope"] == "public_proxy"
                    and row["traffic_verdict"] == "not_applicable"
                }
            ) < 2
            or len(
                {
                    row["cluster_id"]
                    for row in matching_support
                    if row["performance_tier"] == "high"
                    and str(row["cluster_id"] or "").strip()
                }
            ) < 2
            or not any(
                row["performance_tier"] in {"ordinary", "low"}
                and row["visibility_scope"] == "public_proxy"
                and row["traffic_verdict"] == "not_applicable"
                for row in matching_counter
            )
        ):
            raise StyleLibraryError("archetype_review_evidence_gate_failed")
        bundle_support_posts.update(support_posts)
        bundle_counter_posts.update(counter_posts)
        rule_types.add(rule["rule_type"])
        reviewed_rules.append((rule, evidence))
    if "copy" not in rule_types or not (rule_types & VISUAL_RULE_TYPES):
        raise StyleLibraryError("archetype_review_multimodal_coverage_missing")
    if bundle_support_posts & bundle_counter_posts:
        raise StyleLibraryError("archetype_review_bundle_role_conflict")
    return archetype, reviewed_rules


def review_archetype(
    db_path: Path, record: dict[str, object]
) -> dict[str, object]:
    """Recompute the promotion gate without mutating the candidate."""

    review = _normalize_review_record(record)
    con = connect_db(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        archetype, rules = _audit_reviewed_archetype(
            con, review, require_candidate=True
        )
        selected_json = _canonical_json(review["selected_rule_ids"])
        reviewer_json = _canonical_json(review["reviewer_ids"])
        limitations_json = _canonical_json(review["limitations"])
        rule_bundle_sha = _rule_bundle_sha(rules)
        evidence_bundle_sha = _evidence_bundle_sha(rules)
        receipt_sha = _canonical_row_sha256_v2(
            archetype["archetype_id"],
            archetype["current_version"],
            archetype["snapshot_sha256"],
            archetype["category_scope"],
            archetype["carrier"],
            archetype["primary_job_scope"],
            selected_json,
            rule_bundle_sha,
            evidence_bundle_sha,
            review["decision"],
            review["target_status"],
            review["content_owner_id"],
            reviewer_json,
            review["reviewer_independence_status"],
            review["reviewed_at"],
            limitations_json,
        )
        con.execute(
            """
            INSERT OR IGNORE INTO archetype_review_receipts(
                review_receipt_sha256,archetype_id,archetype_version,
                candidate_snapshot_sha256,category,carrier,primary_job,
                selected_rule_ids,rule_bundle_sha256,evidence_bundle_sha256,
                decision,target_status,content_owner_id,reviewer_ids,
                reviewer_independence_status,reviewed_at,limitations_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                receipt_sha,
                archetype["archetype_id"],
                archetype["current_version"],
                archetype["snapshot_sha256"],
                archetype["category_scope"],
                archetype["carrier"],
                archetype["primary_job_scope"],
                selected_json,
                rule_bundle_sha,
                evidence_bundle_sha,
                review["decision"],
                review["target_status"],
                review["content_owner_id"],
                reviewer_json,
                review["reviewer_independence_status"],
                review["reviewed_at"],
                limitations_json,
            ),
        )
        stored = con.execute(
            "SELECT 1 FROM archetype_review_receipts "
            "WHERE review_receipt_sha256=?",
            (receipt_sha,),
        ).fetchone()
        if stored is None:
            raise StyleLibraryError("review_receipt_conflict")
        con.commit()
    except StyleLibraryError:
        if con.in_transaction:
            con.rollback()
        raise
    except (json.JSONDecodeError, sqlite3.Error) as exc:
        if con.in_transaction:
            con.rollback()
        raise StyleLibraryError("archetype_review_failed") from exc
    finally:
        con.close()
    return {
        "status": "review_pass",
        "archetype_id": archetype["archetype_id"],
        "archetype_version": archetype["current_version"],
        "selected_rule_ids": [row[0]["rule_id"] for row in rules],
        "review_receipt_sha256": receipt_sha,
        "review_receipt_storage": "archetype_review_receipts",
        "rule_bundle_sha256": rule_bundle_sha,
        "evidence_bundle_sha256": evidence_bundle_sha,
        "performance_claim_boundary": (
            "first-party traffic validation is unsupported by schema v2"
        ),
    }


def _published_archetype_snapshot_sha(
    archetype: sqlite3.Row, target_status: str
) -> str:
    return _canonical_row_sha256_v2(
        archetype["archetype_id"],
        archetype["name"],
        archetype["category_scope"],
        archetype["carrier"],
        archetype["primary_job_scope"],
        archetype["audience_state"],
        archetype["description"],
        archetype["production_cost"],
        archetype["confidence"],
        target_status,
        archetype["current_version"],
        archetype["taxonomy_version"],
    )


def publish_archetype(
    db_path: Path, record: dict[str, object]
) -> dict[str, object]:
    """Atomically promote and publish one independently reviewed snapshot."""

    review = _normalize_review_record(record)
    con = connect_db(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        archetype, reviewed_rules = _audit_reviewed_archetype(con, review)
        selected_json = _canonical_json(review["selected_rule_ids"])
        reviewer_json = _canonical_json(review["reviewer_ids"])
        limitations_json = _canonical_json(review["limitations"])
        rule_bundle_sha = _rule_bundle_sha(reviewed_rules)
        evidence_bundle_sha = _evidence_bundle_sha(reviewed_rules)
        candidate_snapshot_sha = (
            archetype["snapshot_sha256"]
            if archetype["status"] == "candidate"
            else con.execute(
                """
                SELECT candidate_snapshot_sha256
                FROM archetype_review_receipts
                WHERE archetype_id=? AND archetype_version=?
                  AND selected_rule_ids=?
                  AND content_owner_id=? AND reviewer_ids=?
                  AND reviewed_at=? AND limitations_json=?
                """,
                (
                    archetype["archetype_id"],
                    archetype["current_version"],
                    selected_json,
                    review["content_owner_id"],
                    reviewer_json,
                    review["reviewed_at"],
                    limitations_json,
                ),
            ).fetchone()
        )
        if isinstance(candidate_snapshot_sha, sqlite3.Row):
            candidate_snapshot_sha = candidate_snapshot_sha[0]
        if not _is_sha256(candidate_snapshot_sha):
            raise StyleLibraryError("review_receipt_missing")
        review_receipt_sha = _canonical_row_sha256_v2(
            archetype["archetype_id"],
            archetype["current_version"],
            candidate_snapshot_sha,
            archetype["category_scope"],
            archetype["carrier"],
            archetype["primary_job_scope"],
            selected_json,
            rule_bundle_sha,
            evidence_bundle_sha,
            review["decision"],
            review["target_status"],
            review["content_owner_id"],
            reviewer_json,
            review["reviewer_independence_status"],
            review["reviewed_at"],
            limitations_json,
        )
        receipt = con.execute(
            """
            SELECT 1 FROM archetype_review_receipts
            WHERE review_receipt_sha256=?
              AND rule_bundle_sha256=? AND evidence_bundle_sha256=?
            """,
            (review_receipt_sha, rule_bundle_sha, evidence_bundle_sha),
        ).fetchone()
        if receipt is None:
            raise StyleLibraryError("review_receipt_missing")
        snapshot_sha = _published_archetype_snapshot_sha(
            archetype, str(review["target_status"])
        )
        existing = con.execute(
            """
            SELECT archetype_snapshot_sha256 FROM archetype_publications
            WHERE archetype_id=? AND archetype_version=?
            """,
            (archetype["archetype_id"], archetype["current_version"]),
        ).fetchone()
        if existing is None:
            if archetype["status"] != "candidate":
                raise StyleLibraryError("archetype_publication_state_invalid")
            con.execute(
                """
                UPDATE style_archetypes
                SET status=?,snapshot_sha256=?,updated_at=CURRENT_TIMESTAMP
                WHERE archetype_id=? AND status='candidate'
                """,
                (
                    review["target_status"],
                    snapshot_sha,
                    archetype["archetype_id"],
                ),
            )
            con.execute(
                """
                INSERT INTO archetype_publications(
                    archetype_id,archetype_version,archetype_snapshot_sha256
                ) VALUES (?,?,?)
                """,
                (
                    archetype["archetype_id"],
                    archetype["current_version"],
                    snapshot_sha,
                ),
            )
            publication_status = "published"
        elif existing["archetype_snapshot_sha256"] == snapshot_sha:
            publication_status = "idempotent"
        else:
            raise StyleLibraryError("archetype_publication_conflict")
        for rule, evidence in reviewed_rules:
            rule_sha = _rule_sha(rule)
            evidence_preimages = [
                "|".join(
                    str(row[key])
                    for key in (
                        "rule_evidence_id",
                        "observation_type",
                        "observation_id",
                        "evidence_role",
                        "limitations",
                        "target_sha256",
                    )
                )
                for row in evidence
            ]
            evidence_sha = _sha256_text(_canonical_json(evidence_preimages))
            prior = con.execute(
                """
                SELECT rule_sha256,evidence_set_sha256,evidence_count
                FROM archetype_rule_publications WHERE rule_id=?
                """,
                (rule["rule_id"],),
            ).fetchone()
            if prior is None:
                con.execute(
                    """
                    INSERT INTO archetype_rule_publications(
                        rule_id,archetype_id,archetype_version,
                        archetype_snapshot_sha256,rule_sha256,
                        evidence_set_sha256,evidence_count
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        rule["rule_id"],
                        rule["archetype_id"],
                        rule["archetype_version"],
                        snapshot_sha,
                        rule_sha,
                        evidence_sha,
                        len(evidence),
                    ),
                )
            elif (
                prior["rule_sha256"] != rule_sha
                or prior["evidence_set_sha256"] != evidence_sha
                or prior["evidence_count"] != len(evidence)
            ):
                raise StyleLibraryError("rule_publication_conflict")
        feature_link_set_sha = _feature_link_set_sha(reviewed_rules)
        support_counts = con.execute(
            """
            SELECT count(DISTINCT post.library_account_id),
                   count(DISTINCT CASE
                       WHEN post.cluster_id IS NOT NULL
                        AND trim(post.cluster_id) <> ''
                       THEN post.cluster_id END)
            FROM rule_evidence AS evidence
            JOIN feature_observation_links AS feature
              ON feature.observation_type=evidence.observation_type
             AND feature.observation_id=evidence.observation_id
            JOIN post_performance_publications AS performance
              ON performance.post_observation_id=feature.post_observation_id
            JOIN style_posts AS post
              ON post.library_post_id=feature.library_post_id
            WHERE evidence.rule_id IN (
                SELECT value FROM json_each(?)
            )
              AND evidence.evidence_role='support'
              AND performance.performance_tier='high'
            """,
            (selected_json,),
        ).fetchone()
        support_account_count = int(support_counts[0])
        support_cluster_count = int(support_counts[1])
        qualification_sha = _canonical_row_sha256_v2(
            archetype["archetype_id"],
            archetype["current_version"],
            snapshot_sha,
            review_receipt_sha,
            selected_json,
            feature_link_set_sha,
            support_account_count,
            support_cluster_count,
        )
        con.execute(
            """
            INSERT OR IGNORE INTO qualified_style_publications(
                archetype_id,archetype_version,archetype_snapshot_sha256,
                review_receipt_sha256,selected_rule_ids,
                feature_link_set_sha256,support_account_count,
                support_cluster_count,qualification_sha256
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                archetype["archetype_id"],
                archetype["current_version"],
                snapshot_sha,
                review_receipt_sha,
                selected_json,
                feature_link_set_sha,
                support_account_count,
                support_cluster_count,
                qualification_sha,
            ),
        )
        qualified = con.execute(
            """
            SELECT qualification_sha256 FROM qualified_style_publications
            WHERE archetype_id=? AND archetype_version=?
            """,
            (archetype["archetype_id"], archetype["current_version"]),
        ).fetchone()
        if qualified is None or qualified[0] != qualification_sha:
            raise StyleLibraryError("qualified_publication_conflict")
        con.commit()
        return {
            "status": publication_status,
            "archetype_id": archetype["archetype_id"],
            "archetype_version": archetype["current_version"],
            "archetype_snapshot_sha256": snapshot_sha,
            "published_rule_ids": [
                rule["rule_id"] for rule, _ in reviewed_rules
            ],
            "review_receipt_sha256": review_receipt_sha,
            "review_receipt_storage": "archetype_review_receipts",
            "qualification_sha256": qualification_sha,
        }
    except StyleLibraryError:
        if con.in_transaction:
            con.rollback()
        raise
    except (json.JSONDecodeError, sqlite3.Error) as exc:
        if con.in_transaction:
            con.rollback()
        raise StyleLibraryError("archetype_publication_failed") from exc
    finally:
        con.close()


def _feature_observation_payload(
    con: sqlite3.Connection, observation_type: str, observation_id: str
) -> dict[str, object]:
    if observation_type == "visual":
        row = con.execute(
            """
            SELECT composition,dominant_material,background_type,
                   subject_presence,layout_structure,text_density,
                   hierarchy_levels,alignment,spacing_pattern,font_feel,
                   decoration_types,annotation_style,imperfection_signals,
                   image_text_relationship
            FROM visual_observations WHERE visual_observation_id=?
            """,
            (observation_id,),
        ).fetchone()
    else:
        row = con.execute(
            """
            SELECT text_surface,point_of_view,audience_address,register,
                   sentence_length_pattern,line_break_pattern,
                   punctuation_pattern,emoji_pattern,hook_move,
                   narrative_moves,evidence_move,payoff_move,cta_move,
                   image_caption_division
            FROM copy_observations WHERE observation_id=?
            """,
            (observation_id,),
        ).fetchone()
    if row is None:
        raise StyleLibraryError("published_feature_observation_missing")
    return dict(row)


def _load_current_qualified_bundle(
    con: sqlite3.Connection,
    archetype: sqlite3.Row,
    taxonomy: dict[str, object],
) -> dict[str, object]:
    qualification = con.execute(
        """
        SELECT * FROM qualified_style_publications
        WHERE archetype_id=? AND archetype_version=?
          AND archetype_snapshot_sha256=?
        """,
        (
            archetype["archetype_id"],
            archetype["current_version"],
            archetype["snapshot_sha256"],
        ),
    ).fetchone()
    if qualification is None:
        raise StyleLibraryError("qualified_publication_missing")
    try:
        selected_ids = json.loads(qualification["selected_rule_ids"])
    except json.JSONDecodeError as exc:
        raise StyleLibraryError("qualified_rule_set_invalid") from exc
    if (
        not isinstance(selected_ids, list)
        or selected_ids != sorted(set(selected_ids))
    ):
        raise StyleLibraryError("qualified_rule_set_invalid")
    review = con.execute(
        """
        SELECT * FROM archetype_review_receipts
        WHERE review_receipt_sha256=? AND archetype_id=?
          AND archetype_version=?
        """,
        (
            qualification["review_receipt_sha256"],
            archetype["archetype_id"],
            archetype["current_version"],
        ),
    ).fetchone()
    if review is None or json.loads(review["selected_rule_ids"]) != selected_ids:
        raise StyleLibraryError("archetype_review_receipt_missing")
    reviewed_rules: list[tuple[sqlite3.Row, list[sqlite3.Row]]] = []
    rule_payloads: list[dict[str, object]] = []
    bundle_support_posts: set[str] = set()
    bundle_counter_posts: set[str] = set()
    for rule_id in selected_ids:
        rule = con.execute(
            """
            SELECT rule.*,publication.rule_sha256,
                   publication.evidence_set_sha256,publication.evidence_count
            FROM archetype_rules AS rule
            JOIN archetype_rule_publications AS publication
              ON publication.rule_id=rule.rule_id
             AND publication.archetype_id=rule.archetype_id
             AND publication.archetype_version=rule.archetype_version
             AND publication.archetype_snapshot_sha256=?
            WHERE rule.rule_id=? AND rule.archetype_id=?
              AND rule.archetype_version=? AND rule.status='active'
            """,
            (
                archetype["snapshot_sha256"],
                rule_id,
                archetype["archetype_id"],
                archetype["current_version"],
            ),
        ).fetchone()
        if rule is None or rule["rule_sha256"] != _rule_sha(rule):
            raise StyleLibraryError("qualified_rule_publication_invalid")
        payload = _normalize_rule_payload(
            json.loads(rule["rule_payload_json"]), taxonomy
        )
        if (
            payload["claim_kind"] != "contrastive_performance_hypothesis"
            or payload["performance_evidence_scope"]
            != "public_proxy_association"
        ):
            raise StyleLibraryError("qualified_rule_performance_scope_invalid")
        evidence = _read_rule_evidence_for_publication(con, rule_id)
        if any(
            row["performance_primary_job"]
            != archetype["primary_job_scope"]
            or row["performance_traffic_stage"] != payload["traffic_stage"]
            or row["performance_business_objective"] != "engagement_proxy"
            for row in evidence
        ):
            raise StyleLibraryError("qualified_rule_performance_scope_stale")
        evidence_preimages = [
            "|".join(
                str(row[key])
                for key in (
                    "rule_evidence_id",
                    "observation_type",
                    "observation_id",
                    "evidence_role",
                    "limitations",
                    "target_sha256",
                )
            )
            for row in evidence
        ]
        if (
            len(evidence) != rule["evidence_count"]
            or _ordered_bundle_sha(evidence_preimages)
            != rule["evidence_set_sha256"]
            or not _published_rule_evidence_is_current(
                con, rule_id, archetype["category_scope"]
            )
        ):
            raise StyleLibraryError("qualified_rule_evidence_stale")
        matching_type = "copy" if rule["rule_type"] == "copy" else "visual"
        matching_support = [
            row for row in evidence
            if row["observation_type"] == matching_type
            and row["evidence_role"] == "support"
            and row["performance_tier"] == "high"
            and row["visibility_scope"] == "public_proxy"
            and row["traffic_verdict"] == "not_applicable"
        ]
        matching_counter = [
            row for row in evidence
            if row["observation_type"] == matching_type
            and row["evidence_role"] in {"counterexample", "boundary"}
            and row["performance_tier"] in {"ordinary", "low"}
            and row["visibility_scope"] == "public_proxy"
            and row["traffic_verdict"] == "not_applicable"
        ]
        if (
            len({row["library_account_id"] for row in matching_support}) < 2
            or len(
                {
                    row["cluster_id"] for row in matching_support
                    if str(row["cluster_id"] or "").strip()
                }
            ) < 2
            or not matching_counter
        ):
            raise StyleLibraryError("qualified_rule_contrast_stale")
        support_posts = {
            row["library_post_id"] for row in evidence
            if row["evidence_role"] == "support"
        }
        counter_posts = {
            row["library_post_id"] for row in evidence
            if row["evidence_role"] in {"counterexample", "boundary"}
        }
        bundle_support_posts.update(support_posts)
        bundle_counter_posts.update(counter_posts)
        reviewed_rules.append((rule, evidence))
        rule_payloads.append(
            {
                "rule_id": rule_id,
                "rule_type": rule["rule_type"],
                "applicability_scope": rule["applicability_scope"],
                "payload": payload,
                "rule_sha256": rule["rule_sha256"],
                "evidence_set_sha256": rule["evidence_set_sha256"],
                "evidence": [
                    {
                        "rule_evidence_id": row["rule_evidence_id"],
                        "observation_type": row["observation_type"],
                        "observation_id": row["observation_id"],
                        "post_observation_id": row["post_observation_id"],
                        "library_post_id": row["library_post_id"],
                        "library_account_id": row["library_account_id"],
                        "cluster_id": row["cluster_id"],
                        "evidence_role": row["evidence_role"],
                        "limitations": row["limitations"],
                        "feature_link_sha256": row["feature_link_sha256"],
                        "source_asset_sha256": row["source_asset_sha256"],
                        "performance_tier": row["performance_tier"],
                        "feature_observation": _feature_observation_payload(
                            con, row["observation_type"], row["observation_id"]
                        ),
                    }
                    for row in evidence
                ],
            }
        )
    if bundle_support_posts & bundle_counter_posts:
        raise StyleLibraryError("qualified_bundle_evidence_role_conflict")
    if _rule_bundle_sha(reviewed_rules) != review["rule_bundle_sha256"]:
        raise StyleLibraryError("archetype_review_rule_bundle_stale")
    if _evidence_bundle_sha(reviewed_rules) != review["evidence_bundle_sha256"]:
        raise StyleLibraryError("archetype_review_evidence_bundle_stale")
    if _feature_link_set_sha(reviewed_rules) != qualification[
        "feature_link_set_sha256"
    ]:
        raise StyleLibraryError("qualification_feature_bundle_stale")
    return {
        "qualification_sha256": qualification["qualification_sha256"],
        "review_receipt_sha256": qualification["review_receipt_sha256"],
        "selected_rule_ids": selected_ids,
        "rules": rule_payloads,
        "reference_library_post_ids": sorted(bundle_support_posts),
        "counterexample_library_post_ids": sorted(bundle_counter_posts),
        "selected_asset_bundle_sha256": _selected_asset_bundle_sha(
            reviewed_rules
        ),
    }


def _validate_request_codes(
    values: Sequence[str], allowed: Sequence[str], error: str
) -> list[str]:
    normalized = sorted(set(values))
    if any(value not in allowed for value in normalized):
        raise StyleLibraryError(error)
    return normalized


def query_library(
    db_path: Path,
    *,
    category: str,
    carrier: str,
    primary_job: str,
    available_material_codes: Sequence[str],
    active_constraint_codes: Sequence[str],
    active_contraindication_codes: Sequence[str] = (),
    traffic_stage: str | None = None,
) -> dict[str, object]:
    """Retrieve published rules at exact category × carrier × job scope."""

    taxonomy = load_taxonomy()
    category = _require_text(category, "query_category_invalid")
    if carrier not in taxonomy["carrier"]:
        raise StyleLibraryError("query_carrier_invalid")
    if primary_job not in taxonomy["primary_job"]:
        raise StyleLibraryError("query_primary_job_invalid")
    if traffic_stage is not None and traffic_stage not in TRAFFIC_STAGES:
        raise StyleLibraryError("query_traffic_stage_invalid")
    materials = set(_validate_request_codes(
        available_material_codes, taxonomy["material_code"], "query_material_invalid"
    ))
    constraints = set(_validate_request_codes(
        active_constraint_codes,
        taxonomy["production_constraint_code"],
        "query_constraint_invalid",
    ))
    contraindications = set(_validate_request_codes(
        active_contraindication_codes,
        taxonomy["contraindication_code"],
        "query_contraindication_invalid",
    ))
    con = connect_db(db_path)
    try:
        candidate_rows = con.execute(
            "SELECT * FROM sanitized_style_ledger_entries ORDER BY observation_id"
        ).fetchall()
        archetype_rows = con.execute(
            """
            SELECT archetype.*,publication.archetype_snapshot_sha256
            FROM style_archetypes AS archetype
            JOIN archetype_publications AS publication
              ON publication.archetype_id=archetype.archetype_id
             AND publication.archetype_version=archetype.current_version
             AND publication.archetype_snapshot_sha256=archetype.snapshot_sha256
            ORDER BY archetype.archetype_id
            """
        ).fetchall()
        candidate_audit: list[dict[str, object]] = []
        published_audit: list[dict[str, object]] = []
        eligible_archetypes: list[dict[str, object]] = []
        exact_scope_n = 0
        for row in candidate_rows:
            reasons: list[str] = ["category_unverified"]
            if row["carrier"] != carrier:
                reasons.append("carrier_mismatch")
            if row["primary_job"] != primary_job:
                reasons.append("primary_job_mismatch")
            if traffic_stage is not None:
                if row["traffic_stage"] is None:
                    reasons.append("traffic_stage_unverified")
                elif row["traffic_stage"] != traffic_stage:
                    reasons.append("traffic_stage_mismatch")
            required_materials = set(json.loads(row["material_codes_json"]))
            required_constraints = set(
                json.loads(row["production_constraint_codes_json"])
            )
            reasons.extend(
                f"material_unavailable:{code}"
                for code in sorted(required_materials - materials)
            )
            reasons.extend(
                f"constraint_inactive:{code}"
                for code in sorted(required_constraints - constraints)
            )
            reasons.extend(
                ["qualification_ineligible_unverified", "not_published_qualified_rule"]
            )
            candidate_audit.append(
                {
                    "observation_id": row["observation_id"],
                    "carrier": row["carrier"],
                    "primary_job": row["primary_job"],
                    "traffic_stage": row["traffic_stage"],
                    "reason_codes": reasons,
                }
            )
        for archetype in archetype_rows:
            reasons: list[str] = []
            if archetype["category_scope"] != category:
                reasons.append("category_mismatch")
            if archetype["carrier"] != carrier:
                reasons.append("carrier_mismatch")
            if archetype["primary_job_scope"] != primary_job:
                reasons.append("primary_job_mismatch")
            if archetype["status"] not in {"supported", "reusable"}:
                reasons.append("archetype_not_supported")
            if reasons:
                published_audit.append(
                    {
                        "archetype_id": archetype["archetype_id"],
                        "reason_codes": reasons,
                    }
                )
                continue
            exact_scope_n += 1
            try:
                bundle = _load_current_qualified_bundle(con, archetype, taxonomy)
            except (json.JSONDecodeError, StyleLibraryError) as exc:
                published_audit.append(
                    {
                        "archetype_id": archetype["archetype_id"],
                        "reason_codes": [
                            f"qualified_bundle_unavailable:{exc}"
                        ],
                    }
                )
                continue
            selected: list[dict[str, object]] = []
            rule_rejections: list[str] = []
            required_rejections: list[str] = []
            for rule in bundle["rules"]:
                payload = rule["payload"]
                rule_reasons: list[str] = []
                if traffic_stage is not None and payload["traffic_stage"] != traffic_stage:
                    rule_reasons.append("traffic_stage_mismatch")
                rule_reasons.extend(
                    f"material_unavailable:{code}"
                    for code in sorted(
                        set(payload["required_material_codes"]) - materials
                    )
                )
                rule_reasons.extend(
                    f"constraint_inactive:{code}"
                    for code in sorted(
                        set(payload["required_constraint_codes"]) - constraints
                    )
                )
                rule_reasons.extend(
                    f"contraindication_active:{code}"
                    for code in sorted(
                        set(payload["contraindication_codes"]) & contraindications
                    )
                )
                if rule_reasons:
                    tagged = [
                        f"{reason}@{rule['rule_id']}" for reason in rule_reasons
                    ]
                    rule_rejections.extend(tagged)
                    if payload["selection_requirement"] == "required":
                        required_rejections.extend(tagged)
                    continue
                selected.append(rule)
            changed = True
            while changed:
                changed = False
                selected_ids_now = {rule["rule_id"] for rule in selected}
                for rule in list(selected):
                    missing = sorted(
                        set(rule["payload"]["dependency_rule_ids"])
                        - selected_ids_now
                    )
                    if not missing:
                        continue
                    tagged = [
                        f"dependency_unavailable:{dependency}@{rule['rule_id']}"
                        for dependency in missing
                    ]
                    rule_rejections.extend(tagged)
                    if rule["payload"]["selection_requirement"] == "required":
                        required_rejections.extend(tagged)
                    else:
                        selected.remove(rule)
                        changed = True
            if required_rejections:
                published_audit.append(
                    {
                        "archetype_id": archetype["archetype_id"],
                        "reason_codes": sorted(set(required_rejections)),
                    }
                )
                continue
            selected_types = {rule["rule_type"] for rule in selected}
            coverage_rejections: list[str] = []
            if "copy" not in selected_types:
                coverage_rejections.append("eligible_copy_rule_missing")
            if not (selected_types & VISUAL_RULE_TYPES):
                coverage_rejections.append("eligible_visual_rule_missing")
            if coverage_rejections:
                published_audit.append(
                    {
                        "archetype_id": archetype["archetype_id"],
                        "reason_codes": sorted(
                            set(rule_rejections + coverage_rejections)
                        ),
                    }
                )
                continue
            selected_ids = [rule["rule_id"] for rule in selected]
            reference_posts = sorted(
                {
                    evidence["library_post_id"]
                    for rule in selected
                    for evidence in rule["evidence"]
                    if evidence["evidence_role"] == "support"
                }
            )
            counter_posts = sorted(
                {
                    evidence["library_post_id"]
                    for rule in selected
                    for evidence in rule["evidence"]
                    if evidence["evidence_role"] in {"counterexample", "boundary"}
                }
            )
            if (
                not reference_posts
                or not counter_posts
                or set(reference_posts) & set(counter_posts)
            ):
                published_audit.append(
                    {
                        "archetype_id": archetype["archetype_id"],
                        "reason_codes": ["published_association_roles_invalid"],
                    }
                )
                continue
            eligible_archetypes.append(
                {
                    "archetype_id": archetype["archetype_id"],
                    "archetype_version": archetype["current_version"],
                    "archetype_snapshot_sha256": archetype["snapshot_sha256"],
                    "category": archetype["category_scope"],
                    "carrier": archetype["carrier"],
                    "primary_job": archetype["primary_job_scope"],
                    "selected_rule_ids": selected_ids,
                    "selected_rules": selected,
                    "rule_types": sorted(selected_types),
                    "reference_library_post_ids": reference_posts,
                    "counterexample_library_post_ids": counter_posts,
                    "performance_evidence_scope": "public_proxy_association",
                    "qualification_sha256": bundle["qualification_sha256"],
                    "review_receipt_sha256": bundle["review_receipt_sha256"],
                    "per_rule_evidence_associations": {
                        rule["rule_id"]: [
                            {
                                "library_post_id": evidence["library_post_id"],
                                "evidence_role": evidence["evidence_role"],
                                "feature_link_sha256": evidence[
                                    "feature_link_sha256"
                                ],
                            }
                            for evidence in rule["evidence"]
                        ]
                        for rule in selected
                    },
                    "required_material_codes": sorted(
                        {
                            code
                            for rule in selected
                            for code in rule["payload"]["required_material_codes"]
                        }
                    ),
                    "required_constraint_codes": sorted(
                        {
                            code
                            for rule in selected
                            for code in rule["payload"]["required_constraint_codes"]
                        }
                    ),
                    "contraindication_codes": sorted(
                        {
                            code
                            for rule in selected
                            for code in rule["payload"]["contraindication_codes"]
                        }
                    ),
                    "excluded_rule_reasons": sorted(set(rule_rejections)),
                }
            )
    finally:
        con.close()
    status = "ready_to_bind" if eligible_archetypes else "needs_style_research"
    return {
        "status": status,
        "requested_scope": {
            "category": category,
            "carrier": carrier,
            "primary_job": primary_job,
            "traffic_stage": traffic_stage,
            "available_material_codes": sorted(materials),
            "active_constraint_codes": sorted(constraints),
            "active_contraindication_codes": sorted(contraindications),
        },
        "candidate_count": len(candidate_audit),
        "exact_scope_candidate_count": exact_scope_n,
        "eligible_count": len(eligible_archetypes),
        "eligible_archetypes": eligible_archetypes,
        "rejection_audit": candidate_audit,
        "published_rejection_audit": published_audit,
        "checkpoint": None if eligible_archetypes else (
            "publish an exact-scope multimodal rule bundle or supply its "
            "required materials/constraints; candidate rows never bind drafts"
        ),
        "performance_claim_boundary": (
            "not_performance_evidence or public_proxy_association; "
            "never an unlinked first-party traffic claim"
        ),
    }


def bind_draft(
    db_path: Path,
    *,
    draft_id: str,
    draft_binding_id: str,
    category: str,
    carrier: str,
    primary_job: str,
    business_objective: str,
    available_material_codes: Sequence[str],
    active_constraint_codes: Sequence[str],
    active_contraindication_codes: Sequence[str] = (),
    traffic_stage: str | None = None,
    archetype_id: str | None = None,
) -> dict[str, object]:
    if not draft_id.strip():
        raise StyleLibraryError("draft_id_invalid")
    if not draft_binding_id.strip():
        raise StyleLibraryError("draft_binding_id_invalid")
    if business_objective not in {"traffic_first", "engagement_proxy"}:
        raise StyleLibraryError("business_objective_invalid")
    result = query_library(
        db_path,
        category=category,
        carrier=carrier,
        primary_job=primary_job,
        available_material_codes=available_material_codes,
        active_constraint_codes=active_constraint_codes,
        active_contraindication_codes=active_contraindication_codes,
        traffic_stage=traffic_stage,
    )
    eligible = result["eligible_archetypes"]
    if archetype_id is not None:
        eligible = [row for row in eligible if row["archetype_id"] == archetype_id]
    if not eligible:
        raise StyleLibraryError("no_published_qualified_rule")
    if len(eligible) != 1:
        raise StyleLibraryError("eligible_archetype_ambiguous")
    selected = eligible[0]
    primary_candidates = sorted(
        selected["selected_rules"],
        key=lambda rule: (
            0 if rule["rule_type"] in {"cover", "visual"} else 1,
            rule["rule_id"],
        ),
    )
    if not primary_candidates:
        raise StyleLibraryError("primary_performance_rule_missing")
    primary_performance_rule = primary_candidates[0]
    if (
        business_objective == "traffic_first"
        and (
            primary_performance_rule["payload"]["claim_kind"]
            != "contrastive_performance_hypothesis"
            or primary_performance_rule["payload"]["performance_evidence_scope"]
            != "public_proxy_association"
        )
    ):
        raise StyleLibraryError("traffic_first_primary_contrastive_rule_missing")
    materials = sorted(set(available_material_codes))
    constraints = sorted(set(active_constraint_codes))
    contraindications = sorted(set(active_contraindication_codes))
    material_plan = {
        "category": category,
        "carrier": carrier,
        "primary_job": primary_job,
        "traffic_stage": traffic_stage,
        "business_objective": business_objective,
        "available_material_codes": materials,
        "required_material_codes": selected["required_material_codes"],
        "required_constraint_codes": selected["required_constraint_codes"],
        "active_constraint_codes": constraints,
        "active_contraindication_codes": contraindications,
        "performance_evidence_scope": selected["performance_evidence_scope"],
        "primary_performance_rule_id": primary_performance_rule["rule_id"],
        "primary_performance_evidence_scope": primary_performance_rule[
            "payload"
        ]["performance_evidence_scope"],
    }
    con = connect_db(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            """
            INSERT INTO draft_style_bindings(
                draft_binding_id,draft_id,binding_source,archetype_id,
                binding_role,archetype_version,archetype_snapshot_sha256,
                selected_rule_ids,reference_library_post_ids,
                counterexample_library_post_ids,material_plan_json,
                intentional_deviations_json,anti_patterns_checked_json,
                review_status
            ) VALUES (?,?,'library',?,'primary',?,?,?,?,?,?,'[]',?,'pending')
            """,
            (
                draft_binding_id,
                draft_id,
                selected["archetype_id"],
                selected["archetype_version"],
                selected["archetype_snapshot_sha256"],
                _canonical_json(selected["selected_rule_ids"]),
                _canonical_json(selected["reference_library_post_ids"]),
                _canonical_json(selected["counterexample_library_post_ids"]),
                _canonical_json(material_plan),
                _canonical_json(contraindications),
            ),
        )
        binding = con.execute(
            "SELECT * FROM draft_style_bindings WHERE draft_binding_id=?",
            (draft_binding_id,),
        ).fetchone()
        pending_sha = _draft_binding_sha256(binding)
        con.commit()
        return {
            "status": "binding_created_pending_review",
            "draft_binding_id": draft_binding_id,
            "draft_id": draft_id,
            "archetype_id": selected["archetype_id"],
            "archetype_version": selected["archetype_version"],
            "archetype_snapshot_sha256": selected["archetype_snapshot_sha256"],
            "selected_rule_ids": selected["selected_rule_ids"],
            "selected_rules": selected["selected_rules"],
            "qualification_sha256": selected["qualification_sha256"],
            "pending_binding_sha256": pending_sha,
            "material_plan": material_plan,
        }
    except sqlite3.Error as exc:
        if con.in_transaction:
            con.rollback()
        raise StyleLibraryError("draft_binding_create_failed") from exc
    finally:
        con.close()


def _draft_binding_sha256(
    row: sqlite3.Row, review_status: str | None = None
) -> str:
    return _canonical_row_sha256_v2(
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
        _canonical_json(json.loads(row["selected_rule_ids"])),
        _canonical_json(json.loads(row["reference_library_post_ids"])),
        _canonical_json(json.loads(row["counterexample_library_post_ids"])),
        _canonical_json(json.loads(row["material_plan_json"])),
        _canonical_json(json.loads(row["intentional_deviations_json"])),
        _canonical_json(json.loads(row["anti_patterns_checked_json"])),
        row["review_status"] if review_status is None else review_status,
    )


def _binding_grounding_snapshot(
    con: sqlite3.Connection, binding: sqlite3.Row
) -> dict[str, str]:
    taxonomy = load_taxonomy()
    archetype = con.execute(
        """
        SELECT * FROM style_archetypes
        WHERE archetype_id=? AND current_version=? AND snapshot_sha256=?
          AND status IN ('supported','reusable')
        """,
        (
            binding["archetype_id"],
            binding["archetype_version"],
            binding["archetype_snapshot_sha256"],
        ),
    ).fetchone()
    if archetype is None:
        raise StyleLibraryError("binding_archetype_not_current")
    bundle = _load_current_qualified_bundle(con, archetype, taxonomy)
    selected_ids = json.loads(binding["selected_rule_ids"])
    if (
        not isinstance(selected_ids, list)
        or selected_ids != sorted(set(selected_ids))
        or not set(selected_ids).issubset(bundle["selected_rule_ids"])
    ):
        raise StyleLibraryError("binding_selected_rule_set_invalid")
    selected_rules = [
        rule for rule in bundle["rules"] if rule["rule_id"] in selected_ids
    ]
    selected_by_id = {rule["rule_id"]: rule for rule in selected_rules}
    material_plan = json.loads(binding["material_plan_json"])
    primary_rule_id = material_plan.get("primary_performance_rule_id")
    if primary_rule_id not in selected_by_id:
        raise StyleLibraryError("binding_primary_performance_rule_invalid")
    primary_scope = selected_by_id[primary_rule_id]["payload"][
        "performance_evidence_scope"
    ]
    if (
        material_plan.get("performance_evidence_scope") != primary_scope
        or material_plan.get("primary_performance_evidence_scope")
        != primary_scope
    ):
        raise StyleLibraryError("binding_performance_scope_mismatch")
    reference_posts = sorted(
        {
            evidence["library_post_id"]
            for rule in selected_rules
            for evidence in rule["evidence"]
            if evidence["evidence_role"] == "support"
        }
    )
    counter_posts = sorted(
        {
            evidence["library_post_id"]
            for rule in selected_rules
            for evidence in rule["evidence"]
            if evidence["evidence_role"] in {"counterexample", "boundary"}
        }
    )
    if (
        reference_posts != json.loads(binding["reference_library_post_ids"])
        or counter_posts
        != json.loads(binding["counterexample_library_post_ids"])
        or set(reference_posts) & set(counter_posts)
    ):
        raise StyleLibraryError("binding_evidence_association_mismatch")
    asset_bundle_sha = _ordered_bundle_sha(
        [
            item[2]
            for item in sorted(
                (
                    str(rule["rule_id"]),
                    str(evidence["rule_evidence_id"]),
                    f"{rule['rule_id']}|{evidence['rule_evidence_id']}|"
                    f"{evidence['source_asset_sha256']}",
                )
                for rule in selected_rules
                for evidence in rule["evidence"]
            )
        ]
    )
    grounding_sha = _canonical_row_sha256_v2(
        bundle["qualification_sha256"],
        binding["archetype_snapshot_sha256"],
        _canonical_json(selected_ids),
        _canonical_json(material_plan),
        asset_bundle_sha,
    )
    return {
        "qualification_sha256": str(bundle["qualification_sha256"]),
        "selected_asset_bundle_sha256": asset_bundle_sha,
        "grounding_snapshot_sha256": grounding_sha,
    }


def review_draft_binding(
    db_path: Path, record: dict[str, object]
) -> dict[str, object]:
    """Promote a pending binding only after independent preimage review."""

    required = {
        "draft_binding_id",
        "decision",
        "expected_pending_binding_sha256",
        "content_owner_id",
        "reviewer_ids",
        "reviewer_independence_status",
        "reviewed_at",
    }
    if not isinstance(record, dict) or set(record) != required:
        raise StyleLibraryError("binding_review_record_invalid")
    binding_id = _require_text(
        record.get("draft_binding_id"), "binding_review_record_invalid"
    )
    owner = _require_text(
        record.get("content_owner_id"), "binding_review_record_invalid"
    )
    reviewed_at = _require_text(
        record.get("reviewed_at"), "binding_review_record_invalid"
    )
    try:
        reviewed_on = date.fromisoformat(reviewed_at)
    except ValueError as exc:
        raise StyleLibraryError("binding_review_date_invalid") from exc
    if reviewed_on > date.today():
        raise StyleLibraryError("binding_review_date_invalid")
    expected_sha = record.get("expected_pending_binding_sha256")
    if not _is_sha256(expected_sha):
        raise StyleLibraryError("binding_review_record_invalid")
    if record.get("decision") != "PASS":
        raise StyleLibraryError("binding_review_not_pass")
    if record.get("reviewer_independence_status") != "independent":
        raise StyleLibraryError("reviewer_not_independent")
    reviewers = _require_string_list(
        record.get("reviewer_ids"), "binding_review_record_invalid"
    )
    if owner in reviewers:
        raise StyleLibraryError("reviewer_not_independent")
    con = connect_db(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        binding = con.execute(
            "SELECT * FROM draft_style_bindings WHERE draft_binding_id=?",
            (binding_id,),
        ).fetchone()
        if binding is None:
            raise StyleLibraryError("draft_binding_not_found")
        if binding["review_status"] != "pending":
            raise StyleLibraryError("draft_binding_not_pending")
        if _draft_binding_sha256(binding) != expected_sha:
            raise StyleLibraryError("binding_review_preimage_mismatch")
        grounding = _binding_grounding_snapshot(con, binding)
        reviewed_sha = _draft_binding_sha256(binding, "PASS")
        reviewer_json = _canonical_json(reviewers)
        review_sha = _canonical_row_sha256_v2(
            binding_id,
            binding["draft_id"],
            expected_sha,
            reviewed_sha,
            grounding["qualification_sha256"],
            grounding["selected_asset_bundle_sha256"],
            grounding["grounding_snapshot_sha256"],
            "PASS",
            owner,
            reviewer_json,
            "independent",
            reviewed_at,
        )
        con.execute(
            """
            INSERT INTO draft_binding_review_receipts(
                review_receipt_sha256,draft_binding_id,draft_id,
                expected_pending_binding_sha256,reviewed_binding_sha256,
                qualification_sha256,selected_asset_bundle_sha256,
                grounding_snapshot_sha256,decision,content_owner_id,
                reviewer_ids,reviewer_independence_status,reviewed_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                review_sha,
                binding_id,
                binding["draft_id"],
                expected_sha,
                reviewed_sha,
                grounding["qualification_sha256"],
                grounding["selected_asset_bundle_sha256"],
                grounding["grounding_snapshot_sha256"],
                "PASS",
                owner,
                reviewer_json,
                "independent",
                reviewed_at,
            ),
        )
        con.execute(
            """
            UPDATE draft_style_bindings SET review_status='PASS'
            WHERE draft_binding_id=? AND review_status='pending'
            """,
            (binding_id,),
        )
        reviewed = con.execute(
            "SELECT * FROM draft_style_bindings WHERE draft_binding_id=?",
            (binding_id,),
        ).fetchone()
        if _draft_binding_sha256(reviewed) != reviewed_sha:
            raise StyleLibraryError("binding_review_postimage_mismatch")
        con.commit()
        return {
            "status": "review_pass",
            "draft_binding_id": binding_id,
            "reviewed_binding_sha256": reviewed_sha,
            "review_receipt_sha256": review_sha,
            "review_receipt_storage": "draft_binding_review_receipts",
            "grounding_snapshot_sha256": grounding[
                "grounding_snapshot_sha256"
            ],
        }
    except StyleLibraryError:
        if con.in_transaction:
            con.rollback()
        raise
    except sqlite3.Error as exc:
        if con.in_transaction:
            con.rollback()
        raise StyleLibraryError("binding_review_failed") from exc
    finally:
        con.close()


def _binding_review_receipt(
    con: sqlite3.Connection, binding: sqlite3.Row
) -> str:
    rows = con.execute(
        """
        SELECT * FROM draft_binding_review_receipts
        WHERE draft_binding_id=? ORDER BY review_receipt_sha256
        """,
        (binding["draft_binding_id"],),
    ).fetchall()
    if len(rows) != 1:
        raise StyleLibraryError("binding_review_receipt_missing")
    try:
        reviewer_json = _canonical_json(json.loads(rows[0]["reviewer_ids"]))
    except (json.JSONDecodeError, TypeError) as exc:
        raise StyleLibraryError("binding_review_receipt_invalid") from exc
    grounding = _binding_grounding_snapshot(con, binding)
    expected_receipt_sha = _canonical_row_sha256_v2(
        binding["draft_binding_id"],
        binding["draft_id"],
        _draft_binding_sha256(binding, "pending"),
        _draft_binding_sha256(binding, "PASS"),
        grounding["qualification_sha256"],
        grounding["selected_asset_bundle_sha256"],
        grounding["grounding_snapshot_sha256"],
        "PASS",
        rows[0]["content_owner_id"],
        reviewer_json,
        "independent",
        rows[0]["reviewed_at"],
    )
    if (
        rows[0]["review_receipt_sha256"] != expected_receipt_sha
        or rows[0]["expected_pending_binding_sha256"]
        != _draft_binding_sha256(binding, "pending")
        or rows[0]["reviewed_binding_sha256"]
        != _draft_binding_sha256(binding, "PASS")
        or rows[0]["qualification_sha256"]
        != grounding["qualification_sha256"]
        or rows[0]["selected_asset_bundle_sha256"]
        != grounding["selected_asset_bundle_sha256"]
        or rows[0]["grounding_snapshot_sha256"]
        != grounding["grounding_snapshot_sha256"]
    ):
        raise StyleLibraryError("binding_review_receipt_invalid")
    return expected_receipt_sha


def publish_draft_binding(
    db_path: Path, draft_binding_id: str
) -> dict[str, object]:
    """Finalize one exact binding into an immutable, hash-checked receipt."""

    if not draft_binding_id.strip():
        raise StyleLibraryError("draft_binding_id_invalid")
    con = connect_db(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        binding = con.execute(
            "SELECT * FROM draft_style_bindings WHERE draft_binding_id=?",
            (draft_binding_id,),
        ).fetchone()
        if binding is None:
            raise StyleLibraryError("draft_binding_not_found")
        if binding["review_status"] != "PASS":
            raise StyleLibraryError("draft_binding_review_not_pass")
        review_sha = _binding_review_receipt(con, binding)
        binding_sha256 = _draft_binding_sha256(binding)
        existing = con.execute(
            """
            SELECT binding_sha256 FROM draft_binding_publications
            WHERE draft_binding_id=?
            """,
            (draft_binding_id,),
        ).fetchone()
        if existing is None:
            con.execute(
                """
                INSERT INTO draft_binding_publications(
                    draft_binding_id,draft_id,binding_sha256
                ) VALUES (?,?,?)
                """,
                (draft_binding_id, binding["draft_id"], binding_sha256),
            )
            status = "published"
        elif existing["binding_sha256"] == binding_sha256:
            status = "idempotent"
        else:
            raise StyleLibraryError("draft_binding_publication_conflict")
        con.commit()
        return {
            "status": status,
            "draft_binding_id": draft_binding_id,
            "draft_id": binding["draft_id"],
            "binding_sha256": binding_sha256,
            "review_receipt_sha256": review_sha,
            "review_receipt_storage": "draft_binding_review_receipts",
        }
    except StyleLibraryError:
        con.rollback()
        raise
    except (json.JSONDecodeError, sqlite3.Error) as exc:
        con.rollback()
        raise StyleLibraryError("draft_binding_publication_failed") from exc
    finally:
        con.close()


def derive_tier(
    db_path: Path, post_observation_id: str, baseline_snapshot_id: str
) -> dict[str, object]:
    """Derive relative tier from one closed baseline without target leakage."""

    con = connect_db(db_path)
    try:
        target = con.execute(
            """
            SELECT observation.*, post.library_post_id AS target_library_post_id,
                   metric.metric_value AS target_metric_value,
                   metric.metric_sha256 AS target_metric_sha256,
                   metric.visibility_scope, definition.business_objective,
                   definition.primary_job,
                   definition.traffic_stage AS definition_traffic_stage,
                   definition.tier_rules_json,
                   definition.definition_sha256
            FROM style_post_observations AS observation
            JOIN style_posts AS post
              ON post.library_post_id=observation.library_post_id
            JOIN post_metrics AS metric
              ON metric.post_metric_id=observation.target_post_metric_id
             AND metric.post_observation_id=observation.post_observation_id
             AND metric.metric_name=observation.target_metric_name
            JOIN performance_definitions AS definition
              ON definition.performance_definition_id=observation.performance_definition_id
             AND definition.metric_name=observation.target_metric_name
            WHERE observation.post_observation_id=?
              AND observation.observation_state='complete'
            """,
            (post_observation_id,),
        ).fetchone()
        if target is None:
            raise StyleLibraryError("target_observation_not_complete")
        publication = con.execute(
            """
            SELECT publication.*, snapshot.sample_n, snapshot.median_value
            FROM baseline_snapshot_publications AS publication
            JOIN account_baseline_snapshots AS snapshot
              ON snapshot.baseline_snapshot_id=publication.baseline_snapshot_id
            WHERE publication.baseline_snapshot_id=?
              AND publication.library_account_id=?
              AND publication.performance_definition_id=?
              AND publication.metric_name=?
            """,
            (
                baseline_snapshot_id, target["library_account_id"],
                target["performance_definition_id"], target["target_metric_name"],
            ),
        ).fetchone()
        if publication is None:
            raise StyleLibraryError("published_baseline_not_found")
        if (
            target["baseline_snapshot_id"] != baseline_snapshot_id
            or target["baseline_snapshot_sha256"]
            != publication["baseline_snapshot_sha256"]
        ):
            raise StyleLibraryError("target_baseline_binding_mismatch")
        members = con.execute(
            """
            SELECT member.member_post_observation_id,member.member_post_metric_id,
                   observation.library_post_id,metric.visibility_scope
            FROM account_baseline_members AS member
            JOIN style_post_observations AS observation
              ON observation.post_observation_id=member.member_post_observation_id
            JOIN post_metrics AS metric
              ON metric.post_metric_id=member.member_post_metric_id
            WHERE member.baseline_snapshot_id=?
              AND member.inclusion_status='included'
            ORDER BY member.member_ordinal
            """,
            (baseline_snapshot_id,),
        ).fetchall()
        if any(
            member["library_post_id"] == target["target_library_post_id"]
            for member in members
        ):
            raise StyleLibraryError("baseline_target_post_contamination")
        objective = target["business_objective"]
        metric_name = target["target_metric_name"]
        visibility = target["visibility_scope"]
        if objective == "traffic_first":
            if (
                target["primary_job"] != "feed_stop"
                or target["definition_traffic_stage"] != "feed_stop"
                or metric_name not in {"impressions", "reach"}
                or visibility != "first_party_analytics"
                or any(m["visibility_scope"] != "first_party_analytics" for m in members)
            ):
                raise StyleLibraryError("traffic_definition_invalid")
            traffic_stage: str | None = "feed_stop"
        elif objective == "engagement_proxy":
            if (
                metric_name != "engagement_proxy"
                or visibility != "public_proxy"
                or any(m["visibility_scope"] != "public_proxy" for m in members)
            ):
                raise StyleLibraryError("public_proxy_definition_invalid")
            traffic_stage = None
        else:
            raise StyleLibraryError("business_objective_invalid")
        median_value = publication["median_value"]
        if median_value is None or float(median_value) <= 0:
            raise StyleLibraryError("baseline_median_invalid")
        try:
            rules = json.loads(target["tier_rules_json"])
            high_min = float(rules["high_min_multiple"])
            low_max = float(rules["low_max_multiple"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise StyleLibraryError("tier_rules_invalid") from exc
        if not high_min > 1 or not 0 <= low_max < 1:
            raise StyleLibraryError("tier_rules_invalid")
        if float(target["target_metric_value"]) < 0:
            raise StyleLibraryError("target_metric_invalid")
        multiple = float(target["target_metric_value"]) / float(median_value)
        tier = "high" if multiple >= high_min else "low" if multiple <= low_max else "ordinary"
        traffic_verdict = (
            "not_applicable"
            if visibility == "public_proxy"
            else "win" if tier == "high" else "loss" if tier == "low" else "inconclusive"
        )
        computation = {
            "post_observation_id": post_observation_id,
            "baseline_snapshot_id": baseline_snapshot_id,
            "baseline_snapshot_sha256": publication["baseline_snapshot_sha256"],
            "definition_sha256": target["definition_sha256"],
            "metric_name": metric_name,
            "target_metric_value": target["target_metric_value"],
            "median_value": median_value,
            "multiple": multiple,
            "performance_tier": tier,
        }
        computation_sha256 = _performance_computation_sha256_v2(
            post_observation_id,
            baseline_snapshot_id,
            publication["baseline_snapshot_sha256"],
            target["definition_sha256"],
            metric_name,
            target["target_metric_value"],
            median_value,
            multiple,
            tier,
        )
        if not target["target_metric_sha256"]:
            raise StyleLibraryError("target_metric_hash_missing")
        con.execute("BEGIN IMMEDIATE")
        existing = con.execute(
            """
            SELECT performance_computation_sha256
            FROM post_performance_publications
            WHERE post_observation_id=?
            """,
            (post_observation_id,),
        ).fetchone()
        if existing is None:
            con.execute(
                """
                INSERT INTO post_performance_publications(
                    post_observation_id,library_account_id,
                    baseline_snapshot_id,baseline_snapshot_sha256,
                    performance_definition_id,definition_sha256,metric_name,
                    target_post_metric_id,target_metric_sha256,
                    target_metric_value,baseline_median_value,
                    account_baseline_multiple,performance_tier,
                    performance_computation_sha256,visibility_scope,
                    traffic_stage,traffic_verdict
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    post_observation_id,
                    target["library_account_id"],
                    baseline_snapshot_id,
                    publication["baseline_snapshot_sha256"],
                    target["performance_definition_id"],
                    target["definition_sha256"],
                    metric_name,
                    target["target_post_metric_id"],
                    target["target_metric_sha256"],
                    target["target_metric_value"],
                    median_value,
                    multiple,
                    tier,
                    computation_sha256,
                    visibility,
                    traffic_stage,
                    traffic_verdict,
                ),
            )
        elif existing["performance_computation_sha256"] != computation_sha256:
            raise StyleLibraryError("performance_publication_conflict")
        con.commit()
        return {
            "status": "derived",
            **computation,
            "performance_computation_sha256": computation_sha256,
            "visibility_scope": visibility,
            "traffic_stage": traffic_stage,
            "traffic_verdict": traffic_verdict,
        }
    except StyleLibraryError:
        if con.in_transaction:
            con.rollback()
        raise
    except sqlite3.Error as exc:
        if con.in_transaction:
            con.rollback()
        raise StyleLibraryError("performance_derivation_failed") from exc
    finally:
        con.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init", help="initialize a v2 style database")
    init_parser.add_argument("db", type=Path)
    status_parser = subparsers.add_parser("status", help="show evidence readiness")
    status_parser.add_argument("db", type=Path)
    ingest_parser = subparsers.add_parser(
        "ingest-ledger", help="import sanitized candidate-only observation JSONL"
    )
    ingest_parser.add_argument("db", type=Path)
    ingest_parser.add_argument("jsonl", type=Path)
    derive_parser = subparsers.add_parser(
        "derive-tier", help="derive a tier from a published baseline"
    )
    derive_parser.add_argument("db", type=Path)
    derive_parser.add_argument("--post-observation-id", required=True)
    derive_parser.add_argument("--baseline-snapshot-id", required=True)
    publish_binding_parser = subparsers.add_parser(
        "publish-binding", help="publish one exact draft binding receipt"
    )
    publish_binding_parser.add_argument("db", type=Path)
    publish_binding_parser.add_argument("--draft-binding-id", required=True)
    for command, help_text in (
        ("create-archetype", "create a candidate from typed SQLite observations"),
        ("review-archetype", "recompute an independent archetype review"),
        ("publish-archetype", "promote and publish a reviewed archetype"),
        ("review-binding", "independently review an exact pending binding"),
    ):
        record_parser = subparsers.add_parser(command, help=help_text)
        record_parser.add_argument("db", type=Path)
        record_parser.add_argument("--record", required=True, type=Path)
    for command in ("query", "bind"):
        query_parser = subparsers.add_parser(command)
        query_parser.add_argument("db", type=Path)
        query_parser.add_argument("--category", required=True)
        query_parser.add_argument("--carrier", required=True)
        query_parser.add_argument("--primary-job", required=True)
        query_parser.add_argument("--traffic-stage", choices=sorted(TRAFFIC_STAGES))
        query_parser.add_argument("--materials", default="")
        query_parser.add_argument("--constraints", default="")
        query_parser.add_argument("--contraindications", default="")
        if command == "bind":
            query_parser.add_argument("--draft-id", required=True)
            query_parser.add_argument("--draft-binding-id", required=True)
            query_parser.add_argument("--archetype-id")
            query_parser.add_argument(
                "--business-objective",
                required=True,
                choices=("traffic_first", "engagement_proxy"),
            )
    return parser


def _split_cli_codes(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            result = init_db(args.db)
        elif args.command == "status":
            result = status_db(args.db)
        elif args.command == "ingest-ledger":
            result = ingest_ledger(args.db, args.jsonl)
        elif args.command == "derive-tier":
            result = derive_tier(
                args.db, args.post_observation_id, args.baseline_snapshot_id
            )
        elif args.command == "publish-binding":
            result = publish_draft_binding(args.db, args.draft_binding_id)
        elif args.command == "create-archetype":
            result = create_archetype_candidate(
                args.db,
                _load_json_record(args.record, "candidate_record_load_failed"),
            )
        elif args.command == "review-archetype":
            result = review_archetype(
                args.db,
                _load_json_record(args.record, "archetype_review_load_failed"),
            )
        elif args.command == "publish-archetype":
            result = publish_archetype(
                args.db,
                _load_json_record(args.record, "archetype_review_load_failed"),
            )
        elif args.command == "review-binding":
            result = review_draft_binding(
                args.db,
                _load_json_record(args.record, "binding_review_load_failed"),
            )
        elif args.command == "query":
            result = query_library(
                args.db,
                category=args.category,
                carrier=args.carrier,
                primary_job=args.primary_job,
                traffic_stage=args.traffic_stage,
                available_material_codes=_split_cli_codes(args.materials),
                active_constraint_codes=_split_cli_codes(args.constraints),
                active_contraindication_codes=_split_cli_codes(
                    args.contraindications
                ),
            )
        elif args.command == "bind":
            result = bind_draft(
                args.db,
                draft_id=args.draft_id,
                draft_binding_id=args.draft_binding_id,
                archetype_id=args.archetype_id,
                category=args.category,
                carrier=args.carrier,
                primary_job=args.primary_job,
                business_objective=args.business_objective,
                traffic_stage=args.traffic_stage,
                available_material_codes=_split_cli_codes(args.materials),
                active_constraint_codes=_split_cli_codes(args.constraints),
                active_contraindication_codes=_split_cli_codes(
                    args.contraindications
                ),
            )
        else:  # pragma: no cover - argparse constrains commands.
            raise StyleLibraryError("unsupported_command")
    except StyleLibraryError as exc:
        print(
            json.dumps({"status": "error", "error": str(exc)}, sort_keys=True),
            file=sys.stderr,
        )
        return 1

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 2 if result.get("status") == "needs_style_research" else 0


if __name__ == "__main__":
    raise SystemExit(main())
