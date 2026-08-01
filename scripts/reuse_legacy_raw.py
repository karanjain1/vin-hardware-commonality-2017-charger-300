#!/usr/bin/env python
"""Seed v2 category evidence from hash-verified legacy raw pages.

No database is modified. Only exact source-URL matches are reused. Legacy
source hashes may represent LF-normalized text because of historical Windows
newline translation; both literal and canonical-LF hashes are checked.
"""
from pathlib import Path
import hashlib,sqlite3
ROOT=Path(__file__).resolve().parents[1];CAT=ROOT/'catalog'
legacy=sqlite3.connect(f'file:{(CAT/"mopar_catalog.sqlite3").as_posix()}?mode=ro',uri=True);legacy.row_factory=sqlite3.Row
v2=sqlite3.connect(f'file:{(CAT/"authoritative_catalogue.sqlite3").as_posix()}?mode=ro',uri=True);v2.row_factory=sqlite3.Row
expected={r['source_url']:r for r in v2.execute("SELECT catalogue_leaf_id,variation_id,source_url FROM catalogue_leaves WHERE leaf_type='CATEGORY_INDEX'")}
copied=already=invalid=unmatched=0
for row in legacy.execute("SELECT vc.source_url,vc.source_sha256,vc.raw_path,vc.crawl_state FROM variant_categories vc WHERE vc.crawl_state='complete' AND vc.raw_path IS NOT NULL"):
 target=expected.get(row['source_url'])
 if not target:unmatched+=1;continue
 src=CAT/row['raw_path']
 if not src.exists():invalid+=1;continue
 data=src.read_bytes();literal=hashlib.sha256(data).hexdigest()
 try:canonical=hashlib.sha256(src.read_text(encoding='utf-8').replace('\r\n','\n').replace('\r','\n').encode()).hexdigest()
 except UnicodeDecodeError:canonical=''
 if row['source_sha256'] not in {literal,canonical}:invalid+=1;continue
 dst=CAT/'v2'/'evidence'/'source'/target['variation_id']/'category_index'/(hashlib.sha256(target['catalogue_leaf_id'].encode()).hexdigest()+'.md')
 if dst.exists():already+=1;continue
 dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data);copied+=1
print({'copied':copied,'already':already,'invalid':invalid,'unmatched':unmatched})
legacy.close();v2.close()
