PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS style_schema_metadata (
    singleton INTEGER PRIMARY KEY NOT NULL CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 2),
    schema_revision TEXT NOT NULL CHECK (
        schema_revision = '2.2-qualified-promotion'
    )
) STRICT;

INSERT OR IGNORE INTO style_schema_metadata(
    singleton, schema_version, schema_revision
) VALUES (1, 2, '2.2-qualified-promotion');

CREATE TABLE IF NOT EXISTS style_accounts (
    library_account_id TEXT PRIMARY KEY NOT NULL,
    platform TEXT NOT NULL,
    platform_account_id TEXT,
    profile_url TEXT,
    identity_confidence REAL NOT NULL DEFAULT 1.0
        CHECK (identity_confidence >= 0.0 AND identity_confidence <= 1.0),
    first_seen_at TEXT,
    last_seen_at TEXT
) STRICT;

CREATE UNIQUE INDEX IF NOT EXISTS ux_style_accounts_platform_identity
    ON style_accounts(platform, platform_account_id)
    WHERE platform_account_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS style_assets (
    asset_id TEXT PRIMARY KEY NOT NULL,
    asset_kind TEXT NOT NULL
        CHECK (asset_kind IN ('image', 'caption', 'ocr', 'thumbnail', 'generated')),
    source_url TEXT,
    asset_path TEXT,
    asset_sha256 TEXT NOT NULL UNIQUE,
    mime_type TEXT,
    width INTEGER CHECK (width IS NULL OR width >= 0),
    height INTEGER CHECK (height IS NULL OR height >= 0),
    collected_at TEXT,
    access_status TEXT NOT NULL DEFAULT 'available',
    observation_method TEXT NOT NULL DEFAULT 'direct',
    copyright_notes TEXT NOT NULL DEFAULT '',
    sensitivity TEXT NOT NULL DEFAULT 'unknown',
    retention_until TEXT,
    derivative_of TEXT,
    FOREIGN KEY (derivative_of) REFERENCES style_assets(asset_id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CHECK (derivative_of IS NULL OR derivative_of <> asset_id),
    CHECK (
        asset_path IS NULL
        OR (
            (asset_path GLOB 'raw/*' OR asset_path GLOB 'derived/*')
            AND replace(asset_path, '\', '/') NOT LIKE '../%'
            AND replace(asset_path, '\', '/') NOT LIKE '%/../%'
            AND replace(asset_path, '\', '/') NOT LIKE '%/..'
        )
    )
) STRICT;

CREATE INDEX IF NOT EXISTS ix_style_assets_derivative
    ON style_assets(derivative_of);

CREATE TABLE IF NOT EXISTS style_posts (
    library_post_id TEXT PRIMARY KEY NOT NULL,
    platform TEXT NOT NULL,
    note_id TEXT,
    canonical_url TEXT,
    library_account_id TEXT NOT NULL,
    identity_confidence REAL NOT NULL DEFAULT 1.0
        CHECK (identity_confidence >= 0.0 AND identity_confidence <= 1.0),
    category TEXT NOT NULL DEFAULT '',
    published_at TEXT,
    format TEXT NOT NULL DEFAULT '',
    caption_asset_id TEXT,
    duplicate_of TEXT,
    cluster_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    FOREIGN KEY (library_account_id) REFERENCES style_accounts(library_account_id)
        ON UPDATE CASCADE,
    FOREIGN KEY (caption_asset_id) REFERENCES style_assets(asset_id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (duplicate_of) REFERENCES style_posts(library_post_id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    UNIQUE (library_post_id, library_account_id),
    CHECK (duplicate_of IS NULL OR duplicate_of <> library_post_id)
) STRICT;

CREATE UNIQUE INDEX IF NOT EXISTS ux_style_posts_platform_note
    ON style_posts(platform, note_id)
    WHERE note_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_style_posts_account
    ON style_posts(library_account_id);

CREATE INDEX IF NOT EXISTS ix_style_posts_cluster
    ON style_posts(cluster_id);

CREATE TABLE IF NOT EXISTS run_account_refs (
    run_id TEXT NOT NULL,
    run_account_id TEXT NOT NULL,
    library_account_id TEXT NOT NULL,
    PRIMARY KEY (run_id, run_account_id),
    FOREIGN KEY (library_account_id) REFERENCES style_accounts(library_account_id)
        ON UPDATE CASCADE
) STRICT;

CREATE INDEX IF NOT EXISTS ix_run_account_refs_library_account
    ON run_account_refs(library_account_id);

CREATE TABLE IF NOT EXISTS run_post_refs (
    run_id TEXT NOT NULL,
    run_post_id TEXT NOT NULL,
    library_post_id TEXT NOT NULL,
    PRIMARY KEY (run_id, run_post_id),
    UNIQUE (run_id, run_post_id, library_post_id),
    FOREIGN KEY (library_post_id) REFERENCES style_posts(library_post_id)
        ON UPDATE CASCADE
) STRICT;

CREATE INDEX IF NOT EXISTS ix_run_post_refs_library_post
    ON run_post_refs(library_post_id);

CREATE TABLE IF NOT EXISTS run_query_refs (
    run_id TEXT NOT NULL,
    run_query_id TEXT NOT NULL,
    query_fingerprint TEXT NOT NULL,
    PRIMARY KEY (run_id, run_query_id)
) STRICT;

CREATE INDEX IF NOT EXISTS ix_run_query_refs_fingerprint
    ON run_query_refs(query_fingerprint);

CREATE TABLE IF NOT EXISTS performance_definitions (
    performance_definition_id TEXT PRIMARY KEY NOT NULL,
    definition_version INTEGER NOT NULL CHECK (definition_version > 0),
    metric_name TEXT NOT NULL,
    business_objective TEXT NOT NULL
        CHECK (business_objective IN ('traffic_first', 'engagement_proxy')),
    primary_job TEXT NOT NULL
        CHECK (primary_job IN (
            'feed_stop', 'search_answer', 'explain', 'trust_build',
            'decision_support', 'relationship_build', 'conversion',
            'authority_statement'
        )),
    traffic_stage TEXT CHECK (traffic_stage IS NULL OR traffic_stage IN (
        'feed_stop', 'read_through', 'save_share',
        'comment_cocreation', 'profile_follow'
    )),
    metric_selection_reason TEXT NOT NULL,
    cohort_scope_json TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(cohort_scope_json) AND json_type(cohort_scope_json) = 'object'),
    comparison_design TEXT NOT NULL
        CHECK (comparison_design IN ('account_baseline', 'matched_control')),
    required_match_dimensions_json TEXT NOT NULL DEFAULT '[]'
        CHECK (json_valid(required_match_dimensions_json)
               AND json_type(required_match_dimensions_json) = 'array'),
    mismatch_code_taxonomy_version INTEGER NOT NULL DEFAULT 2
        CHECK (mismatch_code_taxonomy_version = 2),
    baseline_statistic TEXT NOT NULL DEFAULT 'median'
        CHECK (baseline_statistic = 'median'),
    min_baseline_n INTEGER NOT NULL CHECK (min_baseline_n > 0),
    age_tolerance_hours REAL CHECK (age_tolerance_hours IS NULL OR age_tolerance_hours >= 0),
    paid_or_pinned_policy TEXT NOT NULL,
    missing_value_policy TEXT NOT NULL,
    tier_rules_json TEXT NOT NULL
        CHECK (json_valid(tier_rules_json) AND json_type(tier_rules_json) = 'object'),
    as_of TEXT NOT NULL,
    review_by TEXT NOT NULL,
    definition_sha256 TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (performance_definition_id, metric_name)
) STRICT;

CREATE TABLE IF NOT EXISTS account_baseline_snapshots (
    baseline_snapshot_id TEXT PRIMARY KEY NOT NULL,
    library_account_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    window_start TEXT,
    window_end TEXT,
    sample_n INTEGER NOT NULL DEFAULT 0 CHECK (sample_n >= 0),
    median_value REAL,
    format_filter TEXT NOT NULL DEFAULT '',
    paid_or_pinned_filter TEXT NOT NULL DEFAULT '',
    missing_value_policy TEXT NOT NULL DEFAULT '',
    performance_definition_id TEXT,
    included_members_sha256 TEXT,
    all_members_sha256 TEXT,
    baseline_snapshot_sha256 TEXT UNIQUE,
    source_run_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (
        baseline_snapshot_id, library_account_id,
        performance_definition_id, metric_name
    ),
    UNIQUE (
        baseline_snapshot_id, library_account_id,
        performance_definition_id, metric_name, baseline_snapshot_sha256
    ),
    UNIQUE (
        baseline_snapshot_id, library_account_id,
        performance_definition_id, metric_name, baseline_snapshot_sha256,
        included_members_sha256, all_members_sha256
    ),
    FOREIGN KEY (library_account_id) REFERENCES style_accounts(library_account_id)
        ON UPDATE CASCADE,
    FOREIGN KEY (performance_definition_id, metric_name)
        REFERENCES performance_definitions(performance_definition_id, metric_name)
) STRICT;

CREATE INDEX IF NOT EXISTS ix_account_baselines_account_metric
    ON account_baseline_snapshots(library_account_id, metric_name);

CREATE TABLE IF NOT EXISTS style_post_observations (
    post_observation_id TEXT PRIMARY KEY NOT NULL,
    library_post_id TEXT NOT NULL,
    library_account_id TEXT,
    run_id TEXT NOT NULL,
    run_post_id TEXT NOT NULL,
    source_csv_sha256 TEXT NOT NULL,
    collected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    observation_state TEXT NOT NULL DEFAULT 'building'
        CHECK (observation_state IN ('building', 'complete')),
    performance_definition_id TEXT,
    target_metric_name TEXT,
    target_post_metric_id TEXT,
    baseline_snapshot_id TEXT,
    baseline_snapshot_sha256 TEXT,
    account_baseline_multiple REAL
        CHECK (account_baseline_multiple IS NULL OR account_baseline_multiple >= 0.0),
    performance_tier TEXT NOT NULL DEFAULT 'unknown'
        CHECK (performance_tier IN ('high', 'ordinary', 'low', 'unknown')),
    performance_computation_sha256 TEXT,
    query_fingerprints TEXT NOT NULL DEFAULT '[]',
    search_surface TEXT NOT NULL DEFAULT '',
    sort_or_filter TEXT NOT NULL DEFAULT '',
    known_confounds TEXT NOT NULL DEFAULT '[]',
    UNIQUE (post_observation_id, library_account_id, performance_definition_id),
    UNIQUE (post_observation_id, library_post_id),
    FOREIGN KEY (run_id, run_post_id, library_post_id)
        REFERENCES run_post_refs(run_id, run_post_id, library_post_id)
        ON UPDATE CASCADE,
    FOREIGN KEY (library_post_id, library_account_id)
        REFERENCES style_posts(library_post_id, library_account_id),
    FOREIGN KEY (performance_definition_id, target_metric_name)
        REFERENCES performance_definitions(performance_definition_id, metric_name),
    FOREIGN KEY (target_post_metric_id, post_observation_id, target_metric_name)
        REFERENCES post_metrics(post_metric_id, post_observation_id, metric_name),
    FOREIGN KEY (
        baseline_snapshot_id, library_account_id, performance_definition_id,
        target_metric_name, baseline_snapshot_sha256
    ) REFERENCES baseline_snapshot_publications(
        baseline_snapshot_id, library_account_id, performance_definition_id,
        metric_name, baseline_snapshot_sha256
    ),
    CHECK (
        (observation_state = 'building')
        OR (
            target_post_metric_id IS NOT NULL
            AND target_metric_name IS NOT NULL
            AND performance_definition_id IS NOT NULL
            AND library_account_id IS NOT NULL
        )
    )
) STRICT;

CREATE INDEX IF NOT EXISTS ix_style_post_observations_post
    ON style_post_observations(library_post_id);

CREATE INDEX IF NOT EXISTS ix_style_post_observations_run_post
    ON style_post_observations(run_id, run_post_id);

CREATE INDEX IF NOT EXISTS ix_style_post_observations_baseline
    ON style_post_observations(baseline_snapshot_id);

-- Derived performance is published in an immutable receipt.  Research rows
-- must never self-assign a tier, multiple, or computation hash.
CREATE TRIGGER IF NOT EXISTS reject_direct_performance_derivation_insert
BEFORE INSERT ON style_post_observations
WHEN NEW.performance_tier <> 'unknown'
  OR NEW.account_baseline_multiple IS NOT NULL
  OR NEW.performance_computation_sha256 IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'performance_tier_requires_publication');
END;

CREATE TRIGGER IF NOT EXISTS reject_direct_performance_derivation_update
BEFORE UPDATE OF
    performance_tier, account_baseline_multiple, performance_computation_sha256
ON style_post_observations
WHEN NEW.performance_tier <> 'unknown'
  OR NEW.account_baseline_multiple IS NOT NULL
  OR NEW.performance_computation_sha256 IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'performance_tier_requires_publication');
END;

CREATE TABLE IF NOT EXISTS post_metrics (
    post_metric_id TEXT PRIMARY KEY NOT NULL,
    post_observation_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    post_age_hours REAL CHECK (post_age_hours IS NULL OR post_age_hours >= 0.0),
    visibility_scope TEXT NOT NULL DEFAULT 'unknown'
        CHECK (visibility_scope IN ('first_party_analytics', 'public_proxy', 'unknown')),
    metric_sha256 TEXT,
    supersedes_post_metric_id TEXT,
    UNIQUE (post_metric_id, post_observation_id, metric_name),
    FOREIGN KEY (post_observation_id)
        REFERENCES style_post_observations(post_observation_id)
        ON UPDATE CASCADE,
    FOREIGN KEY (supersedes_post_metric_id)
        REFERENCES post_metrics(post_metric_id),
    CHECK (supersedes_post_metric_id IS NULL OR supersedes_post_metric_id <> post_metric_id)
) STRICT;

CREATE INDEX IF NOT EXISTS ix_post_metrics_observation_metric
    ON post_metrics(post_observation_id, metric_name);

CREATE TABLE IF NOT EXISTS account_baseline_members (
    baseline_snapshot_id TEXT NOT NULL,
    library_account_id TEXT NOT NULL,
    performance_definition_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    member_post_observation_id TEXT NOT NULL,
    member_post_metric_id TEXT NOT NULL,
    inclusion_status TEXT NOT NULL
        CHECK (inclusion_status IN ('included', 'excluded')),
    exclusion_reason TEXT NOT NULL DEFAULT '',
    metric_value REAL NOT NULL,
    post_age_hours REAL,
    match_values_json TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(match_values_json) AND json_type(match_values_json) = 'object'),
    mismatch_codes_json TEXT NOT NULL DEFAULT '[]'
        CHECK (json_valid(mismatch_codes_json) AND json_type(mismatch_codes_json) = 'array'),
    member_ordinal INTEGER NOT NULL CHECK (member_ordinal >= 0),
    PRIMARY KEY (
        baseline_snapshot_id, member_post_observation_id, member_post_metric_id
    ),
    UNIQUE (baseline_snapshot_id, member_ordinal),
    FOREIGN KEY (
        baseline_snapshot_id, library_account_id,
        performance_definition_id, metric_name
    ) REFERENCES account_baseline_snapshots(
        baseline_snapshot_id, library_account_id,
        performance_definition_id, metric_name
    ),
    FOREIGN KEY (member_post_metric_id, member_post_observation_id, metric_name)
        REFERENCES post_metrics(post_metric_id, post_observation_id, metric_name),
    FOREIGN KEY (
        member_post_observation_id, library_account_id,
        performance_definition_id
    ) REFERENCES style_post_observations(
        post_observation_id, library_account_id, performance_definition_id
    ),
    CHECK (
        (inclusion_status = 'included' AND exclusion_reason = '')
        OR (inclusion_status = 'excluded' AND exclusion_reason <> '')
    )
) STRICT;

CREATE TABLE IF NOT EXISTS baseline_snapshot_publications (
    baseline_snapshot_id TEXT PRIMARY KEY NOT NULL,
    library_account_id TEXT NOT NULL,
    performance_definition_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    baseline_snapshot_sha256 TEXT NOT NULL,
    included_members_sha256 TEXT NOT NULL,
    all_members_sha256 TEXT NOT NULL,
    published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (
        baseline_snapshot_id, library_account_id,
        performance_definition_id, metric_name, baseline_snapshot_sha256
    ),
    UNIQUE (
        baseline_snapshot_id, library_account_id,
        performance_definition_id, metric_name, baseline_snapshot_sha256,
        included_members_sha256, all_members_sha256
    ),
    FOREIGN KEY (
        baseline_snapshot_id, library_account_id, performance_definition_id,
        metric_name, baseline_snapshot_sha256,
        included_members_sha256, all_members_sha256
    ) REFERENCES account_baseline_snapshots(
        baseline_snapshot_id, library_account_id, performance_definition_id,
        metric_name, baseline_snapshot_sha256,
        included_members_sha256, all_members_sha256
    )
) STRICT;

CREATE TRIGGER IF NOT EXISTS validate_baseline_publication_insert
BEFORE INSERT ON baseline_snapshot_publications
BEGIN
    SELECT CASE WHEN (
        SELECT COUNT(*)
        FROM account_baseline_members
        WHERE baseline_snapshot_id = NEW.baseline_snapshot_id
          AND inclusion_status = 'included'
    ) < (
        SELECT min_baseline_n
        FROM performance_definitions
        WHERE performance_definition_id = NEW.performance_definition_id
          AND metric_name = NEW.metric_name
    ) THEN RAISE(ABORT, 'baseline_minimum_not_met') END;

    SELECT CASE WHEN (
        SELECT COUNT(*)
        FROM account_baseline_members
        WHERE baseline_snapshot_id = NEW.baseline_snapshot_id
          AND inclusion_status = 'included'
    ) <> (
        SELECT sample_n
        FROM account_baseline_snapshots
        WHERE baseline_snapshot_id = NEW.baseline_snapshot_id
    ) THEN RAISE(ABORT, 'baseline_sample_count_mismatch') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM account_baseline_members AS member
        LEFT JOIN post_metrics AS metric
          ON metric.post_metric_id = member.member_post_metric_id
         AND metric.post_observation_id = member.member_post_observation_id
         AND metric.metric_name = member.metric_name
        WHERE member.baseline_snapshot_id = NEW.baseline_snapshot_id
          AND (
              metric.post_metric_id IS NULL
              OR metric.metric_value <> member.metric_value
              OR NOT (metric.post_age_hours IS member.post_age_hours)
          )
    ) THEN RAISE(ABORT, 'baseline_member_metric_mismatch') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM account_baseline_members AS member
        JOIN style_post_observations AS observation
          ON observation.post_observation_id = member.member_post_observation_id
        WHERE member.baseline_snapshot_id = NEW.baseline_snapshot_id
          AND observation.observation_state <> 'complete'
    ) THEN RAISE(ABORT, 'baseline_member_observation_incomplete') END;

    SELECT CASE WHEN NOT (
        SELECT median_agg_v2(metric_value)
        FROM account_baseline_members
        WHERE baseline_snapshot_id = NEW.baseline_snapshot_id
          AND inclusion_status = 'included'
    ) IS (
        SELECT median_value
        FROM account_baseline_snapshots
        WHERE baseline_snapshot_id = NEW.baseline_snapshot_id
    ) THEN RAISE(ABORT, 'baseline_median_mismatch') END;

    SELECT CASE WHEN (
        SELECT canonical_sha256_agg_v2(member_preimage)
        FROM (
            SELECT printf(
                '%d|%s|%s|%!.17g|%s|%s|%s',
                member_ordinal, member_post_observation_id,
                member_post_metric_id, metric_value,
                coalesce(post_age_hours, ''), match_values_json,
                mismatch_codes_json
            ) AS member_preimage
            FROM account_baseline_members
            WHERE baseline_snapshot_id = NEW.baseline_snapshot_id
              AND inclusion_status = 'included'
            ORDER BY member_ordinal
        )
    ) <> NEW.included_members_sha256
    THEN RAISE(ABORT, 'baseline_included_hash_mismatch') END;

    SELECT CASE WHEN (
        SELECT canonical_sha256_agg_v2(member_preimage)
        FROM (
            SELECT printf(
                '%d|%s|%s|%s|%s|%!.17g|%s|%s|%s',
                member_ordinal, member_post_observation_id,
                member_post_metric_id, inclusion_status,
                exclusion_reason, metric_value,
                coalesce(post_age_hours, ''), match_values_json,
                mismatch_codes_json
            ) AS member_preimage
            FROM account_baseline_members
            WHERE baseline_snapshot_id = NEW.baseline_snapshot_id
            ORDER BY member_ordinal
        )
    ) <> NEW.all_members_sha256
    THEN RAISE(ABORT, 'baseline_all_hash_mismatch') END;
END;

CREATE TRIGGER IF NOT EXISTS immutable_performance_definitions_update
BEFORE UPDATE ON performance_definitions
BEGIN
    SELECT RAISE(ABORT, 'immutable_performance_definitions');
END;

CREATE TRIGGER IF NOT EXISTS immutable_performance_definitions_delete
BEFORE DELETE ON performance_definitions
BEGIN
    SELECT RAISE(ABORT, 'immutable_performance_definitions');
END;

CREATE TRIGGER IF NOT EXISTS immutable_account_baseline_snapshots_update
BEFORE UPDATE ON account_baseline_snapshots
BEGIN
    SELECT RAISE(ABORT, 'immutable_account_baseline_snapshots');
END;

CREATE TRIGGER IF NOT EXISTS immutable_account_baseline_snapshots_delete
BEFORE DELETE ON account_baseline_snapshots
BEGIN
    SELECT RAISE(ABORT, 'immutable_account_baseline_snapshots');
END;

CREATE TRIGGER IF NOT EXISTS freeze_baseline_members_after_publish_insert
BEFORE INSERT ON account_baseline_members
WHEN EXISTS (
    SELECT 1 FROM baseline_snapshot_publications
    WHERE baseline_snapshot_id = NEW.baseline_snapshot_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_baseline_members_frozen');
END;

CREATE TRIGGER IF NOT EXISTS immutable_account_baseline_members_update
BEFORE UPDATE ON account_baseline_members
BEGIN
    SELECT RAISE(ABORT, 'immutable_account_baseline_members');
END;

CREATE TRIGGER IF NOT EXISTS immutable_account_baseline_members_delete
BEFORE DELETE ON account_baseline_members
BEGIN
    SELECT RAISE(ABORT, 'immutable_account_baseline_members');
END;

CREATE TRIGGER IF NOT EXISTS immutable_baseline_snapshot_publications_update
BEFORE UPDATE ON baseline_snapshot_publications
BEGIN
    SELECT RAISE(ABORT, 'immutable_baseline_snapshot_publications');
END;

CREATE TRIGGER IF NOT EXISTS immutable_baseline_snapshot_publications_delete
BEFORE DELETE ON baseline_snapshot_publications
BEGIN
    SELECT RAISE(ABORT, 'immutable_baseline_snapshot_publications');
END;

CREATE TABLE IF NOT EXISTS post_performance_publications (
    post_observation_id TEXT PRIMARY KEY NOT NULL,
    library_account_id TEXT NOT NULL,
    baseline_snapshot_id TEXT NOT NULL,
    baseline_snapshot_sha256 TEXT NOT NULL,
    performance_definition_id TEXT NOT NULL,
    definition_sha256 TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    target_post_metric_id TEXT NOT NULL,
    target_metric_sha256 TEXT NOT NULL,
    target_metric_value REAL NOT NULL CHECK (target_metric_value >= 0),
    baseline_median_value REAL NOT NULL CHECK (baseline_median_value > 0),
    account_baseline_multiple REAL NOT NULL CHECK (account_baseline_multiple >= 0),
    performance_tier TEXT NOT NULL
        CHECK (performance_tier IN ('high', 'ordinary', 'low')),
    performance_computation_sha256 TEXT NOT NULL UNIQUE,
    visibility_scope TEXT NOT NULL
        CHECK (visibility_scope IN ('first_party_analytics', 'public_proxy')),
    traffic_stage TEXT CHECK (traffic_stage IS NULL OR traffic_stage = 'feed_stop'),
    traffic_verdict TEXT NOT NULL
        CHECK (traffic_verdict IN ('win', 'loss', 'inconclusive', 'not_applicable')),
    published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_observation_id)
        REFERENCES style_post_observations(post_observation_id),
    FOREIGN KEY (target_post_metric_id, post_observation_id, metric_name)
        REFERENCES post_metrics(post_metric_id, post_observation_id, metric_name),
    FOREIGN KEY (performance_definition_id, metric_name)
        REFERENCES performance_definitions(performance_definition_id, metric_name),
    FOREIGN KEY (
        baseline_snapshot_id, library_account_id,
        performance_definition_id, metric_name,
        baseline_snapshot_sha256
    ) REFERENCES baseline_snapshot_publications(
        baseline_snapshot_id, library_account_id,
        performance_definition_id, metric_name,
        baseline_snapshot_sha256
    )
) STRICT;

CREATE TRIGGER IF NOT EXISTS validate_post_performance_publication_insert
BEFORE INSERT ON post_performance_publications
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM style_post_observations AS observation
        JOIN post_metrics AS target_metric
          ON target_metric.post_metric_id = observation.target_post_metric_id
         AND target_metric.post_observation_id = observation.post_observation_id
         AND target_metric.metric_name = observation.target_metric_name
        JOIN performance_definitions AS definition
          ON definition.performance_definition_id = observation.performance_definition_id
         AND definition.metric_name = observation.target_metric_name
        JOIN baseline_snapshot_publications AS publication
          ON publication.baseline_snapshot_id = observation.baseline_snapshot_id
         AND publication.library_account_id = observation.library_account_id
         AND publication.performance_definition_id = observation.performance_definition_id
         AND publication.metric_name = observation.target_metric_name
         AND publication.baseline_snapshot_sha256 = observation.baseline_snapshot_sha256
        JOIN account_baseline_snapshots AS snapshot
          ON snapshot.baseline_snapshot_id = publication.baseline_snapshot_id
        WHERE observation.post_observation_id = NEW.post_observation_id
          AND observation.observation_state = 'complete'
          AND observation.baseline_snapshot_id = NEW.baseline_snapshot_id
          AND observation.library_account_id = NEW.library_account_id
          AND observation.baseline_snapshot_sha256 = NEW.baseline_snapshot_sha256
          AND observation.performance_definition_id = NEW.performance_definition_id
          AND observation.target_metric_name = NEW.metric_name
          AND observation.target_post_metric_id = NEW.target_post_metric_id
          AND definition.definition_sha256 = NEW.definition_sha256
          AND target_metric.metric_sha256 = NEW.target_metric_sha256
          AND target_metric.metric_value = NEW.target_metric_value
          AND snapshot.median_value = NEW.baseline_median_value
          AND snapshot.median_value > 0
          AND abs(
              NEW.account_baseline_multiple
              - (target_metric.metric_value / snapshot.median_value)
          ) < 0.000000000001
          AND NEW.performance_tier = CASE
              WHEN target_metric.metric_value / snapshot.median_value
                   >= CAST(json_extract(
                       definition.tier_rules_json, '$.high_min_multiple'
                   ) AS REAL) THEN 'high'
              WHEN target_metric.metric_value / snapshot.median_value
                   <= CAST(json_extract(
                       definition.tier_rules_json, '$.low_max_multiple'
                   ) AS REAL) THEN 'low'
              ELSE 'ordinary'
          END
          AND NEW.performance_computation_sha256 =
              performance_computation_sha256_v2(
                  observation.post_observation_id,
                  publication.baseline_snapshot_id,
                  publication.baseline_snapshot_sha256,
                  definition.definition_sha256,
                  target_metric.metric_name,
                  target_metric.metric_value,
                  snapshot.median_value,
                  NEW.account_baseline_multiple,
                  NEW.performance_tier
              )
          AND NOT EXISTS (
              SELECT 1
              FROM account_baseline_members AS member
              JOIN style_post_observations AS member_observation
                ON member_observation.post_observation_id =
                   member.member_post_observation_id
              WHERE member.baseline_snapshot_id = NEW.baseline_snapshot_id
                AND member.inclusion_status = 'included'
                AND member_observation.library_post_id =
                    observation.library_post_id
          )
          AND (
              (
                  definition.business_objective = 'traffic_first'
                  AND definition.primary_job = 'feed_stop'
                  AND definition.traffic_stage = 'feed_stop'
                  AND target_metric.metric_name IN ('impressions', 'reach')
                  AND target_metric.visibility_scope = 'first_party_analytics'
                  AND NEW.visibility_scope = 'first_party_analytics'
                  AND NEW.traffic_stage = 'feed_stop'
                  AND NEW.traffic_verdict = CASE NEW.performance_tier
                      WHEN 'high' THEN 'win'
                      WHEN 'low' THEN 'loss'
                      ELSE 'inconclusive'
                  END
                  AND NOT EXISTS (
                      SELECT 1
                      FROM account_baseline_members AS member
                      JOIN post_metrics AS member_metric
                        ON member_metric.post_metric_id = member.member_post_metric_id
                      WHERE member.baseline_snapshot_id = NEW.baseline_snapshot_id
                        AND member.inclusion_status = 'included'
                        AND member_metric.visibility_scope <> 'first_party_analytics'
                  )
              )
              OR
              (
                  definition.business_objective = 'engagement_proxy'
                  AND target_metric.metric_name = 'engagement_proxy'
                  AND target_metric.visibility_scope = 'public_proxy'
                  AND NEW.visibility_scope = 'public_proxy'
                  AND NEW.traffic_stage IS NULL
                  AND NEW.traffic_verdict = 'not_applicable'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM account_baseline_members AS member
                      JOIN post_metrics AS member_metric
                        ON member_metric.post_metric_id = member.member_post_metric_id
                      WHERE member.baseline_snapshot_id = NEW.baseline_snapshot_id
                        AND member.inclusion_status = 'included'
                        AND member_metric.visibility_scope <> 'public_proxy'
                  )
              )
          )
    ) THEN RAISE(ABORT, 'performance_publication_not_recomputable') END;
END;

CREATE TRIGGER IF NOT EXISTS immutable_post_performance_publications_update
BEFORE UPDATE ON post_performance_publications
BEGIN
    SELECT RAISE(ABORT, 'immutable_post_performance_publications');
END;

CREATE TRIGGER IF NOT EXISTS immutable_post_performance_publications_delete
BEFORE DELETE ON post_performance_publications
BEGIN
    SELECT RAISE(ABORT, 'immutable_post_performance_publications');
END;

CREATE TRIGGER IF NOT EXISTS protect_published_target_metric_update
BEFORE UPDATE ON post_metrics
WHEN EXISTS (
    SELECT 1 FROM post_performance_publications
    WHERE target_post_metric_id = OLD.post_metric_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_performance_metric_frozen');
END;

CREATE TRIGGER IF NOT EXISTS protect_published_target_metric_delete
BEFORE DELETE ON post_metrics
WHEN EXISTS (
    SELECT 1 FROM post_performance_publications
    WHERE target_post_metric_id = OLD.post_metric_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_performance_metric_frozen');
END;

CREATE TRIGGER IF NOT EXISTS protect_published_baseline_metric_update
BEFORE UPDATE ON post_metrics
WHEN EXISTS (
    SELECT 1
    FROM account_baseline_members AS member
    JOIN baseline_snapshot_publications AS publication
      ON publication.baseline_snapshot_id = member.baseline_snapshot_id
    WHERE member.member_post_metric_id = OLD.post_metric_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_baseline_metric_frozen');
END;

CREATE TRIGGER IF NOT EXISTS protect_published_baseline_metric_delete
BEFORE DELETE ON post_metrics
WHEN EXISTS (
    SELECT 1
    FROM account_baseline_members AS member
    JOIN baseline_snapshot_publications AS publication
      ON publication.baseline_snapshot_id = member.baseline_snapshot_id
    WHERE member.member_post_metric_id = OLD.post_metric_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_baseline_metric_frozen');
END;

CREATE TRIGGER IF NOT EXISTS complete_post_observation_requires_target_insert
BEFORE INSERT ON style_post_observations
WHEN NEW.observation_state = 'complete'
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM post_metrics
        WHERE post_metric_id = NEW.target_post_metric_id
          AND post_observation_id = NEW.post_observation_id
          AND metric_name = NEW.target_metric_name
    ) THEN RAISE(ABORT, 'complete_observation_target_missing') END;
END;

CREATE TRIGGER IF NOT EXISTS complete_post_observation_requires_target_update
BEFORE UPDATE ON style_post_observations
WHEN OLD.observation_state = 'building' AND NEW.observation_state = 'complete'
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM post_metrics
        WHERE post_metric_id = NEW.target_post_metric_id
          AND post_observation_id = NEW.post_observation_id
          AND metric_name = NEW.target_metric_name
    ) THEN RAISE(ABORT, 'complete_observation_target_missing') END;
END;

CREATE TRIGGER IF NOT EXISTS freeze_complete_post_observation_update
BEFORE UPDATE ON style_post_observations
WHEN OLD.observation_state = 'complete'
BEGIN
    SELECT RAISE(ABORT, 'complete_observation_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_complete_post_observation_delete
BEFORE DELETE ON style_post_observations
WHEN OLD.observation_state = 'complete'
BEGIN
    SELECT RAISE(ABORT, 'complete_observation_frozen');
END;

CREATE TABLE IF NOT EXISTS style_slides (
    slide_id TEXT PRIMARY KEY NOT NULL,
    library_post_id TEXT NOT NULL,
    slide_index INTEGER NOT NULL CHECK (slide_index >= 0),
    slide_role TEXT NOT NULL DEFAULT 'other'
        CHECK (slide_role IN (
            'cover', 'scene', 'context', 'evidence', 'comparison', 'step',
            'boundary', 'transition', 'summary', 'cta', 'other'
        )),
    asset_id TEXT,
    ocr_asset_id TEXT,
    ocr_confidence REAL
        CHECK (ocr_confidence IS NULL OR (ocr_confidence >= 0.0 AND ocr_confidence <= 1.0)),
    access_status TEXT NOT NULL DEFAULT 'available',
    observation_method TEXT NOT NULL DEFAULT 'direct',
    taxonomy_version INTEGER NOT NULL DEFAULT 2 CHECK (taxonomy_version = 2),
    UNIQUE (library_post_id, slide_index),
    UNIQUE (slide_id, library_post_id),
    FOREIGN KEY (library_post_id) REFERENCES style_posts(library_post_id)
        ON UPDATE CASCADE,
    FOREIGN KEY (asset_id) REFERENCES style_assets(asset_id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (ocr_asset_id) REFERENCES style_assets(asset_id)
        ON UPDATE CASCADE ON DELETE SET NULL
) STRICT;

CREATE INDEX IF NOT EXISTS ix_style_slides_post
    ON style_slides(library_post_id, slide_index);

CREATE INDEX IF NOT EXISTS ix_style_slides_asset
    ON style_slides(asset_id);

CREATE TABLE IF NOT EXISTS visual_observations (
    visual_observation_id TEXT PRIMARY KEY NOT NULL,
    slide_id TEXT NOT NULL,
    library_post_id TEXT NOT NULL,
    observation_sha256 TEXT NOT NULL,
    supersedes_visual_observation_id TEXT,
    composition TEXT NOT NULL DEFAULT 'unknown'
        CHECK (composition IN (
            'single_focus', 'split', 'grid', 'layered_collage', 'full_bleed',
            'interface_capture', 'unknown', 'other'
        )),
    dominant_material TEXT NOT NULL DEFAULT 'unknown'
        CHECK (dominant_material IN (
            'real_photo', 'screenshot', 'chat_ui', 'paper_note', 'illustration',
            'type_only', 'mixed', 'unknown', 'other'
        )),
    background_type TEXT NOT NULL DEFAULT 'unknown'
        CHECK (background_type IN (
            'photo', 'paper', 'screenshot', 'solid', 'texture', 'interface',
            'mixed', 'unknown', 'other'
        )),
    subject_presence TEXT NOT NULL DEFAULT 'unknown'
        CHECK (subject_presence IN (
            'person', 'hand', 'object', 'environment', 'interface_only',
            'none', 'unknown', 'other'
        )),
    crop_and_subject_ratio TEXT NOT NULL DEFAULT '',
    layout_structure TEXT NOT NULL DEFAULT 'unknown'
        CHECK (layout_structure IN (
            'freeform', 'stacked', 'split', 'grid', 'full_bleed_overlay',
            'chat_flow', 'list', 'unknown', 'other'
        )),
    text_zones TEXT NOT NULL DEFAULT '[]',
    text_density TEXT NOT NULL DEFAULT 'unknown'
        CHECK (text_density IN ('sparse', 'medium', 'dense', 'variable', 'unknown')),
    hierarchy_levels TEXT NOT NULL DEFAULT 'unknown'
        CHECK (hierarchy_levels IN ('one', 'two', 'three_plus', 'variable', 'unknown')),
    alignment TEXT NOT NULL DEFAULT 'unknown'
        CHECK (alignment IN (
            'left', 'center', 'right', 'mixed', 'organic', 'unknown', 'other'
        )),
    spacing_pattern TEXT NOT NULL DEFAULT 'unknown'
        CHECK (spacing_pattern IN (
            'tight', 'even', 'variable', 'edge_to_edge', 'unknown', 'other'
        )),
    palette TEXT NOT NULL DEFAULT '[]',
    font_feel TEXT NOT NULL DEFAULT 'unknown'
        CHECK (font_feel IN (
            'system', 'editorial', 'handwritten', 'display', 'mixed',
            'unknown', 'other'
        )),
    decoration_types TEXT NOT NULL DEFAULT 'unknown'
        CHECK (decoration_types IN (
            'none', 'sticker', 'tape', 'doodle', 'shape', 'emoji', 'mixed',
            'unknown', 'other'
        )),
    annotation_style TEXT NOT NULL DEFAULT 'unknown'
        CHECK (annotation_style IN (
            'none', 'circle', 'arrow', 'underline', 'highlight', 'handwritten',
            'mixed', 'unknown', 'other'
        )),
    imperfection_signals TEXT NOT NULL DEFAULT 'unknown'
        CHECK (imperfection_signals IN (
            'none', 'uneven_crop', 'off_grid', 'natural_shadow', 'hand_mark',
            'mixed', 'unknown', 'other'
        )),
    image_text_relationship TEXT NOT NULL DEFAULT 'unknown'
        CHECK (image_text_relationship IN (
            'image_leads', 'text_leads', 'complementary', 'redundant',
            'unknown', 'other'
        )),
    evidence_level TEXT NOT NULL DEFAULT '',
    observation_method TEXT NOT NULL DEFAULT 'direct',
    confidence REAL NOT NULL DEFAULT 1.0
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    taxonomy_version INTEGER NOT NULL DEFAULT 2 CHECK (taxonomy_version = 2),
    notes TEXT NOT NULL DEFAULT '',
    UNIQUE (visual_observation_id, library_post_id),
    FOREIGN KEY (slide_id, library_post_id)
        REFERENCES style_slides(slide_id, library_post_id),
    FOREIGN KEY (supersedes_visual_observation_id)
        REFERENCES visual_observations(visual_observation_id),
    CHECK (
        supersedes_visual_observation_id IS NULL
        OR supersedes_visual_observation_id <> visual_observation_id
    )
) STRICT;

CREATE INDEX IF NOT EXISTS ix_visual_observations_slide
    ON visual_observations(slide_id);

CREATE TABLE IF NOT EXISTS copy_observations (
    observation_id TEXT PRIMARY KEY NOT NULL,
    library_post_id TEXT NOT NULL,
    slide_id TEXT,
    observation_sha256 TEXT NOT NULL,
    supersedes_copy_observation_id TEXT,
    text_surface TEXT NOT NULL DEFAULT 'unknown'
        CHECK (text_surface IN (
            'title', 'cover', 'slide', 'caption', 'cta', 'unknown', 'other'
        )),
    point_of_view TEXT NOT NULL DEFAULT 'unknown'
        CHECK (point_of_view IN (
            'first_person', 'second_person', 'third_person', 'mixed',
            'unknown', 'other'
        )),
    audience_address TEXT NOT NULL DEFAULT 'unknown'
        CHECK (audience_address IN (
            'direct', 'collective', 'implicit', 'none', 'unknown', 'other'
        )),
    register TEXT NOT NULL DEFAULT 'unknown'
        CHECK (register IN (
            'spoken', 'plain_explanatory', 'professional', 'diary', 'playful',
            'sales', 'mixed', 'unknown', 'other'
        )),
    sentence_length_pattern TEXT NOT NULL DEFAULT 'unknown'
        CHECK (sentence_length_pattern IN (
            'short', 'medium', 'long', 'mixed', 'unknown', 'other'
        )),
    line_break_pattern TEXT NOT NULL DEFAULT 'unknown'
        CHECK (line_break_pattern IN (
            'sentence', 'phrase', 'dense_paragraph', 'mixed', 'unknown', 'other'
        )),
    punctuation_pattern TEXT NOT NULL DEFAULT 'unknown'
        CHECK (punctuation_pattern IN (
            'light', 'standard', 'expressive', 'fragmented', 'mixed',
            'unknown', 'other'
        )),
    emoji_pattern TEXT NOT NULL DEFAULT 'unknown'
        CHECK (emoji_pattern IN (
            'none', 'sparse', 'structural', 'dense', 'mixed', 'unknown', 'other'
        )),
    diction_markers TEXT NOT NULL DEFAULT '[]',
    hook_move TEXT NOT NULL DEFAULT 'unknown'
        CHECK (hook_move IN (
            'name_scene', 'state_conflict', 'give_answer', 'show_evidence',
            'ask_question', 'unknown', 'other'
        )),
    narrative_moves TEXT NOT NULL DEFAULT 'unknown'
        CHECK (narrative_moves IN (
            'setup', 'turn', 'contrast', 'reveal', 'reflection', 'none',
            'unknown', 'other'
        )),
    evidence_move TEXT NOT NULL DEFAULT 'unknown'
        CHECK (evidence_move IN (
            'show_process', 'show_example', 'compare', 'cite_source',
            'state_limit', 'none', 'unknown', 'other'
        )),
    payoff_move TEXT NOT NULL DEFAULT 'unknown'
        CHECK (payoff_move IN (
            'answer', 'framework', 'script', 'decision', 'boundary', 'none',
            'unknown', 'other'
        )),
    cta_move TEXT NOT NULL DEFAULT 'unknown'
        CHECK (cta_move IN (
            'none', 'question', 'save', 'follow', 'native_action', 'commercial',
            'unknown', 'other'
        )),
    image_caption_division TEXT NOT NULL DEFAULT 'unknown'
        CHECK (image_caption_division IN (
            'image_core_caption_context', 'image_summary_caption_detail',
            'image_evidence_caption_interpretation', 'redundant',
            'unknown', 'other'
        )),
    quoted_fragments_hash TEXT,
    evidence_level TEXT NOT NULL DEFAULT '',
    observation_method TEXT NOT NULL DEFAULT 'direct',
    confidence REAL NOT NULL DEFAULT 1.0
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    taxonomy_version INTEGER NOT NULL DEFAULT 2 CHECK (taxonomy_version = 2),
    notes TEXT NOT NULL DEFAULT '',
    UNIQUE (observation_id, library_post_id),
    FOREIGN KEY (library_post_id) REFERENCES style_posts(library_post_id)
        ON UPDATE CASCADE,
    FOREIGN KEY (slide_id, library_post_id)
        REFERENCES style_slides(slide_id, library_post_id)
        ON UPDATE CASCADE,
    FOREIGN KEY (supersedes_copy_observation_id)
        REFERENCES copy_observations(observation_id),
    CHECK (
        supersedes_copy_observation_id IS NULL
        OR supersedes_copy_observation_id <> observation_id
    )
) STRICT;

CREATE INDEX IF NOT EXISTS ix_copy_observations_post
    ON copy_observations(library_post_id);

CREATE INDEX IF NOT EXISTS ix_copy_observations_slide
    ON copy_observations(slide_id);

-- Exact bridge from a visual/copy feature observation to the immutable post
-- observation whose published performance receipt is being used.  This
-- prevents joining a page from one capture to a metric from another capture
-- merely because both share library_post_id.
CREATE TABLE IF NOT EXISTS feature_observation_links (
    feature_link_id TEXT PRIMARY KEY NOT NULL,
    observation_type TEXT NOT NULL
        CHECK (observation_type IN ('visual', 'copy')),
    observation_id TEXT NOT NULL,
    post_observation_id TEXT NOT NULL,
    library_post_id TEXT NOT NULL,
    feature_observation_sha256 TEXT NOT NULL,
    source_asset_sha256 TEXT NOT NULL,
    source_csv_sha256 TEXT NOT NULL,
    performance_computation_sha256 TEXT NOT NULL,
    capture_bundle_sha256 TEXT NOT NULL,
    feature_link_sha256 TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (observation_type, observation_id),
    UNIQUE (feature_link_id, observation_type, observation_id),
    FOREIGN KEY (post_observation_id, library_post_id)
        REFERENCES style_post_observations(
            post_observation_id, library_post_id
        )
) STRICT;

CREATE INDEX IF NOT EXISTS ix_feature_observation_links_post_observation
    ON feature_observation_links(post_observation_id, library_post_id);

CREATE TRIGGER IF NOT EXISTS validate_feature_observation_link_insert
BEFORE INSERT ON feature_observation_links
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM style_post_observations AS observation
        JOIN post_performance_publications AS performance
          ON performance.post_observation_id=observation.post_observation_id
        WHERE observation.post_observation_id=NEW.post_observation_id
          AND observation.library_post_id=NEW.library_post_id
          AND observation.observation_state='complete'
          AND observation.source_csv_sha256=NEW.source_csv_sha256
          AND performance.performance_computation_sha256=
              NEW.performance_computation_sha256
    ) THEN RAISE(ABORT, 'feature_link_post_observation_unpublished') END;

    SELECT CASE
        WHEN NEW.observation_type='visual' AND NOT EXISTS (
            SELECT 1
            FROM visual_observations AS visual
            JOIN style_slides AS slide
              ON slide.slide_id=visual.slide_id
             AND slide.library_post_id=visual.library_post_id
            JOIN style_assets AS asset ON asset.asset_id=slide.asset_id
            WHERE visual.visual_observation_id=NEW.observation_id
              AND visual.library_post_id=NEW.library_post_id
              AND visual.observation_sha256=NEW.feature_observation_sha256
              AND asset.asset_sha256=NEW.source_asset_sha256
        ) THEN RAISE(ABORT, 'feature_link_visual_target_invalid')
        WHEN NEW.observation_type='copy' AND NOT EXISTS (
            SELECT 1
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
            WHERE copy.observation_id=NEW.observation_id
              AND copy.library_post_id=NEW.library_post_id
              AND copy.observation_sha256=NEW.feature_observation_sha256
              AND asset.asset_sha256=NEW.source_asset_sha256
        ) THEN RAISE(ABORT, 'feature_link_copy_target_invalid')
    END;

    SELECT CASE WHEN NEW.capture_bundle_sha256 <>
        canonical_row_sha256_v2(
            NEW.observation_type,
            NEW.observation_id,
            NEW.post_observation_id,
            NEW.library_post_id,
            NEW.feature_observation_sha256,
            NEW.source_asset_sha256,
            NEW.source_csv_sha256
        )
    THEN RAISE(ABORT, 'feature_link_capture_hash_mismatch') END;

    SELECT CASE WHEN NEW.feature_link_sha256 <>
        canonical_row_sha256_v2(
            NEW.feature_link_id,
            NEW.observation_type,
            NEW.observation_id,
            NEW.post_observation_id,
            NEW.library_post_id,
            NEW.feature_observation_sha256,
            NEW.source_asset_sha256,
            NEW.source_csv_sha256,
            NEW.performance_computation_sha256,
            NEW.capture_bundle_sha256
        )
    THEN RAISE(ABORT, 'feature_link_hash_mismatch') END;
END;

CREATE TRIGGER IF NOT EXISTS immutable_feature_observation_links_update
BEFORE UPDATE ON feature_observation_links
BEGIN
    SELECT RAISE(ABORT, 'immutable_feature_observation_links');
END;

CREATE TRIGGER IF NOT EXISTS immutable_feature_observation_links_delete
BEFORE DELETE ON feature_observation_links
BEGIN
    SELECT RAISE(ABORT, 'immutable_feature_observation_links');
END;

CREATE TRIGGER IF NOT EXISTS freeze_linked_visual_observation_update
BEFORE UPDATE ON visual_observations
WHEN EXISTS (
    SELECT 1 FROM feature_observation_links
    WHERE observation_type='visual'
      AND observation_id=OLD.visual_observation_id
)
BEGIN
    SELECT RAISE(ABORT, 'linked_feature_observation_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_linked_visual_observation_delete
BEFORE DELETE ON visual_observations
WHEN EXISTS (
    SELECT 1 FROM feature_observation_links
    WHERE observation_type='visual'
      AND observation_id=OLD.visual_observation_id
)
BEGIN
    SELECT RAISE(ABORT, 'linked_feature_observation_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_linked_copy_observation_update
BEFORE UPDATE ON copy_observations
WHEN EXISTS (
    SELECT 1 FROM feature_observation_links
    WHERE observation_type='copy'
      AND observation_id=OLD.observation_id
)
BEGIN
    SELECT RAISE(ABORT, 'linked_feature_observation_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_linked_copy_observation_delete
BEFORE DELETE ON copy_observations
WHEN EXISTS (
    SELECT 1 FROM feature_observation_links
    WHERE observation_type='copy'
      AND observation_id=OLD.observation_id
)
BEGIN
    SELECT RAISE(ABORT, 'linked_feature_observation_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_linked_source_asset_update
BEFORE UPDATE OF
    asset_id,asset_sha256,asset_path,mime_type,width,height,derivative_of
ON style_assets
WHEN EXISTS (
    SELECT 1 FROM feature_observation_links
    WHERE source_asset_sha256=OLD.asset_sha256
)
BEGIN
    SELECT RAISE(ABORT, 'linked_source_asset_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_linked_source_asset_delete
BEFORE DELETE ON style_assets
WHEN EXISTS (
    SELECT 1 FROM feature_observation_links
    WHERE source_asset_sha256=OLD.asset_sha256
)
BEGIN
    SELECT RAISE(ABORT, 'linked_source_asset_frozen');
END;

-- A qualification counts independent accounts/clusters and an exact category.
-- Those identity fields therefore belong to the immutable evidence preimage.
-- `status` intentionally remains mutable so a removed/blocked post can make a
-- formerly qualified style unavailable at query time.
CREATE TRIGGER IF NOT EXISTS freeze_linked_post_identity_update
BEFORE UPDATE OF
    library_post_id,library_account_id,category,cluster_id,caption_asset_id
ON style_posts
WHEN EXISTS (
    SELECT 1 FROM feature_observation_links
    WHERE library_post_id=OLD.library_post_id
)
BEGIN
    SELECT RAISE(ABORT, 'linked_post_identity_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_linked_post_delete
BEFORE DELETE ON style_posts
WHEN EXISTS (
    SELECT 1 FROM feature_observation_links
    WHERE library_post_id=OLD.library_post_id
)
BEGIN
    SELECT RAISE(ABORT, 'linked_post_frozen');
END;

CREATE TABLE IF NOT EXISTS style_archetypes (
    archetype_id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    category_scope TEXT NOT NULL DEFAULT '',
    carrier TEXT NOT NULL DEFAULT 'unknown'
        CHECK (carrier IN (
            'real_photo_diary', 'photo_annotation', 'screenshot_markup',
            'chat_dramatization', 'text_card', 'checklist_steps',
            'comparison_warning', 'collage_journal',
            'single_image_reminder', 'process_video', 'screen_recording',
            'talking_head_or_field_video', 'unknown', 'other'
        )),
    primary_job_scope TEXT NOT NULL DEFAULT '',
    audience_state TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    production_cost TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.0
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    status TEXT NOT NULL DEFAULT 'candidate'
        CHECK (status IN ('candidate', 'supported', 'reusable', 'stale', 'deprecated')),
    current_version INTEGER NOT NULL DEFAULT 1 CHECK (current_version >= 1),
    snapshot_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    taxonomy_version INTEGER NOT NULL DEFAULT 2 CHECK (taxonomy_version = 2),
    UNIQUE (archetype_id, current_version, snapshot_sha256)
) STRICT;

CREATE INDEX IF NOT EXISTS ix_style_archetypes_retrieval
    ON style_archetypes(category_scope, carrier, status);

CREATE TABLE IF NOT EXISTS archetype_rules (
    rule_id TEXT PRIMARY KEY NOT NULL,
    archetype_id TEXT NOT NULL,
    archetype_version INTEGER NOT NULL CHECK (archetype_version >= 1),
    rule_type TEXT NOT NULL
        CHECK (rule_type IN ('cover', 'rhythm', 'visual', 'copy', 'material', 'anti_pattern')),
    rule_payload_json TEXT NOT NULL DEFAULT '{}',
    applicability_scope TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    UNIQUE (rule_id, archetype_id, archetype_version),
    CHECK (json_valid(rule_payload_json) AND json_type(rule_payload_json) = 'object'),
    FOREIGN KEY (archetype_id) REFERENCES style_archetypes(archetype_id)
        ON UPDATE CASCADE
) STRICT;

CREATE INDEX IF NOT EXISTS ix_archetype_rules_archetype_version
    ON archetype_rules(archetype_id, archetype_version);

CREATE TABLE IF NOT EXISTS archetype_publications (
    archetype_id TEXT NOT NULL,
    archetype_version INTEGER NOT NULL CHECK (archetype_version >= 1),
    archetype_snapshot_sha256 TEXT NOT NULL,
    published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (archetype_id, archetype_version),
    UNIQUE (archetype_id, archetype_version, archetype_snapshot_sha256),
    FOREIGN KEY (
        archetype_id, archetype_version, archetype_snapshot_sha256
    ) REFERENCES style_archetypes(
        archetype_id, current_version, snapshot_sha256
    )
) STRICT;

CREATE TRIGGER IF NOT EXISTS validate_archetype_publication_insert
BEFORE INSERT ON archetype_publications
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM style_archetypes AS archetype
        WHERE archetype.archetype_id = NEW.archetype_id
          AND archetype.current_version = NEW.archetype_version
          AND archetype.status IN ('supported', 'reusable')
          AND archetype.snapshot_sha256 = NEW.archetype_snapshot_sha256
          AND NEW.archetype_snapshot_sha256 = canonical_row_sha256_v2(
              archetype.archetype_id,
              archetype.name,
              archetype.category_scope,
              archetype.carrier,
              archetype.primary_job_scope,
              archetype.audience_state,
              archetype.description,
              archetype.production_cost,
              archetype.confidence,
              archetype.status,
              archetype.current_version,
              archetype.taxonomy_version
          )
    ) THEN RAISE(ABORT, 'archetype_snapshot_hash_mismatch') END;
END;

CREATE TRIGGER IF NOT EXISTS immutable_archetype_publications_update
BEFORE UPDATE ON archetype_publications
BEGIN
    SELECT RAISE(ABORT, 'immutable_archetype_publications');
END;

CREATE TRIGGER IF NOT EXISTS immutable_archetype_publications_delete
BEFORE DELETE ON archetype_publications
BEGIN
    SELECT RAISE(ABORT, 'immutable_archetype_publications');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_archetype_update
BEFORE UPDATE ON style_archetypes
WHEN EXISTS (
    SELECT 1 FROM archetype_publications
    WHERE archetype_id = OLD.archetype_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_archetype_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_archetype_delete
BEFORE DELETE ON style_archetypes
WHEN EXISTS (
    SELECT 1 FROM archetype_publications
    WHERE archetype_id = OLD.archetype_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_archetype_frozen');
END;

CREATE TABLE IF NOT EXISTS rule_evidence (
    rule_evidence_id TEXT PRIMARY KEY NOT NULL,
    rule_id TEXT NOT NULL,
    observation_type TEXT NOT NULL
        CHECK (observation_type IN ('visual', 'copy', 'post_metric')),
    observation_id TEXT NOT NULL,
    evidence_role TEXT NOT NULL
        CHECK (evidence_role IN ('support', 'counterexample', 'boundary')),
    limitations TEXT NOT NULL DEFAULT '',
    UNIQUE (rule_id, observation_type, observation_id, evidence_role),
    UNIQUE (rule_id, observation_type, observation_id),
    FOREIGN KEY (rule_id) REFERENCES archetype_rules(rule_id)
        ON UPDATE CASCADE
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_rule_evidence_typed_insert
BEFORE INSERT ON rule_evidence
BEGIN
    SELECT CASE
        WHEN NEW.observation_type = 'visual'
             AND NOT EXISTS (
                 SELECT 1 FROM visual_observations
                 WHERE visual_observation_id = NEW.observation_id
             )
            THEN RAISE(ABORT, 'rule_evidence_observation_missing')
        WHEN NEW.observation_type = 'copy'
             AND NOT EXISTS (
                 SELECT 1 FROM copy_observations
                 WHERE observation_id = NEW.observation_id
             )
            THEN RAISE(ABORT, 'rule_evidence_observation_missing')
        WHEN NEW.observation_type = 'post_metric'
             AND NOT EXISTS (
                 SELECT 1 FROM post_metrics
                 WHERE post_metric_id = NEW.observation_id
             )
            THEN RAISE(ABORT, 'rule_evidence_observation_missing')
    END;
END;

CREATE TRIGGER IF NOT EXISTS trg_rule_evidence_typed_update
BEFORE UPDATE OF observation_type, observation_id ON rule_evidence
BEGIN
    SELECT CASE
        WHEN NEW.observation_type = 'visual'
             AND NOT EXISTS (
                 SELECT 1 FROM visual_observations
                 WHERE visual_observation_id = NEW.observation_id
             )
            THEN RAISE(ABORT, 'rule_evidence_observation_missing')
        WHEN NEW.observation_type = 'copy'
             AND NOT EXISTS (
                 SELECT 1 FROM copy_observations
                 WHERE observation_id = NEW.observation_id
             )
            THEN RAISE(ABORT, 'rule_evidence_observation_missing')
        WHEN NEW.observation_type = 'post_metric'
             AND NOT EXISTS (
                 SELECT 1 FROM post_metrics
                 WHERE post_metric_id = NEW.observation_id
             )
            THEN RAISE(ABORT, 'rule_evidence_observation_missing')
    END;
END;

CREATE TRIGGER IF NOT EXISTS trg_visual_observation_guard_evidence_delete
BEFORE DELETE ON visual_observations
WHEN EXISTS (
    SELECT 1 FROM rule_evidence
    WHERE observation_type = 'visual'
      AND observation_id = OLD.visual_observation_id
)
BEGIN
    SELECT RAISE(ABORT, 'rule_evidence_visual_target_referenced');
END;

CREATE TRIGGER IF NOT EXISTS trg_visual_observation_guard_evidence_update
BEFORE UPDATE OF visual_observation_id ON visual_observations
WHEN NEW.visual_observation_id IS NOT OLD.visual_observation_id
 AND EXISTS (
     SELECT 1 FROM rule_evidence
     WHERE observation_type = 'visual'
       AND observation_id = OLD.visual_observation_id
 )
BEGIN
    SELECT RAISE(ABORT, 'rule_evidence_visual_target_referenced');
END;

CREATE TRIGGER IF NOT EXISTS trg_copy_observation_guard_evidence_delete
BEFORE DELETE ON copy_observations
WHEN EXISTS (
    SELECT 1 FROM rule_evidence
    WHERE observation_type = 'copy'
      AND observation_id = OLD.observation_id
)
BEGIN
    SELECT RAISE(ABORT, 'rule_evidence_copy_target_referenced');
END;

CREATE TRIGGER IF NOT EXISTS trg_copy_observation_guard_evidence_update
BEFORE UPDATE OF observation_id ON copy_observations
WHEN NEW.observation_id IS NOT OLD.observation_id
 AND EXISTS (
     SELECT 1 FROM rule_evidence
     WHERE observation_type = 'copy'
       AND observation_id = OLD.observation_id
 )
BEGIN
    SELECT RAISE(ABORT, 'rule_evidence_copy_target_referenced');
END;

CREATE TRIGGER IF NOT EXISTS trg_post_metric_guard_evidence_delete
BEFORE DELETE ON post_metrics
WHEN EXISTS (
    SELECT 1 FROM rule_evidence
    WHERE observation_type = 'post_metric'
      AND observation_id = OLD.post_metric_id
)
BEGIN
    SELECT RAISE(ABORT, 'rule_evidence_post_metric_target_referenced');
END;

CREATE TRIGGER IF NOT EXISTS trg_post_metric_guard_evidence_update
BEFORE UPDATE OF post_metric_id ON post_metrics
WHEN NEW.post_metric_id IS NOT OLD.post_metric_id
 AND EXISTS (
     SELECT 1 FROM rule_evidence
     WHERE observation_type = 'post_metric'
       AND observation_id = OLD.post_metric_id
 )
BEGIN
    SELECT RAISE(ABORT, 'rule_evidence_post_metric_target_referenced');
END;

CREATE INDEX IF NOT EXISTS ix_rule_evidence_rule
    ON rule_evidence(rule_id);

CREATE INDEX IF NOT EXISTS ix_rule_evidence_observation
    ON rule_evidence(observation_type, observation_id);

CREATE VIEW IF NOT EXISTS rule_evidence_post_associations AS
SELECT
    evidence.rule_evidence_id,
    evidence.rule_id,
    evidence.evidence_role,
    CASE evidence.observation_type
        WHEN 'visual' THEN visual.library_post_id
        WHEN 'copy' THEN copy.library_post_id
        WHEN 'post_metric' THEN metric_observation.library_post_id
    END AS library_post_id
FROM rule_evidence AS evidence
LEFT JOIN visual_observations AS visual
  ON evidence.observation_type = 'visual'
 AND visual.visual_observation_id = evidence.observation_id
LEFT JOIN copy_observations AS copy
  ON evidence.observation_type = 'copy'
 AND copy.observation_id = evidence.observation_id
LEFT JOIN post_metrics AS metric
  ON evidence.observation_type = 'post_metric'
 AND metric.post_metric_id = evidence.observation_id
LEFT JOIN style_post_observations AS metric_observation
  ON metric_observation.post_observation_id = metric.post_observation_id;

CREATE TABLE IF NOT EXISTS archetype_rule_publications (
    rule_id TEXT PRIMARY KEY NOT NULL,
    archetype_id TEXT NOT NULL,
    archetype_version INTEGER NOT NULL CHECK (archetype_version >= 1),
    archetype_snapshot_sha256 TEXT NOT NULL,
    rule_sha256 TEXT NOT NULL UNIQUE,
    evidence_set_sha256 TEXT NOT NULL,
    evidence_count INTEGER NOT NULL CHECK (evidence_count > 0),
    published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rule_id, archetype_id, archetype_version)
        REFERENCES archetype_rules(rule_id, archetype_id, archetype_version),
    FOREIGN KEY (
        archetype_id, archetype_version, archetype_snapshot_sha256
    ) REFERENCES archetype_publications(
        archetype_id, archetype_version, archetype_snapshot_sha256
    ),
    UNIQUE (
        rule_id, archetype_id, archetype_version,
        archetype_snapshot_sha256
    )
) STRICT;

CREATE TRIGGER IF NOT EXISTS validate_archetype_rule_publication_insert
BEFORE INSERT ON archetype_rule_publications
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM archetype_rules AS rule
        WHERE rule.rule_id = NEW.rule_id
          AND rule.archetype_id = NEW.archetype_id
          AND rule.archetype_version = NEW.archetype_version
          AND rule.status = 'active'
          AND NEW.rule_sha256 = canonical_row_sha256_v2(
              rule.rule_id,
              rule.archetype_id,
              rule.archetype_version,
              rule.rule_type,
              canonical_json_v2(rule.rule_payload_json),
              rule.applicability_scope,
              rule.status
          )
    ) THEN RAISE(ABORT, 'rule_publication_hash_mismatch') END;

    SELECT CASE WHEN NEW.evidence_count <> (
        SELECT count(*) FROM rule_evidence
        WHERE rule_id = NEW.rule_id
    ) THEN RAISE(ABORT, 'rule_publication_evidence_count_mismatch') END;

    SELECT CASE WHEN NEW.evidence_set_sha256 <> (
        SELECT canonical_sha256_agg_v2(evidence_preimage)
        FROM (
            SELECT printf(
                '%s|%s|%s|%s|%s|%s',
                evidence.rule_evidence_id,
                evidence.observation_type,
                evidence.observation_id,
                evidence.evidence_role,
                evidence.limitations,
                CASE evidence.observation_type
                    WHEN 'visual' THEN visual.observation_sha256
                    WHEN 'copy' THEN copy.observation_sha256
                    WHEN 'post_metric' THEN performance.performance_computation_sha256
                END
            ) AS evidence_preimage
            FROM rule_evidence AS evidence
            LEFT JOIN visual_observations AS visual
              ON evidence.observation_type = 'visual'
             AND visual.visual_observation_id = evidence.observation_id
            LEFT JOIN copy_observations AS copy
              ON evidence.observation_type = 'copy'
             AND copy.observation_id = evidence.observation_id
            LEFT JOIN post_metrics AS metric
              ON evidence.observation_type = 'post_metric'
             AND metric.post_metric_id = evidence.observation_id
            LEFT JOIN post_performance_publications AS performance
              ON performance.target_post_metric_id = metric.post_metric_id
            WHERE evidence.rule_id = NEW.rule_id
            ORDER BY evidence.rule_evidence_id
        )
    ) THEN RAISE(ABORT, 'rule_publication_evidence_hash_mismatch') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM rule_evidence AS evidence
        LEFT JOIN visual_observations AS visual
          ON evidence.observation_type = 'visual'
         AND visual.visual_observation_id = evidence.observation_id
        LEFT JOIN copy_observations AS copy
          ON evidence.observation_type = 'copy'
         AND copy.observation_id = evidence.observation_id
        LEFT JOIN post_metrics AS metric
          ON evidence.observation_type = 'post_metric'
         AND metric.post_metric_id = evidence.observation_id
        LEFT JOIN post_performance_publications AS performance
          ON performance.target_post_metric_id = metric.post_metric_id
        WHERE evidence.rule_id = NEW.rule_id
          AND CASE evidence.observation_type
              WHEN 'visual' THEN visual.observation_sha256
              WHEN 'copy' THEN copy.observation_sha256
              WHEN 'post_metric' THEN performance.performance_computation_sha256
          END IS NULL
    ) THEN RAISE(ABORT, 'rule_publication_evidence_target_unpublished') END;

    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM rule_evidence
        WHERE rule_id = NEW.rule_id AND evidence_role = 'support'
    ) THEN RAISE(ABORT, 'rule_publication_support_missing') END;

    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM rule_evidence
        WHERE rule_id = NEW.rule_id
          AND evidence_role IN ('counterexample', 'boundary')
    ) THEN RAISE(ABORT, 'rule_publication_counterevidence_missing') END;
END;

CREATE TRIGGER IF NOT EXISTS immutable_archetype_rule_publications_update
BEFORE UPDATE ON archetype_rule_publications
BEGIN
    SELECT RAISE(ABORT, 'immutable_archetype_rule_publications');
END;

CREATE TRIGGER IF NOT EXISTS immutable_archetype_rule_publications_delete
BEFORE DELETE ON archetype_rule_publications
BEGIN
    SELECT RAISE(ABORT, 'immutable_archetype_rule_publications');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_archetype_rule_update
BEFORE UPDATE ON archetype_rules
WHEN EXISTS (
    SELECT 1 FROM archetype_rule_publications
    WHERE rule_id = OLD.rule_id
)
BEGIN
    SELECT RAISE(ABORT, 'binding_rule_published_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_archetype_rule_delete
BEFORE DELETE ON archetype_rules
WHEN EXISTS (
    SELECT 1 FROM archetype_rule_publications
    WHERE rule_id = OLD.rule_id
)
BEGIN
    SELECT RAISE(ABORT, 'binding_rule_published_frozen');
END;

-- One published archetype version is a closed rule bundle.  Publishing a
-- later rule into the same version would silently change what query/bind mean;
-- any addition or edit therefore requires a new archetype version.
CREATE TRIGGER IF NOT EXISTS freeze_published_archetype_rule_insert
BEFORE INSERT ON archetype_rules
WHEN EXISTS (
    SELECT 1 FROM archetype_publications
    WHERE archetype_id=NEW.archetype_id
      AND archetype_version=NEW.archetype_version
)
BEGIN
    SELECT RAISE(ABORT, 'published_archetype_rule_set_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_archetype_any_rule_update
BEFORE UPDATE ON archetype_rules
WHEN EXISTS (
    SELECT 1 FROM archetype_publications
    WHERE archetype_id=OLD.archetype_id
      AND archetype_version=OLD.archetype_version
)
BEGIN
    SELECT RAISE(ABORT, 'published_archetype_rule_set_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_archetype_any_rule_delete
BEFORE DELETE ON archetype_rules
WHEN EXISTS (
    SELECT 1 FROM archetype_publications
    WHERE archetype_id=OLD.archetype_id
      AND archetype_version=OLD.archetype_version
)
BEGIN
    SELECT RAISE(ABORT, 'published_archetype_rule_set_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_archetype_evidence_insert
BEFORE INSERT ON rule_evidence
WHEN EXISTS (
    SELECT 1
    FROM archetype_rules AS rule
    JOIN archetype_publications AS publication
      ON publication.archetype_id=rule.archetype_id
     AND publication.archetype_version=rule.archetype_version
    WHERE rule.rule_id=NEW.rule_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_archetype_evidence_set_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_archetype_evidence_update
BEFORE UPDATE ON rule_evidence
WHEN EXISTS (
    SELECT 1
    FROM archetype_rules AS rule
    JOIN archetype_publications AS publication
      ON publication.archetype_id=rule.archetype_id
     AND publication.archetype_version=rule.archetype_version
    WHERE rule.rule_id=OLD.rule_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_archetype_evidence_set_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_archetype_evidence_delete
BEFORE DELETE ON rule_evidence
WHEN EXISTS (
    SELECT 1
    FROM archetype_rules AS rule
    JOIN archetype_publications AS publication
      ON publication.archetype_id=rule.archetype_id
     AND publication.archetype_version=rule.archetype_version
    WHERE rule.rule_id=OLD.rule_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_archetype_evidence_set_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_rule_evidence_insert
BEFORE INSERT ON rule_evidence
WHEN EXISTS (
    SELECT 1 FROM archetype_rule_publications
    WHERE rule_id = NEW.rule_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_rule_evidence_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_rule_evidence_update
BEFORE UPDATE ON rule_evidence
WHEN EXISTS (
    SELECT 1 FROM archetype_rule_publications
    WHERE rule_id = OLD.rule_id OR rule_id = NEW.rule_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_rule_evidence_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_rule_evidence_delete
BEFORE DELETE ON rule_evidence
WHEN EXISTS (
    SELECT 1 FROM archetype_rule_publications
    WHERE rule_id = OLD.rule_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_rule_evidence_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_visual_evidence_update
BEFORE UPDATE ON visual_observations
WHEN EXISTS (
    SELECT 1
    FROM rule_evidence AS evidence
    JOIN archetype_rule_publications AS publication
      ON publication.rule_id = evidence.rule_id
    WHERE evidence.observation_type = 'visual'
      AND evidence.observation_id = OLD.visual_observation_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_rule_evidence_target_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_visual_evidence_delete
BEFORE DELETE ON visual_observations
WHEN EXISTS (
    SELECT 1
    FROM rule_evidence AS evidence
    JOIN archetype_rule_publications AS publication
      ON publication.rule_id = evidence.rule_id
    WHERE evidence.observation_type = 'visual'
      AND evidence.observation_id = OLD.visual_observation_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_rule_evidence_target_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_copy_evidence_update
BEFORE UPDATE ON copy_observations
WHEN EXISTS (
    SELECT 1
    FROM rule_evidence AS evidence
    JOIN archetype_rule_publications AS publication
      ON publication.rule_id = evidence.rule_id
    WHERE evidence.observation_type = 'copy'
      AND evidence.observation_id = OLD.observation_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_rule_evidence_target_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_copy_evidence_delete
BEFORE DELETE ON copy_observations
WHEN EXISTS (
    SELECT 1
    FROM rule_evidence AS evidence
    JOIN archetype_rule_publications AS publication
      ON publication.rule_id = evidence.rule_id
    WHERE evidence.observation_type = 'copy'
      AND evidence.observation_id = OLD.observation_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_rule_evidence_target_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_metric_evidence_update
BEFORE UPDATE ON post_metrics
WHEN EXISTS (
    SELECT 1
    FROM rule_evidence AS evidence
    JOIN archetype_rule_publications AS publication
      ON publication.rule_id = evidence.rule_id
    WHERE evidence.observation_type = 'post_metric'
      AND evidence.observation_id = OLD.post_metric_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_rule_evidence_target_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_metric_evidence_delete
BEFORE DELETE ON post_metrics
WHEN EXISTS (
    SELECT 1
    FROM rule_evidence AS evidence
    JOIN archetype_rule_publications AS publication
      ON publication.rule_id = evidence.rule_id
    WHERE evidence.observation_type = 'post_metric'
      AND evidence.observation_id = OLD.post_metric_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_rule_evidence_target_frozen');
END;

CREATE TABLE IF NOT EXISTS archetype_review_receipts (
    review_receipt_sha256 TEXT PRIMARY KEY NOT NULL,
    archetype_id TEXT NOT NULL,
    archetype_version INTEGER NOT NULL CHECK (archetype_version >= 1),
    candidate_snapshot_sha256 TEXT NOT NULL,
    category TEXT NOT NULL,
    carrier TEXT NOT NULL,
    primary_job TEXT NOT NULL,
    selected_rule_ids TEXT NOT NULL
        CHECK (json_valid(selected_rule_ids)
               AND json_type(selected_rule_ids)='array'
               AND json_array_length(selected_rule_ids) >= 2),
    rule_bundle_sha256 TEXT NOT NULL,
    evidence_bundle_sha256 TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision='PASS'),
    target_status TEXT NOT NULL CHECK (target_status='supported'),
    content_owner_id TEXT NOT NULL,
    reviewer_ids TEXT NOT NULL
        CHECK (json_valid(reviewer_ids)
               AND json_type(reviewer_ids)='array'
               AND json_array_length(reviewer_ids) >= 1),
    reviewer_independence_status TEXT NOT NULL CHECK (
        reviewer_independence_status='independent'
    ),
    reviewed_at TEXT NOT NULL,
    limitations_json TEXT NOT NULL
        CHECK (json_valid(limitations_json)
               AND json_type(limitations_json)='array'
               AND json_array_length(limitations_json) >= 1),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (review_receipt_sha256, archetype_id, archetype_version),
    FOREIGN KEY (archetype_id) REFERENCES style_archetypes(archetype_id)
) STRICT;

CREATE TRIGGER IF NOT EXISTS validate_archetype_review_receipt_insert
BEFORE INSERT ON archetype_review_receipts
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM style_archetypes AS archetype
        WHERE archetype.archetype_id=NEW.archetype_id
          AND archetype.current_version=NEW.archetype_version
          AND archetype.status='candidate'
          AND archetype.snapshot_sha256=NEW.candidate_snapshot_sha256
          AND archetype.category_scope=NEW.category
          AND archetype.carrier=NEW.carrier
          AND archetype.primary_job_scope=NEW.primary_job
    ) THEN RAISE(ABORT, 'review_candidate_snapshot_mismatch') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM json_each(NEW.selected_rule_ids) AS selected
        LEFT JOIN archetype_rules AS rule ON rule.rule_id=selected.value
        WHERE selected.type <> 'text'
           OR rule.rule_id IS NULL
           OR rule.archetype_id <> NEW.archetype_id
           OR rule.archetype_version <> NEW.archetype_version
           OR rule.status <> 'active'
    ) THEN RAISE(ABORT, 'review_rule_selection_invalid') END;

    SELECT CASE WHEN
        json_array_length(NEW.selected_rule_ids) <> (
            SELECT count(*) FROM archetype_rules
            WHERE archetype_id=NEW.archetype_id
              AND archetype_version=NEW.archetype_version
              AND status='active'
        )
        OR (
            SELECT count(DISTINCT value)
            FROM json_each(NEW.selected_rule_ids)
            WHERE type='text'
        ) <> json_array_length(NEW.selected_rule_ids)
        OR EXISTS (
            SELECT 1 FROM archetype_rules AS rule
            WHERE rule.archetype_id=NEW.archetype_id
              AND rule.archetype_version=NEW.archetype_version
              AND rule.status='active'
              AND NOT EXISTS (
                  SELECT 1 FROM json_each(NEW.selected_rule_ids)
                  WHERE value=rule.rule_id
              )
        )
    THEN RAISE(ABORT, 'review_rule_set_not_closed') END;

    SELECT CASE WHEN NEW.rule_bundle_sha256 <> (
        SELECT canonical_sha256_agg_v2(rule_preimage)
        FROM (
            SELECT printf(
                '%s|%s',
                rule.rule_id,
                canonical_row_sha256_v2(
                    rule.rule_id,
                    rule.archetype_id,
                    rule.archetype_version,
                    rule.rule_type,
                    canonical_json_v2(rule.rule_payload_json),
                    rule.applicability_scope,
                    rule.status
                )
            ) AS rule_preimage
            FROM json_each(NEW.selected_rule_ids) AS selected
            JOIN archetype_rules AS rule ON rule.rule_id=selected.value
            ORDER BY rule.rule_id
        )
    ) THEN RAISE(ABORT, 'review_rule_bundle_hash_mismatch') END;

    SELECT CASE WHEN NEW.evidence_bundle_sha256 <> (
        SELECT canonical_sha256_agg_v2(evidence_preimage)
        FROM (
            SELECT printf(
                '%s|%s|%s|%s|%s|%s|%s',
                evidence.rule_id,
                evidence.rule_evidence_id,
                evidence.observation_type,
                evidence.observation_id,
                evidence.evidence_role,
                evidence.limitations,
                CASE evidence.observation_type
                    WHEN 'visual' THEN feature.feature_link_sha256
                    WHEN 'copy' THEN feature.feature_link_sha256
                    WHEN 'post_metric' THEN performance.performance_computation_sha256
                END
            ) AS evidence_preimage
            FROM json_each(NEW.selected_rule_ids) AS selected
            JOIN rule_evidence AS evidence ON evidence.rule_id=selected.value
            LEFT JOIN feature_observation_links AS feature
              ON evidence.observation_type IN ('visual','copy')
             AND feature.observation_type=evidence.observation_type
             AND feature.observation_id=evidence.observation_id
            LEFT JOIN post_metrics AS metric
              ON evidence.observation_type='post_metric'
             AND metric.post_metric_id=evidence.observation_id
            LEFT JOIN post_performance_publications AS performance
              ON performance.target_post_metric_id=metric.post_metric_id
            ORDER BY evidence.rule_id,evidence.rule_evidence_id
        )
    ) THEN RAISE(ABORT, 'review_evidence_bundle_hash_mismatch') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM json_each(NEW.selected_rule_ids) AS selected
        JOIN rule_evidence AS evidence ON evidence.rule_id=selected.value
        LEFT JOIN feature_observation_links AS feature
          ON evidence.observation_type IN ('visual','copy')
         AND feature.observation_type=evidence.observation_type
         AND feature.observation_id=evidence.observation_id
        LEFT JOIN post_metrics AS metric
          ON evidence.observation_type='post_metric'
         AND metric.post_metric_id=evidence.observation_id
        LEFT JOIN post_performance_publications AS performance
          ON performance.target_post_metric_id=metric.post_metric_id
        WHERE CASE evidence.observation_type
            WHEN 'visual' THEN feature.feature_link_sha256
            WHEN 'copy' THEN feature.feature_link_sha256
            WHEN 'post_metric' THEN performance.performance_computation_sha256
        END IS NULL
    ) THEN RAISE(ABORT, 'review_evidence_link_missing') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM json_each(NEW.reviewer_ids)
        WHERE type <> 'text' OR trim(value)=''
           OR value=NEW.content_owner_id
    ) THEN RAISE(ABORT, 'reviewer_not_independent') END;

    SELECT CASE WHEN date(NEW.reviewed_at) IS NULL
                      OR date(NEW.reviewed_at) > date('now','localtime')
        THEN RAISE(ABORT, 'review_date_invalid') END;

    SELECT CASE WHEN NEW.review_receipt_sha256 <>
        canonical_row_sha256_v2(
            NEW.archetype_id,
            NEW.archetype_version,
            NEW.candidate_snapshot_sha256,
            NEW.category,
            NEW.carrier,
            NEW.primary_job,
            canonical_json_v2(NEW.selected_rule_ids),
            NEW.rule_bundle_sha256,
            NEW.evidence_bundle_sha256,
            NEW.decision,
            NEW.target_status,
            NEW.content_owner_id,
            canonical_json_v2(NEW.reviewer_ids),
            NEW.reviewer_independence_status,
            NEW.reviewed_at,
            canonical_json_v2(NEW.limitations_json)
        )
    THEN RAISE(ABORT, 'review_receipt_hash_mismatch') END;
END;

CREATE TRIGGER IF NOT EXISTS immutable_archetype_review_receipts_update
BEFORE UPDATE ON archetype_review_receipts
BEGIN
    SELECT RAISE(ABORT, 'immutable_archetype_review_receipts');
END;

CREATE TRIGGER IF NOT EXISTS immutable_archetype_review_receipts_delete
BEFORE DELETE ON archetype_review_receipts
BEGIN
    SELECT RAISE(ABORT, 'immutable_archetype_review_receipts');
END;

CREATE TABLE IF NOT EXISTS qualified_style_publications (
    archetype_id TEXT NOT NULL,
    archetype_version INTEGER NOT NULL CHECK (archetype_version >= 1),
    archetype_snapshot_sha256 TEXT NOT NULL,
    review_receipt_sha256 TEXT NOT NULL,
    selected_rule_ids TEXT NOT NULL
        CHECK (json_valid(selected_rule_ids)
               AND json_type(selected_rule_ids)='array'
               AND json_array_length(selected_rule_ids) >= 2),
    feature_link_set_sha256 TEXT NOT NULL,
    support_account_count INTEGER NOT NULL CHECK (support_account_count >= 2),
    support_cluster_count INTEGER NOT NULL CHECK (support_cluster_count >= 2),
    qualification_sha256 TEXT NOT NULL UNIQUE,
    published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (archetype_id, archetype_version),
    FOREIGN KEY (
        archetype_id,archetype_version,archetype_snapshot_sha256
    ) REFERENCES archetype_publications(
        archetype_id,archetype_version,archetype_snapshot_sha256
    ),
    FOREIGN KEY (
        review_receipt_sha256,archetype_id,archetype_version
    ) REFERENCES archetype_review_receipts(
        review_receipt_sha256,archetype_id,archetype_version
    )
) STRICT;

CREATE TRIGGER IF NOT EXISTS validate_qualified_style_publication_insert
BEFORE INSERT ON qualified_style_publications
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM archetype_review_receipts AS review
        WHERE review.review_receipt_sha256=NEW.review_receipt_sha256
          AND review.archetype_id=NEW.archetype_id
          AND review.archetype_version=NEW.archetype_version
          AND canonical_json_v2(review.selected_rule_ids)=
              canonical_json_v2(NEW.selected_rule_ids)
    ) THEN RAISE(ABORT, 'qualification_review_receipt_mismatch') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM json_each(NEW.selected_rule_ids) AS selected
        LEFT JOIN archetype_rule_publications AS publication
          ON publication.rule_id=selected.value
         AND publication.archetype_id=NEW.archetype_id
         AND publication.archetype_version=NEW.archetype_version
         AND publication.archetype_snapshot_sha256=
             NEW.archetype_snapshot_sha256
        LEFT JOIN archetype_rules AS rule ON rule.rule_id=selected.value
        WHERE selected.type <> 'text'
           OR publication.rule_id IS NULL
           OR json_extract(
               rule.rule_payload_json,'$.claim_kind'
           ) <> 'contrastive_performance_hypothesis'
           OR json_extract(
               rule.rule_payload_json,'$.performance_evidence_scope'
           ) <> 'public_proxy_association'
    ) THEN RAISE(ABORT, 'qualification_rule_unpublished_or_unscoped') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM json_each(NEW.selected_rule_ids) AS selected
        JOIN archetype_rules AS rule ON rule.rule_id=selected.value
        JOIN rule_evidence AS evidence ON evidence.rule_id=rule.rule_id
        JOIN feature_observation_links AS feature
          ON feature.observation_type=evidence.observation_type
         AND feature.observation_id=evidence.observation_id
        JOIN post_performance_publications AS performance
          ON performance.post_observation_id=feature.post_observation_id
        JOIN performance_definitions AS definition
          ON definition.performance_definition_id=
             performance.performance_definition_id
         AND definition.metric_name=performance.metric_name
        JOIN style_archetypes AS archetype
          ON archetype.archetype_id=NEW.archetype_id
         AND archetype.current_version=NEW.archetype_version
        WHERE definition.primary_job <> archetype.primary_job_scope
           OR definition.business_objective <> 'engagement_proxy'
           OR definition.traffic_stage <>
              json_extract(rule.rule_payload_json,'$.traffic_stage')
           OR definition.traffic_stage IS NULL
    ) THEN RAISE(ABORT, 'qualification_performance_scope_mismatch') END;

    -- Every rule must have matching-type high support from at least two
    -- independent accounts and clusters, plus a matching-type ordinary/low
    -- counterexample or boundary.
    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM json_each(NEW.selected_rule_ids) AS selected
        JOIN archetype_rules AS rule ON rule.rule_id=selected.value
        WHERE (
            SELECT count(DISTINCT post.library_account_id)
            FROM rule_evidence AS evidence
            JOIN feature_observation_links AS feature
              ON feature.observation_type=evidence.observation_type
             AND feature.observation_id=evidence.observation_id
            JOIN post_performance_publications AS performance
              ON performance.post_observation_id=feature.post_observation_id
            JOIN style_posts AS post
              ON post.library_post_id=feature.library_post_id
            WHERE evidence.rule_id=rule.rule_id
              AND evidence.evidence_role='support'
              AND evidence.observation_type=CASE
                  WHEN rule.rule_type='copy' THEN 'copy' ELSE 'visual' END
              AND performance.performance_tier='high'
              AND performance.visibility_scope='public_proxy'
              AND performance.traffic_verdict='not_applicable'
        ) < 2
        OR (
            SELECT count(DISTINCT post.cluster_id)
            FROM rule_evidence AS evidence
            JOIN feature_observation_links AS feature
              ON feature.observation_type=evidence.observation_type
             AND feature.observation_id=evidence.observation_id
            JOIN post_performance_publications AS performance
              ON performance.post_observation_id=feature.post_observation_id
            JOIN style_posts AS post
              ON post.library_post_id=feature.library_post_id
            WHERE evidence.rule_id=rule.rule_id
              AND evidence.evidence_role='support'
              AND evidence.observation_type=CASE
                  WHEN rule.rule_type='copy' THEN 'copy' ELSE 'visual' END
              AND performance.performance_tier='high'
              AND performance.visibility_scope='public_proxy'
              AND performance.traffic_verdict='not_applicable'
              AND post.cluster_id IS NOT NULL AND trim(post.cluster_id) <> ''
        ) < 2
        OR NOT EXISTS (
            SELECT 1
            FROM rule_evidence AS evidence
            JOIN feature_observation_links AS feature
              ON feature.observation_type=evidence.observation_type
             AND feature.observation_id=evidence.observation_id
            JOIN post_performance_publications AS performance
              ON performance.post_observation_id=feature.post_observation_id
            WHERE evidence.rule_id=rule.rule_id
              AND evidence.evidence_role IN ('counterexample','boundary')
              AND evidence.observation_type=CASE
                  WHEN rule.rule_type='copy' THEN 'copy' ELSE 'visual' END
              AND performance.performance_tier IN ('ordinary','low')
              AND performance.visibility_scope='public_proxy'
              AND performance.traffic_verdict='not_applicable'
        )
    ) THEN RAISE(ABORT, 'qualification_independent_contrast_missing') END;

    -- A post cannot be positive evidence for one rule and negative evidence
    -- for another rule in the same published bundle.  Flattening those roles
    -- into a draft would otherwise erase the contradiction.
    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM json_each(NEW.selected_rule_ids) AS positive_rule
        JOIN rule_evidence_post_associations AS positive
          ON positive.rule_id=positive_rule.value
         AND positive.evidence_role='support'
        JOIN json_each(NEW.selected_rule_ids) AS negative_rule
        JOIN rule_evidence_post_associations AS negative
          ON negative.rule_id=negative_rule.value
         AND negative.evidence_role IN ('counterexample','boundary')
         AND negative.library_post_id=positive.library_post_id
    ) THEN RAISE(ABORT, 'qualification_bundle_evidence_role_conflict') END;

    SELECT CASE WHEN NEW.feature_link_set_sha256 <> (
        SELECT canonical_sha256_agg_v2(feature_preimage)
        FROM (
            SELECT printf(
                '%s|%s|%s',
                evidence.rule_id,
                evidence.rule_evidence_id,
                feature.feature_link_sha256
            ) AS feature_preimage
            FROM json_each(NEW.selected_rule_ids) AS selected
            JOIN rule_evidence AS evidence ON evidence.rule_id=selected.value
            JOIN feature_observation_links AS feature
              ON feature.observation_type=evidence.observation_type
             AND feature.observation_id=evidence.observation_id
            WHERE evidence.observation_type IN ('visual','copy')
            ORDER BY evidence.rule_id,evidence.rule_evidence_id
        )
    ) THEN RAISE(ABORT, 'qualification_feature_link_hash_mismatch') END;

    SELECT CASE WHEN NEW.support_account_count <> (
        SELECT count(DISTINCT post.library_account_id)
        FROM json_each(NEW.selected_rule_ids) AS selected
        JOIN rule_evidence AS evidence ON evidence.rule_id=selected.value
        JOIN feature_observation_links AS feature
          ON feature.observation_type=evidence.observation_type
         AND feature.observation_id=evidence.observation_id
        JOIN post_performance_publications AS performance
          ON performance.post_observation_id=feature.post_observation_id
        JOIN style_posts AS post ON post.library_post_id=feature.library_post_id
        WHERE evidence.evidence_role='support'
          AND performance.performance_tier='high'
    ) THEN RAISE(ABORT, 'qualification_support_account_count_mismatch') END;

    SELECT CASE WHEN NEW.support_cluster_count <> (
        SELECT count(DISTINCT post.cluster_id)
        FROM json_each(NEW.selected_rule_ids) AS selected
        JOIN rule_evidence AS evidence ON evidence.rule_id=selected.value
        JOIN feature_observation_links AS feature
          ON feature.observation_type=evidence.observation_type
         AND feature.observation_id=evidence.observation_id
        JOIN post_performance_publications AS performance
          ON performance.post_observation_id=feature.post_observation_id
        JOIN style_posts AS post ON post.library_post_id=feature.library_post_id
        WHERE evidence.evidence_role='support'
          AND performance.performance_tier='high'
          AND post.cluster_id IS NOT NULL AND trim(post.cluster_id) <> ''
    ) THEN RAISE(ABORT, 'qualification_support_cluster_count_mismatch') END;

    SELECT CASE WHEN NEW.qualification_sha256 <>
        canonical_row_sha256_v2(
            NEW.archetype_id,
            NEW.archetype_version,
            NEW.archetype_snapshot_sha256,
            NEW.review_receipt_sha256,
            canonical_json_v2(NEW.selected_rule_ids),
            NEW.feature_link_set_sha256,
            NEW.support_account_count,
            NEW.support_cluster_count
        )
    THEN RAISE(ABORT, 'qualification_hash_mismatch') END;
END;

CREATE TRIGGER IF NOT EXISTS immutable_qualified_style_publications_update
BEFORE UPDATE ON qualified_style_publications
BEGIN
    SELECT RAISE(ABORT, 'immutable_qualified_style_publications');
END;

CREATE TRIGGER IF NOT EXISTS immutable_qualified_style_publications_delete
BEFORE DELETE ON qualified_style_publications
BEGIN
    SELECT RAISE(ABORT, 'immutable_qualified_style_publications');
END;

CREATE TABLE IF NOT EXISTS starter_pack_publications (
    starter_pack_id TEXT NOT NULL,
    starter_pack_version INTEGER NOT NULL CHECK (starter_pack_version >= 1),
    starter_prompt_id TEXT NOT NULL,
    manifest_json TEXT NOT NULL
        CHECK (json_valid(manifest_json) AND json_type(manifest_json) = 'object'),
    starter_pack_sha256 TEXT NOT NULL UNIQUE,
    published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (starter_pack_id, starter_pack_version),
    UNIQUE (
        starter_pack_id, starter_pack_version,
        starter_pack_sha256, starter_prompt_id
    )
) STRICT;

CREATE TRIGGER IF NOT EXISTS validate_starter_pack_publication_insert
BEFORE INSERT ON starter_pack_publications
WHEN NEW.starter_pack_sha256 <> canonical_row_sha256_v2(
    NEW.starter_pack_id,
    NEW.starter_pack_version,
    NEW.starter_prompt_id,
    canonical_json_v2(NEW.manifest_json)
)
BEGIN
    SELECT RAISE(ABORT, 'starter_pack_manifest_hash_mismatch');
END;

CREATE TRIGGER IF NOT EXISTS immutable_starter_pack_publications_update
BEFORE UPDATE ON starter_pack_publications
BEGIN
    SELECT RAISE(ABORT, 'immutable_starter_pack_publications');
END;

CREATE TRIGGER IF NOT EXISTS immutable_starter_pack_publications_delete
BEFORE DELETE ON starter_pack_publications
BEGIN
    SELECT RAISE(ABORT, 'immutable_starter_pack_publications');
END;

CREATE TABLE IF NOT EXISTS draft_style_bindings (
    draft_binding_id TEXT PRIMARY KEY NOT NULL,
    draft_id TEXT NOT NULL,
    binding_source TEXT NOT NULL DEFAULT 'library'
        CHECK (binding_source IN ('library', 'starter_pack')),
    archetype_id TEXT,
    binding_role TEXT NOT NULL
        CHECK (binding_role = 'primary'),
    archetype_version INTEGER
        CHECK (archetype_version IS NULL OR archetype_version >= 1),
    archetype_snapshot_sha256 TEXT,
    starter_pack_id TEXT,
    starter_pack_version INTEGER
        CHECK (starter_pack_version IS NULL OR starter_pack_version >= 1),
    starter_pack_sha256 TEXT,
    starter_prompt_id TEXT,
    selected_rule_ids TEXT NOT NULL DEFAULT '[]'
        CHECK (
            CASE WHEN json_valid(selected_rule_ids)
                THEN json_type(selected_rule_ids) = 'array'
                ELSE 0
            END
        ),
    reference_library_post_ids TEXT NOT NULL DEFAULT '[]'
        CHECK (
            CASE WHEN json_valid(reference_library_post_ids)
                THEN json_type(reference_library_post_ids) = 'array'
                ELSE 0
            END
        ),
    counterexample_library_post_ids TEXT NOT NULL DEFAULT '[]'
        CHECK (
            CASE WHEN json_valid(counterexample_library_post_ids)
                THEN json_type(counterexample_library_post_ids) = 'array'
                ELSE 0
            END
        ),
    material_plan_json TEXT NOT NULL DEFAULT '{}'
        CHECK (
            CASE WHEN json_valid(material_plan_json)
                THEN json_type(material_plan_json) = 'object'
                ELSE 0
            END
        ),
    intentional_deviations_json TEXT NOT NULL DEFAULT '[]'
        CHECK (
            CASE WHEN json_valid(intentional_deviations_json)
                THEN json_type(intentional_deviations_json) = 'array'
                ELSE 0
            END
        ),
    anti_patterns_checked_json TEXT NOT NULL DEFAULT '[]'
        CHECK (
            CASE WHEN json_valid(anti_patterns_checked_json)
                THEN json_type(anti_patterns_checked_json) = 'array'
                ELSE 0
            END
        ),
    retrieved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'PASS', 'PARTIAL', 'FAIL')),
    CHECK (
        (
            binding_source = 'library'
            AND archetype_id IS NOT NULL
            AND archetype_version IS NOT NULL
            AND archetype_snapshot_sha256 IS NOT NULL
            AND length(trim(archetype_snapshot_sha256)) > 0
            AND json_array_length(selected_rule_ids) > 0
            AND starter_pack_id IS NULL
            AND starter_pack_version IS NULL
            AND starter_pack_sha256 IS NULL
            AND starter_prompt_id IS NULL
        )
        OR
        (
            binding_source = 'starter_pack'
            AND archetype_id IS NULL
            AND archetype_version IS NULL
            AND archetype_snapshot_sha256 IS NULL
            AND json_array_length(selected_rule_ids) = 0
            AND starter_pack_id IS NOT NULL
            AND length(trim(starter_pack_id)) > 0
            AND starter_pack_version IS NOT NULL
            AND starter_pack_sha256 IS NOT NULL
            AND length(trim(starter_pack_sha256)) > 0
            AND starter_prompt_id IS NOT NULL
            AND length(trim(starter_prompt_id)) > 0
        )
    ),
    FOREIGN KEY (archetype_id) REFERENCES style_archetypes(archetype_id)
        ON UPDATE CASCADE,
    FOREIGN KEY (
        archetype_id, archetype_version, archetype_snapshot_sha256
    ) REFERENCES archetype_publications(
        archetype_id, archetype_version, archetype_snapshot_sha256
    ),
    FOREIGN KEY (
        starter_pack_id, starter_pack_version,
        starter_pack_sha256, starter_prompt_id
    ) REFERENCES starter_pack_publications(
        starter_pack_id, starter_pack_version,
        starter_pack_sha256, starter_prompt_id
    ),
    UNIQUE (draft_id),
    UNIQUE (draft_binding_id, draft_id)
) STRICT;

CREATE TABLE IF NOT EXISTS draft_binding_review_receipts (
    review_receipt_sha256 TEXT PRIMARY KEY NOT NULL,
    draft_binding_id TEXT NOT NULL,
    draft_id TEXT NOT NULL,
    expected_pending_binding_sha256 TEXT NOT NULL,
    reviewed_binding_sha256 TEXT NOT NULL,
    qualification_sha256 TEXT NOT NULL,
    selected_asset_bundle_sha256 TEXT NOT NULL,
    grounding_snapshot_sha256 TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision='PASS'),
    content_owner_id TEXT NOT NULL,
    reviewer_ids TEXT NOT NULL CHECK (
        json_valid(reviewer_ids)
        AND json_type(reviewer_ids)='array'
        AND json_array_length(reviewer_ids) >= 1
    ),
    reviewer_independence_status TEXT NOT NULL CHECK (
        reviewer_independence_status='independent'
    ),
    reviewed_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (review_receipt_sha256,draft_binding_id,draft_id),
    FOREIGN KEY (draft_binding_id,draft_id)
        REFERENCES draft_style_bindings(draft_binding_id,draft_id),
    FOREIGN KEY (qualification_sha256)
        REFERENCES qualified_style_publications(qualification_sha256)
) STRICT;

CREATE TRIGGER IF NOT EXISTS validate_draft_binding_review_receipt_insert
BEFORE INSERT ON draft_binding_review_receipts
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM draft_style_bindings AS binding
        WHERE binding.draft_binding_id=NEW.draft_binding_id
          AND binding.draft_id=NEW.draft_id
          AND binding.binding_source='library'
          AND binding.review_status='pending'
          AND NEW.expected_pending_binding_sha256=canonical_row_sha256_v2(
              binding.draft_binding_id,
              binding.draft_id,
              binding.binding_source,
              binding.archetype_id,
              binding.archetype_version,
              binding.archetype_snapshot_sha256,
              binding.starter_pack_id,
              binding.starter_pack_version,
              binding.starter_pack_sha256,
              binding.starter_prompt_id,
              canonical_json_v2(binding.selected_rule_ids),
              canonical_json_v2(binding.reference_library_post_ids),
              canonical_json_v2(binding.counterexample_library_post_ids),
              canonical_json_v2(binding.material_plan_json),
              canonical_json_v2(binding.intentional_deviations_json),
              canonical_json_v2(binding.anti_patterns_checked_json),
              'pending'
          )
          AND NEW.reviewed_binding_sha256=canonical_row_sha256_v2(
              binding.draft_binding_id,
              binding.draft_id,
              binding.binding_source,
              binding.archetype_id,
              binding.archetype_version,
              binding.archetype_snapshot_sha256,
              binding.starter_pack_id,
              binding.starter_pack_version,
              binding.starter_pack_sha256,
              binding.starter_prompt_id,
              canonical_json_v2(binding.selected_rule_ids),
              canonical_json_v2(binding.reference_library_post_ids),
              canonical_json_v2(binding.counterexample_library_post_ids),
              canonical_json_v2(binding.material_plan_json),
              canonical_json_v2(binding.intentional_deviations_json),
              canonical_json_v2(binding.anti_patterns_checked_json),
              'PASS'
          )
    ) THEN RAISE(ABORT, 'binding_review_preimage_mismatch') END;

    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM draft_style_bindings AS binding
        JOIN qualified_style_publications AS qualification
          ON qualification.archetype_id=binding.archetype_id
         AND qualification.archetype_version=binding.archetype_version
         AND qualification.archetype_snapshot_sha256=
             binding.archetype_snapshot_sha256
        WHERE binding.draft_binding_id=NEW.draft_binding_id
          AND qualification.qualification_sha256=NEW.qualification_sha256
          AND NOT EXISTS (
              SELECT 1 FROM json_each(binding.selected_rule_ids) AS selected
              WHERE selected.type <> 'text'
                 OR NOT EXISTS (
                     SELECT 1 FROM json_each(qualification.selected_rule_ids)
                     WHERE value=selected.value
                 )
          )
    ) THEN RAISE(ABORT, 'binding_review_qualification_mismatch') END;

    SELECT CASE WHEN NEW.selected_asset_bundle_sha256 <> (
        SELECT canonical_sha256_agg_v2(asset_preimage)
        FROM (
            SELECT printf(
                '%s|%s|%s',
                evidence.rule_id,
                evidence.rule_evidence_id,
                feature.source_asset_sha256
            ) AS asset_preimage
            FROM draft_style_bindings AS binding
            JOIN json_each(binding.selected_rule_ids) AS selected
            JOIN rule_evidence AS evidence ON evidence.rule_id=selected.value
            JOIN feature_observation_links AS feature
              ON feature.observation_type=evidence.observation_type
             AND feature.observation_id=evidence.observation_id
            WHERE binding.draft_binding_id=NEW.draft_binding_id
            ORDER BY evidence.rule_id,evidence.rule_evidence_id
        )
    ) THEN RAISE(ABORT, 'binding_review_asset_bundle_mismatch') END;

    SELECT CASE WHEN NEW.grounding_snapshot_sha256 <> (
        SELECT canonical_row_sha256_v2(
            NEW.qualification_sha256,
            binding.archetype_snapshot_sha256,
            canonical_json_v2(binding.selected_rule_ids),
            canonical_json_v2(binding.material_plan_json),
            NEW.selected_asset_bundle_sha256
        )
        FROM draft_style_bindings AS binding
        WHERE binding.draft_binding_id=NEW.draft_binding_id
    ) THEN RAISE(ABORT, 'binding_review_grounding_hash_mismatch') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM json_each(NEW.reviewer_ids)
        WHERE type <> 'text' OR trim(value)=''
           OR value=NEW.content_owner_id
    ) THEN RAISE(ABORT, 'reviewer_not_independent') END;

    SELECT CASE WHEN date(NEW.reviewed_at) IS NULL
                      OR date(NEW.reviewed_at) > date('now','localtime')
        THEN RAISE(ABORT, 'review_date_invalid') END;

    SELECT CASE WHEN NEW.review_receipt_sha256 <>
        canonical_row_sha256_v2(
            NEW.draft_binding_id,
            NEW.draft_id,
            NEW.expected_pending_binding_sha256,
            NEW.reviewed_binding_sha256,
            NEW.qualification_sha256,
            NEW.selected_asset_bundle_sha256,
            NEW.grounding_snapshot_sha256,
            NEW.decision,
            NEW.content_owner_id,
            canonical_json_v2(NEW.reviewer_ids),
            NEW.reviewer_independence_status,
            NEW.reviewed_at
        )
    THEN RAISE(ABORT, 'binding_review_receipt_hash_mismatch') END;
END;

CREATE TRIGGER IF NOT EXISTS immutable_draft_binding_review_receipts_update
BEFORE UPDATE ON draft_binding_review_receipts
BEGIN
    SELECT RAISE(ABORT, 'immutable_draft_binding_review_receipts');
END;

CREATE TRIGGER IF NOT EXISTS immutable_draft_binding_review_receipts_delete
BEFORE DELETE ON draft_binding_review_receipts
BEGIN
    SELECT RAISE(ABORT, 'immutable_draft_binding_review_receipts');
END;

CREATE TABLE IF NOT EXISTS draft_binding_publications (
    draft_binding_id TEXT PRIMARY KEY NOT NULL,
    draft_id TEXT NOT NULL,
    binding_sha256 TEXT NOT NULL UNIQUE,
    published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (draft_binding_id, draft_id)
        REFERENCES draft_style_bindings(draft_binding_id, draft_id),
    UNIQUE (draft_binding_id, draft_id, binding_sha256)
) STRICT;

CREATE TRIGGER IF NOT EXISTS validate_draft_binding_publication_insert
BEFORE INSERT ON draft_binding_publications
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM draft_style_bindings AS binding
        WHERE binding.draft_binding_id = NEW.draft_binding_id
          AND binding.draft_id = NEW.draft_id
          AND binding.review_status = 'PASS'
          AND NEW.binding_sha256 = canonical_row_sha256_v2(
              binding.draft_binding_id,
              binding.draft_id,
              binding.binding_source,
              binding.archetype_id,
              binding.archetype_version,
              binding.archetype_snapshot_sha256,
              binding.starter_pack_id,
              binding.starter_pack_version,
              binding.starter_pack_sha256,
              binding.starter_prompt_id,
              canonical_json_v2(binding.selected_rule_ids),
              canonical_json_v2(binding.reference_library_post_ids),
              canonical_json_v2(binding.counterexample_library_post_ids),
              canonical_json_v2(binding.material_plan_json),
              canonical_json_v2(binding.intentional_deviations_json),
              canonical_json_v2(binding.anti_patterns_checked_json),
              binding.review_status
          )
    ) THEN RAISE(ABORT, 'binding_publication_hash_mismatch') END;

    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM draft_binding_review_receipts AS review
        WHERE review.draft_binding_id=NEW.draft_binding_id
          AND review.draft_id=NEW.draft_id
          AND review.reviewed_binding_sha256=NEW.binding_sha256
          AND review.decision='PASS'
          AND review.reviewer_independence_status='independent'
    ) THEN RAISE(ABORT, 'binding_review_receipt_missing') END;
END;

CREATE TRIGGER IF NOT EXISTS immutable_draft_binding_publications_update
BEFORE UPDATE ON draft_binding_publications
BEGIN
    SELECT RAISE(ABORT, 'immutable_draft_binding_publications');
END;

CREATE TRIGGER IF NOT EXISTS immutable_draft_binding_publications_delete
BEFORE DELETE ON draft_binding_publications
BEGIN
    SELECT RAISE(ABORT, 'immutable_draft_binding_publications');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_binding_update
BEFORE UPDATE ON draft_style_bindings
WHEN EXISTS (
    SELECT 1 FROM draft_binding_publications
    WHERE draft_binding_id = OLD.draft_binding_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_binding_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_binding_delete
BEFORE DELETE ON draft_style_bindings
WHEN EXISTS (
    SELECT 1 FROM draft_binding_publications
    WHERE draft_binding_id = OLD.draft_binding_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_binding_frozen');
END;

CREATE TRIGGER IF NOT EXISTS trg_draft_binding_validate_insert
BEFORE INSERT ON draft_style_bindings
BEGIN
    SELECT CASE
        WHEN NEW.binding_source = 'library'
         AND NOT EXISTS (
             SELECT 1 FROM style_archetypes
             WHERE archetype_id = NEW.archetype_id
               AND status IN ('supported', 'reusable')
         )
        THEN RAISE(ABORT, 'primary_archetype_not_supported')
    END;

    SELECT CASE
        WHEN NEW.binding_source = 'starter_pack'
         AND NOT EXISTS (
             SELECT 1 FROM starter_pack_publications
             WHERE starter_pack_id = NEW.starter_pack_id
               AND starter_pack_version = NEW.starter_pack_version
               AND starter_pack_sha256 = NEW.starter_pack_sha256
               AND starter_prompt_id = NEW.starter_prompt_id
         )
        THEN RAISE(ABORT, 'binding_starter_unpublished')
    END;

    SELECT CASE
        WHEN NEW.binding_source = 'library'
         AND NOT EXISTS (
             SELECT 1 FROM archetype_publications
             WHERE archetype_id = NEW.archetype_id
               AND archetype_version = NEW.archetype_version
               AND archetype_snapshot_sha256 = NEW.archetype_snapshot_sha256
         )
        THEN RAISE(ABORT, 'binding_archetype_unpublished')
    END;

    SELECT CASE WHEN json_valid(NEW.selected_rule_ids) = 0
        THEN RAISE(ABORT, 'binding_json_invalid') END;
    SELECT CASE WHEN json_type(NEW.selected_rule_ids) <> 'array'
        THEN RAISE(ABORT, 'binding_json_invalid') END;
    SELECT CASE WHEN json_valid(NEW.reference_library_post_ids) = 0
        THEN RAISE(ABORT, 'binding_json_invalid') END;
    SELECT CASE WHEN json_type(NEW.reference_library_post_ids) <> 'array'
        THEN RAISE(ABORT, 'binding_json_invalid') END;
    SELECT CASE WHEN json_valid(NEW.counterexample_library_post_ids) = 0
        THEN RAISE(ABORT, 'binding_json_invalid') END;
    SELECT CASE WHEN json_type(NEW.counterexample_library_post_ids) <> 'array'
        THEN RAISE(ABORT, 'binding_json_invalid') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM json_each(NEW.selected_rule_ids) AS item
        LEFT JOIN archetype_rules AS rule ON rule.rule_id = item.value
        WHERE item.type <> 'text'
           OR rule.rule_id IS NULL
           OR rule.archetype_id <> NEW.archetype_id
           OR rule.archetype_version <> NEW.archetype_version
    ) THEN RAISE(ABORT, 'binding_rule_invalid') END;

    SELECT CASE WHEN NEW.binding_source = 'library' AND EXISTS (
        SELECT 1
        FROM json_each(NEW.selected_rule_ids) AS item
        LEFT JOIN archetype_rule_publications AS publication
          ON publication.rule_id = item.value
         AND publication.archetype_id = NEW.archetype_id
         AND publication.archetype_version = NEW.archetype_version
         AND publication.archetype_snapshot_sha256 =
             NEW.archetype_snapshot_sha256
        WHERE item.type <> 'text' OR publication.rule_id IS NULL
    ) THEN RAISE(ABORT, 'binding_rule_unpublished') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM json_each(NEW.reference_library_post_ids) AS item
        LEFT JOIN style_posts AS post ON post.library_post_id = item.value
        WHERE item.type <> 'text' OR post.library_post_id IS NULL
    ) THEN RAISE(ABORT, 'binding_reference_post_invalid') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM json_each(NEW.counterexample_library_post_ids) AS item
        LEFT JOIN style_posts AS post ON post.library_post_id = item.value
        WHERE item.type <> 'text' OR post.library_post_id IS NULL
    ) THEN RAISE(ABORT, 'binding_counterexample_post_invalid') END;

    SELECT CASE WHEN NEW.binding_source = 'library' AND EXISTS (
        SELECT 1
        FROM json_each(NEW.reference_library_post_ids) AS reference
        WHERE NOT EXISTS (
            SELECT 1
            FROM json_each(NEW.selected_rule_ids) AS selected
            JOIN rule_evidence_post_associations AS association
              ON association.rule_id = selected.value
             AND association.evidence_role = 'support'
             AND association.library_post_id = reference.value
            WHERE selected.type = 'text'
        )
    ) THEN RAISE(ABORT, 'binding_reference_association_unpublished') END;

    SELECT CASE WHEN NEW.binding_source = 'library' AND EXISTS (
        SELECT 1
        FROM json_each(NEW.counterexample_library_post_ids) AS counterexample
        WHERE NOT EXISTS (
            SELECT 1
            FROM json_each(NEW.selected_rule_ids) AS selected
            JOIN rule_evidence_post_associations AS association
              ON association.rule_id = selected.value
             AND association.evidence_role IN ('counterexample', 'boundary')
             AND association.library_post_id = counterexample.value
            WHERE selected.type = 'text'
        )
    ) THEN RAISE(ABORT, 'binding_counterexample_association_unpublished') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM json_each(NEW.reference_library_post_ids) AS reference
        JOIN json_each(NEW.counterexample_library_post_ids) AS counterexample
          ON counterexample.value=reference.value
        WHERE reference.type='text' AND counterexample.type='text'
    ) THEN RAISE(ABORT, 'binding_evidence_role_overlap') END;


    SELECT CASE
        WHEN NEW.binding_role = 'primary'
         AND NEW.binding_source = 'library'
         AND NOT EXISTS (
             SELECT 1 FROM style_archetypes
             WHERE archetype_id = NEW.archetype_id
               AND status IN ('supported', 'reusable')
         )
        THEN RAISE(ABORT, 'primary_archetype_not_supported')
    END;

END;

CREATE TRIGGER IF NOT EXISTS trg_draft_binding_validate_update
BEFORE UPDATE ON draft_style_bindings
BEGIN
    SELECT CASE
        WHEN NEW.binding_source = 'library'
         AND NOT EXISTS (
             SELECT 1 FROM style_archetypes
             WHERE archetype_id = NEW.archetype_id
               AND status IN ('supported', 'reusable')
         )
        THEN RAISE(ABORT, 'primary_archetype_not_supported')
    END;

    SELECT CASE
        WHEN NEW.binding_source = 'starter_pack'
         AND NOT EXISTS (
             SELECT 1 FROM starter_pack_publications
             WHERE starter_pack_id = NEW.starter_pack_id
               AND starter_pack_version = NEW.starter_pack_version
               AND starter_pack_sha256 = NEW.starter_pack_sha256
               AND starter_prompt_id = NEW.starter_prompt_id
         )
        THEN RAISE(ABORT, 'binding_starter_unpublished')
    END;

    SELECT CASE
        WHEN NEW.binding_source = 'library'
         AND NOT EXISTS (
             SELECT 1 FROM archetype_publications
             WHERE archetype_id = NEW.archetype_id
               AND archetype_version = NEW.archetype_version
               AND archetype_snapshot_sha256 = NEW.archetype_snapshot_sha256
         )
        THEN RAISE(ABORT, 'binding_archetype_unpublished')
    END;

    SELECT CASE WHEN json_valid(NEW.selected_rule_ids) = 0
        THEN RAISE(ABORT, 'binding_json_invalid') END;
    SELECT CASE WHEN json_type(NEW.selected_rule_ids) <> 'array'
        THEN RAISE(ABORT, 'binding_json_invalid') END;
    SELECT CASE WHEN json_valid(NEW.reference_library_post_ids) = 0
        THEN RAISE(ABORT, 'binding_json_invalid') END;
    SELECT CASE WHEN json_type(NEW.reference_library_post_ids) <> 'array'
        THEN RAISE(ABORT, 'binding_json_invalid') END;
    SELECT CASE WHEN json_valid(NEW.counterexample_library_post_ids) = 0
        THEN RAISE(ABORT, 'binding_json_invalid') END;
    SELECT CASE WHEN json_type(NEW.counterexample_library_post_ids) <> 'array'
        THEN RAISE(ABORT, 'binding_json_invalid') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM json_each(NEW.selected_rule_ids) AS item
        LEFT JOIN archetype_rules AS rule ON rule.rule_id = item.value
        WHERE item.type <> 'text'
           OR rule.rule_id IS NULL
           OR rule.archetype_id <> NEW.archetype_id
           OR rule.archetype_version <> NEW.archetype_version
    ) THEN RAISE(ABORT, 'binding_rule_invalid') END;

    SELECT CASE WHEN NEW.binding_source = 'library' AND EXISTS (
        SELECT 1
        FROM json_each(NEW.selected_rule_ids) AS item
        LEFT JOIN archetype_rule_publications AS publication
          ON publication.rule_id = item.value
         AND publication.archetype_id = NEW.archetype_id
         AND publication.archetype_version = NEW.archetype_version
         AND publication.archetype_snapshot_sha256 =
             NEW.archetype_snapshot_sha256
        WHERE item.type <> 'text' OR publication.rule_id IS NULL
    ) THEN RAISE(ABORT, 'binding_rule_unpublished') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM json_each(NEW.reference_library_post_ids) AS item
        LEFT JOIN style_posts AS post ON post.library_post_id = item.value
        WHERE item.type <> 'text' OR post.library_post_id IS NULL
    ) THEN RAISE(ABORT, 'binding_reference_post_invalid') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM json_each(NEW.counterexample_library_post_ids) AS item
        LEFT JOIN style_posts AS post ON post.library_post_id = item.value
        WHERE item.type <> 'text' OR post.library_post_id IS NULL
    ) THEN RAISE(ABORT, 'binding_counterexample_post_invalid') END;

    SELECT CASE WHEN NEW.binding_source = 'library' AND EXISTS (
        SELECT 1
        FROM json_each(NEW.reference_library_post_ids) AS reference
        WHERE NOT EXISTS (
            SELECT 1
            FROM json_each(NEW.selected_rule_ids) AS selected
            JOIN rule_evidence_post_associations AS association
              ON association.rule_id = selected.value
             AND association.evidence_role = 'support'
             AND association.library_post_id = reference.value
            WHERE selected.type = 'text'
        )
    ) THEN RAISE(ABORT, 'binding_reference_association_unpublished') END;

    SELECT CASE WHEN NEW.binding_source = 'library' AND EXISTS (
        SELECT 1
        FROM json_each(NEW.counterexample_library_post_ids) AS counterexample
        WHERE NOT EXISTS (
            SELECT 1
            FROM json_each(NEW.selected_rule_ids) AS selected
            JOIN rule_evidence_post_associations AS association
              ON association.rule_id = selected.value
             AND association.evidence_role IN ('counterexample', 'boundary')
             AND association.library_post_id = counterexample.value
            WHERE selected.type = 'text'
        )
    ) THEN RAISE(ABORT, 'binding_counterexample_association_unpublished') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM json_each(NEW.reference_library_post_ids) AS reference
        JOIN json_each(NEW.counterexample_library_post_ids) AS counterexample
          ON counterexample.value=reference.value
        WHERE reference.type='text' AND counterexample.type='text'
    ) THEN RAISE(ABORT, 'binding_evidence_role_overlap') END;


    SELECT CASE
        WHEN NEW.binding_role = 'primary'
         AND NEW.binding_source = 'library'
         AND NOT EXISTS (
             SELECT 1 FROM style_archetypes
             WHERE archetype_id = NEW.archetype_id
               AND status IN ('supported', 'reusable')
         )
        THEN RAISE(ABORT, 'primary_archetype_not_supported')
    END;

END;

CREATE UNIQUE INDEX IF NOT EXISTS ux_draft_style_bindings_primary
    ON draft_style_bindings(draft_id)
    WHERE binding_role = 'primary';

CREATE INDEX IF NOT EXISTS ix_draft_style_bindings_archetype
    ON draft_style_bindings(archetype_id, archetype_version);

CREATE TABLE IF NOT EXISTS draft_assets (
    draft_asset_id TEXT PRIMARY KEY NOT NULL,
    draft_binding_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    slide_index INTEGER NOT NULL CHECK (slide_index >= 1),
    asset_role TEXT NOT NULL DEFAULT 'generated',
    render_method TEXT NOT NULL DEFAULT '',
    style_rule_ids TEXT NOT NULL DEFAULT '[]'
        CHECK (
            CASE WHEN json_valid(style_rule_ids)
                THEN json_type(style_rule_ids) = 'array'
                 AND json_array_length(style_rule_ids) >= 1
                ELSE 0
            END
        ),
    revision_of TEXT,
    is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'PASS', 'PARTIAL', 'FAIL')),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (draft_binding_id, asset_id),
    FOREIGN KEY (draft_binding_id)
        REFERENCES draft_style_bindings(draft_binding_id)
        ON UPDATE CASCADE,
    FOREIGN KEY (asset_id) REFERENCES style_assets(asset_id)
        ON UPDATE CASCADE,
    FOREIGN KEY (revision_of) REFERENCES draft_assets(draft_asset_id)
        ON UPDATE CASCADE,
    CHECK (revision_of IS NULL OR revision_of <> draft_asset_id)
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_draft_binding_guard_pinned_asset_fields
BEFORE UPDATE OF
    binding_source,
    archetype_id,
    archetype_version,
    archetype_snapshot_sha256,
    selected_rule_ids,
    starter_pack_id,
    starter_pack_version,
    starter_pack_sha256,
    starter_prompt_id
ON draft_style_bindings
WHEN EXISTS (
    SELECT 1 FROM draft_assets
    WHERE draft_binding_id = OLD.draft_binding_id
)
AND (
    NEW.binding_source IS NOT OLD.binding_source
    OR NEW.archetype_id IS NOT OLD.archetype_id
    OR NEW.archetype_version IS NOT OLD.archetype_version
    OR NEW.archetype_snapshot_sha256 IS NOT OLD.archetype_snapshot_sha256
    OR NEW.selected_rule_ids IS NOT OLD.selected_rule_ids
    OR NEW.starter_pack_id IS NOT OLD.starter_pack_id
    OR NEW.starter_pack_version IS NOT OLD.starter_pack_version
    OR NEW.starter_pack_sha256 IS NOT OLD.starter_pack_sha256
    OR NEW.starter_prompt_id IS NOT OLD.starter_prompt_id
)
BEGIN
    SELECT RAISE(ABORT, 'binding_fields_pinned_by_draft_assets');
END;

CREATE TRIGGER IF NOT EXISTS trg_draft_asset_validate_insert
BEFORE INSERT ON draft_assets
BEGIN
    SELECT CASE WHEN json_valid(NEW.style_rule_ids) = 0
        THEN RAISE(ABORT, 'draft_asset_rule_json_invalid') END;
    SELECT CASE WHEN json_type(NEW.style_rule_ids) <> 'array'
        THEN RAISE(ABORT, 'draft_asset_rule_json_invalid') END;
    SELECT CASE WHEN json_array_length(NEW.style_rule_ids) < 1
        THEN RAISE(ABORT, 'draft_asset_rule_json_empty') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM json_each(NEW.style_rule_ids) AS item
        JOIN draft_style_bindings AS binding
          ON binding.draft_binding_id = NEW.draft_binding_id
        LEFT JOIN archetype_rules AS rule ON rule.rule_id = item.value
        WHERE item.type <> 'text'
           OR binding.binding_source <> 'library'
           OR rule.rule_id IS NULL
           OR rule.archetype_id <> binding.archetype_id
           OR rule.archetype_version <> binding.archetype_version
           OR NOT EXISTS (
               SELECT 1
               FROM json_each(binding.selected_rule_ids) AS selected
               WHERE selected.type = 'text' AND selected.value = item.value
           )
    ) THEN RAISE(ABORT, 'draft_asset_rule_invalid') END;

    SELECT CASE
        WHEN NEW.revision_of IS NOT NULL
         AND NOT EXISTS (
             SELECT 1 FROM draft_assets AS previous
             WHERE previous.draft_asset_id = NEW.revision_of
               AND previous.draft_binding_id = NEW.draft_binding_id
               AND previous.slide_index = NEW.slide_index
               AND previous.is_current = 0
         )
        THEN RAISE(ABORT, 'draft_asset_revision_invalid')
    END;
END;

CREATE TRIGGER IF NOT EXISTS trg_draft_asset_validate_update
BEFORE UPDATE ON draft_assets
BEGIN
    SELECT CASE WHEN json_valid(NEW.style_rule_ids) = 0
        THEN RAISE(ABORT, 'draft_asset_rule_json_invalid') END;
    SELECT CASE WHEN json_type(NEW.style_rule_ids) <> 'array'
        THEN RAISE(ABORT, 'draft_asset_rule_json_invalid') END;
    SELECT CASE WHEN json_array_length(NEW.style_rule_ids) < 1
        THEN RAISE(ABORT, 'draft_asset_rule_json_empty') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1
        FROM json_each(NEW.style_rule_ids) AS item
        JOIN draft_style_bindings AS binding
          ON binding.draft_binding_id = NEW.draft_binding_id
        LEFT JOIN archetype_rules AS rule ON rule.rule_id = item.value
        WHERE item.type <> 'text'
           OR binding.binding_source <> 'library'
           OR rule.rule_id IS NULL
           OR rule.archetype_id <> binding.archetype_id
           OR rule.archetype_version <> binding.archetype_version
           OR NOT EXISTS (
               SELECT 1
               FROM json_each(binding.selected_rule_ids) AS selected
               WHERE selected.type = 'text' AND selected.value = item.value
           )
    ) THEN RAISE(ABORT, 'draft_asset_rule_invalid') END;

    SELECT CASE
        WHEN NEW.revision_of IS NOT NULL
         AND NOT EXISTS (
             SELECT 1 FROM draft_assets AS previous
             WHERE previous.draft_asset_id = NEW.revision_of
               AND previous.draft_binding_id = NEW.draft_binding_id
               AND previous.slide_index = NEW.slide_index
               AND previous.is_current = 0
         )
        THEN RAISE(ABORT, 'draft_asset_revision_invalid')
    END;

    SELECT CASE
        WHEN (
            NEW.draft_binding_id <> OLD.draft_binding_id
            OR NEW.slide_index <> OLD.slide_index
        )
         AND EXISTS (
             SELECT 1 FROM draft_assets AS child
             WHERE child.revision_of = OLD.draft_asset_id
         )
        THEN RAISE(ABORT, 'draft_asset_has_revisions')
    END;
END;

CREATE UNIQUE INDEX IF NOT EXISTS ux_draft_assets_current_slide
    ON draft_assets(draft_binding_id, slide_index)
    WHERE is_current = 1;

CREATE INDEX IF NOT EXISTS ix_draft_assets_binding
    ON draft_assets(draft_binding_id);

CREATE TRIGGER IF NOT EXISTS trg_archetype_rule_guard_binding_delete
BEFORE DELETE ON archetype_rules
WHEN EXISTS (
    SELECT 1
    FROM draft_style_bindings AS binding,
         json_each(binding.selected_rule_ids) AS item
    WHERE item.type = 'text'
      AND item.value = OLD.rule_id
)
BEGIN
    SELECT RAISE(ABORT, 'binding_rule_reference_exists');
END;

CREATE TRIGGER IF NOT EXISTS trg_archetype_rule_guard_binding_update
BEFORE UPDATE OF rule_id, archetype_id, archetype_version ON archetype_rules
WHEN (
    NEW.rule_id IS NOT OLD.rule_id
    OR NEW.archetype_id IS NOT OLD.archetype_id
    OR NEW.archetype_version IS NOT OLD.archetype_version
)
AND EXISTS (
    SELECT 1
    FROM draft_style_bindings AS binding,
         json_each(binding.selected_rule_ids) AS item
    WHERE item.type = 'text'
      AND item.value = OLD.rule_id
)
BEGIN
    SELECT RAISE(ABORT, 'binding_rule_reference_exists');
END;

CREATE TRIGGER IF NOT EXISTS trg_archetype_rule_guard_draft_asset_delete
BEFORE DELETE ON archetype_rules
WHEN EXISTS (
    SELECT 1
    FROM draft_assets AS asset,
         json_each(asset.style_rule_ids) AS item
    WHERE item.type = 'text'
      AND item.value = OLD.rule_id
)
BEGIN
    SELECT RAISE(ABORT, 'draft_asset_rule_reference_exists');
END;

CREATE TRIGGER IF NOT EXISTS trg_archetype_rule_guard_draft_asset_update
BEFORE UPDATE OF rule_id, archetype_id, archetype_version ON archetype_rules
WHEN (
    NEW.rule_id IS NOT OLD.rule_id
    OR NEW.archetype_id IS NOT OLD.archetype_id
    OR NEW.archetype_version IS NOT OLD.archetype_version
)
AND EXISTS (
    SELECT 1
    FROM draft_assets AS asset,
         json_each(asset.style_rule_ids) AS item
    WHERE item.type = 'text'
      AND item.value = OLD.rule_id
)
BEGIN
    SELECT RAISE(ABORT, 'draft_asset_rule_reference_exists');
END;

CREATE TRIGGER IF NOT EXISTS trg_style_post_guard_binding_delete
BEFORE DELETE ON style_posts
WHEN EXISTS (
    SELECT 1
    FROM draft_style_bindings AS binding,
         json_each(binding.reference_library_post_ids) AS item
    WHERE item.type = 'text'
      AND item.value = OLD.library_post_id
)
OR EXISTS (
    SELECT 1
    FROM draft_style_bindings AS binding,
         json_each(binding.counterexample_library_post_ids) AS item
    WHERE item.type = 'text'
      AND item.value = OLD.library_post_id
)
BEGIN
    SELECT RAISE(ABORT, 'binding_referenced_post_exists');
END;

CREATE TRIGGER IF NOT EXISTS trg_style_post_guard_binding_update
BEFORE UPDATE OF library_post_id ON style_posts
WHEN NEW.library_post_id IS NOT OLD.library_post_id
AND (
    EXISTS (
        SELECT 1
        FROM draft_style_bindings AS binding,
             json_each(binding.reference_library_post_ids) AS item
        WHERE item.type = 'text'
          AND item.value = OLD.library_post_id
    )
    OR EXISTS (
        SELECT 1
        FROM draft_style_bindings AS binding,
             json_each(binding.counterexample_library_post_ids) AS item
        WHERE item.type = 'text'
          AND item.value = OLD.library_post_id
    )
)
BEGIN
    SELECT RAISE(ABORT, 'binding_referenced_post_exists');
END;

CREATE TABLE IF NOT EXISTS draft_outcomes (
    draft_outcome_id TEXT PRIMARY KEY NOT NULL,
    draft_binding_id TEXT NOT NULL,
    published_at TEXT,
    observed_at TEXT,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    post_age_hours REAL CHECK (post_age_hours IS NULL OR post_age_hours >= 0.0),
    baseline_snapshot_id TEXT,
    known_confounds TEXT NOT NULL DEFAULT '[]',
    decision TEXT NOT NULL
        CHECK (decision IN ('win', 'loss', 'inconclusive')),
    next_single_variable TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (draft_binding_id)
        REFERENCES draft_style_bindings(draft_binding_id)
        ON UPDATE CASCADE,
    FOREIGN KEY (baseline_snapshot_id)
        REFERENCES account_baseline_snapshots(baseline_snapshot_id)
        ON UPDATE CASCADE ON DELETE SET NULL
) STRICT;

CREATE INDEX IF NOT EXISTS ix_draft_outcomes_binding
    ON draft_outcomes(draft_binding_id, observed_at);

CREATE TABLE IF NOT EXISTS ingest_receipts (
    ingest_receipt_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL,
    input_bundle_sha256 TEXT NOT NULL,
    ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    record_counts_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (run_id, input_bundle_sha256)
) STRICT;

CREATE TABLE IF NOT EXISTS sanitized_ledger_ingests (
    input_bundle_sha256 TEXT PRIMARY KEY NOT NULL,
    source_file_sha256 TEXT NOT NULL,
    record_count INTEGER NOT NULL CHECK (record_count > 0),
    ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
) STRICT;

CREATE TABLE IF NOT EXISTS sanitized_style_ledger_entries (
    observation_id TEXT PRIMARY KEY NOT NULL,
    input_bundle_sha256 TEXT NOT NULL,
    library_post_id TEXT NOT NULL,
    library_account_id TEXT NOT NULL,
    capture_date TEXT NOT NULL,
    review_by TEXT NOT NULL,
    query_fingerprint TEXT NOT NULL,
    carrier TEXT NOT NULL CHECK (carrier IN (
        'real_photo_diary', 'photo_annotation', 'screenshot_markup',
        'chat_dramatization', 'text_card', 'checklist_steps',
        'comparison_warning', 'collage_journal', 'single_image_reminder',
        'process_video', 'screen_recording', 'talking_head_or_field_video',
        'unknown', 'other'
    )),
    primary_job TEXT NOT NULL CHECK (primary_job IN (
        'feed_stop', 'search_answer', 'explain', 'trust_build',
        'decision_support', 'relationship_build', 'conversion',
        'authority_statement'
    )),
    traffic_stage TEXT CHECK (traffic_stage IS NULL OR traffic_stage IN (
        'feed_stop', 'read_through', 'save_share',
        'comment_cocreation', 'profile_follow'
    )),
    material_codes_json TEXT NOT NULL
        CHECK (json_valid(material_codes_json)
               AND json_type(material_codes_json) = 'array'),
    production_constraint_codes_json TEXT NOT NULL
        CHECK (json_valid(production_constraint_codes_json)
               AND json_type(production_constraint_codes_json) = 'array'),
    contraindication_codes_json TEXT NOT NULL
        CHECK (json_valid(contraindication_codes_json)
               AND json_type(contraindication_codes_json) = 'array'),
    claim_kind TEXT NOT NULL CHECK (claim_kind IN ('task_fit', 'series_constant')),
    performance_evidence_scope TEXT NOT NULL CHECK (
        performance_evidence_scope IN (
            'not_performance_evidence', 'public_proxy_association'
        )
    ),
    evidence_role TEXT NOT NULL,
    qualification_status TEXT NOT NULL
        CHECK (qualification_status = 'ineligible_unverified'),
    performance_recomputability TEXT NOT NULL
        CHECK (performance_recomputability = 'unverified'),
    derived_tier TEXT NOT NULL CHECK (derived_tier = 'unknown'),
    starter_eligible INTEGER NOT NULL CHECK (starter_eligible = 0),
    visibility_scope TEXT NOT NULL CHECK (visibility_scope = 'public_proxy'),
    traffic_verdict TEXT NOT NULL
        CHECK (traffic_verdict IN ('unavailable', 'not_applicable')),
    record_sha256 TEXT NOT NULL UNIQUE,
    record_json TEXT NOT NULL
        CHECK (json_valid(record_json) AND json_type(record_json) = 'object'),
    ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (input_bundle_sha256)
        REFERENCES sanitized_ledger_ingests(input_bundle_sha256),
    CHECK (
        length(observation_id) = 9
        AND substr(observation_id, 1, 6) = 'O-XHS-'
        AND substr(observation_id, 7, 3) GLOB '[0-9][0-9][0-9]'
        AND CAST(substr(observation_id, 7, 3) AS INTEGER) BETWEEN 1 AND 12
    )
) STRICT;

CREATE INDEX IF NOT EXISTS ix_sanitized_style_ledger_scope
    ON sanitized_style_ledger_entries(carrier, primary_job, observation_id);

CREATE TRIGGER IF NOT EXISTS immutable_sanitized_ledger_ingests_update
BEFORE UPDATE ON sanitized_ledger_ingests
BEGIN
    SELECT RAISE(ABORT, 'immutable_sanitized_ledger_ingests');
END;

CREATE TRIGGER IF NOT EXISTS immutable_sanitized_ledger_ingests_delete
BEFORE DELETE ON sanitized_ledger_ingests
BEGIN
    SELECT RAISE(ABORT, 'immutable_sanitized_ledger_ingests');
END;

CREATE TRIGGER IF NOT EXISTS immutable_sanitized_style_ledger_entries_update
BEFORE UPDATE ON sanitized_style_ledger_entries
BEGIN
    SELECT RAISE(ABORT, 'immutable_sanitized_style_ledger_entries');
END;

CREATE TRIGGER IF NOT EXISTS immutable_sanitized_style_ledger_entries_delete
BEFORE DELETE ON sanitized_style_ledger_entries
BEGIN
    SELECT RAISE(ABORT, 'immutable_sanitized_style_ledger_entries');
END;

-- Outcome-learning foundation. Exact assignment/outcome publication commands are
-- deliberately separate from capture so public proxy data cannot become a
-- first-party traffic verdict by accident.
CREATE TABLE IF NOT EXISTS draft_experiments (
    experiment_id TEXT PRIMARY KEY NOT NULL,
    library_account_id TEXT NOT NULL,
    business_objective TEXT NOT NULL
        CHECK (business_objective IN ('traffic_first', 'engagement_proxy')),
    design_type TEXT NOT NULL
        CHECK (design_type IN ('single_variable', 'blocked_2x2')),
    visibility_scope TEXT NOT NULL
        CHECK (visibility_scope IN ('first_party_analytics', 'public_proxy')),
    primary_metric_name TEXT NOT NULL,
    primary_metric_selection_reason TEXT NOT NULL,
    changed_primary_variable TEXT NOT NULL,
    factor_a_name TEXT,
    factor_a_levels_json TEXT NOT NULL DEFAULT '[]'
        CHECK (json_valid(factor_a_levels_json) AND json_type(factor_a_levels_json) = 'array'),
    factor_b_name TEXT,
    factor_b_levels_json TEXT NOT NULL DEFAULT '[]'
        CHECK (json_valid(factor_b_levels_json) AND json_type(factor_b_levels_json) = 'array'),
    block_name TEXT,
    block_levels_json TEXT NOT NULL DEFAULT '[]'
        CHECK (json_valid(block_levels_json) AND json_type(block_levels_json) = 'array'),
    proposition_sha256 TEXT NOT NULL,
    held_constants_json TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(held_constants_json) AND json_type(held_constants_json) = 'object'),
    held_constants_sha256 TEXT NOT NULL,
    assignment_method TEXT NOT NULL,
    randomization_seed_sha256 TEXT,
    planned_order_json TEXT NOT NULL DEFAULT '[]'
        CHECK (json_valid(planned_order_json) AND json_type(planned_order_json) = 'array'),
    planned_order_sha256 TEXT NOT NULL,
    analysis_plan_json TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(analysis_plan_json) AND json_type(analysis_plan_json) = 'object'),
    early_stop_gate_json TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(early_stop_gate_json) AND json_type(early_stop_gate_json) = 'object'),
    planned_assignment_count INTEGER NOT NULL CHECK (planned_assignment_count > 0),
    pair_contrast_set_sha256 TEXT NOT NULL,
    pair_contrast_count INTEGER NOT NULL DEFAULT 0 CHECK (pair_contrast_count >= 0),
    preregistration_sha256 TEXT NOT NULL,
    assignment_set_sha256 TEXT NOT NULL,
    assignment_count INTEGER NOT NULL DEFAULT 0 CHECK (assignment_count >= 0),
    status TEXT NOT NULL CHECK (status IN ('building', 'preregistered', 'closed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (
        experiment_id, library_account_id, primary_metric_name,
        preregistration_sha256, assignment_set_sha256, assignment_count,
        pair_contrast_set_sha256, pair_contrast_count
    ),
    FOREIGN KEY (library_account_id) REFERENCES style_accounts(library_account_id)
) STRICT;

CREATE TABLE IF NOT EXISTS draft_experiment_assignments (
    experiment_id TEXT NOT NULL,
    draft_binding_id TEXT NOT NULL,
    assignment_ordinal INTEGER NOT NULL CHECK (assignment_ordinal >= 0),
    factor_a_level TEXT,
    factor_b_level TEXT,
    block_level TEXT,
    assignment_sha256 TEXT NOT NULL,
    planned_publish_at TEXT,
    actual_publish_at TEXT,
    order_deviation_codes_json TEXT NOT NULL DEFAULT '[]'
        CHECK (json_valid(order_deviation_codes_json)
               AND json_type(order_deviation_codes_json) = 'array'),
    adult_product_cta_status TEXT NOT NULL DEFAULT 'not_applicable',
    PRIMARY KEY (experiment_id, draft_binding_id),
    UNIQUE (experiment_id, assignment_ordinal),
    FOREIGN KEY (experiment_id) REFERENCES draft_experiments(experiment_id),
    FOREIGN KEY (draft_binding_id) REFERENCES draft_style_bindings(draft_binding_id)
) STRICT;

CREATE TRIGGER IF NOT EXISTS validate_draft_experiment_assignment_insert
BEFORE INSERT ON draft_experiment_assignments
WHEN NEW.assignment_sha256 <> canonical_row_sha256_v2(
    NEW.experiment_id, NEW.draft_binding_id, NEW.assignment_ordinal,
    NEW.factor_a_level, NEW.factor_b_level, NEW.block_level,
    NEW.planned_publish_at, canonical_json_v2(NEW.order_deviation_codes_json),
    NEW.adult_product_cta_status
)
BEGIN
    SELECT RAISE(ABORT, 'draft_experiment_assignment_hash_mismatch');
END;

CREATE TRIGGER IF NOT EXISTS validate_draft_experiment_assignment_update
BEFORE UPDATE ON draft_experiment_assignments
WHEN NEW.assignment_sha256 <> canonical_row_sha256_v2(
    NEW.experiment_id, NEW.draft_binding_id, NEW.assignment_ordinal,
    NEW.factor_a_level, NEW.factor_b_level, NEW.block_level,
    NEW.planned_publish_at, canonical_json_v2(NEW.order_deviation_codes_json),
    NEW.adult_product_cta_status
)
BEGIN
    SELECT RAISE(ABORT, 'draft_experiment_assignment_hash_mismatch');
END;

CREATE TABLE IF NOT EXISTS draft_experiment_publications (
    experiment_id TEXT PRIMARY KEY NOT NULL,
    library_account_id TEXT NOT NULL,
    primary_metric_name TEXT NOT NULL,
    preregistration_sha256 TEXT NOT NULL,
    assignment_set_sha256 TEXT NOT NULL,
    assignment_count INTEGER NOT NULL,
    pair_contrast_set_sha256 TEXT NOT NULL,
    pair_contrast_count INTEGER NOT NULL,
    published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (
        experiment_id, library_account_id, primary_metric_name,
        preregistration_sha256, assignment_set_sha256, assignment_count,
        pair_contrast_set_sha256, pair_contrast_count
    ) REFERENCES draft_experiments(
        experiment_id, library_account_id, primary_metric_name,
        preregistration_sha256, assignment_set_sha256, assignment_count,
        pair_contrast_set_sha256, pair_contrast_count
    )
) STRICT;

CREATE TRIGGER IF NOT EXISTS validate_draft_experiment_publication_insert
BEFORE INSERT ON draft_experiment_publications
BEGIN
    SELECT CASE WHEN abs(
        (julianday(NEW.published_at) - julianday('now')) * 86400.0
    ) > 300.0 OR julianday(NEW.published_at) IS NULL
        THEN RAISE(ABORT, 'draft_experiment_publication_time_invalid') END;
    SELECT CASE WHEN (
        SELECT status FROM draft_experiments
        WHERE experiment_id = NEW.experiment_id
    ) <> 'preregistered'
        THEN RAISE(ABORT, 'draft_experiment_not_preregistered') END;
    SELECT CASE WHEN NEW.assignment_count <> (
        SELECT COUNT(*) FROM draft_experiment_assignments
        WHERE experiment_id = NEW.experiment_id
    ) OR NEW.assignment_count <> (
        SELECT planned_assignment_count FROM draft_experiments
        WHERE experiment_id = NEW.experiment_id
    ) THEN RAISE(ABORT, 'draft_experiment_assignment_count_mismatch') END;
    SELECT CASE WHEN NEW.assignment_set_sha256 <> (
        SELECT canonical_sha256_agg_v2(assignment_sha256)
        FROM (
            SELECT assignment_sha256
            FROM draft_experiment_assignments
            WHERE experiment_id = NEW.experiment_id
            ORDER BY assignment_ordinal, draft_binding_id
        )
    ) THEN RAISE(ABORT, 'draft_experiment_assignment_set_hash_mismatch') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM draft_experiment_assignments
        WHERE experiment_id = NEW.experiment_id
          AND actual_publish_at IS NOT NULL
    ) THEN RAISE(ABORT, 'draft_experiment_already_published') END;
    SELECT CASE WHEN (
        SELECT held_constants_sha256 FROM draft_experiments
        WHERE experiment_id = NEW.experiment_id
    ) <> (
        SELECT canonical_row_sha256_v2(canonical_json_v2(held_constants_json))
        FROM draft_experiments WHERE experiment_id = NEW.experiment_id
    ) THEN RAISE(ABORT, 'draft_experiment_held_constants_hash_mismatch') END;
    SELECT CASE WHEN (
        SELECT planned_order_sha256 FROM draft_experiments
        WHERE experiment_id = NEW.experiment_id
    ) <> (
        SELECT canonical_row_sha256_v2(canonical_json_v2(planned_order_json))
        FROM draft_experiments WHERE experiment_id = NEW.experiment_id
    ) THEN RAISE(ABORT, 'draft_experiment_planned_order_hash_mismatch') END;
    SELECT CASE WHEN (
        SELECT design_type FROM draft_experiments
        WHERE experiment_id = NEW.experiment_id
    ) = 'blocked_2x2'
        THEN RAISE(ABORT, 'draft_pair_contrast_publication_not_implemented') END;
    SELECT CASE WHEN NEW.pair_contrast_count <> 0
        OR NEW.pair_contrast_set_sha256 <>
           '4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945'
        THEN RAISE(ABORT, 'draft_pair_contrast_set_invalid') END;
    SELECT CASE WHEN (
        SELECT preregistration_sha256 FROM draft_experiments
        WHERE experiment_id = NEW.experiment_id
    ) <> (
        SELECT canonical_row_sha256_v2(
            experiment_id, library_account_id, business_objective,
            design_type, visibility_scope, primary_metric_name,
            primary_metric_selection_reason, changed_primary_variable,
            factor_a_name, canonical_json_v2(factor_a_levels_json),
            factor_b_name, canonical_json_v2(factor_b_levels_json),
            block_name, canonical_json_v2(block_levels_json),
            proposition_sha256, held_constants_sha256, assignment_method,
            randomization_seed_sha256, planned_order_sha256,
            canonical_json_v2(analysis_plan_json),
            canonical_json_v2(early_stop_gate_json),
            planned_assignment_count, pair_contrast_set_sha256,
            pair_contrast_count, assignment_set_sha256, assignment_count
        ) FROM draft_experiments WHERE experiment_id = NEW.experiment_id
    ) THEN RAISE(ABORT, 'draft_experiment_preregistration_hash_mismatch') END;
END;

-- Publication is an event after preregistration, not a mutable field on the
-- preregistered assignment. This prevents filling actual_publish_at first and
-- publishing the experiment record afterwards.
CREATE TABLE IF NOT EXISTS draft_publish_events (
    publish_event_id TEXT PRIMARY KEY NOT NULL,
    experiment_id TEXT NOT NULL,
    draft_binding_id TEXT NOT NULL,
    library_account_id TEXT NOT NULL,
    surface TEXT NOT NULL,
    platform_post_id TEXT NOT NULL,
    publication_url TEXT NOT NULL,
    actual_publish_at TEXT NOT NULL,
    publish_event_sha256 TEXT NOT NULL UNIQUE,
    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (experiment_id, draft_binding_id),
    FOREIGN KEY (experiment_id)
        REFERENCES draft_experiment_publications(experiment_id),
    FOREIGN KEY (experiment_id, draft_binding_id)
        REFERENCES draft_experiment_assignments(experiment_id, draft_binding_id),
    FOREIGN KEY (library_account_id)
        REFERENCES style_accounts(library_account_id)
) STRICT;

CREATE TRIGGER IF NOT EXISTS reject_assignment_actual_publish_insert
BEFORE INSERT ON draft_experiment_assignments
WHEN NEW.actual_publish_at IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'use_draft_publish_event_after_preregistration');
END;

CREATE TRIGGER IF NOT EXISTS reject_assignment_actual_publish_update
BEFORE UPDATE OF actual_publish_at ON draft_experiment_assignments
WHEN NEW.actual_publish_at IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'use_draft_publish_event_after_preregistration');
END;

CREATE TRIGGER IF NOT EXISTS validate_draft_publish_event_insert
BEFORE INSERT ON draft_publish_events
BEGIN
    SELECT CASE WHEN abs(
        (julianday(NEW.recorded_at) - julianday('now')) * 86400.0
    ) > 300.0 OR julianday(NEW.recorded_at) IS NULL
        THEN RAISE(ABORT, 'draft_publish_event_recorded_at_invalid') END;
    SELECT CASE WHEN trim(NEW.surface) = ''
        OR trim(NEW.platform_post_id) = ''
        OR trim(NEW.publication_url) = ''
        THEN RAISE(ABORT, 'draft_publish_event_identity_missing') END;
    SELECT CASE WHEN NEW.library_account_id <> (
        SELECT library_account_id
        FROM draft_experiment_publications
        WHERE experiment_id = NEW.experiment_id
    ) THEN RAISE(ABORT, 'draft_publish_event_account_mismatch') END;
    SELECT CASE WHEN julianday(NEW.actual_publish_at) IS NULL
        THEN RAISE(ABORT, 'draft_publish_event_time_invalid') END;
    SELECT CASE WHEN julianday(NEW.actual_publish_at) < julianday((
        SELECT published_at
        FROM draft_experiment_publications
        WHERE experiment_id = NEW.experiment_id
    )) THEN RAISE(ABORT, 'draft_publish_event_before_preregistration') END;
    SELECT CASE WHEN julianday(NEW.actual_publish_at) > julianday(NEW.recorded_at)
        THEN RAISE(ABORT, 'draft_publish_event_from_future') END;
    SELECT CASE WHEN NEW.publish_event_sha256 <> canonical_row_sha256_v2(
        NEW.publish_event_id, NEW.experiment_id, NEW.draft_binding_id,
        NEW.library_account_id, NEW.surface, NEW.platform_post_id,
        NEW.publication_url, NEW.actual_publish_at
    ) THEN RAISE(ABORT, 'draft_publish_event_hash_mismatch') END;
END;

CREATE TRIGGER IF NOT EXISTS immutable_draft_publish_event_update
BEFORE UPDATE ON draft_publish_events
BEGIN
    SELECT RAISE(ABORT, 'immutable_draft_publish_event');
END;

CREATE TRIGGER IF NOT EXISTS immutable_draft_publish_event_delete
BEFORE DELETE ON draft_publish_events
BEGIN
    SELECT RAISE(ABORT, 'immutable_draft_publish_event');
END;

CREATE TABLE IF NOT EXISTS draft_outcome_checkpoints (
    outcome_checkpoint_id TEXT PRIMARY KEY NOT NULL,
    experiment_id TEXT NOT NULL,
    draft_binding_id TEXT NOT NULL,
    library_account_id TEXT NOT NULL,
    checkpoint_hours INTEGER NOT NULL CHECK (checkpoint_hours > 0),
    visibility_scope TEXT NOT NULL
        CHECK (visibility_scope IN ('first_party_analytics', 'public_proxy')),
    primary_metric_name TEXT NOT NULL,
    primary_metric_status TEXT NOT NULL
        CHECK (primary_metric_status IN ('observed', 'unavailable')),
    performance_definition_id TEXT,
    baseline_snapshot_id TEXT,
    baseline_snapshot_sha256 TEXT,
    metric_set_sha256 TEXT NOT NULL,
    metric_count INTEGER NOT NULL CHECK (metric_count >= 0),
    observed_at TEXT NOT NULL,
    known_confounds TEXT NOT NULL DEFAULT '[]',
    traffic_verdict TEXT NOT NULL
        CHECK (traffic_verdict IN (
            'win', 'loss', 'inconclusive', 'unavailable', 'insufficient',
            'not_applicable'
        )),
    next_single_variable TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (experiment_id, draft_binding_id, checkpoint_hours),
    UNIQUE (outcome_checkpoint_id, experiment_id, draft_binding_id),
    UNIQUE (
        outcome_checkpoint_id, experiment_id, draft_binding_id,
        metric_set_sha256, metric_count, traffic_verdict
    ),
    FOREIGN KEY (experiment_id) REFERENCES draft_experiment_publications(experiment_id),
    FOREIGN KEY (experiment_id, draft_binding_id)
        REFERENCES draft_experiment_assignments(experiment_id, draft_binding_id),
    FOREIGN KEY (experiment_id, draft_binding_id)
        REFERENCES draft_publish_events(experiment_id, draft_binding_id),
    FOREIGN KEY (
        baseline_snapshot_id, library_account_id, performance_definition_id,
        primary_metric_name, baseline_snapshot_sha256
    ) REFERENCES baseline_snapshot_publications(
        baseline_snapshot_id, library_account_id, performance_definition_id,
        metric_name, baseline_snapshot_sha256
    ),
    CHECK (
        (primary_metric_status = 'unavailable'
         AND performance_definition_id IS NULL
         AND baseline_snapshot_id IS NULL
         AND baseline_snapshot_sha256 IS NULL
         AND traffic_verdict IN ('unavailable', 'insufficient', 'not_applicable'))
        OR
        (primary_metric_status = 'observed'
         AND performance_definition_id IS NOT NULL
         AND baseline_snapshot_id IS NOT NULL
         AND baseline_snapshot_sha256 IS NOT NULL)
    ),
    CHECK (
        (visibility_scope = 'public_proxy' AND traffic_verdict = 'not_applicable')
        OR visibility_scope = 'first_party_analytics'
    )
) STRICT;

CREATE TRIGGER IF NOT EXISTS validate_draft_outcome_checkpoint_publish_window
BEFORE INSERT ON draft_outcome_checkpoints
BEGIN
    SELECT CASE WHEN abs(
        (julianday(NEW.created_at) - julianday('now')) * 86400.0
    ) > 300.0 OR julianday(NEW.created_at) IS NULL
        THEN RAISE(ABORT, 'draft_outcome_created_at_invalid') END;
    SELECT CASE WHEN julianday(NEW.observed_at) IS NULL
        THEN RAISE(ABORT, 'draft_outcome_observed_at_invalid') END;
    SELECT CASE WHEN abs(
        (julianday(NEW.observed_at) - julianday((
            SELECT actual_publish_at
            FROM draft_publish_events
            WHERE experiment_id = NEW.experiment_id
              AND draft_binding_id = NEW.draft_binding_id
        ))) * 24.0 - NEW.checkpoint_hours
    ) > min(2.0, NEW.checkpoint_hours * 0.1)
        THEN RAISE(ABORT, 'draft_outcome_checkpoint_window_mismatch') END;
    SELECT CASE WHEN julianday(NEW.observed_at) > julianday(NEW.created_at)
        OR (julianday(NEW.created_at) - julianday(NEW.observed_at)) * 24.0 > 2.0
        THEN RAISE(ABORT, 'draft_outcome_recording_delay_invalid') END;
    SELECT CASE WHEN NEW.library_account_id <> (
        SELECT library_account_id
        FROM draft_publish_events
        WHERE experiment_id = NEW.experiment_id
          AND draft_binding_id = NEW.draft_binding_id
    ) THEN RAISE(ABORT, 'draft_outcome_account_mismatch') END;
END;

CREATE TABLE IF NOT EXISTS draft_outcome_metrics (
    outcome_metric_id TEXT PRIMARY KEY NOT NULL,
    outcome_checkpoint_id TEXT NOT NULL,
    experiment_id TEXT NOT NULL,
    draft_binding_id TEXT NOT NULL,
    metric_role TEXT NOT NULL
        CHECK (metric_role IN (
            'primary_exposure', 'attention_diagnostic',
            'value_diagnostic', 'conversion_diagnostic'
        )),
    metric_name TEXT NOT NULL,
    metric_status TEXT NOT NULL
        CHECK (metric_status IN ('observed', 'unavailable', 'not_applicable')),
    metric_value REAL,
    numerator REAL,
    denominator REAL,
    denominator_metric_name TEXT,
    metric_unit TEXT NOT NULL,
    metric_ordinal INTEGER NOT NULL CHECK (metric_ordinal >= 0),
    metric_sha256 TEXT NOT NULL,
    UNIQUE (outcome_checkpoint_id, metric_name),
    UNIQUE (outcome_checkpoint_id, metric_ordinal),
    FOREIGN KEY (outcome_checkpoint_id, experiment_id, draft_binding_id)
        REFERENCES draft_outcome_checkpoints(
            outcome_checkpoint_id, experiment_id, draft_binding_id
        ),
    CHECK (
        (metric_status = 'observed' AND metric_value IS NOT NULL)
        OR (metric_status <> 'observed' AND metric_value IS NULL)
    )
) STRICT;

CREATE TABLE IF NOT EXISTS draft_outcome_publications (
    outcome_checkpoint_id TEXT PRIMARY KEY NOT NULL,
    experiment_id TEXT NOT NULL,
    draft_binding_id TEXT NOT NULL,
    metric_set_sha256 TEXT NOT NULL,
    metric_count INTEGER NOT NULL,
    traffic_verdict TEXT NOT NULL,
    published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (outcome_checkpoint_id, experiment_id, draft_binding_id),
    FOREIGN KEY (
        outcome_checkpoint_id, experiment_id, draft_binding_id,
        metric_set_sha256, metric_count, traffic_verdict
    ) REFERENCES draft_outcome_checkpoints(
        outcome_checkpoint_id, experiment_id, draft_binding_id,
        metric_set_sha256, metric_count, traffic_verdict
    )
) STRICT;

CREATE TRIGGER IF NOT EXISTS immutable_draft_experiment_publications_update
BEFORE UPDATE ON draft_experiment_publications
BEGIN
    SELECT RAISE(ABORT, 'immutable_draft_experiment_publications');
END;

CREATE TRIGGER IF NOT EXISTS immutable_draft_experiment_publications_delete
BEFORE DELETE ON draft_experiment_publications
BEGIN
    SELECT RAISE(ABORT, 'immutable_draft_experiment_publications');
END;

CREATE TRIGGER IF NOT EXISTS immutable_draft_outcome_publications_update
BEFORE UPDATE ON draft_outcome_publications
BEGIN
    SELECT RAISE(ABORT, 'immutable_draft_outcome_publications');
END;

CREATE TRIGGER IF NOT EXISTS immutable_draft_outcome_publications_delete
BEFORE DELETE ON draft_outcome_publications
BEGIN
    SELECT RAISE(ABORT, 'immutable_draft_outcome_publications');
END;

CREATE TRIGGER IF NOT EXISTS validate_draft_outcome_metric_insert
BEFORE INSERT ON draft_outcome_metrics
WHEN NEW.metric_sha256 <> canonical_row_sha256_v2(
    NEW.outcome_metric_id, NEW.outcome_checkpoint_id, NEW.experiment_id,
    NEW.draft_binding_id, NEW.metric_role, NEW.metric_name, NEW.metric_status,
    NEW.metric_value, NEW.numerator, NEW.denominator,
    NEW.denominator_metric_name, NEW.metric_unit, NEW.metric_ordinal
)
BEGIN
    SELECT RAISE(ABORT, 'draft_outcome_metric_hash_mismatch');
END;

CREATE TRIGGER IF NOT EXISTS validate_draft_outcome_metric_update
BEFORE UPDATE ON draft_outcome_metrics
WHEN NEW.metric_sha256 <> canonical_row_sha256_v2(
    NEW.outcome_metric_id, NEW.outcome_checkpoint_id, NEW.experiment_id,
    NEW.draft_binding_id, NEW.metric_role, NEW.metric_name, NEW.metric_status,
    NEW.metric_value, NEW.numerator, NEW.denominator,
    NEW.denominator_metric_name, NEW.metric_unit, NEW.metric_ordinal
)
BEGIN
    SELECT RAISE(ABORT, 'draft_outcome_metric_hash_mismatch');
END;

CREATE TRIGGER IF NOT EXISTS validate_draft_outcome_publication_metrics
BEFORE INSERT ON draft_outcome_publications
BEGIN
    SELECT CASE WHEN abs(
        (julianday(NEW.published_at) - julianday('now')) * 86400.0
    ) > 300.0 OR julianday(NEW.published_at) IS NULL
        THEN RAISE(ABORT, 'draft_outcome_publication_time_invalid') END;
    SELECT CASE WHEN NEW.metric_count <> (
        SELECT COUNT(*) FROM draft_outcome_metrics
        WHERE outcome_checkpoint_id = NEW.outcome_checkpoint_id
    ) THEN RAISE(ABORT, 'draft_outcome_metric_count_mismatch') END;

    SELECT CASE WHEN NEW.metric_set_sha256 <> (
        SELECT canonical_sha256_agg_v2(metric_sha256)
        FROM (
            SELECT metric_sha256
            FROM draft_outcome_metrics
            WHERE outcome_checkpoint_id = NEW.outcome_checkpoint_id
            ORDER BY metric_ordinal, outcome_metric_id
        )
    ) THEN RAISE(ABORT, 'draft_outcome_metric_set_hash_mismatch') END;
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_draft_outcome_metric_insert
BEFORE INSERT ON draft_outcome_metrics
WHEN EXISTS (
    SELECT 1 FROM draft_outcome_publications
    WHERE outcome_checkpoint_id = NEW.outcome_checkpoint_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_draft_outcome_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_draft_outcome_metric_update
BEFORE UPDATE ON draft_outcome_metrics
WHEN EXISTS (
    SELECT 1 FROM draft_outcome_publications
    WHERE outcome_checkpoint_id = OLD.outcome_checkpoint_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_draft_outcome_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_draft_outcome_metric_delete
BEFORE DELETE ON draft_outcome_metrics
WHEN EXISTS (
    SELECT 1 FROM draft_outcome_publications
    WHERE outcome_checkpoint_id = OLD.outcome_checkpoint_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_draft_outcome_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_draft_outcome_checkpoint_update
BEFORE UPDATE ON draft_outcome_checkpoints
WHEN EXISTS (
    SELECT 1 FROM draft_outcome_publications
    WHERE outcome_checkpoint_id = OLD.outcome_checkpoint_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_draft_outcome_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_draft_outcome_checkpoint_delete
BEFORE DELETE ON draft_outcome_checkpoints
WHEN EXISTS (
    SELECT 1 FROM draft_outcome_publications
    WHERE outcome_checkpoint_id = OLD.outcome_checkpoint_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_draft_outcome_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_draft_experiment_update
BEFORE UPDATE ON draft_experiments
WHEN EXISTS (
    SELECT 1 FROM draft_experiment_publications
    WHERE experiment_id = OLD.experiment_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_draft_experiment_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_draft_experiment_delete
BEFORE DELETE ON draft_experiments
WHEN EXISTS (
    SELECT 1 FROM draft_experiment_publications
    WHERE experiment_id = OLD.experiment_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_draft_experiment_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_draft_assignment_insert
BEFORE INSERT ON draft_experiment_assignments
WHEN EXISTS (
    SELECT 1 FROM draft_experiment_publications
    WHERE experiment_id = NEW.experiment_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_draft_experiment_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_draft_assignment_update
BEFORE UPDATE ON draft_experiment_assignments
WHEN EXISTS (
    SELECT 1 FROM draft_experiment_publications
    WHERE experiment_id = OLD.experiment_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_draft_experiment_frozen');
END;

CREATE TRIGGER IF NOT EXISTS freeze_published_draft_assignment_delete
BEFORE DELETE ON draft_experiment_assignments
WHEN EXISTS (
    SELECT 1 FROM draft_experiment_publications
    WHERE experiment_id = OLD.experiment_id
)
BEGIN
    SELECT RAISE(ABORT, 'published_draft_experiment_frozen');
END;
