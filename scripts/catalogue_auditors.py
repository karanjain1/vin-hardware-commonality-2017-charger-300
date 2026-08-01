#!/usr/bin/env python
"""Independent producer-side auditors (Agents 5–8).

These auditors verify evidence already produced. They never extract or repair
source facts and only advance their own downstream status after a complete pass.
"""
from __future__ import annotations
import argparse,datetime as dt,hashlib,io,json,re,sqlite3,subprocess,tempfile
from collections import Counter
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];CAT=ROOT/'catalog';DB=CAT/'authoritative_catalogue.sqlite3'
def now():return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
def sha(b):return hashlib.sha256(b).hexdigest()
def sid(prefix,*parts):return prefix+'-'+hashlib.sha256('\x1f'.join(str(x or '') for x in parts).encode()).hexdigest()[:24]
def norm(s):return re.sub(r'[^a-z0-9]+','',str(s or '').lower())
def con(ro=False):
 c=sqlite3.connect(f'file:{DB.as_posix()}?mode=ro' if ro else DB,uri=ro,timeout=120);c.row_factory=sqlite3.Row
 if not ro:c.execute('pragma foreign_keys=on');c.execute('pragma busy_timeout=120000')
 return c
def fail(code,severity,agent,scope,observed,expected,evidence):return {'check_code':code,'severity':severity,'responsible_agent':agent,'scope':scope,'observed':observed,'expected':expected,'evidence':evidence}
def persist(stage,run,fails,executed):
 c=con();active=set()
 for f in fails:
  did=sid('defect',f['check_code'],f['scope']);active.add(did);old=c.execute('select created_at,status,origin from defects where defect_id=?',(did,)).fetchone();created=old['created_at'] if old else now();status=old['status'] if old and old['status']=='IN_PROGRESS' else 'OPEN'
  c.execute('''INSERT OR REPLACE INTO defects(defect_id,origin,check_code,last_seen_qa_run_id,severity,responsible_agent,affected_record_ids,description,observed_result,expected_result,source_evidence,reproduction_steps,required_correction,same_pattern_search_requirement,retest_requirements,status,created_at,resolved_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(did,'AUTOMATED',f['check_code'],run,f['severity'],f['responsible_agent'],json.dumps(f.get('records',[])),f['check_code'],json.dumps(f['observed'],ensure_ascii=False),json.dumps(f['expected'],ensure_ascii=False),json.dumps(f['evidence'],ensure_ascii=False),f'Run scripts/catalogue_auditors.py {stage}; scope={f["scope"]}','Correct the owning producer output; do not edit auditor results','Search all six variations for this check code',f'Rerun {stage} and then Agent 9 QA',status,created,None))
 # Resolve only automated OPEN defects for checks fully rerun now; never manual, source-review, or IN_PROGRESS.
 for r in c.execute("SELECT defect_id,check_code FROM defects WHERE origin='AUTOMATED' AND status='OPEN'").fetchall():
  if r['check_code'] in executed and r['defect_id'] not in active:c.execute("UPDATE defects SET status='RESOLVED',resolved_at=?,retest_run_id=? WHERE defect_id=?",(now(),run,r['defect_id']))
 c.commit();c.close()
def snapshot_text(c,snapshot_id):
 s=c.execute('select * from source_snapshots where snapshot_id=?',(snapshot_id,)).fetchone()
 if not s:return None,None,'missing snapshot row'
 p=CAT/s['raw_path']
 if not p.exists():return s,None,'missing raw path'
 b=p.read_bytes()
 if sha(b)!=s['byte_sha256']:return s,None,'snapshot byte hash mismatch'
 return s,b.decode('utf-8',errors='replace'),None
def independent_leaf_counts(text):
 header=re.search(r'\n\s*No\.\s*\n\s*\n\s*Part\s*#\s*/\s*Description\s*/\s*Price',text,re.I);table=text[header.end():] if header else ''
 detailed=len(re.findall(r'\[!\[Image\s+\d+:[^\]]*\]\([^)]*\)\]\(https?://www\.moparamerica\.com/oem-parts/',table))
 result=re.search(r'###\s+(\d+)\s+Results?\s*\|\s*Showing\s+(\d+)\s*[–-]\s*(\d+)\s+of\s+(\d+)',text,re.I);accessory=(0 if int(result.group(4))==0 else int(result.group(3))-int(result.group(2))+1) if result else 0
 if result:
  nav=re.search(r'(?m)^\*\*Navigation\*\*$',text[result.end():]);asection=text[result.end():result.end()+(nav.start() if nav else len(text)-result.end())];accessory_images=len(re.findall(r'\[!\[Image\s+\d+:[^\]]*\]\([^)]*\)\]\(https?://www\.moparamerica\.com/(?:oem-parts/|p-)',asection))
 else:accessory_images=0
 markerless=markerless_images=0
 if not result and 'Markdown Content:' in text and 'No results found.' in text:
  ms=text[text.find('Markdown Content:')+len('Markdown Content:'):text.find('No results found.',text.find('Markdown Content:'))];markerless=len(re.findall(r'(?m)^#{1,2}\s+\[[^\]]+\]\(https?://www\.moparamerica\.com/(?:oem-parts/|p-)',ms));markerless_images=len(re.findall(r'\[!\[Image\s+\d+:[^\]]*\]\([^)]*\)\]\(https?://www\.moparamerica\.com/(?:oem-parts/|p-)',ms))
 relhead=re.search(r'(?m)^##\s+Related Parts\s*$',text)
 if relhead:
  relnav=re.search(r'(?m)^\*\*Navigation\*\*$',text[relhead.end():]);relsection=text[relhead.end():relhead.end()+(relnav.start() if relnav else len(text)-relhead.end())];related=len(re.findall(r'\[!\[Image\s+\d+:[^\]]*\]\([^)]*\)\]\(https?://www\.moparamerica\.com/oem-parts/',relsection))
 else:related=0
 cut=header.start() if header else len(text);pre=text[:cut];heads=list(re.finditer(r'(?m)^Diagram\s+\d+:\s*[^\n]+?\s+\d+\s*$',pre));active=heads[-1] if heads else None;body=pre[active.end():] if active else ''
 markers=list(re.finditer(r'(?m)^\[[^\]]+\]\(https?://www\.moparamerica\.com/#part_row_[^)]+\)',body));callrows=0
 for i,m in enumerate(markers):
  block=body[m.start():(markers[i+1].start() if i+1<len(markers) else len(body))];callrows+=max(1,len(re.findall(r'https?://www\.moparamerica\.com/oem-parts/[^)\s"]+',block)))
 selectors=len(set(re.findall(r'https?://www\.moparamerica\.com/[^)\s"]+\?assembly=\d+',text)));selector_images=len(set(re.findall(r'\[!\[Image\s+\d+:[^\]]*\]\([^)]*\)[^\]]*\]\((https?://www\.moparamerica\.com/[^)\s"]+\?assembly=\d+)',text)));active_images=1 if active and re.search(r'!\[Image\s+\d+:[^\]]*\]\(https?://[^)\s]+\)',body) else 0
 return {'rows':detailed+accessory+markerless+related+callrows,'detailed':detailed,'accessory_rows':accessory,'markerless_rows':markerless,'related_rows':related,'callout_markers':len(markers),'callout_rows':callrows,'images':detailed+accessory_images+markerless_images+related+selector_images+active_images,'selectors':selectors,'selector_images':selector_images,'active_images':active_images}
def complete_product_structure_status(value):return value=='PRODUCT_DETAIL_COMPLETE'
def source_audit():
 run='source-audit-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');c=con();fails=[];executed={'ACTIVE_SCOPE_TERMINAL','SNAPSHOT_INTEGRITY','INDEPENDENT_ROW_RECONCILIATION','ROW_EVIDENCE_ASSOCIATION','INDEPENDENT_IMAGE_ENUMERATION','SELECTOR_CHILD_RECONCILIATION','PRODUCT_SOURCE_STRUCTURE'}
 active=c.execute("select * from catalogue_leaves where status!='RETIRED_SOURCE'").fetchall();bad=[dict(x) for x in active if x['status'] not in ('EXTRACTED','SOURCE_VERIFIED','IMAGE_VERIFIED','FITMENT_AUDITED','COMPLETENESS_CHECKED','INTEGRITY_CHECKED','QA_PASSED')]
 if bad:fails.append(fail('ACTIVE_SCOPE_TERMINAL','CRITICAL','AGENT_3_PART_RECORD_EXTRACTION','project',len(bad),0,[x['catalogue_leaf_id'] for x in bad[:50]]))
 passed=[]
 for l in active:
  if not l['current_snapshot_id']:continue
  s,text,err=snapshot_text(c,l['current_snapshot_id']);scope=l['catalogue_leaf_id']
  if err:fails.append(fail('SNAPSHOT_INTEGRITY','CRITICAL','AGENT_8_REPOSITORY_INTEGRITY',scope,err,'literal hash-valid snapshot',l['source_url']));continue
  ic=independent_leaf_counts(text);rows=c.execute('select * from visible_source_rows where catalogue_leaf_id=?',(scope,)).fetchall();records=c.execute('select r.*,v.evidence_snippet_source from part_records r join visible_source_rows v on v.source_row_key=r.source_row_key where r.catalogue_leaf_id=?',(scope,)).fetchall();obs=c.execute('select * from image_observations where catalogue_leaf_id=?',(scope,)).fetchall();local=[]
  if len(rows)!=len(records) or len(rows)!=l['expected_source_row_count'] or ic['rows']!=len(rows):local.append(fail('INDEPENDENT_ROW_RECONCILIATION','CRITICAL','AGENT_7_COMPLETENESS',scope,{'independent':ic['rows'],'staged':len(rows),'records':len(records),'stored_expected':l['expected_source_row_count']},'all equal',s['raw_path']))
  if ic['callout_markers']!=l['expected_callout_count'] or ic['callout_markers']!=l['extracted_callout_count']:local.append(fail('INDEPENDENT_ROW_RECONCILIATION','MAJOR','AGENT_7_COMPLETENESS',scope,{'independent_callouts':ic['callout_markers'],'expected':l['expected_callout_count'],'extracted':l['extracted_callout_count']},'all equal',s['raw_path']))
  for r in records:
   snippet=r['evidence_snippet_source'];prov=json.loads(r['field_provenance_json'])
   if sha(snippet.encode())!=r['evidence_snippet_sha256'] or snippet not in text or r['part_detail_url'] not in snippet:local.append(fail('ROW_EVIDENCE_ASSOCIATION','CRITICAL','AGENT_3_PART_RECORD_EXTRACTION',r['record_id'],'record/snippet mismatch','exact URL-bearing immutable source snippet',r['source_row_key']))
   if prov.get('oem_part_number_source')=='VISIBLE_SOURCE_ROW' and r['oem_part_number_source'] not in snippet:local.append(fail('ROW_EVIDENCE_ASSOCIATION','CRITICAL','AGENT_6_FITMENT_PART_NUMBER',r['record_id'],r['oem_part_number_source'],'displayed PN present in exact row snippet',r['source_row_key']))
  if ic['images']!=len(obs) or len(obs)!=l['expected_image_count']:local.append(fail('INDEPENDENT_IMAGE_ENUMERATION','MAJOR','AGENT_4_IMAGE_ACQUISITION',scope,{'independent':ic['images'],'observations':len(obs),'stored_expected':l['expected_image_count']},'all visible content image occurrences captured',s['raw_path']))
  for o in obs:
   m=re.fullmatch(r'markdown:char:(\d+)-(\d+)',o['source_locator']);frag=text[int(m.group(1)):int(m.group(2))] if m else ''
   if o['source_page_sha256']!=s['byte_sha256'] or o['image_source_url'] not in frag:local.append(fail('ROW_EVIDENCE_ASSOCIATION','CRITICAL','AGENT_5_IMAGE_INTEGRITY',o['image_observation_id'],'image locator/page mismatch','exact source wrapper contains URL and page hash',o['source_locator']))
  if l['leaf_type']=='CATEGORY_INDEX':
   children=c.execute("select count(*) from catalogue_leaves where parent_leaf_id=? and status!='RETIRED_SOURCE'",(scope,)).fetchone()[0]
   if children!=ic['selectors']:local.append(fail('SELECTOR_CHILD_RECONCILIATION','CRITICAL','AGENT_2_TAXONOMY',scope,children,ic['selectors'],s['raw_path']))
  fails.extend(local)
  if not local:passed.append(scope)
 products=c.execute('select * from product_sources').fetchall()
 for p in products:
  if p['status'] not in ('EXTRACTED_COMPLETE','SOURCE_VERIFIED','IMAGE_VERIFIED','INTEGRITY_CHECKED','QA_PASSED') or not complete_product_structure_status(p['structure_status']):fails.append(fail('PRODUCT_SOURCE_STRUCTURE','MAJOR','AGENT_3_PART_RECORD_EXTRACTION',p['product_source_id'],{'status':p['status'],'structure':p['structure_status']},'complete product detail source',p['source_url']))
  elif p['current_snapshot_id']:
   s,text,err=snapshot_text(c,p['current_snapshot_id']);
   if err:fails.append(fail('SNAPSHOT_INTEGRITY','CRITICAL','AGENT_8_REPOSITORY_INTEGRITY',p['product_source_id'],err,'literal hash-valid snapshot',p['source_url']))
 if not fails:
  c.execute("update catalogue_leaves set status='SOURCE_VERIFIED' where status='EXTRACTED'");c.execute("update product_sources set status='SOURCE_VERIFIED' where status='EXTRACTED_COMPLETE'");c.execute("update part_records set source_verification_status='SOURCE_VERIFIED'");c.execute("update batches set status='SOURCE_VERIFIED' where status='EXTRACTED'");c.commit()
 c.close();persist('source',run,fails,executed);print(json.dumps({'run_id':run,'status':'PASS' if not fails else 'FAIL','failures':fails},indent=2));return not fails
def decode_asset(path):
 b=path.read_bytes();im=Image.open(io.BytesIO(b));im.load();rgba=im.convert('RGBA');return b,im.size,sha(rgba.tobytes())
def record_has_terminal_no_image(c,record_id):
 return c.execute("""select count(*) from record_product_sources x join product_sources p on p.product_source_id=x.product_source_id where x.record_id=? and p.status in ('SOURCE_VERIFIED','IMAGE_VERIFIED','INTEGRITY_CHECKED','QA_PASSED') and p.no_image_disposition='NO_OEM_IMAGE_AVAILABLE' and p.structure_status='PRODUCT_DETAIL_COMPLETE'""",(record_id,)).fetchone()[0]
def image_audit():
 run='image-audit-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');c=con();fails=[];executed={'IMAGE_BYTE_AND_PIXEL_INTEGRITY','IMAGE_ASSOCIATION','PLACEHOLDER_REJECTION','RECORD_IMAGE_DISPOSITION'}
 obs=c.execute('select o.*,a.* from image_observations o left join image_assets a on a.image_sha256=o.image_sha256').fetchall()
 for o in obs:
  scope=o['image_observation_id'];local=[]
  if o['acquisition_status']!='ACQUIRED' or o['verification_status'] not in ('IMAGE_VERIFIED_BYTE_EXACT','DIAGRAM_VERIFIED_BYTE_EXACT'):local.append(fail('IMAGE_BYTE_AND_PIXEL_INTEGRITY','MAJOR','AGENT_5_IMAGE_INTEGRITY',scope,{'acquisition':o['acquisition_status'],'verification':o['verification_status']},'acquired and byte-exact verified',o['image_source_url']))
  elif not o['local_image_path'] or not (CAT/o['local_image_path']).exists():local.append(fail('IMAGE_BYTE_AND_PIXEL_INTEGRITY','CRITICAL','AGENT_8_REPOSITORY_INTEGRITY',scope,'missing local file','present hash-addressed file',o['local_image_path']))
  else:
   try:b,size,pixel=decode_asset(CAT/o['local_image_path']);
   except Exception as e:local.append(fail('IMAGE_BYTE_AND_PIXEL_INTEGRITY','CRITICAL','AGENT_5_IMAGE_INTEGRITY',scope,repr(e),'decodable asset',o['local_image_path']))
   else:
    if sha(b)!=o['image_sha256'] or len(b)!=o['image_byte_size'] or list(size)!=[o['image_width'],o['image_height']] or pixel!=o['pixel_sha256']:local.append(fail('IMAGE_BYTE_AND_PIXEL_INTEGRITY','CRITICAL','AGENT_5_IMAGE_INTEGRITY',scope,'asset metadata/hash mismatch','all exact',o['local_image_path']))
  if o['association_status'] not in ('ASSOCIATION_FROM_EXACT_SOURCE_WRAPPER','ASSOCIATION_FROM_ASSEMBLY_SELECTOR','ASSOCIATION_FROM_ACTIVE_DIAGRAM','ASSOCIATION_FROM_PRODUCT_GALLERY'):local.append(fail('IMAGE_ASSOCIATION','MAJOR','AGENT_5_IMAGE_INTEGRITY',scope,o['association_status'],'exact source occurrence association',o['source_locator']))
  if o['placeholder_classification']!='CONTENT_IMAGE':local.append(fail('PLACEHOLDER_REJECTION','MAJOR','AGENT_5_IMAGE_INTEGRITY',scope,o['placeholder_classification'],'CONTENT_IMAGE',o['local_image_path']))
  fails.extend(local)
 records=c.execute('select record_id from part_records').fetchall()
 for r in records:
  linked=c.execute('''select o.verification_status,o.association_status from image_observation_records x join image_observations o on o.image_observation_id=x.image_observation_id where x.record_id=?''',(r['record_id'],)).fetchall();noimg=record_has_terminal_no_image(c,r['record_id'])
  if not linked and not noimg:fails.append(fail('RECORD_IMAGE_DISPOSITION','MAJOR','AGENT_5_IMAGE_INTEGRITY',r['record_id'],'no verified image or source-supported no-image disposition','terminal image disposition',r['record_id']))
 if not fails:
  c.execute("update part_records set image_verification_status=case when exists(select 1 from image_observation_records x join image_observations o on o.image_observation_id=x.image_observation_id where x.record_id=part_records.record_id) then 'IMAGE_VERIFIED_BYTE_EXACT' else 'NO_OEM_IMAGE_AVAILABLE' end");c.execute("update catalogue_leaves set status='IMAGE_VERIFIED' where status='SOURCE_VERIFIED'");c.execute("update product_sources set status='IMAGE_VERIFIED' where status='SOURCE_VERIFIED'");c.execute("update batches set status='IMAGE_VERIFIED' where status='SOURCE_VERIFIED'");c.commit()
 c.close();persist('image',run,fails,executed);print(json.dumps({'run_id':run,'status':'PASS' if not fails else 'FAIL','failures':fails},indent=2));return not fails
def fitment_decision(fitment,year,make,model,label):
 f=norm(fitment);expected=norm(f'{year} {make} {model} {label}');modelkey=norm(f'{year} {make} {model}')
 if expected and expected in f:return 'FITMENT_AUDITED_PRODUCT_DETAIL'
 if f and modelkey in f:return 'FITMENT_CONFLICT'
 return 'FITMENT_AUDITED_CONFIGURED_ROUTE'
def fitment_audit():
 run='fitment-audit-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');c=con();fails=[];executed={'FITMENT_VARIATION_MAPPING'}
 rows=c.execute('''select r.record_id,r.fitment_notes_source,v.variation_source_label,ve.year,ve.make_source,ve.model_source from part_records r join variations v on v.variation_id=r.variation_id join vehicles ve on ve.vehicle_id=v.vehicle_id''').fetchall()
 for r in rows:
  state=fitment_decision(r['fitment_notes_source'],r['year'],r['make_source'],r['model_source'],r['variation_source_label'])
  if state=='FITMENT_CONFLICT':fails.append(fail('FITMENT_VARIATION_MAPPING','MAJOR','AGENT_6_FITMENT_PART_NUMBER',r['record_id'],r['fitment_notes_source'],r['variation_source_label'],r['record_id']))
  else:c.execute('update part_records set fitment_audit_status=? where record_id=?',(state,r['record_id']))
 if not fails:c.execute("update catalogue_leaves set status='FITMENT_AUDITED' where status='IMAGE_VERIFIED'");c.execute("update batches set status='FITMENT_AUDITED' where status='IMAGE_VERIFIED'");c.commit()
 c.close();persist('fitment',run,fails,executed);print(json.dumps({'run_id':run,'status':'PASS' if not fails else 'FAIL','failures':fails},indent=2));return not fails
def completeness_audit():
 run='completeness-audit-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');c=con();fails=[];executed={'VARIATION_SCOPE_RECONCILIATION','LEAF_COUNT_RECONCILIATION','PRODUCT_ASSOCIATION_RECONCILIATION','NONTERMINAL_SCOPE'}
 for v in c.execute('select * from variations'):
  n=c.execute("select count(*) from catalogue_leaves where variation_id=? and leaf_type='CATEGORY_INDEX' and status!='RETIRED_SOURCE'",(v['variation_id'],)).fetchone()[0]
  if n!=v['expected_category_count']:fails.append(fail('VARIATION_SCOPE_RECONCILIATION','CRITICAL','AGENT_7_COMPLETENESS',v['variation_id'],n,v['expected_category_count'],v['evidence_url']))
 for l in c.execute("select * from catalogue_leaves where status!='RETIRED_SOURCE'"):
  actual=c.execute('select count(*) from visible_source_rows where catalogue_leaf_id=?',(l['catalogue_leaf_id'],)).fetchone()[0];recs=c.execute('select count(*) from part_records where catalogue_leaf_id=?',(l['catalogue_leaf_id'],)).fetchone()[0];obs=c.execute('select count(*) from image_observations where catalogue_leaf_id=?',(l['catalogue_leaf_id'],)).fetchone()[0]
  if actual!=l['expected_source_row_count'] or recs!=actual or obs!=l['expected_image_count']:fails.append(fail('LEAF_COUNT_RECONCILIATION','CRITICAL','AGENT_7_COMPLETENESS',l['catalogue_leaf_id'],{'rows':actual,'records':recs,'images':obs},{'rows':l['expected_source_row_count'],'records':l['expected_source_row_count'],'images':l['expected_image_count']},l['source_url']))
 missing=c.execute("select count(*) from part_records r left join record_product_sources x on x.record_id=r.record_id where r.part_detail_url like '%/oem-parts/%' and x.record_id is null").fetchone()[0]
 if missing:fails.append(fail('PRODUCT_ASSOCIATION_RECONCILIATION','MAJOR','AGENT_7_COMPLETENESS','project',missing,0,'part_records'))
 nonterminal=c.execute("select count(*) from catalogue_leaves where status not in ('FITMENT_AUDITED','COMPLETENESS_CHECKED','INTEGRITY_CHECKED','QA_PASSED','BLOCKED_EXTERNAL','RETIRED_SOURCE')").fetchone()[0]+c.execute("select count(*) from product_sources where status not in ('IMAGE_VERIFIED','INTEGRITY_CHECKED','QA_PASSED','BLOCKED_EXTERNAL')").fetchone()[0]
 if nonterminal:fails.append(fail('NONTERMINAL_SCOPE','CRITICAL','AGENT_7_COMPLETENESS','project',nonterminal,0,'catalogue_leaves/product_sources'))
 if not fails:c.execute("update part_records set completeness_status='COMPLETENESS_CHECKED'");c.execute("update catalogue_leaves set status='COMPLETENESS_CHECKED' where status='FITMENT_AUDITED'");c.execute("update batches set status='COMPLETENESS_CHECKED' where status='FITMENT_AUDITED'");c.commit()
 c.close();persist('completeness',run,fails,executed);print(json.dumps({'run_id':run,'status':'PASS' if not fails else 'FAIL','failures':fails},indent=2));return not fails
def integrity_audit():
 run='integrity-audit-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');c=con();fails=[];executed={'SQLITE_INTEGRITY','REFERENTIAL_INTEGRITY','CONTEXT_INTEGRITY','PATH_INTEGRITY','FTS_RECONCILIATION','GIT_LFS_INTEGRITY'}
 if c.execute('pragma integrity_check').fetchone()[0]!='ok':fails.append(fail('SQLITE_INTEGRITY','CRITICAL','AGENT_8_REPOSITORY_INTEGRITY','database','failed','ok',str(DB)))
 fk=c.execute('pragma foreign_key_check').fetchall()
 if fk:fails.append(fail('REFERENTIAL_INTEGRITY','CRITICAL','AGENT_8_REPOSITORY_INTEGRITY','database',len(fk),0,[tuple(x) for x in fk[:20]]))
 cross=c.execute('''select count(*) from part_records r join catalogue_leaves l on l.catalogue_leaf_id=r.catalogue_leaf_id where r.variation_id!=l.variation_id or r.category_id!=l.category_id or r.subcategory_id!=l.subcategory_id''').fetchone()[0]
 if cross:fails.append(fail('CONTEXT_INTEGRITY','CRITICAL','AGENT_8_REPOSITORY_INTEGRITY','database',cross,0,'cross-context query'))
 badpaths=[]
 for r in c.execute('select local_image_path,image_sha256 from image_assets'):
  p=CAT/r['local_image_path'];
  if not p.exists() or sha(p.read_bytes())!=r['image_sha256']:badpaths.append(r['local_image_path'])
 for r in c.execute('select raw_path,byte_sha256 from source_snapshots'):
  p=CAT/r['raw_path'];
  if not p.exists() or sha(p.read_bytes())!=r['byte_sha256']:badpaths.append(r['raw_path'])
 if badpaths:fails.append(fail('PATH_INTEGRITY','CRITICAL','AGENT_8_REPOSITORY_INTEGRITY','repository',len(badpaths),0,badpaths[:50]))
 recs=c.execute('select count(*) from part_records').fetchone()[0];fts=c.execute('select count(*) from catalogue_fts').fetchone()[0]
 if recs!=fts:fails.append(fail('FTS_RECONCILIATION','MAJOR','AGENT_8_REPOSITORY_INTEGRITY','database',fts,recs,'catalogue_fts'))
 lfs=subprocess.run(['git','lfs','fsck'],cwd=ROOT,text=True,capture_output=True)
 if lfs.returncode:fails.append(fail('GIT_LFS_INTEGRITY','CRITICAL','AGENT_8_REPOSITORY_INTEGRITY','repository',lfs.stdout+lfs.stderr,'git lfs fsck exit 0','.gitattributes'))
 if not fails:c.execute("update part_records set repository_integrity_status='INTEGRITY_CHECKED'");c.execute("update catalogue_leaves set status='INTEGRITY_CHECKED' where status='COMPLETENESS_CHECKED'");c.execute("update product_sources set status='INTEGRITY_CHECKED' where status='IMAGE_VERIFIED'");c.execute("update batches set status='INTEGRITY_CHECKED' where status='COMPLETENESS_CHECKED'");c.commit()
 c.close();persist('integrity',run,fails,executed);print(json.dumps({'run_id':run,'status':'PASS' if not fails else 'FAIL','failures':fails},indent=2));return not fails
def main():
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['source','image','fitment','completeness','integrity','all']);a=p.parse_args();stages=[source_audit,image_audit,fitment_audit,completeness_audit,integrity_audit] if a.stage=='all' else [globals()[a.stage+'_audit']];ok=True
 for f in stages:
  if not f():ok=False;break
 raise SystemExit(0 if ok else 1)
if __name__=='__main__':main()
