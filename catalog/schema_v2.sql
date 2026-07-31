PRAGMA foreign_keys=ON;
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS project_meta(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vehicles(
  vehicle_id TEXT PRIMARY KEY,
  year TEXT NOT NULL,
  make_source TEXT NOT NULL,
  model_source TEXT NOT NULL,
  project_label TEXT NOT NULL,
  source_label_note TEXT
);

CREATE TABLE IF NOT EXISTS variations(
  variation_id TEXT PRIMARY KEY,
  vehicle_id TEXT NOT NULL REFERENCES vehicles(vehicle_id),
  variation_source_label TEXT NOT NULL,
  trim_source TEXT NOT NULL,
  engine_source TEXT NOT NULL,
  route_slug TEXT NOT NULL UNIQUE,
  source_url TEXT NOT NULL UNIQUE,
  expected_category_links INTEGER NOT NULL,
  validation_title TEXT NOT NULL,
  validation_status TEXT NOT NULL CHECK(validation_status IN ('NOT_STARTED','VALIDATED','BLOCKED_RETRYABLE','INVALID')),
  source_accessed_at TEXT,
  source_byte_sha256 TEXT,
  source_lf_sha256 TEXT,
  raw_path TEXT,
  evidence_notes TEXT
);

CREATE TABLE IF NOT EXISTS taxonomy_nodes(
  node_id TEXT PRIMARY KEY,
  variation_id TEXT NOT NULL REFERENCES variations(variation_id),
  parent_node_id TEXT REFERENCES taxonomy_nodes(node_id),
  node_type TEXT NOT NULL CHECK(node_type IN ('CATEGORY','SUBCATEGORY')),
  source_label TEXT NOT NULL,
  normalized_label TEXT NOT NULL,
  source_slug TEXT NOT NULL,
  source_url TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  discovery_status TEXT NOT NULL,
  source_accessed_at TEXT NOT NULL,
  UNIQUE(variation_id,source_slug,node_type)
);

CREATE TABLE IF NOT EXISTS catalogue_leaves(
  catalogue_leaf_id TEXT PRIMARY KEY,
  variation_id TEXT NOT NULL REFERENCES variations(variation_id),
  category_id TEXT NOT NULL REFERENCES taxonomy_nodes(node_id),
  subcategory_id TEXT REFERENCES taxonomy_nodes(node_id),
  parent_leaf_id TEXT REFERENCES catalogue_leaves(catalogue_leaf_id),
  leaf_type TEXT NOT NULL CHECK(leaf_type IN ('CATEGORY_INDEX','DIAGRAM','PRODUCT_DETAIL')),
  diagram_id TEXT,
  diagram_title_source TEXT,
  source_url TEXT NOT NULL,
  renderer_url TEXT,
  expected INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL CHECK(status IN ('NOT_STARTED','IN_PROGRESS','EXTRACTED','SOURCE_VERIFIED','IMAGE_ACQUIRED','IMAGE_VERIFIED','FITMENT_AUDITED','COMPLETENESS_CHECKED','INTEGRITY_CHECKED','QA_FAILED','QA_PASSED','BLOCKED_EXTERNAL')),
  http_status INTEGER,
  source_accessed_at TEXT,
  source_byte_sha256 TEXT,
  source_lf_sha256 TEXT,
  raw_path TEXT,
  visible_row_expected INTEGER,
  extracted_record_count INTEGER NOT NULL DEFAULT 0,
  visible_callout_expected INTEGER,
  extracted_callout_count INTEGER NOT NULL DEFAULT 0,
  image_observation_count INTEGER NOT NULL DEFAULT 0,
  exception_code TEXT,
  evidence_notes TEXT,
  UNIQUE(variation_id,leaf_type,source_url)
);

CREATE TABLE IF NOT EXISTS batches(
  batch_id TEXT PRIMARY KEY,
  variation_id TEXT NOT NULL REFERENCES variations(variation_id),
  catalogue_leaf_id TEXT REFERENCES catalogue_leaves(catalogue_leaf_id),
  stage TEXT NOT NULL,
  responsible_agent TEXT NOT NULL,
  allowed_output_prefix TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('NOT_STARTED','IN_PROGRESS','EXTRACTED','SOURCE_VERIFIED','IMAGE_ACQUIRED','IMAGE_VERIFIED','FITMENT_AUDITED','COMPLETENESS_CHECKED','INTEGRITY_CHECKED','QA_FAILED','QA_PASSED','BLOCKED_EXTERNAL')),
  attempt_count INTEGER NOT NULL DEFAULT 0,
  code_version TEXT NOT NULL,
  skill_version TEXT NOT NULL,
  started_at TEXT,
  completed_at TEXT,
  last_error TEXT,
  checkpoint_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS part_records(
  record_id TEXT PRIMARY KEY,
  vehicle_id TEXT NOT NULL REFERENCES vehicles(vehicle_id),
  year TEXT NOT NULL,
  make_source TEXT NOT NULL,
  model_source TEXT NOT NULL,
  variation_id TEXT NOT NULL REFERENCES variations(variation_id),
  variation_source_label TEXT NOT NULL,
  category_id TEXT NOT NULL REFERENCES taxonomy_nodes(node_id),
  category_source_label TEXT NOT NULL,
  subcategory_id TEXT REFERENCES taxonomy_nodes(node_id),
  subcategory_source_label TEXT,
  catalogue_leaf_id TEXT NOT NULL REFERENCES catalogue_leaves(catalogue_leaf_id),
  diagram_id TEXT,
  diagram_title_source TEXT,
  diagram_callout_source TEXT,
  part_name_source TEXT NOT NULL,
  part_name_normalized TEXT NOT NULL,
  part_description_source TEXT,
  oem_part_number_source TEXT NOT NULL,
  oem_part_number_normalized TEXT NOT NULL,
  superseded_part_number_source TEXT,
  quantity_source TEXT,
  fitment_notes_source TEXT,
  fitment_normalized TEXT,
  applicability_status TEXT NOT NULL,
  part_detail_url TEXT NOT NULL,
  catalogue_page_url TEXT NOT NULL,
  diagram_page_url TEXT,
  image_source_url TEXT,
  image_final_resolved_url TEXT,
  local_image_path TEXT,
  image_mime_type TEXT,
  image_byte_size INTEGER,
  image_width INTEGER,
  image_height INTEGER,
  image_sha256 TEXT,
  source_accessed_at TEXT NOT NULL,
  extractor_agent TEXT NOT NULL,
  extraction_run_id TEXT NOT NULL,
  extraction_status TEXT NOT NULL,
  source_verification_status TEXT NOT NULL,
  image_verification_status TEXT NOT NULL,
  fitment_audit_status TEXT NOT NULL,
  completeness_status TEXT NOT NULL,
  repository_integrity_status TEXT NOT NULL,
  qa_status TEXT NOT NULL,
  exception_code TEXT,
  evidence_notes TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_part_number ON part_records(oem_part_number_normalized);
CREATE INDEX IF NOT EXISTS idx_part_variation ON part_records(variation_id,category_id);
CREATE INDEX IF NOT EXISTS idx_part_url ON part_records(part_detail_url);

CREATE TABLE IF NOT EXISTS image_assets(
  image_sha256 TEXT PRIMARY KEY,
  local_image_path TEXT NOT NULL UNIQUE,
  image_mime_type TEXT NOT NULL,
  image_byte_size INTEGER NOT NULL,
  image_width INTEGER NOT NULL,
  image_height INTEGER NOT NULL,
  decode_status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS image_observations(
  image_observation_id TEXT PRIMARY KEY,
  catalogue_leaf_id TEXT NOT NULL REFERENCES catalogue_leaves(catalogue_leaf_id),
  record_id TEXT REFERENCES part_records(record_id),
  image_role TEXT NOT NULL CHECK(image_role IN ('DIAGRAM','PRODUCT_IMAGE','ILLUSTRATION_THUMBNAIL','STATIC_PLACEHOLDER','STATIC_SITE_ASSET')),
  image_source_url TEXT NOT NULL,
  image_final_resolved_url TEXT,
  image_sha256 TEXT REFERENCES image_assets(image_sha256),
  source_page_url TEXT NOT NULL,
  source_accessed_at TEXT NOT NULL,
  acquisition_status TEXT NOT NULL,
  verification_status TEXT NOT NULL,
  association_status TEXT NOT NULL,
  exception_code TEXT,
  evidence_notes TEXT,
  UNIQUE(catalogue_leaf_id,record_id,image_role,image_source_url)
);
CREATE INDEX IF NOT EXISTS idx_image_obs_status ON image_observations(acquisition_status,verification_status);

CREATE TABLE IF NOT EXISTS defects(
  defect_id TEXT PRIMARY KEY,
  batch_id TEXT REFERENCES batches(batch_id),
  severity TEXT NOT NULL CHECK(severity IN ('CRITICAL','MAJOR','MINOR')),
  responsible_agent TEXT NOT NULL,
  vehicle_id TEXT REFERENCES vehicles(vehicle_id),
  variation_id TEXT REFERENCES variations(variation_id),
  category_id TEXT REFERENCES taxonomy_nodes(node_id),
  subcategory_id TEXT REFERENCES taxonomy_nodes(node_id),
  catalogue_leaf_id TEXT REFERENCES catalogue_leaves(catalogue_leaf_id),
  affected_record_ids TEXT NOT NULL DEFAULT '[]',
  description TEXT NOT NULL,
  observed_result TEXT NOT NULL,
  expected_result TEXT NOT NULL,
  source_evidence TEXT NOT NULL,
  reproduction_steps TEXT NOT NULL,
  required_correction TEXT NOT NULL,
  same_pattern_search_requirement TEXT NOT NULL,
  retest_requirements TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('OPEN','IN_PROGRESS','RESOLVED','WONT_FIX_EXTERNAL')),
  created_at TEXT NOT NULL,
  resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS crawl_events(
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at TEXT NOT NULL,
  run_id TEXT NOT NULL,
  stage TEXT NOT NULL,
  variation_id TEXT,
  catalogue_leaf_id TEXT,
  status TEXT NOT NULL,
  http_status INTEGER,
  message TEXT,
  FOREIGN KEY(variation_id) REFERENCES variations(variation_id),
  FOREIGN KEY(catalogue_leaf_id) REFERENCES catalogue_leaves(catalogue_leaf_id)
);

CREATE TABLE IF NOT EXISTS qa_runs(
  qa_run_id TEXT PRIMARY KEY,
  quality_agent TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  deterministic_checks_json TEXT NOT NULL,
  source_resample_json TEXT NOT NULL,
  critical_open INTEGER NOT NULL,
  major_open INTEGER NOT NULL,
  minor_open INTEGER NOT NULL,
  final_status TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS catalogue_fts USING fts5(
  record_id UNINDEXED,
  vehicle,
  variation,
  category,
  subcategory,
  diagram,
  callout,
  part_number,
  part_name,
  description,
  fitment,
  source_url UNINDEXED,
  tokenize='unicode61 remove_diacritics 2'
);
