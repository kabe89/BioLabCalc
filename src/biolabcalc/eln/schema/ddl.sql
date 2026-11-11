-- ============================================================================
-- Architecture: PostgreSQL 16+ Production DDL for ELN & LIMS Pipeline
-- Component: Core Schema DDL
-- Description: Production-grade PostgreSQL 16+ DDL script containing extensions,
--              custom ENUM types, 21 relational tables, strict foreign keys,
--              domain constraints, and state-of-the-art vector and lexical indexes
--              (HNSW vector indexing for 1536-dim embeddings, GIN for tsvector &
--              JSONB, pg_trgm trigram search, and B-Tree provenance indexing).
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. PostgreSQL Extensions
-- ----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- ----------------------------------------------------------------------------
-- 2. Enumerated Domain Types
-- ----------------------------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM (
        'principal_investigator',
        'active_researcher',
        'rotation_student',
        'lab_manager',
        'alumni',
        'guest'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE expt_status AS ENUM (
        'planned',
        'in_progress',
        'completed',
        'failed',
        'archived',
        'on_hold'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE file_format_category AS ENUM (
        'fplc_res',
        'nanodrop_csv',
        'gel_image_png',
        'gel_image_tiff',
        'ephys_abf',
        'fasta',
        'genbank',
        'pdf',
        'markdown',
        'json',
        'tabular_csv'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE biomolecule_type AS ENUM (
        'plasmid_dna',
        'genomic_dna',
        'mrna',
        'sirna',
        'recombinant_protein',
        'antibody',
        'peptide',
        'chemical_reagent'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE storage_node_type AS ENUM (
        'facility',
        'room',
        'freezer_minus80',
        'freezer_minus20',
        'fridge_4c',
        'liquid_nitrogen',
        'shelf',
        'rack',
        'box',
        'plate_96',
        'plate_384'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ----------------------------------------------------------------------------
-- 3. Core Identity & Access Tables
-- ----------------------------------------------------------------------------

-- Table 1: users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'active_researcher',
    department VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table 2: audit_logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(64) NOT NULL,
    entity_type VARCHAR(64) NOT NULL,
    entity_id VARCHAR(128) NOT NULL,
    changes JSONB,
    client_ip VARCHAR(45),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table 3: storage_blobs
CREATE TABLE IF NOT EXISTS storage_blobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(1024) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    file_hash_sha256 VARCHAR(64) NOT NULL,
    format_category file_format_category NOT NULL,
    mime_type VARCHAR(128) NOT NULL,
    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table 4: sop_templates
CREATE TABLE IF NOT EXISTS sop_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    code VARCHAR(64) UNIQUE NOT NULL,
    version VARCHAR(32) NOT NULL DEFAULT '1.0',
    category VARCHAR(64) NOT NULL,
    content_markdown TEXT NOT NULL,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 4. Experimental Notebook & Campaigns
-- ----------------------------------------------------------------------------

-- Table 5: experimental_campaigns
CREATE TABLE IF NOT EXISTS experimental_campaigns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(128) UNIQUE NOT NULL,
    objective TEXT NOT NULL,
    status expt_status NOT NULL DEFAULT 'planned',
    lead_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    sop_id UUID REFERENCES sop_templates(id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    yield_mg_total DOUBLE PRECISION,
    yield_percent_recovery DOUBLE PRECISION,
    yield_mg_per_liter_culture DOUBLE PRECISION,
    yield_ug_plasmid DOUBLE PRECISION,
    yield_calculation_method VARCHAR(255),
    metadata_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table 6: notebook_daily_entries
CREATE TABLE IF NOT EXISTS notebook_daily_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID NOT NULL REFERENCES experimental_campaigns(id) ON DELETE CASCADE,
    day_number INTEGER NOT NULL,
    entry_date DATE NOT NULL,
    title VARCHAR(255) NOT NULL,
    summary TEXT NOT NULL,
    protocol_deviations TEXT,
    status expt_status NOT NULL DEFAULT 'completed',
    completed_at TIMESTAMPTZ,
    yield_mg_total DOUBLE PRECISION,
    yield_percent_recovery DOUBLE PRECISION,
    yield_mg_per_liter_culture DOUBLE PRECISION,
    yield_ug_plasmid DOUBLE PRECISION,
    yield_calculation_method VARCHAR(255),
    operator_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_campaign_day UNIQUE (campaign_id, day_number)
);

-- Table 7: notebook_timepoint_logs
CREATE TABLE IF NOT EXISTS notebook_timepoint_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entry_id UUID NOT NULL REFERENCES notebook_daily_entries(id) ON DELETE CASCADE,
    timepoint_label VARCHAR(64) NOT NULL,
    elapsed_minutes INTEGER NOT NULL,
    temperature_c DOUBLE PRECISION,
    od600 DOUBLE PRECISION,
    rpm INTEGER,
    parameters_json JSONB,
    notes TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table 8: bio_sequences
CREATE TABLE IF NOT EXISTS bio_sequences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    biomolecule_type biomolecule_type NOT NULL,
    sequence_data TEXT NOT NULL,
    length_bp_or_aa INTEGER NOT NULL,
    molecular_weight_da DOUBLE PRECISION,
    isoelectric_point_pi DOUBLE PRECISION,
    extinction_coefficient_e280 DOUBLE PRECISION,
    plasmid_map_json JSONB,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 5. Molecular Biology, Chromatography & Analytical Tables
-- ----------------------------------------------------------------------------

-- Table 9: pcr_assays
CREATE TABLE IF NOT EXISTS pcr_assays (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID REFERENCES experimental_campaigns(id) ON DELETE CASCADE,
    daily_entry_id UUID REFERENCES notebook_daily_entries(id) ON DELETE CASCADE,
    target_gene VARCHAR(128) NOT NULL,
    forward_primer_name VARCHAR(128) NOT NULL,
    forward_primer_seq VARCHAR(255) NOT NULL,
    reverse_primer_name VARCHAR(128) NOT NULL,
    reverse_primer_seq VARCHAR(255) NOT NULL,
    annealing_temp_c DOUBLE PRECISION NOT NULL,
    extension_time_sec INTEGER NOT NULL,
    cycle_count INTEGER NOT NULL,
    status expt_status NOT NULL DEFAULT 'completed',
    completed_at TIMESTAMPTZ,
    yield_mg_total DOUBLE PRECISION,
    yield_percent_recovery DOUBLE PRECISION,
    yield_mg_per_liter_culture DOUBLE PRECISION,
    yield_ug_plasmid DOUBLE PRECISION,
    yield_calculation_method VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table 10: nanodrop_measurements
CREATE TABLE IF NOT EXISTS nanodrop_measurements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID REFERENCES experimental_campaigns(id) ON DELETE CASCADE,
    daily_entry_id UUID REFERENCES notebook_daily_entries(id) ON DELETE CASCADE,
    sample_name VARCHAR(255) NOT NULL,
    biomolecule_type biomolecule_type NOT NULL,
    concentration_mg_per_ml DOUBLE PRECISION NOT NULL,
    a280 DOUBLE PRECISION NOT NULL,
    a260 DOUBLE PRECISION NOT NULL,
    a260_a280_ratio DOUBLE PRECISION NOT NULL,
    a260_a230_ratio DOUBLE PRECISION,
    buffer_blank VARCHAR(255) NOT NULL,
    status expt_status NOT NULL DEFAULT 'completed',
    completed_at TIMESTAMPTZ,
    yield_mg_total DOUBLE PRECISION,
    yield_percent_recovery DOUBLE PRECISION,
    yield_mg_per_liter_culture DOUBLE PRECISION,
    yield_ug_plasmid DOUBLE PRECISION,
    yield_calculation_method VARCHAR(255),
    raw_blob_id UUID REFERENCES storage_blobs(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table 11: fplc_columns
CREATE TABLE IF NOT EXISTS fplc_columns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    column_type VARCHAR(64) NOT NULL,
    bed_volume_ml DOUBLE PRECISION NOT NULL,
    max_pressure_mpa DOUBLE PRECISION NOT NULL,
    recommended_flow_rate_ml_min DOUBLE PRECISION NOT NULL,
    serial_number VARCHAR(128),
    current_status VARCHAR(64) NOT NULL DEFAULT 'operational',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table 12: fplc_runs
CREATE TABLE IF NOT EXISTS fplc_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID REFERENCES experimental_campaigns(id) ON DELETE CASCADE,
    daily_entry_id UUID REFERENCES notebook_daily_entries(id) ON DELETE CASCADE,
    column_id UUID REFERENCES fplc_columns(id) ON DELETE SET NULL,
    run_name VARCHAR(255) NOT NULL,
    purification_step VARCHAR(64) NOT NULL,
    flow_rate_ml_min DOUBLE PRECISION NOT NULL,
    buffer_a TEXT NOT NULL,
    buffer_b TEXT,
    gradient_profile_json JSONB,
    status expt_status NOT NULL DEFAULT 'completed',
    completed_at TIMESTAMPTZ,
    yield_mg_total DOUBLE PRECISION,
    yield_percent_recovery DOUBLE PRECISION,
    yield_mg_per_liter_culture DOUBLE PRECISION,
    yield_ug_plasmid DOUBLE PRECISION,
    yield_calculation_method VARCHAR(255),
    raw_data_blob_id UUID REFERENCES storage_blobs(id) ON DELETE SET NULL,
    chromatogram_summary_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table 13: fplc_fractions
CREATE TABLE IF NOT EXISTS fplc_fractions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL REFERENCES fplc_runs(id) ON DELETE CASCADE,
    fraction_number VARCHAR(32) NOT NULL,
    retention_volume_ml DOUBLE PRECISION NOT NULL,
    uv280_mau DOUBLE PRECISION NOT NULL,
    uv260_mau DOUBLE PRECISION,
    conductivity_ms_cm DOUBLE PRECISION,
    is_pooled BOOLEAN NOT NULL DEFAULT false,
    notes TEXT,
    CONSTRAINT uq_run_fraction UNIQUE (run_id, fraction_number)
);

-- Table 14: gel_records
CREATE TABLE IF NOT EXISTS gel_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID REFERENCES experimental_campaigns(id) ON DELETE CASCADE,
    daily_entry_id UUID REFERENCES notebook_daily_entries(id) ON DELETE CASCADE,
    gel_type VARCHAR(64) NOT NULL,
    voltage_v INTEGER NOT NULL,
    run_time_minutes INTEGER NOT NULL,
    staining_method VARCHAR(128) NOT NULL,
    status expt_status NOT NULL DEFAULT 'completed',
    completed_at TIMESTAMPTZ,
    image_blob_id UUID REFERENCES storage_blobs(id) ON DELETE SET NULL,
    purity_assessment_percent DOUBLE PRECISION,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table 15: gel_lanes
CREATE TABLE IF NOT EXISTS gel_lanes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    gel_id UUID NOT NULL REFERENCES gel_records(id) ON DELETE CASCADE,
    lane_number INTEGER NOT NULL,
    sample_name VARCHAR(255) NOT NULL,
    sample_type VARCHAR(64) NOT NULL,
    volume_loaded_ul DOUBLE PRECISION NOT NULL,
    estimated_mw_kda DOUBLE PRECISION,
    estimated_mass_ng DOUBLE PRECISION,
    purity_percentage DOUBLE PRECISION,
    band_analysis_json JSONB,
    notes TEXT,
    CONSTRAINT uq_gel_lane UNIQUE (gel_id, lane_number)
);

-- Table 16: ephys_recordings
CREATE TABLE IF NOT EXISTS ephys_recordings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID REFERENCES experimental_campaigns(id) ON DELETE CASCADE,
    cell_type VARCHAR(128) NOT NULL,
    patch_configuration VARCHAR(64) NOT NULL,
    bath_solution TEXT NOT NULL,
    pipette_solution TEXT NOT NULL,
    holding_potential_mv DOUBLE PRECISION NOT NULL,
    sampling_rate_khz DOUBLE PRECISION NOT NULL,
    raw_data_blob_id UUID REFERENCES storage_blobs(id) ON DELETE SET NULL,
    status expt_status NOT NULL DEFAULT 'completed',
    completed_at TIMESTAMPTZ,
    summary_metrics_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table 17: code_analysis_runs
CREATE TABLE IF NOT EXISTS code_analysis_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID REFERENCES experimental_campaigns(id) ON DELETE CASCADE,
    tool_name VARCHAR(128) NOT NULL,
    script_path VARCHAR(512) NOT NULL,
    git_commit_hash VARCHAR(64),
    parameters_json JSONB,
    results_json JSONB,
    status expt_status NOT NULL DEFAULT 'completed',
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 6. LIMS Freezer Hierarchy & Inventory Storage Tables
-- ----------------------------------------------------------------------------

-- Table 18: storage_hierarchy_nodes
CREATE TABLE IF NOT EXISTS storage_hierarchy_nodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parent_id UUID REFERENCES storage_hierarchy_nodes(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    node_type storage_node_type NOT NULL,
    temperature_c DOUBLE PRECISION,
    barcode VARCHAR(128) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table 19: freezer_boxes
CREATE TABLE IF NOT EXISTS freezer_boxes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hierarchy_node_id UUID REFERENCES storage_hierarchy_nodes(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    barcode VARCHAR(128) UNIQUE NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 9,
    col_count INTEGER NOT NULL DEFAULT 9,
    temperature_c DOUBLE PRECISION NOT NULL DEFAULT -80.0,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table 20: inventory_tubes
CREATE TABLE IF NOT EXISTS inventory_tubes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    box_id UUID NOT NULL REFERENCES freezer_boxes(id) ON DELETE CASCADE,
    box_position VARCHAR(16) NOT NULL,
    barcode VARCHAR(128) UNIQUE NOT NULL,
    sample_name VARCHAR(255) NOT NULL,
    biomolecule_type biomolecule_type NOT NULL,
    concentration_mg_ml DOUBLE PRECISION NOT NULL,
    volume_ul DOUBLE PRECISION NOT NULL,
    buffer_composition TEXT NOT NULL,
    campaign_id UUID REFERENCES experimental_campaigns(id) ON DELETE SET NULL,
    status expt_status NOT NULL DEFAULT 'completed',
    completed_at TIMESTAMPTZ,
    yield_mg_total DOUBLE PRECISION,
    yield_percent_recovery DOUBLE PRECISION,
    yield_mg_per_liter_culture DOUBLE PRECISION,
    yield_ug_plasmid DOUBLE PRECISION,
    yield_calculation_method VARCHAR(255),
    metadata_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_box_position UNIQUE (box_id, box_position)
);

-- ----------------------------------------------------------------------------
-- 7. Multi-Modal RAG Document Chunks & Vector Store
-- ----------------------------------------------------------------------------

-- Table 21: rag_document_chunks
CREATE TABLE IF NOT EXISTS rag_document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_entity_type VARCHAR(64) NOT NULL,
    source_entity_id UUID NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    lexical_tsvector TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED,
    extracted_metadata JSONB,
    provenance_context VARCHAR(512) NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_entity_chunk UNIQUE (source_entity_type, source_entity_id, chunk_index)
);

-- ----------------------------------------------------------------------------
-- 8. Specialized Production Indexes
-- ----------------------------------------------------------------------------

-- Vector Index: HNSW with Cosine Distance on RAG Document Chunks
CREATE INDEX IF NOT EXISTS idx_rag_document_chunks_embedding_hnsw
    ON rag_document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Full-Text Lexical Search Index: GIN on TSVECTOR
CREATE INDEX IF NOT EXISTS idx_rag_document_chunks_lexical_tsv
    ON rag_document_chunks
    USING gin (lexical_tsvector);

-- Semi-Structured Metadata Index: GIN on JSONB
CREATE INDEX IF NOT EXISTS idx_rag_document_chunks_extracted_metadata_gin
    ON rag_document_chunks
    USING gin (extracted_metadata);

-- Fuzzy Substring Trigram Index: GIN on chunk_text
CREATE INDEX IF NOT EXISTS idx_rag_document_chunks_trgm
    ON rag_document_chunks
    USING gin (chunk_text gin_trgm_ops);

-- Provenance Traceability Index: B-Tree on provenance_context
CREATE INDEX IF NOT EXISTS idx_rag_document_chunks_provenance_btree
    ON rag_document_chunks (provenance_context);

-- Performance B-Tree Indexes on Foreign Keys, Status & Yield Columns
CREATE INDEX IF NOT EXISTS idx_campaigns_status_completed ON experimental_campaigns (status, completed_at);
CREATE INDEX IF NOT EXISTS idx_campaigns_slug ON experimental_campaigns (slug);
CREATE INDEX IF NOT EXISTS idx_daily_entries_campaign ON notebook_daily_entries (campaign_id, day_number);
CREATE INDEX IF NOT EXISTS idx_fplc_runs_campaign ON fplc_runs (campaign_id);
CREATE INDEX IF NOT EXISTS idx_fplc_fractions_run ON fplc_fractions (run_id);
CREATE INDEX IF NOT EXISTS idx_gel_lanes_gel ON gel_lanes (gel_id);
CREATE INDEX IF NOT EXISTS idx_nanodrop_campaign ON nanodrop_measurements (campaign_id);
CREATE INDEX IF NOT EXISTS idx_inventory_tubes_box ON inventory_tubes (box_id, box_position);
CREATE INDEX IF NOT EXISTS idx_inventory_tubes_barcode ON inventory_tubes (barcode);
CREATE INDEX IF NOT EXISTS idx_freezer_boxes_barcode ON freezer_boxes (barcode);
CREATE INDEX IF NOT EXISTS idx_hierarchy_parent ON storage_hierarchy_nodes (parent_id);

-- End of PostgreSQL 16+ DDL
