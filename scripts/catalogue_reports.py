#!/usr/bin/env python
"""Generate required human-readable and machine-readable v2 deliverables."""
from __future__ import annotations
import csv,datetime as dt,hashlib,importlib.util,json,sqlite3,subprocess
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];CAT=ROOT/'catalog';DB=CAT/'authoritative_catalogue.sqlite3';OUT=CAT/'quality'/'reports';EXPORT=CAT/'v2'/'exports';OUT.mkdir(parents=True,exist_ok=True);EXPORT.mkdir(parents=True,exist_ok=True)
SPEC=importlib.util.spec_from_file_location('catalogue_qa',ROOT/'scripts'/'catalogue_qa.py');qa=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(qa)
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def dump(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def md(v):return str(v or '').replace('|','\\|').replace('\r',' ').replace('\n',' ')
def count(c,sql,p=()):return c.execute(sql,p).fetchone()[0]
def repo(command):
 try:return subprocess.check_output(command,cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
 except Exception:return 'UNAVAILABLE'
def generate():
 c=sqlite3.connect(f'file:{DB.as_posix()}?mode=ro',uri=True);c.row_factory=sqlite3.Row;ts=now();status=json.loads((EXPORT/'status.json').read_text(encoding='utf-8')) if (EXPORT/'status.json').exists() else {}
 variations=[]
 for v in c.execute('SELECT v.*,ve.year,ve.make_source,ve.model_source FROM variations v JOIN vehicles ve ON ve.vehicle_id=v.vehicle_id ORDER BY v.vehicle_id,v.variation_id'):
  p=(v['variation_id'],);variations.append({'variation_id':v['variation_id'],'vehicle_id':v['vehicle_id'],'source_label':v['variation_source_label'],'categories':count(c,"SELECT count(*) FROM catalogue_leaves WHERE variation_id=? AND leaf_type='CATEGORY_INDEX'",p),'subcategories':count(c,"SELECT count(*) FROM taxonomy_nodes WHERE variation_id=? AND node_type='SUBCATEGORY'",p),'diagrams':count(c,"SELECT count(*) FROM catalogue_leaves WHERE variation_id=? AND leaf_type='DIAGRAM'",p),'product_detail_pages':count(c,"SELECT count(*) FROM catalogue_leaves WHERE variation_id=? AND leaf_type='PRODUCT_DETAIL'",p),'part_records':count(c,'SELECT count(*) FROM part_records WHERE variation_id=?',p),'unique_oem_part_numbers':count(c,"SELECT count(DISTINCT oem_part_number_source) FROM part_records WHERE variation_id=? AND oem_part_number_source!='PART_NUMBER_NOT_DISPLAYED'",p),'qa_passed_leaves':count(c,"SELECT count(*) FROM catalogue_leaves WHERE variation_id=? AND status='QA_PASSED'",p),'blocked_external_leaves':count(c,"SELECT count(*) FROM catalogue_leaves WHERE variation_id=? AND status='BLOCKED_EXTERNAL'",p)})
 shared=count(c,"SELECT count(*) FROM (SELECT oem_part_number_normalized FROM part_records WHERE oem_part_number_source!='PART_NUMBER_NOT_DISPLAYED' GROUP BY oem_part_number_normalized HAVING count(DISTINCT variation_id)>1)")
 applicability=count(c,"SELECT count(*) FROM (SELECT DISTINCT oem_part_number_normalized,variation_id FROM part_records WHERE oem_part_number_source!='PART_NUMBER_NOT_DISPLAYED')")
 metrics={'generated_at':ts,'database_sha256':hashlib.sha256(DB.read_bytes()).hexdigest(),'branch':repo(['git','branch','--show-current']),'head_at_report_generation':repo(['git','rev-parse','HEAD']),'checkpoint_identifier':'refs/tags/catalogue-qa-passed-2026-08-01','variations':variations,'total_records':count(c,'SELECT count(*) FROM part_records'),'total_unique_oem_part_numbers':count(c,"SELECT count(DISTINCT oem_part_number_normalized) FROM part_records WHERE oem_part_number_source!='PART_NUMBER_NOT_DISPLAYED'"),'total_shared_part_numbers':shared,'total_applicability_relationships':applicability,'total_unique_verified_image_assets':count(c,"SELECT count(DISTINCT image_sha256) FROM image_observations WHERE verification_status IN ('IMAGE_VERIFIED_BYTE_EXACT','DIAGRAM_VERIFIED_BYTE_EXACT')"),'total_verified_image_observations':count(c,"SELECT count(*) FROM image_observations WHERE verification_status IN ('IMAGE_VERIFIED_BYTE_EXACT','DIAGRAM_VERIFIED_BYTE_EXACT')"),'total_no_oem_image_available':count(c,"SELECT count(*) FROM part_records WHERE image_verification_status='NO_OEM_IMAGE_AVAILABLE'"),'total_part_number_not_displayed':count(c,"SELECT count(*) FROM part_records WHERE oem_part_number_source='PART_NUMBER_NOT_DISPLAYED'"),'resolved_defects_by_severity':{r['severity']:r['n'] for r in c.execute("SELECT severity,count(*) n FROM defects WHERE status='RESOLVED' GROUP BY severity")},'open_defects_by_severity':{r['severity']:r['n'] for r in c.execute("SELECT severity,count(*) n FROM defects WHERE status!='RESOLVED' GROUP BY severity")},'blocked_external_items':count(c,"SELECT count(*) FROM catalogue_leaves WHERE status='BLOCKED_EXTERNAL'")}
 dump(OUT/'final_metrics.json',metrics)
 # Completeness reconciliation
 comp=[]
 for v in variations:
  p=(v['variation_id'],);comp.append({'variation_id':v['variation_id'],'expected_leaves':count(c,'SELECT count(*) FROM catalogue_leaves WHERE variation_id=?',p),'processed_leaves':count(c,"SELECT count(*) FROM catalogue_leaves WHERE variation_id=? AND status NOT IN ('NOT_STARTED','IN_PROGRESS')",p),'passed_leaves':count(c,"SELECT count(*) FROM catalogue_leaves WHERE variation_id=? AND status='QA_PASSED'",p),'failed_leaves':count(c,"SELECT count(*) FROM catalogue_leaves WHERE variation_id=? AND status='QA_FAILED'",p),'blocked_leaves':count(c,"SELECT count(*) FROM catalogue_leaves WHERE variation_id=? AND status='BLOCKED_EXTERNAL'",p),'expected_visible_rows':count(c,'SELECT COALESCE(sum(visible_row_expected),0) FROM catalogue_leaves WHERE variation_id=?',p),'extracted_records':count(c,'SELECT COALESCE(sum(extracted_record_count),0) FROM catalogue_leaves WHERE variation_id=?',p),'expected_callouts':count(c,'SELECT COALESCE(sum(visible_callout_expected),0) FROM catalogue_leaves WHERE variation_id=?',p),'extracted_callouts':count(c,'SELECT COALESCE(sum(extracted_callout_count),0) FROM catalogue_leaves WHERE variation_id=?',p)})
 dump(OUT/'completeness_reconciliation.json',{'generated_at':ts,'variations':comp})
 lines=['# Completeness Reconciliation Report','',f'Generated: {ts}','','| Variation | Expected leaves | Processed | QA passed | Failed | Blocked | Expected rows | Extracted records | Expected callouts | Extracted callouts |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
 for x in comp:lines.append(f"| {x['variation_id']} | {x['expected_leaves']} | {x['processed_leaves']} | {x['passed_leaves']} | {x['failed_leaves']} | {x['blocked_leaves']} | {x['expected_visible_rows']} | {x['extracted_records']} | {x['expected_callouts']} | {x['extracted_callouts']} |")
 (OUT/'COMPLETENESS_RECONCILIATION.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 # Part number / fitment report
 pnf={r['fitment_audit_status']:r['n'] for r in c.execute('SELECT fitment_audit_status,count(*) n FROM part_records GROUP BY fitment_audit_status')};pn_states={r['oem_part_number_source']:r['n'] for r in c.execute("SELECT CASE WHEN oem_part_number_source='PART_NUMBER_NOT_DISPLAYED' THEN 'PART_NUMBER_NOT_DISPLAYED' ELSE 'DISPLAYED' END oem_part_number_source,count(*) n FROM part_records GROUP BY 1")};dump(OUT/'part_number_fitment_audit.json',{'generated_at':ts,'part_number_states':pn_states,'fitment_audit_states':pnf,'unique_numbers':metrics['total_unique_oem_part_numbers'],'shared_numbers':shared,'applicability_relationships':applicability})
 (OUT/'PART_NUMBER_FITMENT_AUDIT.md').write_text('# Part Number and Fitment Audit Report\n\nGenerated: '+ts+'\n\n## Part-number states\n\n'+''.join(f'- {k}: {v}\n' for k,v in sorted(pn_states.items()))+'\n## Fitment-audit states\n\n'+''.join(f'- {k}: {v}\n' for k,v in sorted(pnf.items()))+f'\n**Unique displayed OEM numbers:** {metrics["total_unique_oem_part_numbers"]}  \n**Shared numbers:** {shared}  \n**Applicability relationships:** {applicability}\n',encoding='utf-8')
 # Repository integrity report from independent checks
 checks,fails=qa.run_checks(final=True);integrity={'generated_at':ts,'checks':checks,'failures':fails,'status':'PASS' if not fails else 'FAIL'};dump(OUT/'repository_integrity.json',integrity)
 lines=['# Repository Integrity Report','',f'Generated: {ts}','',f'**Status: {integrity["status"]}**','']
 for x in ([{'name':k,'value':v} for k,v in checks.items()] if isinstance(checks,dict) else checks):
  if 'name' in x:lines.append(f'- {x["name"]}: {json.dumps(x.get("value"),ensure_ascii=False)}')
  else:
   k=next(iter(x));lines.append(f'- {k}: {json.dumps(x[k],ensure_ascii=False)}')
 if fails:lines += ['','## Failures','']+[f'- **{x["severity"]} {x["code"]}:** {x["description"]}' for x in fails]
 (OUT/'REPOSITORY_INTEGRITY.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 # Human-readable catalogue
 lines=['# Human-readable Mopar OEM Catalogue','',f'Generated: {ts}','',"The SQLite database is authoritative; this is a deterministic projection.",'']
 for v in c.execute('SELECT v.*,ve.year,ve.make_source,ve.model_source FROM variations v JOIN vehicles ve ON ve.vehicle_id=v.vehicle_id ORDER BY v.vehicle_id,v.variation_id'):
  lines += [f"## {md(v['year'])} {md(v['make_source'])} {md(v['model_source'])} — {md(v['variation_source_label'])}",'',f"Variation ID: `{v['variation_id']}`",'']
  rows=c.execute('''SELECT pr.*,tn.source_label category_label,sn.source_label subcategory_label,cl.diagram_title_source FROM part_records pr LEFT JOIN taxonomy_nodes tn ON tn.node_id=pr.category_id LEFT JOIN taxonomy_nodes sn ON sn.node_id=pr.subcategory_id LEFT JOIN catalogue_leaves cl ON cl.catalogue_leaf_id=pr.catalogue_leaf_id WHERE pr.variation_id=? ORDER BY tn.ordinal,sn.ordinal,cl.diagram_id,pr.diagram_callout_source,pr.oem_part_number_source''',(v['variation_id'],)).fetchall();current=None
  for r in rows:
   key=(r['category_label'],r['subcategory_label']);
   if key!=current:
    current=key;lines += [f"### {md(key[0])} / {md(key[1])}",'','| Callout | OEM part number | Part name | Diagram | Fitment/source notes | Part URL |','|---|---|---|---|---|---|']
   lines.append(f"| {md(r['diagram_callout_source'])} | {md(r['oem_part_number_source'])} | {md(r['part_name_source'])} | {md(r['diagram_title_source'])} | {md(r['fitment_notes_source'])} | {md(r['part_detail_url'])} |")
 (EXPORT/'CATALOGUE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 c.close();print(json.dumps(metrics,indent=2))
if __name__=='__main__':generate()
