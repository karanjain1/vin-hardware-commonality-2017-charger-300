#!/usr/bin/env python
"""Agent 9 independent, fail-closed final quality gate.

This module never repairs extraction, rebuilds FTS, changes audit statuses, or
marks defects resolved without rerunning the exact automated check. Only a fully
passing run may promote already-INTEGRITY_CHECKED rows to QA_PASSED.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,io,json,re,sqlite3,subprocess,time
from collections import Counter
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1];CAT=ROOT/'catalog';DB=CAT/'authoritative_catalogue.sqlite3';OUT=CAT/'quality'/'reports'
def now():return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
def sha(b):return hashlib.sha256(b).hexdigest()
def sid(prefix,*parts):return prefix+'-'+hashlib.sha256('\x1f'.join(str(x or '') for x in parts).encode()).hexdigest()[:24]
def con(ro=False):
 c=sqlite3.connect(f'file:{DB.as_posix()}?mode=ro' if ro else DB,uri=ro,timeout=120);c.row_factory=sqlite3.Row
 if not ro:c.execute('pragma foreign_keys=on');c.execute('pragma busy_timeout=120000')
 return c
def failure(code,severity,agent,scope,observed,expected,evidence):return {'check_code':code,'severity':severity,'responsible_agent':agent,'scope':scope,'observed':observed,'expected':expected,'evidence':evidence}
def independent_counts(text):
 header=re.search(r'\n\s*No\.\s*\n\s*\n\s*Part\s*#\s*/\s*Description\s*/\s*Price',text,re.I);table=text[header.end():] if header else '';detailed=len(re.findall(r'\[!\[Image\s+\d+:[^\]]*\]\([^)]*\)\]\(https://www\.moparamerica\.com/oem-parts/',table));cut=header.start() if header else len(text);pre=text[:cut];heads=list(re.finditer(r'(?m)^Diagram\s+(\d+):\s*[^\n]+?\s+\d+\s*$',pre));active=heads[-1] if heads else None;body=pre[active.end():] if active else '';marks=list(re.finditer(r'(?m)^\[[^\]]+\]\(https://www\.moparamerica\.com/#part_row_[^)]+\)',body));callrows=0
 for i,m in enumerate(marks):callrows+=max(1,len(re.findall(r'https://www\.moparamerica\.com/oem-parts/[^)\s"]+',body[m.start():(marks[i+1].start() if i+1<len(marks) else len(body))])))
 selectors=len(set(re.findall(r'https://www\.moparamerica\.com/[^)\s"]+\?assembly=\d+',text)));active_img=1 if active and re.search(r'!\[Image\s+\d+:[^\]]*\]\(https?://[^)\s]+\)',body) else 0
 return {'rows':detailed+callrows,'callouts':len(marks),'images':detailed+selectors+active_img,'selectors':selectors,'active_assembly':int(active.group(1)) if active else None}
def read_snapshot(c,snapshot):
 r=c.execute('select * from source_snapshots where snapshot_id=?',(snapshot,)).fetchone();p=CAT/r['raw_path'] if r else None
 if not r or not p.exists():return None,None
 b=p.read_bytes();return r,b.decode('utf-8',errors='replace') if sha(b)==r['byte_sha256'] else None
def deterministic_checks():
 c=con(True);fails=[];executed=set()
 def check(code,severity,agent,scope,observed,expected,evidence=''):
  executed.add(code)
  if observed!=expected:fails.append(failure(code,severity,agent,scope,observed,expected,evidence))
 check('SCHEMA_VERSION','CRITICAL','AGENT_8_REPOSITORY_INTEGRITY','database',c.execute("select value from project_meta where key='schema_version'").fetchone()[0],'3',str(DB));check('SQLITE_INTEGRITY','CRITICAL','AGENT_8_REPOSITORY_INTEGRITY','database',c.execute('pragma integrity_check').fetchone()[0],'ok',str(DB));check('FOREIGN_KEYS','CRITICAL','AGENT_8_REPOSITORY_INTEGRITY','database',len(c.execute('pragma foreign_key_check').fetchall()),0,str(DB))
 vehicles={r['vehicle_id']:r['n'] for r in c.execute('select vehicle_id,count(*) n from variations group by vehicle_id')};check('EXACT_SIX_VARIATIONS','CRITICAL','AGENT_2_TAXONOMY','project',vehicles,{'2017-chrysler-300c':3,'2017-dodge-challenger':3},'variation_manifest.json')
 for v in c.execute('select * from variations'):
  n=c.execute("select count(*) from catalogue_leaves where variation_id=? and leaf_type='CATEGORY_INDEX' and status!='RETIRED_SOURCE'",(v['variation_id'],)).fetchone()[0];check('CATEGORY_DENOMINATOR','CRITICAL','AGENT_7_COMPLETENESS',v['variation_id'],n,v['expected_category_count'],v['evidence_url'])
 leaves=c.execute("select * from catalogue_leaves where status!='RETIRED_SOURCE'").fetchall();check('LEAF_TERMINAL_STATE','CRITICAL','AGENT_7_COMPLETENESS','project',Counter(r['status'] for r in leaves),Counter({'INTEGRITY_CHECKED':len(leaves)}),'catalogue_leaves')
 products=c.execute('select * from product_sources').fetchall();check('PRODUCT_TERMINAL_STATE','CRITICAL','AGENT_7_COMPLETENESS','project',Counter(r['status'] for r in products),Counter({'INTEGRITY_CHECKED':len(products)}),'product_sources')
 batches=c.execute('select * from batches').fetchall();check('BATCH_TERMINAL_STATE','CRITICAL','AGENT_0_ORCHESTRATOR','project',Counter(r['status'] for r in batches),Counter({'INTEGRITY_CHECKED':len(batches)}),'batches')
 for l in leaves:
  rows=c.execute('select count(*) from visible_source_rows where catalogue_leaf_id=?',(l['catalogue_leaf_id'],)).fetchone()[0];recs=c.execute('select count(*) from part_records where catalogue_leaf_id=?',(l['catalogue_leaf_id'],)).fetchone()[0];obs=c.execute('select count(*) from image_observations where catalogue_leaf_id=?',(l['catalogue_leaf_id'],)).fetchone()[0];s,text=read_snapshot(c,l['current_snapshot_id']);ind=independent_counts(text) if text else None
  expected={'rows':l['expected_source_row_count'],'records':l['expected_source_row_count'],'images':l['expected_image_count'],'independent_rows':l['expected_source_row_count'],'independent_images':l['expected_image_count'],'independent_callouts':l['expected_callout_count']};observed={'rows':rows,'records':recs,'images':obs,'independent_rows':ind['rows'] if ind else None,'independent_images':ind['images'] if ind else None,'independent_callouts':ind['callouts'] if ind else None};check('LEAF_RECONCILIATION','CRITICAL','AGENT_7_COMPLETENESS',l['catalogue_leaf_id'],observed,expected,l['source_url'])
  if l['leaf_type']=='CATEGORY_INDEX':children=c.execute("select count(*) from catalogue_leaves where parent_leaf_id=? and status!='RETIRED_SOURCE'",(l['catalogue_leaf_id'],)).fetchone()[0];check('DIAGRAM_SELECTOR_RECONCILIATION','CRITICAL','AGENT_2_TAXONOMY',l['catalogue_leaf_id'],children,ind['selectors'] if ind else None,l['source_url'])
 records=c.execute('select * from part_records').fetchall();check('ROW_RECORD_BIJECTION','CRITICAL','AGENT_3_PART_RECORD_EXTRACTION','project',len(records),c.execute('select count(*) from visible_source_rows').fetchone()[0],'source_row_key UNIQUE')
 states=Counter((r['source_verification_status'],r['image_verification_status'],r['fitment_audit_status'],r['completeness_status'],r['repository_integrity_status']) for r in records);allowed=all(a=='SOURCE_VERIFIED' and b in ('IMAGE_VERIFIED_BYTE_EXACT','NO_OEM_IMAGE_AVAILABLE') and d=='COMPLETENESS_CHECKED' and e=='INTEGRITY_CHECKED' and str(f).startswith('FITMENT_AUDITED') for (a,b,f,d,e) in states);check('RECORD_AUDIT_STATES','CRITICAL','AGENT_9_INDEPENDENT_QUALITY','project',allowed,True,{str(k):v for k,v in states.items()})
 badimg=c.execute("""select count(*) from image_observations o left join image_assets a on a.image_sha256=o.image_sha256 where o.acquisition_status!='ACQUIRED' or o.verification_status not in ('IMAGE_VERIFIED_BYTE_EXACT','DIAGRAM_VERIFIED_BYTE_EXACT') or o.association_status not in ('ASSOCIATION_FROM_EXACT_SOURCE_WRAPPER','ASSOCIATION_FROM_ASSEMBLY_SELECTOR','ASSOCIATION_FROM_ACTIVE_DIAGRAM','ASSOCIATION_FROM_PRODUCT_GALLERY') or a.placeholder_classification!='CONTENT_IMAGE'""").fetchone()[0];check('IMAGE_TERMINAL_STATE','CRITICAL','AGENT_5_IMAGE_INTEGRITY','project',badimg,0,'image_observations/image_assets')
 orphan_assets=c.execute('select count(*) from image_assets a left join image_observations o on o.image_sha256=a.image_sha256 where o.image_sha256 is null').fetchone()[0];check('ORPHAN_IMAGE_ASSETS','MAJOR','AGENT_8_REPOSITORY_INTEGRITY','project',orphan_assets,0,'image_assets')
 check('FTS_RECONCILIATION','MAJOR','AGENT_8_REPOSITORY_INTEGRITY','database',c.execute('select count(*) from catalogue_fts').fetchone()[0],len(records),'catalogue_fts')
 unresolved=c.execute("select count(*) from defects where severity in ('CRITICAL','MAJOR') and status!='RESOLVED'").fetchone()[0];check('UNRESOLVED_DEFECTS','CRITICAL','AGENT_9_INDEPENDENT_QUALITY','project',unresolved,0,'defects')
 # Exact export-byte reproduction.
 specs={'part_records.csv':'SELECT * FROM part_records ORDER BY variation_id,catalogue_leaf_id,source_section,source_row_anchor,source_occurrence_ordinal','visible_source_rows.csv':'SELECT * FROM visible_source_rows ORDER BY catalogue_leaf_id,source_section,source_row_anchor,source_occurrence_ordinal','product_sources.csv':'SELECT * FROM product_sources ORDER BY product_source_id','defects.csv':'SELECT * FROM defects ORDER BY created_at,defect_id'}
 for fn,q in specs.items():
  rows=c.execute(q);cols=[d[0] for d in rows.description];buf=io.StringIO(newline='');w=csv.writer(buf);w.writerow(cols);w.writerows(rows);p=CAT/'v2'/'exports'/fn;expected_bytes=buf.getvalue().encode();actual_bytes=p.read_bytes() if p.exists() else None;check('DERIVED_EXPORT_REPRODUCIBILITY','MAJOR','AGENT_8_REPOSITORY_INTEGRITY',fn,{'exists':actual_bytes is not None,'sha256':sha(actual_bytes) if actual_bytes is not None else None,'bytes':len(actual_bytes) if actual_bytes is not None else None},{'exists':True,'sha256':sha(expected_bytes),'bytes':len(expected_bytes)},q)
 c.close()
 # Git/LFS and clean extraction checkpoint are checked before QA writes anything.
 clean=subprocess.run(['git','status','--porcelain'],cwd=ROOT,text=True,capture_output=True);check('GIT_CLEAN_CHECKPOINT','CRITICAL','AGENT_8_REPOSITORY_INTEGRITY','repository',clean.stdout,'','git status --porcelain')
 lfs=subprocess.run(['git','lfs','fsck'],cwd=ROOT,text=True,capture_output=True);check('GIT_LFS_FSCK','CRITICAL','AGENT_8_REPOSITORY_INTEGRITY','repository',lfs.returncode,0,lfs.stdout+lfs.stderr)
 local=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,capture_output=True).stdout.strip();remote=subprocess.run(['git','rev-parse','@{u}'],cwd=ROOT,text=True,capture_output=True).stdout.strip();check('REMOTE_CHECKPOINT_PARITY','CRITICAL','AGENT_8_REPOSITORY_INTEGRITY','repository',local,remote,'git rev-parse HEAD/@{u}')
 return fails,executed,{'leaf_count':len(leaves),'product_source_count':len(products),'record_count':len(records),'image_observation_count':c and None,'git_commit':local}
def fetch(url):
 r=requests.get('https://r.jina.ai/https://'+url.split('://',1)[1],headers={'X-No-Cache':'true','User-Agent':'Hermes-Agent-9-Independent-QA/1.0'},timeout=180);return r.status_code,r.text
def resample():
 c=con(True);fails=[];samples=[];executed={'SOURCE_RESAMPLE_COVERAGE','SOURCE_RESAMPLE_ROWS','SOURCE_RESAMPLE_ASSEMBLY','SOURCE_RESAMPLE_PRODUCT'}
 for v in c.execute('select variation_id from variations order by variation_id'):
  vid=v['variation_id'];cat=c.execute("select * from catalogue_leaves where variation_id=? and leaf_type='CATEGORY_INDEX' and status='INTEGRITY_CHECKED' order by catalogue_leaf_id limit 1",(vid,)).fetchone();dia=c.execute("select * from catalogue_leaves where variation_id=? and leaf_type='DIAGRAM' and status='INTEGRITY_CHECKED' order by catalogue_leaf_id limit 1",(vid,)).fetchone();prod=c.execute('''select p.* from product_sources p join record_product_sources x on x.product_source_id=p.product_source_id join part_records r on r.record_id=x.record_id where r.variation_id=? and p.status='INTEGRITY_CHECKED' order by p.product_source_id limit 1''',(vid,)).fetchone()
  if not cat or not dia or not prod:fails.append(failure('SOURCE_RESAMPLE_COVERAGE','CRITICAL','AGENT_9_INDEPENDENT_QUALITY',vid,{'category':bool(cat),'diagram':bool(dia),'product':bool(prod)},{'category':True,'diagram':True,'product':True},'stratified deterministic sample'));continue
  for leaf in (cat,dia):
   status,text=fetch(leaf['source_url']);ind=independent_counts(text);observed={'http':status,'rows':ind['rows'],'images':ind['images']};expected={'http':200,'rows':leaf['expected_source_row_count'],'images':leaf['expected_image_count']}
   if observed!=expected:fails.append(failure('SOURCE_RESAMPLE_ROWS','CRITICAL','AGENT_9_INDEPENDENT_QUALITY',leaf['catalogue_leaf_id'],observed,expected,leaf['source_url']))
   if leaf['leaf_type']=='DIAGRAM' and ind['active_assembly']!=leaf['assembly_number']:fails.append(failure('SOURCE_RESAMPLE_ASSEMBLY','CRITICAL','AGENT_9_INDEPENDENT_QUALITY',leaf['catalogue_leaf_id'],ind['active_assembly'],leaf['assembly_number'],leaf['source_url']))
   samples.append({'variation_id':vid,'type':leaf['leaf_type'],'scope':leaf['catalogue_leaf_id'],'observed':observed});time.sleep(10)
  status,text=fetch(prod['source_url']);pn=re.search(r'\*\s+Part Number:\s*([^\n]+)',text,re.I);imgs=set(re.findall(r'https?://(?:cdn-product-images|cdn-illustrations)\.revolutionparts\.io/[^)\s]+',text));dbimgs={x[0] for x in c.execute('select image_source_url from image_observations where product_source_id=?',(prod['product_source_id'],))};observed={'http':status,'pn':pn.group(1).strip() if pn else None,'images':sorted(imgs)};expected={'http':200,'pn':prod['displayed_part_number_source'],'images':sorted(dbimgs)}
  if observed!=expected:fails.append(failure('SOURCE_RESAMPLE_PRODUCT','CRITICAL','AGENT_9_INDEPENDENT_QUALITY',prod['product_source_id'],observed,expected,prod['source_url']))
  samples.append({'variation_id':vid,'type':'PRODUCT_SOURCE','scope':prod['product_source_id'],'observed':observed});time.sleep(10)
 c.close();return fails,executed,samples
def persist(run,fails,executed):
 c=con();active=set()
 for f in fails:
  did=sid('defect',f['check_code'],f['scope']);active.add(did);old=c.execute('select created_at,status,origin from defects where defect_id=?',(did,)).fetchone();created=old['created_at'] if old else now();status=old['status'] if old and old['status']=='IN_PROGRESS' else 'OPEN';c.execute('''INSERT OR REPLACE INTO defects(defect_id,origin,check_code,last_seen_qa_run_id,severity,responsible_agent,affected_record_ids,description,observed_result,expected_result,source_evidence,reproduction_steps,required_correction,same_pattern_search_requirement,retest_requirements,status,created_at,resolved_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(did,'AUTOMATED',f['check_code'],run,f['severity'],f['responsible_agent'],'[]',f['check_code'],json.dumps(f['observed'],ensure_ascii=False),json.dumps(f['expected'],ensure_ascii=False),json.dumps(f['evidence'],ensure_ascii=False),f'python scripts/catalogue_qa.py check --scope {f["scope"]}','Route to responsible agent; do not edit QA output','Search all six variations for same check code','Rerun exact deterministic check and same deterministic sample','OPEN' if status!='IN_PROGRESS' else status,created,None))
 for r in c.execute("select defect_id,check_code from defects where origin='AUTOMATED' and status='OPEN'").fetchall():
  if r['check_code'] in executed and r['defect_id'] not in active:c.execute("update defects set status='RESOLVED',resolved_at=?,retest_run_id=? where defect_id=?",(now(),run,r['defect_id']))
 c.commit();c.close()
def final_report(run,status,fails,samples,started,completed):
 c=con(True);variations=[]
 for v in c.execute('select * from variations order by variation_id'):
  variations.append({'variation_id':v['variation_id'],'source_label':v['variation_source_label'],'categories':c.execute("select count(*) from catalogue_leaves where variation_id=? and leaf_type='CATEGORY_INDEX' and status!='RETIRED_SOURCE'",(v['variation_id'],)).fetchone()[0],'diagrams':c.execute("select count(*) from catalogue_leaves where variation_id=? and leaf_type='DIAGRAM' and status!='RETIRED_SOURCE'",(v['variation_id'],)).fetchone()[0],'records':c.execute('select count(*) from part_records where variation_id=?',(v['variation_id'],)).fetchone()[0]})
 metrics={'repository':'https://github.com/karanjain1/vin-hardware-commonality-2017-charger-300','branch':'catalogue/2017-chrysler300c-challenger-master','checkpoint_identifier':'refs/tags/catalogue-qa-passed-20260801','vehicles':2,'variations':variations,'total_records':c.execute('select count(*) from part_records').fetchone()[0],'unique_oem_part_numbers':c.execute("select count(distinct oem_part_number_normalized) from part_records where oem_part_number_source!='PART_NUMBER_NOT_DISPLAYED'").fetchone()[0],'shared_part_numbers':c.execute("select count(*) from (select oem_part_number_normalized from part_records where oem_part_number_source!='PART_NUMBER_NOT_DISPLAYED' group by oem_part_number_normalized having count(distinct variation_id)>1)").fetchone()[0],'applicability_relationships':c.execute("select count(*) from (select distinct oem_part_number_normalized,variation_id from part_records where oem_part_number_source!='PART_NUMBER_NOT_DISPLAYED')").fetchone()[0],'exact_verified_image_observations':c.execute("select count(*) from image_observations where verification_status in ('IMAGE_VERIFIED_BYTE_EXACT','DIAGRAM_VERIFIED_BYTE_EXACT')").fetchone()[0],'unique_verified_image_assets':c.execute('select count(*) from image_assets').fetchone()[0],'no_oem_image_dispositions':c.execute("select count(*) from product_sources where no_image_disposition='NO_OEM_IMAGE_AVAILABLE'").fetchone()[0],'part_number_not_displayed_dispositions':c.execute("select count(*) from part_records where oem_part_number_source='PART_NUMBER_NOT_DISPLAYED'").fetchone()[0],'resolved_defects_by_severity':{r[0]:r[1] for r in c.execute("select severity,count(*) from defects where status='RESOLVED' group by severity")},'remaining_external_blocks':c.execute("select count(*) from defects where status='BLOCKED_EXTERNAL'").fetchone()[0]};c.close();report={'qa_run_id':run,'quality_agent':'AGENT_9_INDEPENDENT_QUALITY_RED_TEAM','started_at':started,'completed_at':completed,'status':status,'metrics':metrics,'source_resamples':samples,'failures':fails,'validation_commands':['python -m unittest discover -s tests -p test_catalogue_v2.py -v','python scripts/catalogue_auditors.py all','python scripts/catalogue_v2.py export','git lfs fsck','python scripts/catalogue_qa.py final'],'deliverables':['catalog/quality/recovery_audit.json','catalog/manifests/variation_manifest.json','catalog/v2/manifests/master_expected_scope.json','catalog/authoritative_catalogue.sqlite3','catalog/v2/exports/CATALOGUE.md','catalog/v2/images/','catalog/v2/exports/image_provenance.csv','catalog/quality/reports/PART_NUMBER_FITMENT_AUDIT.md','catalog/quality/reports/COMPLETENESS_RECONCILIATION.md','catalog/quality/reports/REPOSITORY_INTEGRITY.md','catalog/v2/exports/defects.csv','catalog/quality/reports/FINAL_INDEPENDENT_QUALITY_REPORT.md','catalog/README_V2.md']};OUT.mkdir(parents=True,exist_ok=True);(OUT/'FINAL_INDEPENDENT_QUALITY_REPORT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');lines=['# Final Independent Quality Report','',f'**Agent:** {report["quality_agent"]}',f'**Run:** `{run}`',f'**Completed:** {completed}',f'**Status:** {status}','','## Metrics','```json',json.dumps(metrics,indent=2,ensure_ascii=False),'```','','## Failures','```json',json.dumps(fails,indent=2,ensure_ascii=False),'```','',('FINAL STATUS: QA PASSED' if status=='QA_PASSED' else 'FINAL STATUS: QA FAILED')];(OUT/'FINAL_INDEPENDENT_QUALITY_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');return report
def final():
 started=now();run='qa9-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');fails,executed,summary=deterministic_checks();samples=[]
 if not fails:
  sf,se,samples=resample();fails.extend(sf);executed|=se
 persist(run,fails,executed);c=con();c.execute("insert into qa_runs(qa_run_id,quality_agent,started_at,completed_at,check_results_json,status,git_commit,report_path) values(?,?,?,?,?,?,?,?)",(run,'AGENT_9_INDEPENDENT_QUALITY_RED_TEAM',started,now(),json.dumps({'failures':fails,'samples':samples}),'QA_FAILED' if fails else 'CHECKS_PASSED',summary['git_commit'],'catalog/quality/reports/FINAL_INDEPENDENT_QUALITY_REPORT.md'));c.commit();c.close()
 if not fails:
  c=con();unresolved=c.execute("select count(*) from defects where severity in ('CRITICAL','MAJOR') and status!='RESOLVED'").fetchone()[0]
  if unresolved:fails.append(failure('UNRESOLVED_DEFECTS','CRITICAL','AGENT_9_INDEPENDENT_QUALITY','project',unresolved,0,'post-retest defect gate'))
  else:
   expected=c.execute("select count(*) from catalogue_leaves where status='INTEGRITY_CHECKED'").fetchone()[0];total=c.execute("select count(*) from catalogue_leaves where status!='RETIRED_SOURCE'").fetchone()[0]
   if expected!=total:fails.append(failure('PROMOTION_GUARD','CRITICAL','AGENT_9_INDEPENDENT_QUALITY','project',expected,total,'only INTEGRITY_CHECKED eligible'))
   else:
    c.execute("update catalogue_leaves set status='QA_PASSED' where status='INTEGRITY_CHECKED'");c.execute("update product_sources set status='QA_PASSED' where status='INTEGRITY_CHECKED'");c.execute("update batches set status='QA_PASSED' where status='INTEGRITY_CHECKED'");c.execute("update part_records set qa_status='QA_PASSED' where repository_integrity_status='INTEGRITY_CHECKED'");c.execute("update qa_runs set status='QA_PASSED',completed_at=? where qa_run_id=?",(now(),run));c.commit()
  c.close()
 status='QA_PASSED' if not fails else 'QA_FAILED';report=final_report(run,status,fails,samples,started,now());print(json.dumps({'qa_run_id':run,'status':status,'failures':len(fails),'report':'catalog/quality/reports/FINAL_INDEPENDENT_QUALITY_REPORT.md'},indent=2));return not fails
def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['check','final']);a=p.parse_args()
 if a.command=='check':fails,_,summary=deterministic_checks();print(json.dumps({'status':'PASS' if not fails else 'FAIL','failures':fails,'summary':summary},indent=2));raise SystemExit(0 if not fails else 1)
 raise SystemExit(0 if final() else 1)
if __name__=='__main__':main()
