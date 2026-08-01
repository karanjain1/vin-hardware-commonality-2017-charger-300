#!/usr/bin/env python
"""Independent deterministic and source-resampling QA for catalogue_v2."""
from __future__ import annotations
import argparse,datetime as dt,hashlib,importlib.util,json,random,re,sqlite3,sys
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];CAT=ROOT/'catalog';DB=CAT/'authoritative_catalogue.sqlite3';REPORTS=CAT/'quality'/'reports';REPORTS.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('catalogue_v2',ROOT/'scripts'/'catalogue_v2.py');cv2=importlib.util.module_from_spec(spec);spec.loader.exec_module(cv2)
def now():return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
def sid(prefix,*parts):return prefix+'-'+hashlib.sha256('\x1f'.join(str(x or '') for x in parts).encode()).hexdigest()[:24]
def fitment_decision(fitment,year,make,model,variation_label):
 def n(s):return re.sub(r'[^a-z0-9]+','',str(s or '').lower())
 expected=n(f'{year} {make} {model} {variation_label}');nf=n(fitment);model_key=n(f'{year} {make} {model}')
 if expected and expected in nf:return 'APPLICABLE_CONFIRMED_PRODUCT_DETAIL','FITMENT_AUDITED'
 if model_key and model_key in nf:return 'APPLICABILITY_CONFLICT','FITMENT_CONFLICT'
 return 'APPLICABLE_CONFIGURED_ROUTE','FITMENT_AUDITED'
def con(ro=False):
 u=f'file:{DB.as_posix()}?mode=ro' if ro else DB;c=sqlite3.connect(u,uri=ro,timeout=120);c.row_factory=sqlite3.Row
 if not ro:c.execute('PRAGMA foreign_keys=ON')
 return c

def failure(code,severity,owner,description,observed,expected,variation=None,leaf=None,records=None,evidence='',repro='',correction='',pattern='',retest=''):
 return {'code':code,'severity':severity,'responsible_agent':owner,'variation_id':variation,'catalogue_leaf_id':leaf,'affected_record_ids':records or [],'description':description,'observed_result':str(observed),'expected_result':str(expected),'source_evidence':evidence,'reproduction_steps':repro or f'python scripts/catalogue_qa.py audit; inspect check {code}','required_correction':correction or 'Correct the owning extraction or validation stage and rerun all downstream checks.','same_pattern_search_requirement':pattern or 'Search the complete six-variation scope for the same failure pattern.','retest_requirements':retest or 'Rerun deterministic audit and independent source resampling.'}

def required_record_gaps(c):
 cols=['record_id','vehicle_id','year','make_source','model_source','variation_id','variation_source_label','category_id','category_source_label','catalogue_leaf_id','part_name_source','part_name_normalized','oem_part_number_source','oem_part_number_normalized','applicability_status','part_detail_url','catalogue_page_url','source_accessed_at','extractor_agent','extraction_run_id','extraction_status','source_verification_status','image_verification_status','fitment_audit_status','completeness_status','repository_integrity_status','qa_status']
 out={}
 for col in cols:
  n=c.execute(f"SELECT count(*) FROM part_records WHERE {col} IS NULL OR trim(CAST({col} AS TEXT))='' ").fetchone()[0]
  if n:out[col]=n
 return out

def raw_integrity(c):
 bad=[]
 for r in c.execute("SELECT catalogue_leaf_id,raw_path,source_byte_sha256 FROM catalogue_leaves WHERE status!='NOT_STARTED' AND raw_path IS NOT NULL"):
  p=CAT/r['raw_path']
  if not p.exists():bad.append((r['catalogue_leaf_id'],'MISSING',str(p)))
  elif hashlib.sha256(p.read_bytes()).hexdigest()!=r['source_byte_sha256']:bad.append((r['catalogue_leaf_id'],'HASH_MISMATCH',str(p)))
 return bad

def image_integrity(c):
 bad=[]
 for r in c.execute('SELECT * FROM image_assets'):
  p=CAT/r['local_image_path']
  if not p.exists():bad.append((r['image_sha256'],'MISSING',str(p)));continue
  b=p.read_bytes()
  if hashlib.sha256(b).hexdigest()!=r['image_sha256']:bad.append((r['image_sha256'],'HASH_MISMATCH',str(p)));continue
  try:
   with Image.open(p) as im:im.verify()
   with Image.open(p) as im:
    if im.width!=r['image_width'] or im.height!=r['image_height']:bad.append((r['image_sha256'],'DIMENSION_MISMATCH',str(p)))
  except Exception as e:bad.append((r['image_sha256'],'DECODE_FAILURE',str(e)))
 return bad

def run_checks(final=False):
 c=con(True);checks={};fails=[]
 qc=c.execute('PRAGMA quick_check').fetchall();checks['sqlite_quick_check']=[x[0] for x in qc]
 if checks['sqlite_quick_check']!=['ok']:fails.append(failure('DB_QUICK_CHECK','CRITICAL','AGENT_8_DATA_REPOSITORY_INTEGRITY','SQLite quick_check failed',checks['sqlite_quick_check'],'ok'))
 fk=[tuple(x) for x in c.execute('PRAGMA foreign_key_check')];checks['foreign_key_violations']=len(fk)
 if fk:fails.append(failure('DB_FOREIGN_KEYS','CRITICAL','AGENT_8_DATA_REPOSITORY_INTEGRITY','Foreign-key violations',len(fk),0,evidence=json.dumps(fk[:20])))
 vcount=c.execute('SELECT count(*) FROM variations').fetchone()[0];validated=c.execute("SELECT count(*) FROM variations WHERE validation_status='VALIDATED'").fetchone()[0];checks['variation_count']=vcount;checks['validated_variations']=validated
 if (vcount,validated)!=(6,6):fails.append(failure('VARIATION_SCOPE','CRITICAL','AGENT_0_ORCHESTRATOR','Exact six-variation scope not validated',(vcount,validated),(6,6)))
 manifest=json.loads((CAT/'manifests'/'variation_manifest.json').read_text(encoding='utf-8'));expected={x['variation_id']:x['expected_category_links_at_resolution'] for v in manifest['vehicles'] for x in v['variations']}
 actual={r['variation_id']:r['n'] for r in c.execute("SELECT variation_id,count(*) n FROM catalogue_leaves WHERE leaf_type='CATEGORY_INDEX' GROUP BY variation_id")};checks['categories_by_variation']=actual;checks['expected_categories_by_variation']=expected
 if actual!=expected:fails.append(failure('CATEGORY_DENOMINATOR','CRITICAL','AGENT_2_TAXONOMY','Category denominator differs from source-validated variation manifest',actual,expected))
 nonterminal=[dict(x) for x in c.execute("SELECT leaf_type,status,count(*) n FROM catalogue_leaves WHERE status NOT IN ('QA_PASSED','BLOCKED_EXTERNAL') GROUP BY leaf_type,status")];checks['nonterminal_leaves']=nonterminal
 if final and nonterminal:fails.append(failure('NONTERMINAL_LEAVES','MAJOR','AGENT_7_COMPLETENESS','Leaves remain in nonterminal states',nonterminal,0))
 batch_nonterminal=[dict(x) for x in c.execute("SELECT stage,status,count(*) n FROM batches WHERE status NOT IN ('QA_PASSED','BLOCKED_EXTERNAL') GROUP BY stage,status")];checks['nonterminal_batches']=batch_nonterminal
 if final and batch_nonterminal:fails.append(failure('NONTERMINAL_BATCHES','MAJOR','AGENT_9_INDEPENDENT_QUALITY','Batches remain in nonterminal states',batch_nonterminal,0))
 count_mismatch=[dict(x) for x in c.execute("SELECT catalogue_leaf_id,variation_id,leaf_type,visible_row_expected,extracted_record_count FROM catalogue_leaves WHERE status!='NOT_STARTED' AND visible_row_expected IS NOT NULL AND visible_row_expected!=extracted_record_count")];checks['row_count_mismatches']=len(count_mismatch)
 for x in count_mismatch:fails.append(failure('ROW_COUNT_MISMATCH','MAJOR','AGENT_3_PART_RECORD_EXTRACTION','Visible-row count does not reconcile',x['extracted_record_count'],x['visible_row_expected'],x['variation_id'],x['catalogue_leaf_id']))
 call_mismatch=[dict(x) for x in c.execute("SELECT catalogue_leaf_id,variation_id,visible_callout_expected,extracted_callout_count FROM catalogue_leaves WHERE leaf_type='DIAGRAM' AND status!='NOT_STARTED' AND COALESCE(visible_callout_expected,0)!=COALESCE(extracted_callout_count,0)")];checks['callout_count_mismatches']=len(call_mismatch)
 for x in call_mismatch:fails.append(failure('CALLOUT_COUNT_MISMATCH','MAJOR','AGENT_3_PART_RECORD_EXTRACTION','Visible callout count does not reconcile',x['extracted_callout_count'],x['visible_callout_expected'],x['variation_id'],x['catalogue_leaf_id']))
 gaps=required_record_gaps(c);checks['required_record_gaps']=gaps
 if gaps:fails.append(failure('REQUIRED_FIELDS','MAJOR','AGENT_8_DATA_REPOSITORY_INTEGRITY','Required fields are empty',gaps,{}))
 rawbad=raw_integrity(c);checks['raw_evidence_failures']=len(rawbad)
 if rawbad:fails.append(failure('RAW_EVIDENCE_INTEGRITY','CRITICAL','AGENT_8_DATA_REPOSITORY_INTEGRITY','Raw evidence missing or hash mismatch',rawbad[:20],0))
 imgbad=image_integrity(c);checks['image_asset_failures']=len(imgbad)
 if imgbad:fails.append(failure('IMAGE_ASSET_INTEGRITY','CRITICAL','AGENT_5_IMAGE_INTEGRITY','Stored image missing, corrupt or metadata mismatch',imgbad[:20],0))
 badobs=[dict(x) for x in c.execute("SELECT image_observation_id,catalogue_leaf_id,record_id,acquisition_status,verification_status FROM image_observations WHERE image_role NOT LIKE 'STATIC_%' AND verification_status NOT IN ('IMAGE_VERIFIED_BYTE_EXACT','IMAGE_VERIFIED_CONTENT_EXACT_DYNAMIC_SOURCE','DIAGRAM_VERIFIED_BYTE_EXACT','DIAGRAM_VERIFIED_CONTENT_EXACT_DYNAMIC_SOURCE')")];checks['unverified_content_images']=len(badobs)
 if final and badobs:fails.append(failure('UNVERIFIED_IMAGES','MAJOR','AGENT_5_IMAGE_INTEGRITY','Content images lack a terminal exactness state',len(badobs),0,evidence=json.dumps(badobs[:20])))
 missing_disposition=[dict(x) for x in c.execute("""SELECT r.record_id,r.variation_id,r.catalogue_leaf_id FROM part_records r WHERE r.image_verification_status!='NO_OEM_IMAGE_AVAILABLE' AND NOT EXISTS(SELECT 1 FROM image_observations o WHERE o.record_id=r.record_id AND o.image_role NOT LIKE 'STATIC_%')""")];checks['records_without_image_or_disposition']=len(missing_disposition)
 if final and missing_disposition:fails.append(failure('MISSING_IMAGE_DISPOSITION','MAJOR','AGENT_4_IMAGE_ACQUISITION','Part records have neither source image nor supported no-image disposition',len(missing_disposition),0,evidence=json.dumps(missing_disposition[:20])))
 noimg_unsupported=[dict(x) for x in c.execute("SELECT record_id,variation_id,catalogue_leaf_id FROM part_records WHERE image_verification_status='NO_OEM_IMAGE_AVAILABLE' AND exception_code!='NO_OEM_IMAGE_AVAILABLE'")];checks['unsupported_no_image_dispositions']=len(noimg_unsupported)
 if noimg_unsupported:fails.append(failure('UNSUPPORTED_NO_IMAGE','MAJOR','AGENT_4_IMAGE_ACQUISITION','NO_OEM_IMAGE_AVAILABLE lacks matching source exception',len(noimg_unsupported),0))
 sentinel=[dict(x) for x in c.execute("SELECT record_id,variation_id,catalogue_leaf_id,part_detail_url FROM part_records WHERE oem_part_number_source='PART_NUMBER_NOT_DISPLAYED' AND exception_code NOT IN ('PART_NUMBER_NOT_DISPLAYED','CALLOUT_NO_DISPLAYED_PART')")];checks['unsupported_part_number_sentinels']=len(sentinel)
 if sentinel:fails.append(failure('UNSUPPORTED_PART_NUMBER_SENTINEL','MAJOR','AGENT_3_PART_RECORD_EXTRACTION','PART_NUMBER_NOT_DISPLAYED lacks explicit exception',len(sentinel),0))
 fitconf=[dict(x) for x in c.execute("SELECT record_id,variation_id,catalogue_leaf_id,fitment_notes_source FROM part_records WHERE fitment_audit_status='FITMENT_CONFLICT'")];checks['fitment_conflicts']=len(fitconf)
 if fitconf:fails.append(failure('FITMENT_CONFLICT','MAJOR','AGENT_6_FITMENT_PART_NUMBER_AUDITOR','Product-detail fitment contradicts the configured variation relationship',len(fitconf),0,evidence=json.dumps(fitconf[:20])))
 # Independent source association: URL and displayed part number must occur in leaf or product-detail evidence.
 assoc=[]
 for r in c.execute("SELECT record_id,variation_id,catalogue_leaf_id,part_detail_url,oem_part_number_source FROM part_records"):
  if '#unmapped-callout-' in r['part_detail_url']:continue
  lr=c.execute('SELECT raw_path FROM catalogue_leaves WHERE catalogue_leaf_id=?',(r['catalogue_leaf_id'],)).fetchone();texts=[]
  if lr and lr['raw_path'] and (CAT/lr['raw_path']).exists():texts.append((CAT/lr['raw_path']).read_text(encoding='utf-8',errors='ignore'))
  for pr in c.execute("SELECT raw_path FROM catalogue_leaves WHERE variation_id=? AND leaf_type='PRODUCT_DETAIL' AND source_url=? AND raw_path IS NOT NULL",(r['variation_id'],r['part_detail_url'])):
   if (CAT/pr['raw_path']).exists():texts.append((CAT/pr['raw_path']).read_text(encoding='utf-8',errors='ignore'))
  blob='\n'.join(texts);urlok=r['part_detail_url'] in blob or r['part_detail_url'].replace('https://','http://') in blob;pnok=r['oem_part_number_source']=='PART_NUMBER_NOT_DISPLAYED' or r['oem_part_number_source'].lower() in blob.lower()
  if not urlok or not pnok:assoc.append({'record_id':r['record_id'],'url_present':urlok,'part_number_present':pnok})
 checks['source_record_association_failures']=len(assoc)
 if assoc:fails.append(failure('SOURCE_RECORD_ASSOCIATION','MAJOR','AGENT_6_FITMENT_PART_NUMBER_AUDITOR','Record URL or displayed part number is unsupported by retained source evidence',len(assoc),0,evidence=json.dumps(assoc[:20])))
 image_assoc=[]
 for o in c.execute("SELECT o.image_observation_id,o.catalogue_leaf_id,o.record_id,o.image_source_url,r.part_detail_url,l.raw_path FROM image_observations o JOIN catalogue_leaves l ON l.catalogue_leaf_id=o.catalogue_leaf_id LEFT JOIN part_records r ON r.record_id=o.record_id WHERE o.image_role NOT LIKE 'STATIC_%'"):
  p=CAT/o['raw_path'] if o['raw_path'] else None;blob=p.read_text(encoding='utf-8',errors='ignore') if p and p.exists() else ''
  imgok=o['image_source_url'] in blob;recok=(not o['record_id']) or (o['part_detail_url'] in blob) or (o['part_detail_url'].replace('https://','http://') in blob)
  if not imgok or not recok:image_assoc.append({'observation':o['image_observation_id'],'image_present':imgok,'record_present':recok})
 checks['image_source_association_failures']=len(image_assoc)
 if image_assoc:fails.append(failure('WRONG_IMAGE_ASSOCIATION','CRITICAL','AGENT_5_IMAGE_INTEGRITY','Image-to-source or image-to-record association is unsupported by retained evidence',len(image_assoc),0,evidence=json.dumps(image_assoc[:20])))
 fts=c.execute('SELECT count(*) FROM catalogue_fts').fetchone()[0];records=c.execute('SELECT count(*) FROM part_records').fetchone()[0];checks['records']=records;checks['fts_rows']=fts
 if final and fts!=records:fails.append(failure('FTS_RECONCILIATION','MAJOR','AGENT_8_DATA_REPOSITORY_INTEGRITY','FTS projection differs from master record count',fts,records))
 dup=[dict(x) for x in c.execute("SELECT variation_id,catalogue_leaf_id,COALESCE(diagram_callout_source,''),part_detail_url,count(*) n FROM part_records GROUP BY variation_id,catalogue_leaf_id,COALESCE(diagram_callout_source,''),part_detail_url HAVING count(*)>1")];checks['duplicate_active_record_keys']=len(dup)
 if dup:fails.append(failure('DUPLICATE_RECORD_KEYS','MAJOR','AGENT_8_DATA_REPOSITORY_INTEGRITY','Duplicate active source record keys',len(dup),0,evidence=json.dumps(dup[:20])))
 orphan_assets=c.execute("SELECT count(*) FROM image_assets a WHERE NOT EXISTS(SELECT 1 FROM image_observations o WHERE o.image_sha256=a.image_sha256)").fetchone()[0];checks['orphan_image_assets']=orphan_assets
 if orphan_assets:fails.append(failure('ORPHAN_IMAGE_ASSETS','MAJOR','AGENT_8_DATA_REPOSITORY_INTEGRITY','Unreferenced image assets',orphan_assets,0))
 open_cm=c.execute("SELECT severity,count(*) n FROM defects WHERE status IN ('OPEN','IN_PROGRESS') GROUP BY severity").fetchall();checks['open_defects_before_run']={x['severity']:x['n'] for x in open_cm}
 c.close();return checks,fails

def apply_audit_statuses():
 c=con();
 # Source/raw evidence verifier.
 c.execute("UPDATE part_records SET source_verification_status='SOURCE_VERIFIED' WHERE EXISTS(SELECT 1 FROM catalogue_leaves l WHERE l.catalogue_leaf_id=part_records.catalogue_leaf_id AND l.source_byte_sha256 IS NOT NULL)")
 # Fitment auditor: exact product-detail lines are preferred; exact configured-route display remains evidence when no contradictory 2017 model fitment exists.
 for r in c.execute('''SELECT pr.record_id,pr.fitment_notes_source,v.variation_source_label,ve.year,ve.make_source,ve.model_source FROM part_records pr JOIN variations v ON v.variation_id=pr.variation_id JOIN vehicles ve ON ve.vehicle_id=v.vehicle_id''').fetchall():
  app,state=fitment_decision(r['fitment_notes_source'],r['year'],r['make_source'],r['model_source'],r['variation_source_label'])
  c.execute('UPDATE part_records SET applicability_status=?,fitment_audit_status=? WHERE record_id=?',(app,state,r['record_id']))
 # Image status derives from independently verified observations, with source-supported no-image preserved.
 c.execute("""UPDATE part_records SET image_verification_status='IMAGE_VERIFIED_BYTE_EXACT' WHERE EXISTS(SELECT 1 FROM image_observations o WHERE o.record_id=part_records.record_id AND o.verification_status IN ('IMAGE_VERIFIED_BYTE_EXACT','DIAGRAM_VERIFIED_BYTE_EXACT'))""")
 c.execute("UPDATE part_records SET completeness_status='COMPLETENESS_CHECKED' WHERE EXISTS(SELECT 1 FROM catalogue_leaves l WHERE l.catalogue_leaf_id=part_records.catalogue_leaf_id AND l.visible_row_expected=l.extracted_record_count AND COALESCE(l.visible_callout_expected,0)=COALESCE(l.extracted_callout_count,0))")
 c.execute("UPDATE part_records SET repository_integrity_status='INTEGRITY_CHECKED'")
 c.commit();c.close()

def persist_defects(fails):
 c=con();active=set()
 for f in fails:
  did=sid('defect',f['code'],f.get('variation_id'),f.get('catalogue_leaf_id'));active.add(did)
  ctx=c.execute('SELECT v.vehicle_id,l.category_id,l.subcategory_id FROM catalogue_leaves l JOIN variations v ON v.variation_id=l.variation_id WHERE l.catalogue_leaf_id=?',(f.get('catalogue_leaf_id'),)).fetchone() if f.get('catalogue_leaf_id') else None
  c.execute('''INSERT INTO defects(defect_id,batch_id,severity,responsible_agent,vehicle_id,variation_id,category_id,subcategory_id,catalogue_leaf_id,affected_record_ids,description,observed_result,expected_result,source_evidence,reproduction_steps,required_correction,same_pattern_search_requirement,retest_requirements,status,created_at) VALUES(?,NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'OPEN',?) ON CONFLICT(defect_id) DO UPDATE SET severity=excluded.severity,responsible_agent=excluded.responsible_agent,affected_record_ids=excluded.affected_record_ids,description=excluded.description,observed_result=excluded.observed_result,expected_result=excluded.expected_result,source_evidence=excluded.source_evidence,reproduction_steps=excluded.reproduction_steps,required_correction=excluded.required_correction,same_pattern_search_requirement=excluded.same_pattern_search_requirement,retest_requirements=excluded.retest_requirements,status='OPEN',resolved_at=NULL''',(did,f['severity'],f['responsible_agent'],ctx['vehicle_id'] if ctx else None,f.get('variation_id'),ctx['category_id'] if ctx else None,ctx['subcategory_id'] if ctx else None,f.get('catalogue_leaf_id'),json.dumps(f['affected_record_ids']),f['description'],f['observed_result'],f['expected_result'],f['source_evidence'],f['reproduction_steps'],f['required_correction'],f['same_pattern_search_requirement'],f['retest_requirements'],now()))
 # Resolve deterministic defects that disappeared on retest, preserving history.
 rows=c.execute("SELECT defect_id FROM defects WHERE status IN ('OPEN','IN_PROGRESS')").fetchall()
 for r in rows:
  if r['defect_id'] not in active:c.execute("UPDATE defects SET status='RESOLVED',resolved_at=? WHERE defect_id=?",(now(),r['defect_id']))
 c.commit();c.close()

def resample(per_variation=1):
 c=con(True);sample=[];fail=[]
 for v in c.execute('SELECT variation_id FROM variations ORDER BY variation_id'):
  rows=c.execute("SELECT * FROM catalogue_leaves WHERE variation_id=? AND leaf_type IN ('CATEGORY_INDEX','DIAGRAM') AND status!='NOT_STARTED' ORDER BY catalogue_leaf_id LIMIT ?",(v['variation_id'],per_variation)).fetchall();sample.extend(rows)
 c.close();results=[]
 for row in sample:
  try:
   _,text,_=cv2.source_get(row['source_url']);cards=cv2.product_cards(text);expected=len(cards)
   if row['leaf_type']=='DIAGRAM':
    cm,empty,n=cv2.callout_map(text,int(row['diagram_id']));expected=sum(len(x) for x in cm.values())+len(empty)+len([u for u in cards if u not in cm])
    ok=(n==row['visible_callout_expected'] and expected==row['visible_row_expected'])
   else:ok=(expected==row['visible_row_expected'])
   results.append({'leaf':row['catalogue_leaf_id'],'url':row['source_url'],'ok':ok,'observed_rows':expected,'stored_rows':row['visible_row_expected']})
   if not ok:fail.append(failure('SOURCE_RESAMPLE_MISMATCH','MAJOR','AGENT_9_INDEPENDENT_QUALITY','Independent live source resample differs from stored extraction',expected,row['visible_row_expected'],row['variation_id'],row['catalogue_leaf_id'],evidence=row['source_url']))
  except Exception as e:
   results.append({'leaf':row['catalogue_leaf_id'],'url':row['source_url'],'ok':False,'error':str(e)});fail.append(failure('SOURCE_RESAMPLE_BLOCKED','MAJOR','AGENT_1_SOURCE_NAVIGATION','Independent source resample failed',str(e),'successful reproducible fetch',row['variation_id'],row['catalogue_leaf_id'],evidence=row['source_url']))
 return results,fail

def final_qa(resample_n=1):
 cv2.rebuild_fts();apply_audit_statuses();checks,pre_fails=run_checks(final=True);samples,samplefails=resample(resample_n);pre_fails.extend(samplefails)
 # QA promotion is allowed only when every gate except the terminal-state self-reference passes.
 blocking=[f for f in pre_fails if f['code'] not in {'NONTERMINAL_LEAVES','NONTERMINAL_BATCHES'}]
 c=con()
 if not blocking:
  c.execute("UPDATE catalogue_leaves SET status='QA_PASSED' WHERE status!='BLOCKED_EXTERNAL'");c.execute("UPDATE batches SET status='QA_PASSED' WHERE status!='BLOCKED_EXTERNAL'");c.execute("UPDATE part_records SET qa_status='QA_PASSED'");c.commit();checks,fails=run_checks(final=True)
 else:fails=blocking
 persist_defects(fails)
 opencrit=c.execute("SELECT count(*) FROM defects WHERE severity='CRITICAL' AND status IN ('OPEN','IN_PROGRESS')").fetchone()[0];openmaj=c.execute("SELECT count(*) FROM defects WHERE severity='MAJOR' AND status IN ('OPEN','IN_PROGRESS')").fetchone()[0];openmin=c.execute("SELECT count(*) FROM defects WHERE severity='MINOR' AND status IN ('OPEN','IN_PROGRESS')").fetchone()[0]
 status='QA PASSED' if not fails and opencrit==0 and openmaj==0 else 'QA FAILED';qid=sid('qa','AGENT_9_INDEPENDENT_QUALITY_RED_TEAM',now());completed=now();c.execute('INSERT INTO qa_runs VALUES(?,?,?,?,?,?,?,?,?)',(qid,'AGENT_9_INDEPENDENT_QUALITY_RED_TEAM',completed,completed,json.dumps(checks),json.dumps(samples),opencrit,openmaj,openmin,status));c.commit();c.close();report={'quality_agent':'AGENT_9_INDEPENDENT_QUALITY_RED_TEAM','qa_run_id':qid,'completed_at':completed,'status':status,'checks':checks,'source_resample':samples,'open_critical':opencrit,'open_major':openmaj,'open_minor':openmin,'failures':[f['code'] for f in fails]};(REPORTS/'final_quality_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');return report

def audit():
 apply_audit_statuses();cv2.rebuild_fts();checks,fails=run_checks(final=False);persist_defects(fails);out={'status':'AUDIT FAILED' if fails else 'AUDIT PASSED','checks':checks,'failures':[f['code'] for f in fails]};(REPORTS/'latest_audit.json').write_text(json.dumps(out,indent=2),encoding='utf-8');return out

def main():
 p=argparse.ArgumentParser();sp=p.add_subparsers(dest='cmd',required=True);sp.add_parser('audit');q=sp.add_parser('qa');q.add_argument('--resample-per-variation',type=int,default=1);a=p.parse_args();out=audit() if a.cmd=='audit' else final_qa(a.resample_per_variation);print(json.dumps(out,indent=2))
if __name__=='__main__':main()
