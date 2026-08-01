#!/usr/bin/env python
"""Fail-closed six-variation MoparAmerica catalogue producer.

Every visible row occurrence is staged before one-to-one record creation. Source
snapshots and image occurrences are immutable evidence; retries transactionally
replace the active projection for a leaf. Agent-9 QA is implemented separately.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,io,json,mimetypes,re,sqlite3,sys,threading,time
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
import requests
from PIL import Image,ImageChops
ROOT=Path(__file__).resolve().parents[1];CAT=ROOT/'catalog';DB=CAT/'authoritative_catalogue.sqlite3';SCHEMA=CAT/'schema_v2.sql';MANIFEST=CAT/'manifests'/'variation_manifest.json';CACHE_INDEX=CAT/'v2'/'checkpoints'/'recovery_source_cache_index.json';HIST_DEFECTS=CAT/'quality'/'defects'/'preproduction_red_team_defects.json'
RUN_AGENT={'discover':'AGENT_2_TAXONOMY','category':'AGENT_3_PART_RECORD_EXTRACTION','diagram':'AGENT_3_PART_RECORD_EXTRACTION','product':'AGENT_3_PART_RECORD_EXTRACTION','image':'AGENT_4_IMAGE_ACQUISITION','verify':'AGENT_5_IMAGE_INTEGRITY'}
STATUSES=('NOT_STARTED','IN_PROGRESS','EXTRACTED','SOURCE_VERIFIED','IMAGE_ACQUIRED','IMAGE_VERIFIED','FITMENT_AUDITED','COMPLETENESS_CHECKED','INTEGRITY_CHECKED','QA_FAILED','QA_PASSED','BLOCKED_EXTERNAL','RETIRED_SOURCE')
_lock=threading.Lock();_last_request=0.0
def now():return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
def sid(prefix,*parts):return prefix+'-'+hashlib.sha256('\x1f'.join(str(x or '') for x in parts).encode()).hexdigest()[:24]
def sha(b):return hashlib.sha256(b).hexdigest()
def norm(s):return re.sub(r'[^A-Z0-9]','',str(s or '').upper())
def clean(s):return re.sub(r'\s+',' ',str(s or '')).strip()
def con(ro=False):
 u=f'file:{DB.as_posix()}?mode=ro' if ro else str(DB);c=sqlite3.connect(u,uri=ro,timeout=120);c.row_factory=sqlite3.Row
 if not ro:c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA busy_timeout=120000')
 return c
def run_id(stage):return f'{stage}-{dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:8]}'
def cache_entries():
 try:return json.loads(CACHE_INDEX.read_text(encoding='utf-8'))['entries']
 except Exception:return {}
def throttled_get(url,timeout=180,no_cache=False):
 global _last_request
 with _lock:
  wait=max(0,10-(time.time()-_last_request))
  if wait:time.sleep(wait)
  headers={'User-Agent':'Hermes-Mopar-Catalogue-Audit/3.0'}
  if no_cache:headers['X-No-Cache']='true'
  r=requests.get(url,timeout=timeout,headers=headers);_last_request=time.time();return r
def source_get(original,refresh=False,prefer_https=False):
 if not refresh:
  e=cache_entries().get(original)
  if e:
   p=CAT/e['path'];b=p.read_bytes()
   if sha(b)==e['sha256'] and len(b)==e['byte_size']:return 200,b.decode('utf-8',errors='replace'),original,'RECOVERY_CACHE',e['path']
 https_first=prefer_https or '/oem-parts/' in original or '/p-' in original
 candidates=['https://r.jina.ai/https://'+original.split('://',1)[1],'https://r.jina.ai/http://'+original.split('://',1)[1]] if https_first else ['https://r.jina.ai/http://'+original.split('://',1)[1],'https://r.jina.ai/https://'+original.split('://',1)[1]]
 errors=[]
 for renderer in candidates:
  for attempt in range(3):
   r=throttled_get(renderer,no_cache=refresh);text=r.text;bad=any(x in text[:1500] for x in ('Page Not Found','Internal Server Error','Security Verification','Access Denied'))
   if r.status_code==200 and len(text)>900 and not bad:return r.status_code,text,r.url,renderer,None
   errors.append({'renderer':renderer,'attempt':attempt+1,'status':r.status_code,'bytes':len(r.content),'title':(re.search(r'^Title:\s*(.+)$',text,re.M).group(1) if re.search(r'^Title:\s*(.+)$',text,re.M) else '')});time.sleep(10*(attempt+1))
 raise RuntimeError('source retrieval failed '+json.dumps({'url':original,'errors':errors}))
def snapshot(c,url,text,http,final,renderer,run,structure):
 b=text.encode('utf-8');h=sha(b);raw=CAT/'v2'/'evidence'/'snapshots'/f'{h}.md';raw.parent.mkdir(parents=True,exist_ok=True)
 if raw.exists() and sha(raw.read_bytes())!=h:raise RuntimeError(f'immutable snapshot collision {raw}')
 if not raw.exists():raw.write_bytes(b)
 snap=sid('snapshot',url,h)
 c.execute('''INSERT INTO source_snapshots(snapshot_id,source_url,renderer_url,source_accessed_at,http_status,final_url,byte_sha256,canonical_text_sha256,byte_size,raw_path,structure_status,retrieval_run_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(snapshot_id) DO NOTHING''',(snap,url,renderer,now(),http,final,h,sha(text.replace('\r\n','\n').replace('\r','\n').encode()),len(b),raw.relative_to(CAT).as_posix(),structure,run))
 return snap,h,raw
def init_db():
 if DB.exists():
  c=con(True)
  try:v=c.execute("SELECT value FROM project_meta WHERE key='schema_version'").fetchone()
  except sqlite3.Error:v=None
  c.close()
  if not v or v[0]!='3.1':raise RuntimeError('existing authoritative DB is not schema v3.1; archive it before controlled rebuild')
  return
 DB.parent.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(DB);c.executescript(SCHEMA.read_text(encoding='utf-8'));c.execute("INSERT INTO project_meta VALUES('schema_version','3.1')");c.execute("INSERT INTO project_meta VALUES('scope','2017 Chrysler 300C and Dodge Challenger — exact six variations')");c.commit();c.close();load_manifest()
def load_manifest():
 m=json.loads(MANIFEST.read_text(encoding='utf-8'));c=con()
 for vehicle in m['vehicles']:
  vid=vehicle['vehicle_id'];c.execute('INSERT OR IGNORE INTO vehicles VALUES(?,?,?,?)',(vid,int(vehicle['year']),vehicle['make_source'],vehicle['model_source']))
  for v in vehicle['variations']:
   fuel=v['engine_source'].rsplit(' ',1)[-1];basis='; '.join(m.get('resolution_basis',[])+[v.get('derivation_status','')])
   c.execute('''INSERT OR REPLACE INTO variations(variation_id,vehicle_id,variation_source_label,trim_source,engine_source,fuel_source,route_slug,route_url,derivation_basis,evidence_url,expected_category_count,validation_status,source_accessed_at,source_page_sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(v['variation_id'],vid,v['variation_source_label'],v['trim_source'],v['engine_source'],fuel,v['route_slug'],v['source_url'],basis,v['source_url'],v.get('current_expected_category_links',v['expected_category_links_at_resolution']),'NOT_STARTED',None,None))
 c.commit();load_historical_defects(c);c.close()
def load_historical_defects(c):
 if not HIST_DEFECTS.exists():return
 reg=json.loads(HIST_DEFECTS.read_text(encoding='utf-8'));stamp=reg.get('created_at',now())
 for d in reg.get('defects',[]):
  vals=(d['defect_id'],'MANUAL',d['defect_id'],d['severity'],d['responsible_agent'],'[]',d['description'],d.get('observed_result') or 'See registered defect',d.get('required_correction') or 'Pass controlled regression',json.dumps({'evidence':d.get('evidence'),'register':HIST_DEFECTS.relative_to(ROOT).as_posix()}),d.get('retest') or 'See controlled test',d.get('required_correction') or 'Correct defect',d.get('same_pattern_search_requirement') or 'Entire controlled scope',d.get('retest') or 'Controlled regression','RESOLVED' if d.get('status','').startswith('RESOLVED') else 'OPEN',stamp,stamp,'preproduction-regression-suite')
  c.execute('''INSERT OR IGNORE INTO defects(defect_id,origin,check_code,severity,responsible_agent,affected_record_ids,description,observed_result,expected_result,source_evidence,reproduction_steps,required_correction,same_pattern_search_requirement,retest_requirements,status,created_at,resolved_at,retest_run_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',vals)
 c.commit()
def category_links(text,route):
 pat=re.compile(r'\[([^\]\n]+)\]\((https://www\.moparamerica\.com/'+re.escape(route)+r'/([a-z0-9-]+--[a-z0-9-]+))(?:\s+"[^"]*")?\)')
 out={}
 for m in pat.finditer(text):out[m.group(3)]={'label':clean(m.group(1)),'url':m.group(2),'locator':f'markdown:char:{m.start()}-{m.end()}'}
 return [dict(slug=k,**v) for k,v in sorted(out.items())]
def validate_route(text,v):
 title=re.search(r'^Title:\s*(.+)$',text,re.M);expected=f"2017 {v['make_source']} {v['model_source']} {v['variation_source_label'].replace(' / ',' ')}"
 return bool(title and str(v['year']) in title.group(1) and v['make_source'] in title.group(1) and v['model_source'] in title.group(1)),title.group(1) if title else '',expected
def discover(refresh=False):
 init_db();c=con();run=run_id('discover')
 for v in c.execute('SELECT v.*,ve.year,ve.make_source,ve.model_source FROM variations v JOIN vehicles ve ON ve.vehicle_id=v.vehicle_id ORDER BY v.variation_id').fetchall():
  try:
   http,text,final,renderer,_=source_get(v['route_url'],refresh);ok,title,expected=validate_route(text,v);links=category_links(text,v['route_slug'])
   if not ok or len(links)!=v['expected_category_count']:raise RuntimeError(json.dumps({'title':title,'expected_title':expected,'categories':len(links),'expected_categories':v['expected_category_count']}))
   snap,h,_=snapshot(c,v['route_url'],text,http,final,renderer,run,'ROUTE_VALIDATED');c.execute("UPDATE variations SET validation_status='VALIDATED',source_accessed_at=?,source_page_sha256=? WHERE variation_id=?",(now(),h,v['variation_id']))
   for ordinal,x in enumerate(links,1):
    major,minor=x['slug'].split('--',1);cat=sid('tax',v['variation_id'],'category',major);sub=sid('tax',v['variation_id'],'subcategory',x['slug']);leaf=sid('leaf',v['variation_id'],'CATEGORY_INDEX',x['url'])
    c.execute("INSERT INTO taxonomy_nodes VALUES(?,?,NULL,'CATEGORY',?,?,?,?,?,'DISCOVERED',?) ON CONFLICT(node_id) DO UPDATE SET source_label=excluded.source_label,source_url=excluded.source_url,ordinal=excluded.ordinal",(cat,v['variation_id'],major.replace('-',' ').title(),major.upper(),major,x['url'].rsplit('/',1)[0]+'/#cat-'+major,ordinal,now()))
    c.execute("INSERT INTO taxonomy_nodes VALUES(?,?,?,'SUBCATEGORY',?,?,?,?,?,'DISCOVERED',?) ON CONFLICT(node_id) DO UPDATE SET source_label=excluded.source_label,source_url=excluded.source_url,ordinal=excluded.ordinal",(sub,v['variation_id'],cat,x['label'],norm(x['label']),x['slug'],x['url'],ordinal,now()))
    c.execute("""INSERT INTO catalogue_leaves(catalogue_leaf_id,variation_id,category_id,subcategory_id,parent_leaf_id,leaf_type,source_url,status,evidence_notes) VALUES(?,?,?,?,NULL,'CATEGORY_INDEX',?,'NOT_STARTED',?) ON CONFLICT(catalogue_leaf_id) DO UPDATE SET evidence_notes=excluded.evidence_notes WHERE catalogue_leaves.status='NOT_STARTED'""",(leaf,v['variation_id'],cat,sub,x['url'],json.dumps({'route_snapshot_id':snap,'taxonomy_locator':x['locator']})))
    c.execute("INSERT OR IGNORE INTO batches(batch_id,stage,scope_type,scope_id,responsible_agent,allowed_output_paths,expected_output,completion_test,status,code_version,skill_version) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(sid('batch','category',leaf),'CATEGORY_EXTRACTION','LEAF',leaf,RUN_AGENT['category'],'catalog/v2/evidence;catalog/authoritative_catalogue.sqlite3','Complete visible-row and image-occurrence projection','source rows equal records; parser-independent structural counts reconcile','NOT_STARTED','3.1.0','S2-S4-v1'))
   c.commit()
  except Exception as e:c.rollback();c.execute("UPDATE variations SET validation_status='QA_FAILED' WHERE variation_id=?",(v['variation_id'],));c.commit();raise
 export_scope(c);c.close()
def assembly_selectors(text):
 pat=re.compile(r'\[!\[Image\s+\d+:\s*([^\]]*)\]\((https?://[^)\s]+)\)([^\]]*)\]\((https://www\.moparamerica\.com/[^)\s"]+\?assembly=(\d+))(?:\s+"Diagram\s+\d+:\s*([^"]*)")?\)')
 out=[];seen=set()
 for m in pat.finditer(text):
  n=int(m.group(5));key=(n,m.group(4))
  if key in seen:continue
  seen.add(key);title=clean(m.group(6) or re.sub(r'^\s*\d+\.\s*','',m.group(3)) or m.group(1));out.append({'assembly':n,'title':title,'image_url':m.group(2),'image_alt':m.group(1),'url':m.group(4),'locator':f'markdown:char:{m.start()}-{m.end()}','ordinal':len(out)+1})
 total=len(re.findall(r'https://www\.moparamerica\.com/[^)\s"]+\?assembly=\d+',text))
 if total!=len(out):raise ValueError(f'assembly selector reconciliation failed parsed={len(out)} references={total}')
 return out
def table_rows(text):
 header=re.search(r'\n\s*No\.\s*\n\s*\n\s*Part\s*#\s*/\s*Description\s*/\s*Price',text,re.I)
 if not header:return []
 section=text[header.end():];base=header.end()
 pat=re.compile(r'\[!\[Image\s+\d+:\s*([^\]]*)\]\((https?://[^)\s]+)\)\]\((https?://www\.moparamerica\.com/oem-parts/[^)\s"]+)(?:\s+"([^"]*)")?\)')
 ms=list(pat.finditer(section));rows=[];occ=Counter()
 for i,m in enumerate(ms):
  start=m.start();end=ms[i+1].start() if i+1<len(ms) else len(section);block=section[start:end];prefix=section[(ms[i-1].end() if i else 0):start];nums=re.findall(r'(?m)^\s*([A-Za-z0-9.-]+)\s*$',prefix[-500:]);rowlabel=nums[-1] if nums else f'image-{i+1}';url=m.group(3)
  nm=re.search(r'\*\*\[([^\]]+)\]\('+re.escape(url)+r'(?:\s+"[^"]*")?\)\*\*',block);name=clean(nm.group(1)) if nm else 'PART_NAME_NOT_DISPLAYED'
  pnm=re.search(r'\[([A-Za-z0-9-]{5,30})\]\('+re.escape(url)+r'(?:\s+"[^"]*")?\)',block);titlepn=re.search(r'Part No\s+([A-Za-z0-9-]+)',m.group(4) or '',re.I);pn=(pnm.group(1) if pnm and re.search(r'\d',pnm.group(1)) else titlepn.group(1) if titlepn else 'PART_NUMBER_NOT_DISPLAYED')
  descm=re.search(r'\*\*Description:\*\*\s*([^\n]+)',block,re.I);notesm=re.search(r'\*\*Notes:\*\*(.*?)(?:\n\s*MSRP|\n\s*\$|\Z)',block,re.I|re.S)
  anchor='table-row-'+clean(rowlabel);occ[anchor]+=1;snippet=block.rstrip();loc=f'markdown:char:{base+start}-{base+end}'
  rows.append({'section':'DETAILED_TABLE','anchor':anchor,'ordinal':occ[anchor],'locator':loc,'snippet':snippet,'callout':rowlabel,'url':url,'pn':pn,'name':name,'description':clean(descm.group(1)) if descm else None,'quantity':None,'fitment':clean(notesm.group(1)) if notesm else None,'images':[{'url':m.group(2),'alt':m.group(1),'role':'PRODUCT_IMAGE' if 'cdn-product-images.' in m.group(2) else 'ILLUSTRATION_THUMBNAIL' if 'cdn-illustrations.' in m.group(2) else 'UNKNOWN_CONTENT_IMAGE','locator':f'markdown:char:{base+m.start()}-{base+m.end()}','ordinal':1,'association':'ASSOCIATION_FROM_EXACT_SOURCE_WRAPPER'}]})
 independent=len(re.findall(r'\[!\[Image\s+\d+:[^\]]*\]\([^)]*\)\]\(https?://www\.moparamerica\.com/oem-parts/',section))
 if independent!=len(rows):raise ValueError(f'detailed row structural count mismatch parsed={len(rows)} markers={independent}')
 return rows
def accessory_rows(text):
 result=re.search(r'###\s+(\d+)\s+Results?\s*\|\s*Showing\s+(\d+)\s*[–-]\s*(\d+)\s+of\s+(\d+)',text,re.I)
 if not result:return []
 sect_start=result.end();nav=re.search(r'(?m)^\*\*Navigation\*\*$',text[sect_start:]);sect_end=sect_start+(nav.start() if nav else len(text)-sect_start);section=text[sect_start:sect_end]
 hp=re.compile(r'(?m)^##\s+\[([^\]]+)\]\((https?://www\.moparamerica\.com/(?:oem-parts/|p-)[^)\s"]+)(?:\s+"[^"]*")?\)\s*$');heads=list(hp.finditer(section));images=list(re.finditer(r'\[!\[Image\s+\d+:\s*([^\]]*)\]\((https?://[^)\s]+)\)\]\((https?://www\.moparamerica\.com/(?:oem-parts/|p-)[^)\s"]+)(?:\s+"[^"]*")?\)',section));rows=[]
 for i,h in enumerate(heads):
  url=h.group(2);prev=heads[i-1].end() if i else 0;im=next((x for x in reversed(images) if x.group(3)==url and prev<=x.start()<h.start()),None);start=im.start() if im else h.start();next_starts=[x.start() for x in images if x.start()>h.end()];end=min(next_starts) if next_starts else len(section);block=section[start:end];pnm=re.search(r'\[([A-Za-z0-9-]{5,30})\]\('+re.escape(url)+r'(?:\s+"[^"]*")?\)',block);pn=pnm.group(1) if pnm and re.search(r'\d',pnm.group(1)) else 'PART_NUMBER_NOT_DISPLAYED';ordinal=i+1;imgs=[]
  if im:imgs=[{'url':im.group(2),'alt':im.group(1),'role':'PRODUCT_IMAGE' if 'cdn-product-images.' in im.group(2) else 'ILLUSTRATION_THUMBNAIL' if 'cdn-illustrations.' in im.group(2) else 'UNKNOWN_CONTENT_IMAGE','locator':f'markdown:char:{sect_start+im.start()}-{sect_start+im.end()}','ordinal':1,'association':'ASSOCIATION_FROM_EXACT_SOURCE_WRAPPER'}]
  descm=re.search(r'\n\s*([^\n\[\]*][^\n]+?)\s*\n\s*\[Browse more',block);rows.append({'section':'ACCESSORY_RESULTS','anchor':f'accessory-result-{ordinal}','ordinal':1,'locator':f'markdown:char:{sect_start+start}-{sect_start+end}','snippet':block.rstrip(),'callout':str(ordinal),'url':url,'pn':pn,'name':clean(h.group(1)),'description':clean(descm.group(1)) if descm else None,'quantity':None,'fitment':'Fits Your Vehicle' if 'Fits Your Vehicle' in block else None,'images':imgs})
 expected=0 if int(result.group(4))==0 else int(result.group(3))-int(result.group(2))+1
 if len(rows)!=expected:raise ValueError(f'accessory result reconciliation failed parsed={len(rows)} expected_visible={expected} total={result.group(4)}')
 return rows
def markerless_card_rows(text):
 if re.search(r'###\s+\d+\s+Results?',text,re.I) or not re.search(r'^Title:\s+.+(?:accessories|for 2017)',text,re.I|re.M) or 'Markdown Content:' not in text or 'No results found.' not in text:return []
 start=text.find('Markdown Content:')+len('Markdown Content:');end=text.find('No results found.',start);section=text[start:end]
 if '‹‹››' in section or re.search(r'(?i)next page|page\s+\d+\s+of\s+\d+',section):raise ValueError('markerless card list exposes pagination without a source denominator')
 hp=re.compile(r'(?m)^#{1,2}\s+\[([^\]]+)\]\((https?://www\.moparamerica\.com/(?:oem-parts/|p-)[^)\s"]+)(?:\s+"[^"]*")?\)\s*$');heads=list(hp.finditer(section));ip=re.compile(r'\[!\[Image\s+\d+:\s*([^\]]*)\]\((https?://[^)\s]+)\)\]\((https?://www\.moparamerica\.com/(?:oem-parts/|p-)[^)\s"]+)(?:\s+"[^"]*")?\)');images=list(ip.finditer(section))
 if len(heads)!=len(images) or not heads:raise ValueError(f'markerless card reconciliation failed headings={len(heads)} images={len(images)}')
 rows=[]
 for i,h in enumerate(heads):
  url=h.group(2);im=images[i]
  if im.group(3)!=url:raise ValueError(f'markerless card image association mismatch index={i+1}')
  stop=images[i+1].start() if i+1<len(images) else len(section);block=section[im.start():stop];pnm=re.search(r'\[([A-Za-z0-9-]{5,30})\]\('+re.escape(url)+r'(?:\s+"[^"]*")?\)',block);pn=pnm.group(1) if pnm and re.search(r'\d',pnm.group(1)) else 'PART_NUMBER_NOT_DISPLAYED';descm=re.search(r'\)\s*\n\s*\n([^\n\[*$][^\n]+)',block);ordinal=i+1
  rows.append({'section':'MARKERLESS_PRODUCT_CARDS','anchor':f'markerless-card-{ordinal}','ordinal':1,'locator':f'markdown:char:{start+im.start()}-{start+stop}','snippet':block.rstrip(),'callout':str(ordinal),'url':url,'pn':pn,'name':clean(h.group(1)),'description':clean(descm.group(1)) if descm else None,'quantity':None,'fitment':'Fits Your Vehicle' if 'Fits Your Vehicle' in block else None,'images':[{'url':im.group(2),'alt':im.group(1),'role':'PRODUCT_IMAGE' if 'cdn-product-images.' in im.group(2) else 'ILLUSTRATION_THUMBNAIL' if 'cdn-illustrations.' in im.group(2) else 'UNKNOWN_CONTENT_IMAGE','locator':f'markdown:char:{start+im.start()}-{start+im.end()}','ordinal':1,'association':'ASSOCIATION_FROM_EXACT_SOURCE_WRAPPER'}]})
 return rows
def related_rows(text):
 head=re.search(r'(?m)^##\s+Related Parts\s*$',text)
 if not head:return []
 nav=re.search(r'(?m)^\*\*Navigation\*\*$',text[head.end():]);end=head.end()+(nav.start() if nav else len(text)-head.end());section=text[head.end():end];base=head.end();pat=re.compile(r'\[!\[Image\s+\d+:\s*([^\]]*)\]\((https?://[^)\s]+)\)\]\((https?://www\.moparamerica\.com/oem-parts/[^)\s"]+)(?:\s+"([^"]*)")?\)');ms=list(pat.finditer(section));rows=[]
 for i,m in enumerate(ms):
  stop=ms[i+1].start() if i+1<len(ms) else len(section);block=section[m.start():stop];url=m.group(3);nm=re.search(r'\*\*\[([^\]]+)\]\('+re.escape(url)+r'(?:\s+"[^"]*")?\)\*\*',block);pnm=re.search(r'\[([A-Za-z0-9-]{5,30})\]\('+re.escape(url)+r'(?:\s+"[^"]*")?\)',block);titlepn=re.search(r'Part No\s+([A-Za-z0-9-]+)',m.group(4) or '',re.I);pn=pnm.group(1) if pnm and re.search(r'\d',pnm.group(1)) else titlepn.group(1) if titlepn else 'PART_NUMBER_NOT_DISPLAYED';descm=re.search(r'\*\*Description:\*\*\s*([^\n]+)',block,re.I);notesm=re.search(r'\*\*Notes:\*\*(.*?)(?:\n\s*MSRP|\n\s*\$|\Z)',block,re.I|re.S);ordinal=i+1
  rows.append({'section':'RELATED_PARTS','anchor':f'related-part-{ordinal}','ordinal':1,'locator':f'markdown:char:{base+m.start()}-{base+stop}','snippet':block.rstrip(),'callout':str(ordinal),'url':url,'pn':pn,'name':clean(nm.group(1)) if nm else 'PART_NAME_NOT_DISPLAYED','description':clean(descm.group(1)) if descm else None,'quantity':None,'fitment':clean(notesm.group(1)) if notesm else None,'images':[{'url':m.group(2),'alt':m.group(1),'role':'PRODUCT_IMAGE' if 'cdn-product-images.' in m.group(2) else 'ILLUSTRATION_THUMBNAIL' if 'cdn-illustrations.' in m.group(2) else 'UNKNOWN_CONTENT_IMAGE','locator':f'markdown:char:{base+m.start()}-{base+m.end()}','ordinal':1,'association':'ASSOCIATION_FROM_EXACT_SOURCE_WRAPPER'}]})
 return rows
def active_diagram(text,requested=None):
 heads=[];table_header=re.search(r'\n\s*No\.\s*\n',text);cut=table_header.start() if table_header else len(text)
 for m in re.finditer(r'(?m)^Diagram\s+(\d+):\s*([^\n]+?)\s+(\d+)\s*$',text):
  if m.start()<cut:heads.append((int(m.group(1)),clean(m.group(2)),m))
 if requested is not None:heads=[x for x in heads if x[0]==int(requested)]
 if not heads:return None
 n,title,m=heads[0];end=(re.search(r'\n\s*No\.\s*\n',text[m.end():]).start()+m.end()) if re.search(r'\n\s*No\.\s*\n',text[m.end():]) else len(text);body=text[m.end():end]
 im=re.search(r'!\[Image\s+\d+:\s*([^\]]*)\]\((https?://[^)\s]+)\)',body)
 return {'assembly':n,'title':title,'start':m.start(),'end':end,'body':body,'image':({'url':im.group(2),'alt':im.group(1),'role':'DIAGRAM','locator':f'markdown:char:{m.end()+im.start()}-{m.end()+im.end()}','ordinal':1,'association':'ASSOCIATION_FROM_ACTIVE_DIAGRAM'} if im else None)}
def callout_rows(text,active):
 if not active:return []
 body=active['body'];base=text.find(body);pat=re.compile(r'(?m)^\[([^\]]+)\]\(https://www\.moparamerica\.com/#part_row_([^)]+)\)');ms=list(pat.finditer(body));rows=[];occ=Counter()
 for i,m in enumerate(ms):
  end=ms[i+1].start() if i+1<len(ms) else len(body);block=body[m.start():end];urls=re.findall(r'https?://www\.moparamerica\.com/oem-parts/[^)\s"]+',block);callout=clean(m.group(1));anchor='#part_row_'+m.group(2)
  if not urls:urls=[f'https://www.moparamerica.com/{anchor}-unmapped']
  for u in urls:
   occ[anchor]+=1;name_match=re.search(r'\[([^\]]+)\]\('+re.escape(u)+r'\)',block);name=clean(re.sub(r'^\$[0-9.,]+\s+|\s+Mopar.*$','',name_match.group(1))) if name_match else 'PART_NAME_NOT_DISPLAYED';snippet=block.rstrip();rows.append({'section':'CALLOUT_SUMMARY','anchor':anchor,'ordinal':occ[anchor],'locator':f'markdown:char:{base+m.start()}-{base+end}','snippet':snippet,'callout':callout,'url':u,'pn':'PART_NUMBER_NOT_DISPLAYED','name':name,'description':None,'quantity':None,'fitment':None,'images':[],'exception':'CALLOUT_NO_DISPLAYED_PART' if '-unmapped' in u else None})
 return rows
def product_candidates(text,heading_start=0):return sorted(set(re.findall(r'https?://www\.moparamerica\.com/(?:oem-parts/|p-)[^)\s"]+',text[heading_start:])))
def leaf_structure_complete(text,leaf_type,requested_assembly=None):
 has_denominator=bool(re.search(r'\n\s*No\.\s*\n\s*\n\s*Part\s*#\s*/\s*Description\s*/\s*Price',text,re.I) or re.search(r'###\s+\d+\s+Results?\s*\|\s*Showing\s+\d+\s*[–-]\s*\d+\s+of\s+\d+',text,re.I) or re.search(r'(?m)^##\s+Related Parts\s*$',text) or 'No Parts Found' in text)
 active=active_diagram(text,requested_assembly)
 if leaf_type=='DIAGRAM':return active is not None and active['assembly']==int(requested_assembly)
 if active:return True
 try:
  if markerless_card_rows(text):return True
 except ValueError:return False
 return has_denominator
def parse_leaf(text,leaf_type,requested_assembly=None):
 selectors=assembly_selectors(text);active=active_diagram(text,requested_assembly)
 if leaf_type=='DIAGRAM' and (not active or active['assembly']!=int(requested_assembly)):raise ValueError(f'wrong assembly body requested={requested_assembly} active={active and active["assembly"]}')
 rows=table_rows(text)+accessory_rows(text)+markerless_card_rows(text)+related_rows(text)+callout_rows(text,active);heading=(re.search(r'(?m)^#\s+.+$',text).start() if re.search(r'(?m)^#\s+.+$',text) else 0);allurls=set(product_candidates(text,heading));accounted={r['url'] for r in rows if r['url'].startswith(('https://www.moparamerica.com/','http://www.moparamerica.com/'))}
 if allurls-accounted:raise ValueError('unaccounted product links '+json.dumps(sorted(allurls-accounted)[:20]))
 return {'selectors':selectors,'active':active,'rows':rows,'all_product_urls':allurls,'structural':{'detailed_rows':len([r for r in rows if r['section']=='DETAILED_TABLE']),'callout_rows':len([r for r in rows if r['section']=='CALLOUT_SUMMARY']),'callout_markers':len(re.findall(r'(?m)^\[[^\]]+\]\(https://www\.moparamerica\.com/#part_row_',active['body'])) if active else 0,'selectors':len(selectors)}}
def row_key(leaf,r):return sid('row',leaf,r['section'],r['anchor'],r['ordinal'])
def insert_image(c,source_context,snapshot_id,page_sha,record_id,rowkey,img,target_notes=None):
 leaf,product=source_context;obs=sid('imgobs',snapshot_id,img['locator'],img['ordinal']);c.execute('''INSERT INTO image_observations(image_observation_id,catalogue_leaf_id,product_source_id,record_id,source_row_key,source_snapshot_id,source_page_sha256,source_locator,source_occurrence_ordinal,image_role,image_alt_source,image_source_url,association_basis,association_status,acquisition_status,verification_status,evidence_notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'NOT_STARTED','NOT_STARTED',?)''',(obs,leaf,product,record_id,rowkey,snapshot_id,page_sha,img['locator'],img['ordinal'],img['role'],img.get('alt'),img['url'],img['association'],img['association'],json.dumps(target_notes or {})))
 if record_id:c.execute("INSERT OR IGNORE INTO image_observation_records VALUES(?,?,?)",(obs,record_id,img['association']))
 return obs
def insert_row(c,leafctx,snapshot_id,page_sha,r,run):
 key=row_key(leafctx['catalogue_leaf_id'],r);snippet_sha=sha(r['snippet'].encode());c.execute('''INSERT INTO visible_source_rows VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(key,leafctx['catalogue_leaf_id'],r['section'],r['anchor'],r['ordinal'],r['locator'],snippet_sha,r['snippet'],r.get('callout'),r.get('url'),r.get('pn'),r.get('name'),r.get('quantity'),r.get('fitment'),len(r['images']),'EXPLICIT_SOURCE_EXCEPTION' if r.get('exception') else 'EXTRACTED'))
 pn=r['pn'];name=r['name'];rid=sid('record',key);notes={'source_row_locator':r['locator'],'source_exception':r.get('exception')};provenance={'part_name_source':'VISIBLE_SOURCE_ROW','oem_part_number_source':'VISIBLE_SOURCE_ROW' if pn!='PART_NUMBER_NOT_DISPLAYED' else 'SOURCE_NOT_DISPLAYED','fitment_notes_source':'VISIBLE_SOURCE_ROW' if r.get('fitment') else None}
 c.execute('''INSERT INTO part_records(record_id,source_row_key,vehicle_id,year,make_source,model_source,variation_id,variation_source_label,category_id,category_source_label,subcategory_id,subcategory_source_label,catalogue_leaf_id,diagram_id,diagram_title_source,diagram_callout_source,source_section,source_row_anchor,source_occurrence_ordinal,evidence_snippet_sha256,part_name_source,part_name_normalized,part_description_source,oem_part_number_source,oem_part_number_normalized,quantity_source,fitment_notes_source,fitment_normalized,applicability_status,part_detail_url,catalogue_page_url,diagram_page_url,source_accessed_at,extractor_agent,extraction_run_id,extraction_status,source_verification_status,image_verification_status,fitment_audit_status,completeness_status,repository_integrity_status,qa_status,exception_code,evidence_notes,field_provenance_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(rid,key,leafctx['vehicle_id'],leafctx['year'],leafctx['make_source'],leafctx['model_source'],leafctx['variation_id'],leafctx['variation_source_label'],leafctx['category_id'],leafctx['category_label'],leafctx['subcategory_id'],leafctx['subcategory_label'],leafctx['catalogue_leaf_id'],leafctx['diagram_id'],leafctx['diagram_title_source'],r.get('callout'),r['section'],r['anchor'],r['ordinal'],snippet_sha,name,norm(name),r.get('description'),pn,norm(pn),r.get('quantity'),r.get('fitment'),norm(r.get('fitment')) if r.get('fitment') else None,'CATALOGUE_ROUTE_APPLICABLE',r['url'],leafctx['catalogue_page_url'],leafctx['diagram_page_url'],now(),RUN_AGENT['category'] if leafctx['leaf_type']=='CATEGORY_INDEX' else RUN_AGENT['diagram'],run,'EXTRACTED','NOT_STARTED','NOT_STARTED','NOT_STARTED','NOT_STARTED','NOT_STARTED','NOT_STARTED',r.get('exception') or ('PART_NUMBER_NOT_DISPLAYED' if pn=='PART_NUMBER_NOT_DISPLAYED' else None),json.dumps(notes),json.dumps(provenance)))
 if '/oem-parts/' in r['url'] or '/p-' in r['url']:
  product_url=re.sub(r'^http://www\.moparamerica\.com','https://www.moparamerica.com',r['url']);ps=sid('product',product_url);c.execute("INSERT INTO product_sources(product_source_id,source_url,status) VALUES(?,?,'NOT_STARTED') ON CONFLICT(product_source_id) DO NOTHING",(ps,product_url));c.execute("INSERT OR IGNORE INTO record_product_sources VALUES(?,?,?)",(rid,ps,'EXACT_VISIBLE_SOURCE_ROW_URL'));c.execute("INSERT OR IGNORE INTO batches(batch_id,stage,scope_type,scope_id,responsible_agent,allowed_output_paths,expected_output,completion_test,status,code_version,skill_version) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(sid('batch','product',ps),'PRODUCT_DETAIL_EXTRACTION','PRODUCT_SOURCE',ps,RUN_AGENT['product'],'catalog/v2/evidence;catalog/authoritative_catalogue.sqlite3','Complete product detail fields and image occurrence enumeration','required structural markers and all content images reconcile','NOT_STARTED','3.1.0','S3-S4-v1'))
 for img in r['images']:insert_image(c,(leafctx['catalogue_leaf_id'],None),snapshot_id,page_sha,rid,key,img)
 return rid
def leaf_context(c,leaf):
 return c.execute('''SELECT l.*,v.vehicle_id,v.variation_source_label,ve.year,ve.make_source,ve.model_source,tn.source_label category_label,sn.source_label subcategory_label,p.source_url catalogue_page_url FROM catalogue_leaves l JOIN variations v ON v.variation_id=l.variation_id JOIN vehicles ve ON ve.vehicle_id=v.vehicle_id JOIN taxonomy_nodes tn ON tn.node_id=l.category_id JOIN taxonomy_nodes sn ON sn.node_id=l.subcategory_id LEFT JOIN catalogue_leaves p ON p.catalogue_leaf_id=COALESCE(l.parent_leaf_id,l.catalogue_leaf_id) WHERE l.catalogue_leaf_id=?''',(leaf,)).fetchone()
def process_leaf(leaf_id,refresh=False):
 c=con();ctx=leaf_context(c,leaf_id);run=run_id(ctx['leaf_type'].lower());batch=sid('batch','category' if ctx['leaf_type']=='CATEGORY_INDEX' else 'diagram',leaf_id);c.execute("UPDATE catalogue_leaves SET status='IN_PROGRESS',processing_started_at=?,exception_code=NULL WHERE catalogue_leaf_id=?",(now(),leaf_id));c.execute("UPDATE batches SET status='IN_PROGRESS',attempt_count=attempt_count+1,started_at=?,last_error=NULL WHERE batch_id=?",(now(),batch));c.commit()
 try:
  http,text,final,renderer,_=source_get(ctx['source_url'],refresh)
  if not leaf_structure_complete(text,ctx['leaf_type'],ctx['assembly_number']):
   http,text,final,renderer,_=source_get(ctx['source_url'],True,True)
  if not leaf_structure_complete(text,ctx['leaf_type'],ctx['assembly_number']):raise ValueError('source structure incomplete after uncached re-fetch')
  parsed=parse_leaf(text,ctx['leaf_type'],ctx['assembly_number']);c.execute('BEGIN IMMEDIATE');snap,page_sha,raw=snapshot(c,ctx['source_url'],text,http,final,renderer,run,'LEAF_STRUCTURE_VALIDATED')
  c.execute('DELETE FROM image_observations WHERE catalogue_leaf_id=?',(leaf_id,));c.execute('DELETE FROM visible_source_rows WHERE catalogue_leaf_id=?',(leaf_id,))
  # Reconcile child diagrams from the complete selector set.
  if ctx['leaf_type']=='CATEGORY_INDEX':
   wanted=set()
   for s in parsed['selectors']:
    child=sid('leaf',ctx['variation_id'],'DIAGRAM',s['url']);wanted.add(child);c.execute('''INSERT INTO catalogue_leaves(catalogue_leaf_id,variation_id,category_id,subcategory_id,parent_leaf_id,leaf_type,diagram_id,diagram_title_source,assembly_number,source_url,status,evidence_notes) VALUES(?,?,?,?,?,'DIAGRAM',?,?,?,?, 'NOT_STARTED',?) ON CONFLICT(catalogue_leaf_id) DO UPDATE SET diagram_title_source=excluded.diagram_title_source,evidence_notes=excluded.evidence_notes WHERE catalogue_leaves.status IN ('NOT_STARTED','QA_FAILED','RETIRED_SOURCE')''',(child,ctx['variation_id'],ctx['category_id'],ctx['subcategory_id'],leaf_id,str(s['assembly']),s['title'],s['assembly'],s['url'],json.dumps({'selector_locator':s['locator']})))
    c.execute("INSERT OR IGNORE INTO batches(batch_id,stage,scope_type,scope_id,responsible_agent,allowed_output_paths,expected_output,completion_test,status,code_version,skill_version) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(sid('batch','diagram',child),'DIAGRAM_EXTRACTION','LEAF',child,RUN_AGENT['diagram'],'catalog/v2/evidence;catalog/authoritative_catalogue.sqlite3','Exact active diagram and all visible source rows','requested assembly identity and row/callout/image counts reconcile','NOT_STARTED','3.1.0','S2-S4-v1'))
   for old in c.execute("SELECT catalogue_leaf_id FROM catalogue_leaves WHERE parent_leaf_id=? AND leaf_type='DIAGRAM'",(leaf_id,)).fetchall():
    if old['catalogue_leaf_id'] not in wanted:c.execute("DELETE FROM image_observations WHERE catalogue_leaf_id=?",(old['catalogue_leaf_id'],));c.execute("DELETE FROM visible_source_rows WHERE catalogue_leaf_id=?",(old['catalogue_leaf_id'],));c.execute("UPDATE catalogue_leaves SET status='RETIRED_SOURCE',exception_code='ABSENT_FROM_REFRESHED_SELECTOR_SET' WHERE catalogue_leaf_id=?",(old['catalogue_leaf_id'],))
  for s in parsed['selectors']:
   target=sid('leaf',ctx['variation_id'],'DIAGRAM',s['url']);insert_image(c,(leaf_id,None),snap,page_sha,None,None,{'url':s['image_url'],'alt':s['image_alt'],'role':'DIAGRAM_SELECTOR_THUMBNAIL','locator':s['locator'],'ordinal':s['ordinal'],'association':'ASSOCIATION_FROM_ASSEMBLY_SELECTOR'},{'target_diagram_leaf_id':target,'assembly':s['assembly']})
  if parsed['active'] and parsed['active']['image']:insert_image(c,(leaf_id,None),snap,page_sha,None,None,parsed['active']['image'],{'assembly':parsed['active']['assembly']})
  ctx=leaf_context(c,leaf_id);leafdict=dict(ctx);leafdict['catalogue_page_url']=ctx['catalogue_page_url'] or ctx['source_url'];leafdict['diagram_page_url']=ctx['source_url'] if ctx['leaf_type']=='DIAGRAM' or parsed['active'] else None;leafdict['diagram_id']=ctx['diagram_id'] or (str(parsed['active']['assembly']) if parsed['active'] else None);leafdict['diagram_title_source']=ctx['diagram_title_source'] or (parsed['active']['title'] if parsed['active'] else None)
  for r in parsed['rows']:insert_row(c,leafdict,snap,page_sha,r,run)
  actual=c.execute('SELECT count(*) FROM visible_source_rows WHERE catalogue_leaf_id=?',(leaf_id,)).fetchone()[0];recs=c.execute('SELECT count(*) FROM part_records WHERE catalogue_leaf_id=?',(leaf_id,)).fetchone()[0];obs=c.execute('SELECT count(*) FROM image_observations WHERE catalogue_leaf_id=?',(leaf_id,)).fetchone()[0]
  if actual!=len(parsed['rows']) or recs!=actual:raise RuntimeError(f'committed row reconciliation failed expected={len(parsed["rows"])} staged={actual} records={recs}')
  c.execute("""UPDATE catalogue_leaves SET current_snapshot_id=?,status='EXTRACTED',source_structure_status='LEAF_STRUCTURE_VALIDATED',expected_source_row_count=?,extracted_source_row_count=?,expected_callout_count=?,extracted_callout_count=?,expected_image_count=?,observed_image_count=?,processing_completed_at=?,evidence_notes=? WHERE catalogue_leaf_id=?""",(snap,len(parsed['rows']),recs,parsed['structural']['callout_markers'],len({(r['anchor'],r['ordinal']) for r in parsed['rows'] if r['section']=='CALLOUT_SUMMARY'}),obs,obs,now(),json.dumps({'structural':parsed['structural'],'raw_path':raw.relative_to(CAT).as_posix()}),leaf_id));c.execute("UPDATE batches SET status='EXTRACTED',completed_at=?,checkpoint_path=? WHERE batch_id=?",(now(),raw.relative_to(CAT).as_posix(),batch));c.commit()
 except Exception as e:c.rollback();c.execute("UPDATE catalogue_leaves SET status='QA_FAILED',exception_code='SOURCE_OR_PARSER_FAILURE',evidence_notes=? WHERE catalogue_leaf_id=?",(json.dumps({'error':repr(e)}),leaf_id));c.execute("UPDATE batches SET status='QA_FAILED',last_error=?,completed_at=? WHERE batch_id=?",(repr(e),now(),batch));c.commit();raise
 finally:c.close()
def crawl(kind,limit=None,retry=False,refresh=False):
 init_db();c=con(True);types={'categories':'CATEGORY_INDEX','diagrams':'DIAGRAM'};lt=types[kind];states="('NOT_STARTED','QA_FAILED')" if retry else "('NOT_STARTED')";q=f"SELECT catalogue_leaf_id FROM catalogue_leaves WHERE leaf_type=? AND status IN {states} ORDER BY variation_id,catalogue_leaf_id"+(" LIMIT ?" if limit else '');rows=c.execute(q,(lt,limit) if limit else (lt,)).fetchall();c.close()
 errors=[]
 for r in rows:
  try:process_leaf(r['catalogue_leaf_id'],refresh)
  except Exception as e:errors.append({'catalogue_leaf_id':r['catalogue_leaf_id'],'error':repr(e)})
 export_scope()
 if errors:raise RuntimeError(json.dumps({'phase':kind,'failed_leaves':len(errors),'failures':errors[:50]}))
def parse_product_detail(text):
 pm=re.search(r'\*\s+Part Number:\s*([^\n]+)',text,re.I);title=re.search(r'^#{1,3}\s+(.+?)(?:\s+-\s+Mopar|\s*\()',text,re.M);marker='**Genuine Mopar Parts**' in text or 'Genuine Mopar Parts' in text
 complete=bool(pm and title and marker);body=text[:text.find('**Genuine Mopar Parts**')] if '**Genuine Mopar Parts**' in text else text
 fields={}
 for label,key in [('Description','description'),('Replaces','replaces'),('Other Names','other_names')]:
  m=re.search(r'\*\s+'+label+r':\s*([^\n]+)',text,re.I);fields[key]=clean(m.group(1)) if m else None
 fitlines=re.findall(r'(?m)^20\d{2}\s+(?:Chrysler|Dodge)\s+[^\n]+$',text);images=[]
 for i,m in enumerate(re.finditer(r'!\[Image\s+\d+:\s*([^\]]*)\]\((https?://[^)\s]+)\)',body),1):
  u=m.group(2)
  if 'cdn-product-images.' in u or 'cdn-illustrations.' in u:images.append({'url':u,'alt':m.group(1),'role':'PRODUCT_GALLERY_IMAGE','locator':f'markdown:char:{m.start()}-{m.end()}','ordinal':i,'association':'ASSOCIATION_FROM_PRODUCT_GALLERY'})
 return {'complete':complete,'pn':clean(pm.group(1)) if pm else None,'name':clean(title.group(1)) if title else None,'description':fields['description'],'replaces':fields['replaces'],'other_names':fields['other_names'],'fitment':' || '.join(fitlines) if fitlines else None,'images':images,'marker':marker}
def crawl_products(limit=None,retry=False,refresh=False):
 init_db();c=con(True);states="('NOT_STARTED','QA_FAILED','SOURCE_RENDERER_PARTIAL')" if retry else "('NOT_STARTED')";q=f"SELECT product_source_id FROM product_sources WHERE status IN {states} ORDER BY product_source_id"+(" LIMIT ?" if limit else '');ids=[x[0] for x in c.execute(q,(limit,) if limit else ())];c.close()
 for psid in ids:
  c=con();p=c.execute('SELECT * FROM product_sources WHERE product_source_id=?',(psid,)).fetchone();run=run_id('product');batch=sid('batch','product',psid);c.execute("UPDATE product_sources SET status='IN_PROGRESS',processing_started_at=? WHERE product_source_id=?",(now(),psid));c.execute("UPDATE batches SET status='IN_PROGRESS',attempt_count=attempt_count+1,started_at=?,last_error=NULL WHERE batch_id=?",(now(),batch));c.commit()
  try:
   http,text,final,renderer,_=source_get(p['source_url'],refresh);d=parse_product_detail(text)
   if not d['complete'] and renderer=='RECOVERY_CACHE':
    http,text,final,renderer,_=source_get(p['source_url'],True);d=parse_product_detail(text)
   structure='PRODUCT_DETAIL_COMPLETE' if d['complete'] else 'PRODUCT_DETAIL_PARTIAL';c.execute('BEGIN IMMEDIATE');snap,page_sha,raw=snapshot(c,p['source_url'],text,http,final,renderer,run,structure);c.execute('DELETE FROM image_observations WHERE product_source_id=?',(psid,));recs=c.execute('SELECT r.* FROM part_records r JOIN record_product_sources x ON x.record_id=r.record_id WHERE x.product_source_id=?',(psid,)).fetchall()
   if not d['complete']:
    c.execute("UPDATE product_sources SET current_snapshot_id=?,status='SOURCE_RENDERER_PARTIAL',structure_status=?,processing_completed_at=?,exception_code='IMAGE_ENUMERATION_INCOMPLETE',evidence_notes=? WHERE product_source_id=?",(snap,structure,now(),json.dumps({'raw_path':raw.relative_to(CAT).as_posix(),'reason':'required product-detail markers absent'}),psid));c.execute("UPDATE batches SET status='QA_FAILED',completed_at=?,last_error='IMAGE_ENUMERATION_INCOMPLETE',checkpoint_path=? WHERE batch_id=?",(now(),raw.relative_to(CAT).as_posix(),batch));c.commit();continue
   for r in recs:
    prov=json.loads(r['field_provenance_json']);pn=r['oem_part_number_source'];name=r['part_name_source'];exc=r['exception_code']
    if pn=='PART_NUMBER_NOT_DISPLAYED' and d['pn']:pn=d['pn'];prov['oem_part_number_source']='PRODUCT_DETAIL';exc=None if exc=='PART_NUMBER_NOT_DISPLAYED' else exc
    if name=='PART_NAME_NOT_DISPLAYED' and d['name']:name=d['name'];prov['part_name_source']='PRODUCT_DETAIL'
    c.execute("UPDATE part_records SET oem_part_number_source=?,oem_part_number_normalized=?,part_name_source=?,part_name_normalized=?,part_description_source=COALESCE(part_description_source,?),superseded_part_number_source=COALESCE(?,superseded_part_number_source),fitment_notes_source=COALESCE(?,fitment_notes_source),fitment_normalized=COALESCE(?,fitment_normalized),exception_code=?,field_provenance_json=? WHERE record_id=?",(pn,norm(pn),name,norm(name),d['description'],d['replaces'],d['fitment'],norm(d['fitment']) if d['fitment'] else None,exc,json.dumps(prov),r['record_id']))
   for img in d['images']:
    obs=insert_image(c,(None,psid),snap,page_sha,None,None,img)
    for r in recs:c.execute("INSERT OR IGNORE INTO image_observation_records VALUES(?,?,?)",(obs,r['record_id'],'EXACT_PRODUCT_SOURCE_ASSOCIATION'))
   noimg='NO_OEM_IMAGE_AVAILABLE' if not d['images'] else None;c.execute("UPDATE product_sources SET current_snapshot_id=?,status='EXTRACTED_COMPLETE',structure_status=?,displayed_part_number_source=?,part_name_source=?,description_source=?,superseded_part_number_source=?,fitment_source=?,expected_image_count=?,observed_image_count=?,no_image_disposition=?,processing_completed_at=?,exception_code=NULL,evidence_notes=? WHERE product_source_id=?",(snap,structure,d['pn'],d['name'],d['description'],d['replaces'],d['fitment'],len(d['images']),len(d['images']),noimg,now(),json.dumps({'raw_path':raw.relative_to(CAT).as_posix(),'no_image_basis':'complete product structure with zero content image references' if noimg else None}),psid));c.execute("UPDATE batches SET status='EXTRACTED',completed_at=?,checkpoint_path=? WHERE batch_id=?",(now(),raw.relative_to(CAT).as_posix(),batch));c.commit()
  except Exception as e:c.rollback();c.execute("UPDATE product_sources SET status='QA_FAILED',exception_code='SOURCE_OR_PARSER_FAILURE',evidence_notes=?,processing_completed_at=? WHERE product_source_id=?",(json.dumps({'error':repr(e)}),now(),psid));c.execute("UPDATE batches SET status='QA_FAILED',completed_at=?,last_error=? WHERE batch_id=?",(now(),repr(e),batch));c.commit();raise
  finally:c.close()
 export_scope()
def classify_image_bytes(data):
 if len(data)<100:raise ValueError('zero/tiny image payload')
 with Image.open(io.BytesIO(data)) as im:
  im.load();fmt=im.format or 'UNKNOWN';mime=Image.MIME.get(fmt) or mimetypes.guess_type('x.'+fmt.lower())[0] or 'application/octet-stream';w,h=im.size;rgba=im.convert('RGBA');alpha=rgba.getchannel('A');alpha_present=1 if alpha.getextrema()!=(255,255) else 0;rgb=rgba.convert('RGB');bbox=ImageChops.difference(rgb,Image.new('RGB',rgb.size,rgb.getpixel((0,0)))).getbbox();pixel=sha(rgba.tobytes());placeholder=[]
  if w<32 or h<32:placeholder.append('TINY_DIMENSIONS')
  if bbox is None:placeholder.append('UNIFORM_PIXELS')
  if alpha.getbbox() is None:placeholder.append('FULLY_TRANSPARENT')
  return {'format':fmt,'mime':mime,'width':w,'height':h,'pixel_sha256':pixel,'alpha':alpha_present,'placeholder':'PLACEHOLDER_SUSPECT' if placeholder else 'CONTENT_IMAGE','placeholder_evidence':placeholder}
def download_image(url):
 r=requests.get(url,timeout=180,headers={'User-Agent':'Hermes-Mopar-Catalogue-Audit/3.0'});r.raise_for_status();data=r.content;meta=classify_image_bytes(data);return data,meta,r
def acquire_images(limit=None,workers=6):
 c=con(True);q="SELECT DISTINCT image_source_url FROM image_observations WHERE acquisition_status='NOT_STARTED' ORDER BY image_source_url"+(" LIMIT ?" if limit else '');urls=[x[0] for x in c.execute(q,(limit,) if limit else ())];c.close();run=run_id('image')
 def one(url):return url,*download_image(url)
 with ThreadPoolExecutor(max_workers=workers) as ex:
  futs={ex.submit(one,u):u for u in urls}
  for f in as_completed(futs):
   url=futs[f];c=con()
   try:
    _,data,m,r=f.result();h=sha(data);ext={'PNG':'png','WEBP':'webp','JPEG':'jpg','GIF':'gif'}.get(m['format'],m['format'].lower());path=CAT/'v2'/'images'/h[:2]/f'{h}.{ext}';path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
     existing=path.read_bytes()
     if sha(existing)!=h or classify_image_bytes(existing)['pixel_sha256']!=m['pixel_sha256']:raise ValueError('existing content-addressed asset corrupt')
    else:path.write_bytes(data)
    c.execute('''INSERT INTO image_assets VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(image_sha256) DO UPDATE SET local_image_path=excluded.local_image_path''',(h,path.relative_to(CAT).as_posix(),m['mime'],m['format'],len(data),m['width'],m['height'],m['pixel_sha256'],m['alpha'],'DECODE_OK',m['placeholder'],json.dumps(m['placeholder_evidence']),now(),run))
    c.execute("UPDATE image_observations SET image_final_resolved_url=?,acquisition_status='ACQUIRED',image_sha256=?,http_status=?,http_content_type=?,response_etag=?,response_last_modified=?,acquired_at=?,acquisition_run_id=?,exception_code=NULL WHERE image_source_url=?",(r.url,h,r.status_code,r.headers.get('Content-Type'),r.headers.get('ETag'),r.headers.get('Last-Modified'),now(),run,url));c.commit()
   except Exception as e:c.execute("UPDATE image_observations SET acquisition_status='FAILED',exception_code='IMAGE_ACQUISITION_FAILURE',evidence_notes=? WHERE image_source_url=?",(json.dumps({'error':repr(e)}),url));c.commit()
   finally:c.close()
def verify_images(limit=None,workers=4):
 c=con(True);q="""SELECT DISTINCT o.image_source_url,o.image_sha256,a.local_image_path,a.image_byte_size,a.image_width,a.image_height,a.pixel_sha256,a.placeholder_classification FROM image_observations o JOIN image_assets a ON a.image_sha256=o.image_sha256 WHERE o.acquisition_status='ACQUIRED' AND o.verification_status='NOT_STARTED' ORDER BY o.image_source_url"""+(" LIMIT ?" if limit else '');rows=c.execute(q,(limit,) if limit else ()).fetchall();c.close();run=run_id('verify')
 def one(row):
  path=CAT/row['local_image_path'];local=path.read_bytes();lm=classify_image_bytes(local)
  if sha(local)!=row['image_sha256'] or len(local)!=row['image_byte_size'] or lm['width']!=row['image_width'] or lm['height']!=row['image_height'] or lm['pixel_sha256']!=row['pixel_sha256']:raise ValueError('local asset integrity mismatch')
  data,rm,r=download_image(row['image_source_url']);return sha(data),rm,r
 with ThreadPoolExecutor(max_workers=workers) as ex:
  futs={ex.submit(one,r):r for r in rows}
  for f in as_completed(futs):
   row=futs[f];c=con()
   try:
    h,m,r=f.result();ok=h==row['image_sha256'];role=c.execute('SELECT image_role FROM image_observations WHERE image_source_url=? LIMIT 1',(row['image_source_url'],)).fetchone()[0];state=('DIAGRAM_VERIFIED_BYTE_EXACT' if 'DIAGRAM' in role else 'IMAGE_VERIFIED_BYTE_EXACT') if ok else 'SOURCE_IMAGE_CHANGED';exc=None if ok else 'SOURCE_IMAGE_CHANGED';c.execute("UPDATE image_observations SET verification_status=?,verified_at=?,verification_run_id=?,exception_code=? WHERE image_source_url=?",(state,now(),run,exc,row['image_source_url']));c.commit()
   except Exception as e:c.execute("UPDATE image_observations SET verification_status='SOURCE_LINK_BROKEN',verified_at=?,verification_run_id=?,exception_code='IMAGE_VERIFICATION_FAILURE',evidence_notes=? WHERE image_source_url=?",(now(),run,json.dumps({'error':repr(e)}),row['image_source_url']));c.commit()
   finally:c.close()
def rebuild_fts(c=None):
 own=c is None;c=c or con();c.execute("INSERT INTO catalogue_fts(catalogue_fts) VALUES('delete-all')");c.execute('''INSERT INTO catalogue_fts(rowid,record_id,variation_source_label,category_source_label,subcategory_source_label,diagram_title_source,diagram_callout_source,part_name_source,part_description_source,oem_part_number_source,fitment_notes_source) SELECT row_number() OVER(ORDER BY record_id),record_id,variation_source_label,category_source_label,subcategory_source_label,diagram_title_source,diagram_callout_source,part_name_source,part_description_source,oem_part_number_source,fitment_notes_source FROM part_records''');c.commit();
 if own:c.close()
def export_scope(c=None):
 own=c is None;c=c or con();out=CAT/'v2'/'manifests';out.mkdir(parents=True,exist_ok=True);data={'generated_at':now(),'schema_version':3,'variations':[]}
 for v in c.execute('SELECT * FROM variations ORDER BY variation_id'):
  leaves=[dict(x) for x in c.execute("SELECT catalogue_leaf_id,leaf_type,diagram_id,diagram_title_source,assembly_number,source_url,status,expected_source_row_count,extracted_source_row_count,expected_callout_count,extracted_callout_count,expected_image_count,observed_image_count,exception_code FROM catalogue_leaves WHERE variation_id=? AND status!='RETIRED_SOURCE' ORDER BY leaf_type,source_url",(v['variation_id'],))];data['variations'].append({'variation':dict(v),'leaves':leaves})
 (out/'master_expected_scope.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 if own:c.close()
def export_all():
 c=con();rebuild_fts(c);out=CAT/'v2'/'exports';out.mkdir(parents=True,exist_ok=True)
 specs={'variations.csv':'SELECT * FROM variations ORDER BY variation_id','taxonomy_nodes.csv':'SELECT * FROM taxonomy_nodes ORDER BY variation_id,node_type,ordinal,node_id','leaves.csv':"SELECT * FROM catalogue_leaves WHERE status!='RETIRED_SOURCE' ORDER BY variation_id,leaf_type,source_url",'part_records.csv':'SELECT * FROM part_records ORDER BY variation_id,catalogue_leaf_id,source_section,source_row_anchor,source_occurrence_ordinal','visible_source_rows.csv':'SELECT * FROM visible_source_rows ORDER BY catalogue_leaf_id,source_section,source_row_anchor,source_occurrence_ordinal','image_provenance.csv':'SELECT o.*,a.local_image_path,a.image_mime_type,a.image_format,a.image_byte_size,a.image_width,a.image_height,a.pixel_sha256,a.placeholder_classification FROM image_observations o LEFT JOIN image_assets a ON a.image_sha256=o.image_sha256 ORDER BY o.image_observation_id','product_sources.csv':'SELECT * FROM product_sources ORDER BY product_source_id','defects.csv':'SELECT * FROM defects ORDER BY created_at,defect_id'}
 for fn,q in specs.items():
  rows=c.execute(q);cols=[d[0] for d in rows.description]
  with (out/fn).open('w',newline='',encoding='utf-8') as f:w=csv.writer(f);w.writerow(cols);w.writerows(rows)
 export_scope(c);c.commit();c.close();status()
def status():
 c=con(True);d={'generated_at':now(),'schema_version':c.execute("SELECT value FROM project_meta WHERE key='schema_version'").fetchone()[0],'vehicles':c.execute('SELECT count(*) FROM vehicles').fetchone()[0],'variations':c.execute('SELECT count(*) FROM variations').fetchone()[0],'taxonomy_nodes':c.execute('SELECT count(*) FROM taxonomy_nodes').fetchone()[0],'leaves_by_type_status':{f'{x[0]}:{x[1]}':x[2] for x in c.execute('SELECT leaf_type,status,count(*) FROM catalogue_leaves GROUP BY leaf_type,status')},'source_rows':c.execute('SELECT count(*) FROM visible_source_rows').fetchone()[0],'records':c.execute('SELECT count(*) FROM part_records').fetchone()[0],'product_sources_by_status':{x[0]:x[1] for x in c.execute('SELECT status,count(*) FROM product_sources GROUP BY status')},'image_observations':c.execute('SELECT count(*) FROM image_observations').fetchone()[0],'image_assets':c.execute('SELECT count(*) FROM image_assets').fetchone()[0],'fts_rows':c.execute('SELECT count(*) FROM catalogue_fts').fetchone()[0]};c.close();(CAT/'v2'/'exports').mkdir(parents=True,exist_ok=True);(CAT/'v2'/'exports'/'status.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8');print(json.dumps(d,indent=2))
def main():
 p=argparse.ArgumentParser();sp=p.add_subparsers(dest='cmd',required=True)
 for n in ('init','discover','crawl-categories','crawl-diagrams','crawl-products','acquire-images','verify-images','export','status'):q=sp.add_parser(n);q.add_argument('--limit',type=int);q.add_argument('--refresh',action='store_true');q.add_argument('--retry-failed',action='store_true')
 a=p.parse_args()
 if a.cmd=='init':init_db()
 elif a.cmd=='discover':discover(a.refresh)
 elif a.cmd=='crawl-categories':crawl('categories',a.limit,a.retry_failed,a.refresh)
 elif a.cmd=='crawl-diagrams':crawl('diagrams',a.limit,a.retry_failed,a.refresh)
 elif a.cmd=='crawl-products':crawl_products(a.limit,a.retry_failed,a.refresh)
 elif a.cmd=='acquire-images':acquire_images(a.limit)
 elif a.cmd=='verify-images':verify_images(a.limit)
 elif a.cmd=='export':export_all()
 elif a.cmd=='status':status()
if __name__=='__main__':main()
