PRAGMA foreign_keys=ON;
PRAGMA journal_mode=WAL;

CREATE TABLE project_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE vehicles(
 vehicle_id TEXT PRIMARY KEY, year INTEGER NOT NULL CHECK(year=2017), make_source TEXT NOT NULL, model_source TEXT NOT NULL,
 CHECK(length(trim(make_source))>0 AND length(trim(model_source))>0)
);
CREATE TABLE variations(
 variation_id TEXT PRIMARY KEY,vehicle_id TEXT NOT NULL REFERENCES vehicles(vehicle_id),variation_source_label TEXT NOT NULL,
 trim_source TEXT NOT NULL,engine_source TEXT NOT NULL,fuel_source TEXT NOT NULL,route_slug TEXT NOT NULL UNIQUE,route_url TEXT NOT NULL UNIQUE,
 derivation_basis TEXT NOT NULL,evidence_url TEXT NOT NULL,expected_category_count INTEGER NOT NULL CHECK(expected_category_count>0),
 validation_status TEXT NOT NULL CHECK(validation_status IN ('NOT_STARTED','VALIDATED','BLOCKED_EXTERNAL','QA_FAILED')),source_accessed_at TEXT,source_page_sha256 TEXT,
 UNIQUE(variation_id,vehicle_id)
);
CREATE TABLE taxonomy_nodes(
 node_id TEXT PRIMARY KEY,variation_id TEXT NOT NULL REFERENCES variations(variation_id),parent_node_id TEXT REFERENCES taxonomy_nodes(node_id),
 node_type TEXT NOT NULL CHECK(node_type IN ('CATEGORY','SUBCATEGORY')),source_label TEXT NOT NULL,normalized_label TEXT NOT NULL,source_slug TEXT NOT NULL,source_url TEXT NOT NULL,ordinal INTEGER NOT NULL,
 discovery_status TEXT NOT NULL CHECK(discovery_status IN ('DISCOVERED','SOURCE_VERIFIED','QA_PASSED','BLOCKED_EXTERNAL')),source_accessed_at TEXT,
 UNIQUE(variation_id,node_type,source_slug),UNIQUE(node_id,variation_id)
);
CREATE TRIGGER taxonomy_parent_context_insert BEFORE INSERT ON taxonomy_nodes WHEN NEW.parent_node_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM taxonomy_nodes p WHERE p.node_id=NEW.parent_node_id AND p.variation_id=NEW.variation_id) BEGIN SELECT RAISE(ABORT,'taxonomy parent variation mismatch');END;
CREATE TRIGGER taxonomy_parent_context_update BEFORE UPDATE OF parent_node_id,variation_id ON taxonomy_nodes WHEN NEW.parent_node_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM taxonomy_nodes p WHERE p.node_id=NEW.parent_node_id AND p.variation_id=NEW.variation_id) BEGIN SELECT RAISE(ABORT,'taxonomy parent variation mismatch');END;
CREATE TABLE source_snapshots(
 snapshot_id TEXT PRIMARY KEY,source_url TEXT NOT NULL,renderer_url TEXT,source_accessed_at TEXT NOT NULL,http_status INTEGER NOT NULL,final_url TEXT,
 byte_sha256 TEXT NOT NULL,canonical_text_sha256 TEXT NOT NULL,byte_size INTEGER NOT NULL,raw_path TEXT NOT NULL UNIQUE,structure_status TEXT NOT NULL,
 retrieval_run_id TEXT NOT NULL,UNIQUE(source_url,byte_sha256)
);
CREATE TABLE catalogue_leaves(
 catalogue_leaf_id TEXT PRIMARY KEY,variation_id TEXT NOT NULL,category_id TEXT NOT NULL,subcategory_id TEXT NOT NULL,parent_leaf_id TEXT REFERENCES catalogue_leaves(catalogue_leaf_id),
 leaf_type TEXT NOT NULL CHECK(leaf_type IN ('CATEGORY_INDEX','DIAGRAM')),diagram_id TEXT,diagram_title_source TEXT,assembly_number INTEGER,source_url TEXT NOT NULL,current_snapshot_id TEXT REFERENCES source_snapshots(snapshot_id),
 status TEXT NOT NULL CHECK(status IN ('NOT_STARTED','IN_PROGRESS','EXTRACTED','SOURCE_VERIFIED','IMAGE_ACQUIRED','IMAGE_VERIFIED','FITMENT_AUDITED','COMPLETENESS_CHECKED','INTEGRITY_CHECKED','QA_FAILED','QA_PASSED','BLOCKED_EXTERNAL','RETIRED_SOURCE')),source_structure_status TEXT,
 expected_source_row_count INTEGER,extracted_source_row_count INTEGER,expected_callout_count INTEGER,extracted_callout_count INTEGER,expected_image_count INTEGER,observed_image_count INTEGER,
 processing_started_at TEXT,processing_completed_at TEXT,exception_code TEXT,evidence_notes TEXT,
 UNIQUE(variation_id,source_url),UNIQUE(catalogue_leaf_id,variation_id),
 FOREIGN KEY(category_id,variation_id) REFERENCES taxonomy_nodes(node_id,variation_id),FOREIGN KEY(subcategory_id,variation_id) REFERENCES taxonomy_nodes(node_id,variation_id)
);
CREATE TRIGGER leaf_parent_context_insert BEFORE INSERT ON catalogue_leaves WHEN NEW.parent_leaf_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM catalogue_leaves p WHERE p.catalogue_leaf_id=NEW.parent_leaf_id AND p.variation_id=NEW.variation_id AND p.category_id=NEW.category_id AND p.subcategory_id=NEW.subcategory_id) BEGIN SELECT RAISE(ABORT,'leaf parent context mismatch');END;
CREATE TABLE visible_source_rows(
 source_row_key TEXT PRIMARY KEY,catalogue_leaf_id TEXT NOT NULL REFERENCES catalogue_leaves(catalogue_leaf_id) ON DELETE CASCADE,source_section TEXT NOT NULL CHECK(source_section IN ('DETAILED_TABLE','CALLOUT_SUMMARY','ACCESSORY_RESULTS','RELATED_PARTS','MARKERLESS_PRODUCT_CARDS')),
 source_row_anchor TEXT NOT NULL,source_occurrence_ordinal INTEGER NOT NULL CHECK(source_occurrence_ordinal>=1),source_locator TEXT NOT NULL,evidence_snippet_sha256 TEXT NOT NULL,evidence_snippet_source TEXT NOT NULL,
 diagram_callout_source TEXT,part_detail_url TEXT,displayed_part_number_source TEXT,displayed_part_name_source TEXT,displayed_quantity_source TEXT,displayed_fitment_source TEXT,
 expected_image_count INTEGER NOT NULL DEFAULT 0,extraction_status TEXT NOT NULL CHECK(extraction_status IN ('EXTRACTED','EXPLICIT_SOURCE_EXCEPTION')),
 UNIQUE(catalogue_leaf_id,source_section,source_row_anchor,source_occurrence_ordinal)
);
CREATE TABLE part_records(
 record_id TEXT PRIMARY KEY,source_row_key TEXT NOT NULL UNIQUE REFERENCES visible_source_rows(source_row_key) ON DELETE CASCADE,
 vehicle_id TEXT NOT NULL REFERENCES vehicles(vehicle_id),year INTEGER NOT NULL,make_source TEXT NOT NULL,model_source TEXT NOT NULL,variation_id TEXT NOT NULL,variation_source_label TEXT NOT NULL,
 category_id TEXT NOT NULL,category_source_label TEXT NOT NULL,subcategory_id TEXT NOT NULL,subcategory_source_label TEXT NOT NULL,catalogue_leaf_id TEXT NOT NULL,
 diagram_id TEXT,diagram_title_source TEXT,diagram_callout_source TEXT,source_section TEXT NOT NULL,source_row_anchor TEXT NOT NULL,source_occurrence_ordinal INTEGER NOT NULL,evidence_snippet_sha256 TEXT NOT NULL,
 part_name_source TEXT NOT NULL,part_name_normalized TEXT NOT NULL,part_description_source TEXT,oem_part_number_source TEXT NOT NULL,oem_part_number_normalized TEXT NOT NULL,
 superseded_part_number_source TEXT,quantity_source TEXT,fitment_notes_source TEXT,fitment_normalized TEXT,applicability_status TEXT NOT NULL,
 part_detail_url TEXT NOT NULL,catalogue_page_url TEXT NOT NULL,diagram_page_url TEXT,image_source_url TEXT,image_final_resolved_url TEXT,local_image_path TEXT,image_mime_type TEXT,image_byte_size INTEGER,image_width INTEGER,image_height INTEGER,image_sha256 TEXT,
 source_accessed_at TEXT NOT NULL,extractor_agent TEXT NOT NULL,extraction_run_id TEXT NOT NULL,extraction_status TEXT NOT NULL,source_verification_status TEXT NOT NULL,image_verification_status TEXT NOT NULL,fitment_audit_status TEXT NOT NULL,completeness_status TEXT NOT NULL,repository_integrity_status TEXT NOT NULL,qa_status TEXT NOT NULL,exception_code TEXT,evidence_notes TEXT,field_provenance_json TEXT NOT NULL,
 FOREIGN KEY(catalogue_leaf_id,variation_id) REFERENCES catalogue_leaves(catalogue_leaf_id,variation_id),FOREIGN KEY(category_id,variation_id) REFERENCES taxonomy_nodes(node_id,variation_id),FOREIGN KEY(subcategory_id,variation_id) REFERENCES taxonomy_nodes(node_id,variation_id)
);
CREATE TRIGGER record_context_insert BEFORE INSERT ON part_records WHEN NOT EXISTS(SELECT 1 FROM catalogue_leaves l JOIN variations v ON v.variation_id=l.variation_id JOIN vehicles ve ON ve.vehicle_id=v.vehicle_id WHERE l.catalogue_leaf_id=NEW.catalogue_leaf_id AND l.variation_id=NEW.variation_id AND l.category_id=NEW.category_id AND l.subcategory_id=NEW.subcategory_id AND v.vehicle_id=NEW.vehicle_id AND ve.year=NEW.year AND ve.make_source=NEW.make_source AND ve.model_source=NEW.model_source) BEGIN SELECT RAISE(ABORT,'record context mismatch');END;
CREATE TABLE product_sources(
 product_source_id TEXT PRIMARY KEY,source_url TEXT NOT NULL UNIQUE,current_snapshot_id TEXT REFERENCES source_snapshots(snapshot_id),status TEXT NOT NULL CHECK(status IN ('NOT_STARTED','IN_PROGRESS','EXTRACTED_COMPLETE','SOURCE_RENDERER_PARTIAL','QA_FAILED','SOURCE_VERIFIED','IMAGE_VERIFIED','INTEGRITY_CHECKED','QA_PASSED','BLOCKED_EXTERNAL')),
 structure_status TEXT,displayed_part_number_source TEXT,part_name_source TEXT,description_source TEXT,superseded_part_number_source TEXT,fitment_source TEXT,expected_image_count INTEGER,observed_image_count INTEGER,no_image_disposition TEXT,
 processing_started_at TEXT,processing_completed_at TEXT,exception_code TEXT,evidence_notes TEXT
);
CREATE TABLE record_product_sources(record_id TEXT NOT NULL REFERENCES part_records(record_id) ON DELETE CASCADE,product_source_id TEXT NOT NULL REFERENCES product_sources(product_source_id) ON DELETE CASCADE,association_basis TEXT NOT NULL,PRIMARY KEY(record_id,product_source_id));
CREATE TABLE image_assets(
 image_sha256 TEXT PRIMARY KEY,local_image_path TEXT NOT NULL UNIQUE,image_mime_type TEXT NOT NULL,image_format TEXT NOT NULL,image_byte_size INTEGER NOT NULL CHECK(image_byte_size>0),image_width INTEGER NOT NULL CHECK(image_width>0),image_height INTEGER NOT NULL CHECK(image_height>0),pixel_sha256 TEXT NOT NULL,alpha_present INTEGER NOT NULL CHECK(alpha_present IN (0,1)),decode_status TEXT NOT NULL CHECK(decode_status='DECODE_OK'),placeholder_classification TEXT NOT NULL,placeholder_evidence TEXT,first_acquired_at TEXT NOT NULL,acquisition_run_id TEXT NOT NULL
);
CREATE TABLE image_observations(
 image_observation_id TEXT PRIMARY KEY,catalogue_leaf_id TEXT REFERENCES catalogue_leaves(catalogue_leaf_id) ON DELETE CASCADE,product_source_id TEXT REFERENCES product_sources(product_source_id) ON DELETE CASCADE,record_id TEXT REFERENCES part_records(record_id) ON DELETE CASCADE,
 source_row_key TEXT REFERENCES visible_source_rows(source_row_key) ON DELETE CASCADE,source_snapshot_id TEXT NOT NULL REFERENCES source_snapshots(snapshot_id),source_page_sha256 TEXT NOT NULL,source_locator TEXT NOT NULL,source_occurrence_ordinal INTEGER NOT NULL,image_role TEXT NOT NULL,image_alt_source TEXT,image_source_url TEXT NOT NULL,image_final_resolved_url TEXT,
 association_basis TEXT NOT NULL,association_status TEXT NOT NULL CHECK(association_status IN ('ASSOCIATION_FROM_EXACT_SOURCE_WRAPPER','ASSOCIATION_FROM_ASSEMBLY_SELECTOR','ASSOCIATION_FROM_ACTIVE_DIAGRAM','ASSOCIATION_FROM_PRODUCT_GALLERY','ASSOCIATION_METADATA_CONFLICT','REQUIRES_MANUAL_REVIEW')),
 acquisition_status TEXT NOT NULL CHECK(acquisition_status IN ('NOT_STARTED','ACQUIRED','FAILED','NOT_APPLICABLE')),verification_status TEXT NOT NULL,image_sha256 TEXT REFERENCES image_assets(image_sha256),http_status INTEGER,http_content_type TEXT,response_etag TEXT,response_last_modified TEXT,acquired_at TEXT,verified_at TEXT,acquisition_run_id TEXT,verification_run_id TEXT,exception_code TEXT,evidence_notes TEXT,
 CHECK((catalogue_leaf_id IS NOT NULL) != (product_source_id IS NOT NULL)),UNIQUE(source_snapshot_id,source_locator,source_occurrence_ordinal)
);
CREATE TABLE image_observation_records(image_observation_id TEXT NOT NULL REFERENCES image_observations(image_observation_id) ON DELETE CASCADE,record_id TEXT NOT NULL REFERENCES part_records(record_id) ON DELETE CASCADE,association_basis TEXT NOT NULL,PRIMARY KEY(image_observation_id,record_id));
CREATE TRIGGER image_record_context_insert BEFORE INSERT ON image_observations WHEN NEW.record_id IS NOT NULL AND NEW.catalogue_leaf_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM part_records r WHERE r.record_id=NEW.record_id AND r.catalogue_leaf_id=NEW.catalogue_leaf_id AND (NEW.source_row_key IS NULL OR r.source_row_key=NEW.source_row_key)) BEGIN SELECT RAISE(ABORT,'image record leaf mismatch');END;
CREATE TABLE batches(
 batch_id TEXT PRIMARY KEY,stage TEXT NOT NULL,scope_type TEXT NOT NULL,scope_id TEXT NOT NULL,responsible_agent TEXT NOT NULL,allowed_output_paths TEXT NOT NULL,expected_output TEXT NOT NULL,completion_test TEXT NOT NULL,status TEXT NOT NULL,attempt_count INTEGER NOT NULL DEFAULT 0,source_selector_state TEXT,code_version TEXT NOT NULL,skill_version TEXT NOT NULL,first_item TEXT,last_item TEXT,started_at TEXT,completed_at TEXT,last_error TEXT,checkpoint_path TEXT,UNIQUE(stage,scope_type,scope_id)
);
CREATE TABLE defects(
 defect_id TEXT PRIMARY KEY,origin TEXT NOT NULL CHECK(origin IN ('AUTOMATED','MANUAL','SOURCE_REVIEW')),check_code TEXT NOT NULL,last_seen_qa_run_id TEXT,batch_id TEXT,severity TEXT NOT NULL CHECK(severity IN ('CRITICAL','MAJOR','MINOR')),responsible_agent TEXT NOT NULL,vehicle_id TEXT,variation_id TEXT,category_id TEXT,subcategory_id TEXT,catalogue_leaf_id TEXT,affected_record_ids TEXT NOT NULL,description TEXT NOT NULL,observed_result TEXT NOT NULL,expected_result TEXT NOT NULL,source_evidence TEXT NOT NULL,reproduction_steps TEXT NOT NULL,required_correction TEXT NOT NULL,same_pattern_search_requirement TEXT NOT NULL,retest_requirements TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('OPEN','IN_PROGRESS','RESOLVED','BLOCKED_EXTERNAL')),created_at TEXT NOT NULL,resolved_at TEXT,retest_run_id TEXT
);
CREATE TABLE qa_runs(qa_run_id TEXT PRIMARY KEY,quality_agent TEXT NOT NULL,started_at TEXT NOT NULL,completed_at TEXT,check_results_json TEXT,status TEXT NOT NULL,git_commit TEXT,db_sha256 TEXT,report_path TEXT);
CREATE VIRTUAL TABLE catalogue_fts USING fts5(record_id UNINDEXED,variation_source_label,category_source_label,subcategory_source_label,diagram_title_source,diagram_callout_source,part_name_source,part_description_source,oem_part_number_source,fitment_notes_source,content='');
CREATE INDEX idx_leaves_status ON catalogue_leaves(leaf_type,status);CREATE INDEX idx_rows_leaf ON visible_source_rows(catalogue_leaf_id,source_section);CREATE INDEX idx_records_part ON part_records(oem_part_number_normalized);CREATE INDEX idx_records_var ON part_records(variation_id);CREATE INDEX idx_product_status ON product_sources(status);CREATE INDEX idx_img_status ON image_observations(acquisition_status,verification_status);CREATE INDEX idx_defects_status ON defects(status,severity);
