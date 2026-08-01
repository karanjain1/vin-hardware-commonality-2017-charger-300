#!/usr/bin/env python
"""Silent durable backstop: advance one bounded catalogue batch when idle.

This never retries QA_FAILED work. It recovers only process-interrupted IN_PROGRESS
states, executes at most eight Mopar pages per invocation, and stays silent on
normal progress. A single local diagnostic is emitted for an internal failure.
"""
from pathlib import Path
import json,os,sqlite3,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];CAT=ROOT/'catalog';DB=CAT/'authoritative_catalogue.sqlite3';STATE=CAT/'v2'/'checkpoints';STATE.mkdir(parents=True,exist_ok=True);LOCK=STATE/'.watchdog.lock';ALERT=STATE/'.watchdog_internal_failure.json';READY=STATE/'READY_FOR_QA.json'
def active_crawler():
 ps='Get-CimInstance Win32_Process | Where-Object { $_.Name -like "python*.exe" -and $_.CommandLine -like "*scripts/catalogue_v2.py crawl-*" } | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress'
 try:return bool(subprocess.check_output(['powershell.exe','-NoProfile','-Command',ps],text=True,stderr=subprocess.DEVNULL).strip())
 except Exception:return True  # fail closed: never risk concurrent source access
try:fd=os.open(LOCK,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
except FileExistsError:sys.exit(0)
try:
 if active_crawler():sys.exit(0)
 c=sqlite3.connect(DB,timeout=120);c.row_factory=sqlite3.Row
 # A dead process can strand one leaf/batch. Return it to its last safe checkpoint.
 c.execute("UPDATE catalogue_leaves SET status='NOT_STARTED',exception_code='RECOVERED_INTERRUPTED_PROCESS' WHERE status='IN_PROGRESS'")
 c.execute("UPDATE batches SET status='NOT_STARTED',last_error='RECOVERED_INTERRUPTED_PROCESS' WHERE status='IN_PROGRESS'");c.commit()
 failed=[dict(x) for x in c.execute("SELECT leaf_type,status,count(*) n FROM catalogue_leaves WHERE status='QA_FAILED' GROUP BY leaf_type,status")]
 if failed:
  if not ALERT.exists():ALERT.write_text(json.dumps({'state':'INTERNAL_FAILURE_REQUIRES_ROOT_CAUSE','failures':failed})+'\n',encoding='utf-8');print(ALERT.read_text(encoding='utf-8').strip())
  sys.exit(0)
 stages=[('CATEGORY_INDEX','crawl-categories'),('DIAGRAM','crawl-diagrams'),('PRODUCT_DETAIL','crawl-products')]
 command=None
 for leaf_type,cmd in stages:
  if c.execute("SELECT count(*) FROM catalogue_leaves WHERE leaf_type=? AND status='NOT_STARTED'",(leaf_type,)).fetchone()[0]:command=['python','scripts/catalogue_v2.py',cmd,'--limit','8'];break
 if not command:
  if c.execute("SELECT count(*) FROM image_observations WHERE image_role NOT LIKE 'STATIC_%' AND acquisition_status='NOT_STARTED'").fetchone()[0]:command=['python','scripts/catalogue_v2.py','acquire-images','--limit','500']
  elif c.execute("SELECT count(*) FROM image_observations WHERE image_role NOT LIKE 'STATIC_%' AND acquisition_status='ACQUIRED' AND verification_status='NOT_STARTED'").fetchone()[0]:command=['python','scripts/catalogue_v2.py','verify-images','--limit','500']
  elif c.execute("SELECT count(*) FROM image_observations WHERE image_role NOT LIKE 'STATIC_%' AND (acquisition_status='FAILED' OR verification_status IN ('SOURCE_IMAGE_CHANGED','SOURCE_LINK_BROKEN'))").fetchone()[0]:
   payload={'state':'IMAGE_FAILURE_REQUIRES_ROOT_CAUSE'}
   if not ALERT.exists():ALERT.write_text(json.dumps(payload)+'\n',encoding='utf-8');print(json.dumps(payload))
   sys.exit(0)
  else:
   subprocess.run(['python','scripts/catalogue_v2.py','export'],cwd=ROOT,check=True,timeout=170,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
   if not READY.exists():READY.write_text(json.dumps({'state':'READY_FOR_INDEPENDENT_QA'})+'\n',encoding='utf-8');print(READY.read_text(encoding='utf-8').strip())
   sys.exit(0)
 c.close();r=subprocess.run(command,cwd=ROOT,timeout=170,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
 if r.returncode:
  payload={'state':'WATCHDOG_BATCH_FAILED','command':command,'returncode':r.returncode,'stderr':r.stderr[-4000:]}
  if not ALERT.exists():ALERT.write_text(json.dumps(payload)+'\n',encoding='utf-8');print(json.dumps(payload))
finally:
 try:LOCK.unlink()
 except FileNotFoundError:pass
