PRAGMA foreign_keys=ON;
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS variants(
 id INTEGER PRIMARY KEY, model TEXT NOT NULL, trim TEXT NOT NULL, engine TEXT NOT NULL,
 route_slug TEXT NOT NULL UNIQUE, source_url TEXT NOT NULL, valid INTEGER NOT NULL DEFAULT 0,
 validation_state TEXT NOT NULL DEFAULT 'pending', page_title TEXT, retrieved_at TEXT, source_sha256 TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS categories(
 id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, title TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS variant_categories(
 id INTEGER PRIMARY KEY, variant_id INTEGER NOT NULL REFERENCES variants(id), category_id INTEGER NOT NULL REFERENCES categories(id),
 source_url TEXT NOT NULL, crawl_state TEXT NOT NULL DEFAULT 'pending', retrieved_at TEXT, source_sha256 TEXT,
 raw_path TEXT, part_count INTEGER NOT NULL DEFAULT 0, assembly_count INTEGER NOT NULL DEFAULT 0, error TEXT,
 UNIQUE(variant_id,category_id)
);
CREATE TABLE IF NOT EXISTS parts(
 id INTEGER PRIMARY KEY, part_number TEXT NOT NULL, normalized_part_number TEXT NOT NULL,
 description TEXT NOT NULL, product_url TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_parts_number ON parts(normalized_part_number);
CREATE TABLE IF NOT EXISTS part_offerings(
 id INTEGER PRIMARY KEY, variant_category_id INTEGER NOT NULL REFERENCES variant_categories(id), part_id INTEGER NOT NULL REFERENCES parts(id),
 detail TEXT, evidence_url TEXT NOT NULL, retrieved_at TEXT NOT NULL,
 UNIQUE(variant_category_id,part_id)
);
CREATE TABLE IF NOT EXISTS assemblies(
 id INTEGER PRIMARY KEY, variant_category_id INTEGER NOT NULL REFERENCES variant_categories(id), assembly_no INTEGER NOT NULL,
 title TEXT NOT NULL, source_url TEXT NOT NULL, image_url TEXT NOT NULL, image_path TEXT,
 image_sha256 TEXT, image_bytes INTEGER, retrieved_at TEXT NOT NULL,
 UNIQUE(variant_category_id,assembly_no)
);
CREATE TABLE IF NOT EXISTS callouts(
 id INTEGER PRIMARY KEY, assembly_id INTEGER NOT NULL REFERENCES assemblies(id), callout TEXT NOT NULL,
 part_id INTEGER REFERENCES parts(id), description TEXT, evidence_url TEXT,
 UNIQUE(assembly_id,callout,part_id)
);
CREATE VIRTUAL TABLE IF NOT EXISTS catalog_fts USING fts5(
 entity_type UNINDEXED, model, trim, engine, category, assembly, callout, part_number,
 description, source_url UNINDEXED, tokenize='unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS crawl_events(
 id INTEGER PRIMARY KEY, occurred_at TEXT NOT NULL, stage TEXT NOT NULL, route TEXT,
 status TEXT NOT NULL, http_status INTEGER, message TEXT
);
