PRAGMA foreign_keys = ON;

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
    source_run_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (library_account_id) REFERENCES style_accounts(library_account_id)
        ON UPDATE CASCADE
) STRICT;

CREATE INDEX IF NOT EXISTS ix_account_baselines_account_metric
    ON account_baseline_snapshots(library_account_id, metric_name);

CREATE TABLE IF NOT EXISTS style_post_observations (
    post_observation_id TEXT PRIMARY KEY NOT NULL,
    library_post_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    run_post_id TEXT NOT NULL,
    source_csv_sha256 TEXT NOT NULL,
    collected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    baseline_snapshot_id TEXT,
    account_baseline_multiple REAL
        CHECK (account_baseline_multiple IS NULL OR account_baseline_multiple >= 0.0),
    performance_tier TEXT NOT NULL DEFAULT 'unknown'
        CHECK (performance_tier IN ('high', 'ordinary', 'low', 'unknown')),
    query_fingerprints TEXT NOT NULL DEFAULT '[]',
    search_surface TEXT NOT NULL DEFAULT '',
    sort_or_filter TEXT NOT NULL DEFAULT '',
    known_confounds TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (run_id, run_post_id, library_post_id)
        REFERENCES run_post_refs(run_id, run_post_id, library_post_id)
        ON UPDATE CASCADE,
    FOREIGN KEY (baseline_snapshot_id)
        REFERENCES account_baseline_snapshots(baseline_snapshot_id)
        ON UPDATE CASCADE ON DELETE SET NULL
) STRICT;

CREATE INDEX IF NOT EXISTS ix_style_post_observations_post
    ON style_post_observations(library_post_id);

CREATE INDEX IF NOT EXISTS ix_style_post_observations_run_post
    ON style_post_observations(run_id, run_post_id);

CREATE INDEX IF NOT EXISTS ix_style_post_observations_baseline
    ON style_post_observations(baseline_snapshot_id);

CREATE TABLE IF NOT EXISTS post_metrics (
    post_metric_id TEXT PRIMARY KEY NOT NULL,
    post_observation_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    post_age_hours REAL CHECK (post_age_hours IS NULL OR post_age_hours >= 0.0),
    visibility_scope TEXT NOT NULL DEFAULT 'unknown',
    FOREIGN KEY (post_observation_id)
        REFERENCES style_post_observations(post_observation_id)
        ON UPDATE CASCADE
) STRICT;

CREATE INDEX IF NOT EXISTS ix_post_metrics_observation_metric
    ON post_metrics(post_observation_id, metric_name);

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
    taxonomy_version INTEGER NOT NULL DEFAULT 1 CHECK (taxonomy_version = 1),
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
    taxonomy_version INTEGER NOT NULL DEFAULT 1 CHECK (taxonomy_version = 1),
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (slide_id) REFERENCES style_slides(slide_id)
        ON UPDATE CASCADE
) STRICT;

CREATE INDEX IF NOT EXISTS ix_visual_observations_slide
    ON visual_observations(slide_id);

CREATE TABLE IF NOT EXISTS copy_observations (
    observation_id TEXT PRIMARY KEY NOT NULL,
    library_post_id TEXT NOT NULL,
    slide_id TEXT,
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
    taxonomy_version INTEGER NOT NULL DEFAULT 1 CHECK (taxonomy_version = 1),
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (library_post_id) REFERENCES style_posts(library_post_id)
        ON UPDATE CASCADE,
    FOREIGN KEY (slide_id, library_post_id)
        REFERENCES style_slides(slide_id, library_post_id)
        ON UPDATE CASCADE
) STRICT;

CREATE INDEX IF NOT EXISTS ix_copy_observations_post
    ON copy_observations(library_post_id);

CREATE INDEX IF NOT EXISTS ix_copy_observations_slide
    ON copy_observations(slide_id);

CREATE TABLE IF NOT EXISTS style_archetypes (
    archetype_id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    category_scope TEXT NOT NULL DEFAULT '',
    carrier TEXT NOT NULL DEFAULT 'unknown'
        CHECK (carrier IN (
            'real_photo_diary', 'photo_annotation', 'screenshot_markup',
            'chat_dramatization', 'text_card', 'checklist_steps',
            'comparison_warning', 'collage_journal',
            'single_image_reminder', 'unknown', 'other'
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
    taxonomy_version INTEGER NOT NULL DEFAULT 1 CHECK (taxonomy_version = 1)
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
    FOREIGN KEY (archetype_id) REFERENCES style_archetypes(archetype_id)
        ON UPDATE CASCADE
) STRICT;

CREATE INDEX IF NOT EXISTS ix_archetype_rules_archetype_version
    ON archetype_rules(archetype_id, archetype_version);

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

CREATE TABLE IF NOT EXISTS draft_style_bindings (
    draft_binding_id TEXT PRIMARY KEY NOT NULL,
    draft_id TEXT NOT NULL,
    binding_source TEXT NOT NULL DEFAULT 'library'
        CHECK (binding_source IN ('library', 'starter_pack')),
    archetype_id TEXT,
    binding_role TEXT NOT NULL
        CHECK (binding_role IN ('primary', 'secondary')),
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
        ON UPDATE CASCADE
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_draft_binding_validate_insert
BEFORE INSERT ON draft_style_bindings
BEGIN
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

    SELECT CASE
        WHEN NEW.binding_role = 'secondary'
         AND NOT EXISTS (
             SELECT 1 FROM draft_style_bindings
             WHERE draft_id = NEW.draft_id AND binding_role = 'primary'
         )
        THEN RAISE(ABORT, 'secondary_requires_primary')
    END;
END;

CREATE TRIGGER IF NOT EXISTS trg_draft_binding_validate_update
BEFORE UPDATE ON draft_style_bindings
BEGIN
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

    SELECT CASE
        WHEN NEW.binding_role = 'secondary'
         AND NOT EXISTS (
             SELECT 1 FROM draft_style_bindings
             WHERE draft_id = NEW.draft_id
               AND binding_role = 'primary'
               AND draft_binding_id <> OLD.draft_binding_id
         )
        THEN RAISE(ABORT, 'secondary_requires_primary')
    END;

    SELECT CASE
        WHEN OLD.binding_role = 'primary'
         AND (NEW.binding_role <> 'primary' OR NEW.draft_id <> OLD.draft_id)
         AND EXISTS (
             SELECT 1 FROM draft_style_bindings
             WHERE draft_id = OLD.draft_id
               AND binding_role = 'secondary'
         )
        THEN RAISE(ABORT, 'primary_has_secondary')
    END;
END;

CREATE TRIGGER IF NOT EXISTS trg_draft_binding_guard_primary_delete
BEFORE DELETE ON draft_style_bindings
WHEN OLD.binding_role = 'primary'
 AND EXISTS (
     SELECT 1 FROM draft_style_bindings
     WHERE draft_id = OLD.draft_id AND binding_role = 'secondary'
 )
BEGIN
    SELECT RAISE(ABORT, 'primary_has_secondary');
END;

CREATE UNIQUE INDEX IF NOT EXISTS ux_draft_style_bindings_primary
    ON draft_style_bindings(draft_id)
    WHERE binding_role = 'primary';

CREATE UNIQUE INDEX IF NOT EXISTS ux_draft_style_bindings_secondary
    ON draft_style_bindings(draft_id)
    WHERE binding_role = 'secondary';

CREATE INDEX IF NOT EXISTS ix_draft_style_bindings_archetype
    ON draft_style_bindings(archetype_id, archetype_version);

CREATE TABLE IF NOT EXISTS draft_assets (
    draft_asset_id TEXT PRIMARY KEY NOT NULL,
    draft_binding_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    slide_index INTEGER NOT NULL CHECK (slide_index >= 0),
    asset_role TEXT NOT NULL DEFAULT 'generated',
    render_method TEXT NOT NULL DEFAULT '',
    style_rule_ids TEXT NOT NULL DEFAULT '[]'
        CHECK (
            CASE WHEN json_valid(style_rule_ids)
                THEN json_type(style_rule_ids) = 'array'
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
