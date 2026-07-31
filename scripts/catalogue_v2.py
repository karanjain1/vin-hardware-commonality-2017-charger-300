#!/usr/bin/env python
"""Authoritative six-variation MoparAmerica catalogue builder.

Scope is controlled by catalog/manifests/variation_manifest.json. Mopar page
requests are serialized at ten seconds. Image CDN work may run concurrently.
All writes are idempotent SQLite upserts and per-leaf checkpoints.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,io,json,mimetypes,re,sqlite3,time,uuid
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
CAT=ROOT/'catalog'; DB=CAT/'authoritative_catalogue.sqlite3'; SCHEMA=CAT/'schema_v2.sql'
MANIFEST=CAT/'manifests'/'variation_manifest.json'; EVIDENCE=CAT/'v2'/'evidence'; RAW=EVIDENCE/'source'
IMAGES=CAT/'v2'/'images'; EXPORTS=CAT/'v2'/'exports'; CHECKPOINTS=CAT/'v2'/'checkpoints'; LOGS=CAT/'v2'/'logs'
for p in (RAW,IMAGES,EXPORTS,CHECKPOINTS,LOGS):p.mkdir(parents=True,exist_ok=True)
UA='HermesMoparCatalogue/2.0 (+auditable public OEM catalogue indexing)'; S=requests.Session();S.headers.update({'User-Agent':UA})
LAST=[0.0]; CODE_VERSION='2.0.0'; SKILL_VERSION='1.0.0'; RENDERER='https://r.jina.ai/http://www.moparamerica.com/'
TERMINAL={'EXTRACTED','SOURCE_VERIFIED','IMAGE_ACQUIRED','IMAGE_VERIFIED','FITMENT_AUDITED','COMPLETENESS_CHECKED','INTEGRITY_CHECKED','QA_PASSED'}

def now():return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
def h(b):return hashlib.sha256(b).hexdigest()
def sid(prefix,*parts):return prefix+'-'+h('\x1f'.join(str(x or '') for x in parts).encode())[:24]
def norm(s):return re.sub(r'[^A-Z0-9]','',str(s or '').upper())
def clean_label(s):return re.sub(r'\s+',' ',re.sub(r'[*_`]+','',s or '')).strip()
def slug_label(s):return s.replace('--',' / ').replace('-',' ').title()
def lf_bytes(text):return text.replace('\r\n','\n').replace('\r','\n').encode('utf-8')
def con():
 c=sqlite3.connect(DB,timeout=120);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c

def init_db():
 c=con();c.executescript(SCHEMA.read_text(encoding='utf-8'));meta={'schema_version':'2','code_version':CODE_VERSION,'source':'MoparAmerica public OEM catalogue','scope':'2017 Chrysler 300C and Dodge Challenger; exactly three variations each','authoritative':'true'}
 for k,v in meta.items():c.execute('INSERT OR REPLACE INTO project_meta VALUES(?,?)',(k,v))
 m=json.loads(MANIFEST.read_text(encoding='utf-8'))
 for vehicle in m['vehicles']:
  c.execute('INSERT INTO vehicles VALUES(?,?,?,?,?,?) ON CONFLICT(vehicle_id) DO UPDATE SET year=excluded.year,make_source=excluded.make_source,model_source=excluded.model_source,project_label=excluded.project_label,source_label_note=excluded.source_label_note',(vehicle['vehicle_id'],vehicle['year'],vehicle['make_source'],vehicle['model_source'],vehicle['project_label'],vehicle.get('source_label_note')))
  for v in vehicle['variations']:
   c.execute('''INSERT INTO variations(variation_id,vehicle_id,variation_source_label,trim_source,engine_source,route_slug,source_url,expected_category_links,validation_title,validation_status,evidence_notes)
    VALUES(?,?,?,?,?,?,?,?,?,'NOT_STARTED',?) ON CONFLICT(variation_id) DO UPDATE SET vehicle_id=excluded.vehicle_id,variation_source_label=excluded.variation_source_label,trim_source=excluded.trim_source,engine_source=excluded.engine_source,route_slug=excluded.route_slug,source_url=excluded.source_url,expected_category_links=excluded.expected_category_links,validation_title=excluded.validation_title''',(v['variation_id'],vehicle['vehicle_id'],v['variation_source_label'],v['trim_source'],v['engine_source'],v['route_slug'],v['source_url'],v['expected_category_links_at_resolution'],v['validation_title'],json.dumps({'derivation_status':v['derivation_status']})))
 c.commit();c.close()

def event(c,run,stage,status,variation=None,leaf=None,http=None,message=None):c.execute('INSERT INTO crawl_events(occurred_at,run_id,stage,variation_id,catalogue_leaf_id,status,http_status,message) VALUES(?,?,?,?,?,?,?,?)',(now(),run,stage,variation,leaf,status,http,message))
def renderer_url(original):
 if not original.startswith('https://www.moparamerica.com/'):raise ValueError(original)
 return RENDERER+original.split('https://www.moparamerica.com/',1)[1]
def source_get(original,tries=5):
 u=renderer_url(original);last=None
 for attempt in range(tries):
  delay=max(0,10-(time.monotonic()-LAST[0]))
  if delay:time.sleep(delay)
  LAST[0]=time.monotonic();r=S.get(u,timeout=180);t=r.text;last=r
  blocked='Just a moment' in t or len(t)<900 or 'Page Not Found' in t[:1000]
  if r.status_code==200 and not blocked:return r,t,u
  if r.status_code not in (200,429,503):break
  time.sleep(10*(attempt+1))
 title_match=re.search(r'^Title:\s*(.+)$',last.text,re.M) if last else None
 title=title_match.group(1) if title_match else ''
 raise RuntimeError(f'source retrieval failed: {original} http={last.status_code if last else None} bytes={len(last.content) if last else 0} title={title}')
def save_raw(path,text):path.parent.mkdir(parents=True,exist_ok=True);b=lf_bytes(text);path.write_bytes(b);return h(b),h(lf_bytes(text))

def category_links(text,route):
 found={};rx=re.compile(r'\[([^\]]+)\]\(https://www\.moparamerica\.com/'+re.escape(route)+r'/([^\s)"?#/]+)(?:\s+"[^"]*")?\)')
 for label,slug in rx.findall(text):
  if slug.startswith(('oem-parts','search','cart','account')):continue
  found.setdefault(slug,clean_label(label) or slug_label(slug))
 # Nested links can hide labels; preserve every route-bound slug.
 for slug in re.findall(r'https://www\.moparamerica\.com/'+re.escape(route)+r'/([^\s)"?#/]+)',text):
  if not slug.startswith(('oem-parts','search','cart','account')):found.setdefault(slug,slug_label(slug))
 return list(found.items())

def split_taxonomy(slug,label):
 bits=slug.split('--',1)
 if len(bits)==2:
  cat_slug,sub_slug=bits; cat_label=slug_label(cat_slug);sub_label=label if label and '/' not in label else slug_label(sub_slug)
 else:cat_slug=slug;sub_slug=None;cat_label=label or slug_label(slug);sub_label=None
 return cat_slug,cat_label,sub_slug,sub_label

def discover(refresh=False):
 init_db();c=con();run=sid('run','discover',now())
 for v in c.execute('SELECT * FROM variations ORDER BY variation_id').fetchall():
  raw=RAW/v['variation_id']/'route.md'
  try:
   if raw.exists() and not refresh and v['validation_status']=='VALIDATED':text=raw.read_text(encoding='utf-8');http=200;ru=renderer_url(v['source_url'])
   else:
    r,text,ru=source_get(v['source_url']);http=r.status_code;save_raw(raw,text)
   links=category_links(text,v['route_slug']);title=(re.search(r'^Title:\s*(.+)$',text,re.M) or ['',''])[1]
   if title!=v['validation_title'] or len(links)!=v['expected_category_links']:raise RuntimeError(f'route taxonomy mismatch title={title!r} categories={len(links)} expected={v["expected_category_links"]}')
   b=raw.read_bytes();c.execute("UPDATE variations SET validation_status='VALIDATED',source_accessed_at=?,source_byte_sha256=?,source_lf_sha256=?,raw_path=?,evidence_notes=? WHERE variation_id=?",(now(),h(b),h(lf_bytes(b.decode('utf-8'))),raw.relative_to(CAT).as_posix(),json.dumps({'category_links':len(links),'title':title}),v['variation_id']))
   for ordinal,(slug,label) in enumerate(links,1):
    cat_slug,cat_label,sub_slug,sub_label=split_taxonomy(slug,label);cat_id=sid('cat',v['variation_id'],cat_slug);src=v['source_url']+'/'+slug
    c.execute('''INSERT INTO taxonomy_nodes(node_id,variation_id,parent_node_id,node_type,source_label,normalized_label,source_slug,source_url,ordinal,discovery_status,source_accessed_at) VALUES(?,?,NULL,'CATEGORY',?,?,?,?,?,'DISCOVERED',?) ON CONFLICT(node_id) DO UPDATE SET source_label=excluded.source_label,source_url=excluded.source_url,ordinal=excluded.ordinal''',(cat_id,v['variation_id'],cat_label,clean_label(cat_label).lower(),cat_slug,v['source_url']+'/'+cat_slug,ordinal,now()))
    sub_id=None
    if sub_slug:
     sub_id=sid('sub',v['variation_id'],slug);c.execute('''INSERT INTO taxonomy_nodes(node_id,variation_id,parent_node_id,node_type,source_label,normalized_label,source_slug,source_url,ordinal,discovery_status,source_accessed_at) VALUES(?,?,?,'SUBCATEGORY',?,?,?,?,?,'DISCOVERED',?) ON CONFLICT(node_id) DO UPDATE SET source_label=excluded.source_label,source_url=excluded.source_url,ordinal=excluded.ordinal''',(sub_id,v['variation_id'],cat_id,sub_label,clean_label(sub_label).lower(),slug,src,ordinal,now()))
    leaf=sid('leaf',v['variation_id'],'CATEGORY_INDEX',src);c.execute('''INSERT INTO catalogue_leaves(catalogue_leaf_id,variation_id,category_id,subcategory_id,leaf_type,source_url,renderer_url,status,evidence_notes) VALUES(?,?,?,?, 'CATEGORY_INDEX',?,?, 'NOT_STARTED',?) ON CONFLICT(catalogue_leaf_id) DO UPDATE SET category_id=excluded.category_id,subcategory_id=excluded.subcategory_id,source_url=excluded.source_url''',(leaf,v['variation_id'],cat_id,sub_id,src,renderer_url(src),json.dumps({'ordinal':ordinal})))
    batch=sid('batch',leaf,'category');c.execute("INSERT INTO batches(batch_id,variation_id,catalogue_leaf_id,stage,responsible_agent,allowed_output_prefix,status,code_version,skill_version) VALUES(?,?,?,'CATEGORY_EXTRACTION','AGENT_3_PART_RECORD_EXTRACTION','catalog/v2/','NOT_STARTED',?,?) ON CONFLICT(batch_id) DO NOTHING",(batch,v['variation_id'],leaf,CODE_VERSION,SKILL_VERSION))
   event(c,run,'DISCOVER','VALIDATED',v['variation_id'],http=http,message=f'categories={len(links)}');c.commit()
  except Exception as e:
   c.execute("UPDATE variations SET validation_status='BLOCKED_RETRYABLE',evidence_notes=? WHERE variation_id=?",(json.dumps({'error':str(e)}),v['variation_id']));event(c,run,'DISCOVER','BLOCKED_RETRYABLE',v['variation_id'],message=str(e));c.commit();raise
 c.close();write_scope_manifest();return run

def assembly_selectors(text,page_url):
 out={}
 rx=re.compile(r'\[!\[Image \d+: ([^\]]*)\]\((https?://[^)]+)\)([^\]]*)\]\((https://www\.moparamerica\.com/[^)\s]+\?assembly=(\d+))(?:\s+"Diagram\s+\d+:\s*([^"]+)")?\)')
 for alt,img,inside,url,num,title in rx.findall(text):
  n=int(num);out[n]={'assembly_no':n,'title':clean_label(title or re.sub(r'^\s*\d+\.\s*','',inside) or alt),'source_url':url,'image_url':img}
 rx2=re.compile(r'\[([^\]]+)\]\((https://www\.moparamerica\.com/[^)]+\?assembly=(\d+))\)\s*\n\s*\[!\[Image \d+: ([^\]]*)\]\((https?://[^)]+)\)')
 for title,url,num,alt,img in rx2.findall(text):out.setdefault(int(num),{'assembly_no':int(num),'title':clean_label(title or alt),'source_url':url,'image_url':img})
 if not out:
  # Direct #0 image not nested in a product link is the single full diagram.
  m=re.search(r'(?m)^!\[Image \d+: ([^\]]*?#0)\]\((https://cdn-illustrations\.revolutionparts\.io/[^)]+)\)',text)
  if m:
   heading=(re.search(r'^#\s+(.+)$',text,re.M) or ['',m.group(1)])[1];out[0]={'assembly_no':0,'title':clean_label(heading),'source_url':page_url,'image_url':m.group(2)}
 return [out[k] for k in sorted(out)]

def product_image_map(text):
 out={}
 rx=re.compile(r'\[!\[Image \d+: ([^\]]*)\]\((https?://[^)]+)\)\]\((https://www\.moparamerica\.com/oem-parts/[^)\s]+)(?:\s+"[^"]*")?\)')
 for alt,img,url in rx.findall(text):out.setdefault(url,[]).append((img,alt))
 return out

def all_product_urls(text):return list(dict.fromkeys(re.findall(r'https://www\.moparamerica\.com/oem-parts/[^\s)"<>]+',text)))
def product_cards(text):
 urls=all_product_urls(text);images=product_image_map(text);cards={}
 bold={u:clean_label(name) for name,u in re.findall(r'\*\*\[([^\]]+)\]\((https://www\.moparamerica\.com/oem-parts/[^)\s]+)(?:\s+"[^"]*")?\)\*\*',text)}
 for url in urls:
  poses=[m.start() for m in re.finditer(re.escape(url),text)];pos=poses[-1] if poses else 0;block=text[max(0,pos-700):min(len(text),pos+1800)]
  pn='PART_NUMBER_NOT_DISPLAYED'
  link_matches=list(re.finditer(r'\[([A-Za-z0-9][A-Za-z0-9 -]{4,29})\]\('+re.escape(url)+r'(?:\s+"([^"]*)")?\)',block))
  pnlink=next((x for x in link_matches if re.fullmatch(r'[A-Za-z0-9-]{5,24}',x.group(1).replace(' ','')) and re.search(r'\d',x.group(1))),None)
  if pnlink:pn=pnlink.group(1).strip()
  if pn=='PART_NUMBER_NOT_DISPLAYED':
   pnm=re.search(r'Part No\s+([A-Za-z0-9-]{5,24})',block,re.I)
   if pnm:pn=pnm.group(1)
  name=bold.get(url)
  if not name:
   names=[]
   for m in re.finditer(r'\[([^\]]+)\]\('+re.escape(url),text):
    x=clean_label(re.sub(r'^\$[\d,.]+\s*','',m.group(1)));x=re.sub(r'\s+Mopar.*$','',x).strip()
    if x and not re.fullmatch(r'[A-Za-z0-9-]{5,24}',x):names.append(x)
   name=max(names,key=len) if names else 'PART_NAME_NOT_DISPLAYED'
  dm=re.search(r'\*\*Description:\*\*\s*([^\n]+)',block,re.I);desc=clean_label(dm.group(1)) if dm else None
  fit=pnlink.group(2).strip() if pnlink and pnlink.lastindex and pnlink.lastindex>=2 and pnlink.group(2) else None
  cards[url]={'part_detail_url':url,'part_name_source':name,'part_description_source':desc,'oem_part_number_source':pn,'fitment_notes_source':fit,'images':images.get(url,[])}
 return cards

def callout_map(text,assembly_no):
 start=re.search(rf'Diagram\s+{assembly_no}:',text) if assembly_no is not None else None
 section=text[start.end():] if start else text
 end=re.search(r'\n\s*No\.\s*\n',section);section=section[:end.start()] if end else section
 marks=list(re.finditer(r'\n\[([^\]]+)\]\(https://www\.moparamerica\.com/#part_row_[^)]+\)',section));out={};empty=[]
 for i,m in enumerate(marks):
  call=clean_label(m.group(1));block=section[m.end():marks[i+1].start() if i+1<len(marks) else len(section)];urls=all_product_urls(block)
  if urls:
   for u in urls:out.setdefault(u,[]).append(call)
  else:empty.append(call)
 return out,empty,len(marks)

def current_context(c,leaf):
 return c.execute('''SELECT l.*,v.vehicle_id,v.variation_source_label,v.route_slug,veh.year,veh.make_source,veh.model_source,t.source_label category_label,t.parent_node_id,st.source_label subcategory_label FROM catalogue_leaves l JOIN variations v ON v.variation_id=l.variation_id JOIN vehicles veh ON veh.vehicle_id=v.vehicle_id JOIN taxonomy_nodes t ON t.node_id=l.category_id LEFT JOIN taxonomy_nodes st ON st.node_id=l.subcategory_id WHERE l.catalogue_leaf_id=?''',(leaf,)).fetchone()
def record_upsert(c,ctx,leaf,card,callout,run):
 pn=card['oem_part_number_source'];rid=sid('rec',ctx['variation_id'],leaf,callout or '',card['part_detail_url']);notes={'source_record_key':[callout,card['part_detail_url']]}
 c.execute('''INSERT INTO part_records(record_id,vehicle_id,year,make_source,model_source,variation_id,variation_source_label,category_id,category_source_label,subcategory_id,subcategory_source_label,catalogue_leaf_id,diagram_id,diagram_title_source,diagram_callout_source,part_name_source,part_name_normalized,part_description_source,oem_part_number_source,oem_part_number_normalized,fitment_notes_source,fitment_normalized,applicability_status,part_detail_url,catalogue_page_url,diagram_page_url,source_accessed_at,extractor_agent,extraction_run_id,extraction_status,source_verification_status,image_verification_status,fitment_audit_status,completeness_status,repository_integrity_status,qa_status,exception_code,evidence_notes)
 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'EXTRACTED','SOURCE_CAPTURED','NOT_STARTED','NOT_STARTED','NOT_STARTED','NOT_STARTED','NOT_STARTED',?,?) ON CONFLICT(record_id) DO UPDATE SET part_name_source=excluded.part_name_source,part_name_normalized=excluded.part_name_normalized,part_description_source=COALESCE(excluded.part_description_source,part_records.part_description_source),oem_part_number_source=excluded.oem_part_number_source,oem_part_number_normalized=excluded.oem_part_number_normalized,fitment_notes_source=COALESCE(excluded.fitment_notes_source,part_records.fitment_notes_source),source_accessed_at=excluded.source_accessed_at,extraction_run_id=excluded.extraction_run_id,exception_code=excluded.exception_code''',(rid,ctx['vehicle_id'],ctx['year'],ctx['make_source'],ctx['model_source'],ctx['variation_id'],ctx['variation_source_label'],ctx['category_id'],ctx['category_label'],ctx['subcategory_id'],ctx['subcategory_label'],leaf,ctx['diagram_id'],ctx['diagram_title_source'],callout,card['part_name_source'],clean_label(card['part_name_source']).lower(),card['part_description_source'],pn,norm(pn),card['fitment_notes_source'],clean_label(card['fitment_notes_source']).lower() if card['fitment_notes_source'] else None,'VEHICLE_FAMILY_CANDIDATE',card['part_detail_url'],ctx['source_url'] if ctx['leaf_type']=='CATEGORY_INDEX' else c.execute('SELECT source_url FROM catalogue_leaves WHERE catalogue_leaf_id=?',(ctx['parent_leaf_id'],)).fetchone()[0],ctx['source_url'] if ctx['leaf_type']=='DIAGRAM' else None,now(),'AGENT_3_PART_RECORD_EXTRACTION',run,'PART_NUMBER_NOT_DISPLAYED' if pn=='PART_NUMBER_NOT_DISPLAYED' else None,json.dumps(notes)))
 return rid

def image_observe(c,leaf,record,role,url,page):
 oid=sid('imgobs',leaf,record or '',role,url);static=role.startswith('STATIC_');c.execute('''INSERT INTO image_observations(image_observation_id,catalogue_leaf_id,record_id,image_role,image_source_url,source_page_url,source_accessed_at,acquisition_status,verification_status,association_status,exception_code,evidence_notes) VALUES(?,?,?,?,?,?,?, ?,?,?,?,?) ON CONFLICT(image_observation_id) DO NOTHING''',(oid,leaf,record,role,url,page,now(),'NOT_APPLICABLE' if static else 'NOT_STARTED','PLACEHOLDER_IMAGE' if role=='STATIC_PLACEHOLDER' else ('NOT_APPLICABLE' if static else 'NOT_STARTED'),'ASSOCIATED_FROM_SOURCE','STATIC_PLACEHOLDER' if role=='STATIC_PLACEHOLDER' else None,json.dumps({})))

def ensure_product_leaf(c,ctx,url):
 leaf=sid('leaf',ctx['variation_id'],'PRODUCT_DETAIL',url);c.execute('''INSERT INTO catalogue_leaves(catalogue_leaf_id,variation_id,category_id,subcategory_id,parent_leaf_id,leaf_type,source_url,renderer_url,status,evidence_notes) VALUES(?,?,?,?,?,'PRODUCT_DETAIL',?,?,'NOT_STARTED',?) ON CONFLICT(catalogue_leaf_id) DO NOTHING''',(leaf,ctx['variation_id'],ctx['category_id'],ctx['subcategory_id'],ctx['catalogue_leaf_id'],url,renderer_url(url),json.dumps({'discovered_from':ctx['catalogue_leaf_id']})));batch=sid('batch',leaf,'product');c.execute("INSERT INTO batches(batch_id,variation_id,catalogue_leaf_id,stage,responsible_agent,allowed_output_prefix,status,code_version,skill_version) VALUES(?,?,?,'PRODUCT_DETAIL_EXTRACTION','AGENT_3_PART_RECORD_EXTRACTION','catalog/v2/','NOT_STARTED',?,?) ON CONFLICT(batch_id) DO NOTHING",(batch,ctx['variation_id'],leaf,CODE_VERSION,SKILL_VERSION))

def process_leaf(c,row,text,raw,run,http):
 ctx=current_context(c,row['catalogue_leaf_id']);cards=product_cards(text);selectors=assembly_selectors(text,row['source_url']);callmap={};empty=[];expected_callouts=0
 if row['leaf_type']=='DIAGRAM':callmap,empty,expected_callouts=callout_map(text,int(row['diagram_id']))
 records=[]
 if row['leaf_type']=='DIAGRAM':
  pairs=[]
  for url,calls in callmap.items():
   for call in calls:pairs.append((url,call))
  # Detailed rows without a callout remain explicit diagram-page records.
  seenurls={u for u,_ in pairs};pairs += [(u,None) for u in cards if u not in seenurls]
 else:pairs=[(u,None) for u in cards]
 for url,call in pairs:
  card=cards[url];rid=record_upsert(c,ctx,row['catalogue_leaf_id'],card,call,run);records.append(rid);ensure_product_leaf(c,ctx,url)
  for img,alt in card['images']:
   role='PRODUCT_IMAGE' if 'cdn-product-images' in img else ('ILLUSTRATION_THUMBNAIL' if 'cdn-illustrations' in img else 'STATIC_PLACEHOLDER')
   image_observe(c,row['catalogue_leaf_id'],rid,role,img,row['source_url'])
 # Visible callouts with no product become explicit source-supported exception records.
 for call in empty:
  card={'part_detail_url':row['source_url']+f'#unmapped-callout-{call}','part_name_source':'PART_NAME_NOT_DISPLAYED','part_description_source':None,'oem_part_number_source':'PART_NUMBER_NOT_DISPLAYED','fitment_notes_source':None,'images':[]};records.append(record_upsert(c,ctx,row['catalogue_leaf_id'],card,call,run))
 if row['leaf_type']=='CATEGORY_INDEX':
  for a in selectors:
   leaf=sid('leaf',ctx['variation_id'],'DIAGRAM',a['source_url']);c.execute('''INSERT INTO catalogue_leaves(catalogue_leaf_id,variation_id,category_id,subcategory_id,parent_leaf_id,leaf_type,diagram_id,diagram_title_source,source_url,renderer_url,status,evidence_notes) VALUES(?,?,?,?,?,'DIAGRAM',?,?,?,?, 'NOT_STARTED',?) ON CONFLICT(catalogue_leaf_id) DO UPDATE SET diagram_title_source=excluded.diagram_title_source''',(leaf,ctx['variation_id'],ctx['category_id'],ctx['subcategory_id'],ctx['catalogue_leaf_id'],str(a['assembly_no']),a['title'],a['source_url'],renderer_url(a['source_url']),json.dumps({'selector_image_url':a['image_url']})));batch=sid('batch',leaf,'diagram');c.execute("INSERT INTO batches(batch_id,variation_id,catalogue_leaf_id,stage,responsible_agent,allowed_output_prefix,status,code_version,skill_version) VALUES(?,?,?,'DIAGRAM_EXTRACTION','AGENT_3_PART_RECORD_EXTRACTION','catalog/v2/','NOT_STARTED',?,?) ON CONFLICT(batch_id) DO NOTHING",(batch,ctx['variation_id'],leaf,CODE_VERSION,SKILL_VERSION));image_observe(c,leaf,None,'DIAGRAM',a['image_url'],a['source_url'])
  expected=len(cards)
 else:expected=len(pairs)+len(empty)
 b=raw.read_bytes();obs=c.execute('SELECT count(*) FROM image_observations WHERE catalogue_leaf_id=?',(row['catalogue_leaf_id'],)).fetchone()[0]
 c.execute("UPDATE catalogue_leaves SET status='EXTRACTED',http_status=?,source_accessed_at=?,source_byte_sha256=?,source_lf_sha256=?,raw_path=?,visible_row_expected=?,extracted_record_count=?,visible_callout_expected=?,extracted_callout_count=?,image_observation_count=?,exception_code=NULL,evidence_notes=? WHERE catalogue_leaf_id=?",(http,now(),h(b),h(lf_bytes(b.decode('utf-8'))),raw.relative_to(CAT).as_posix(),expected,len(records),expected_callouts,expected_callouts-len(empty),obs,json.dumps({'assembly_selectors':len(selectors),'empty_callouts':empty}),row['catalogue_leaf_id']))

def crawl_leaves(kind,limit=None,retry_failed=False,refresh=False):
 init_db();c=con();run=sid('run',kind,now());states="('NOT_STARTED','QA_FAILED')" if retry_failed else "('NOT_STARTED')";rows=c.execute(f"SELECT * FROM catalogue_leaves WHERE leaf_type=? AND status IN {states} ORDER BY variation_id,source_url",(kind,)).fetchall();rows=rows[:limit] if limit else rows
 for row in rows:
  batch=sid('batch',row['catalogue_leaf_id'],'category' if kind=='CATEGORY_INDEX' else ('diagram' if kind=='DIAGRAM' else 'product'));raw=RAW/row['variation_id']/kind.lower()/f"{h(row['source_url'].encode())}.md"
  try:
   c.execute("UPDATE catalogue_leaves SET status='IN_PROGRESS' WHERE catalogue_leaf_id=?",(row['catalogue_leaf_id'],));c.execute("UPDATE batches SET status='IN_PROGRESS',attempt_count=attempt_count+1,started_at=?,last_error=NULL WHERE batch_id=?",(now(),batch));c.commit()
   if raw.exists() and not refresh:text=raw.read_text(encoding='utf-8');http=200
   else:r,text,_=source_get(row['source_url']);http=r.status_code;save_raw(raw,text)
   process_leaf(c,row,text,raw,run,http);c.execute("UPDATE batches SET status='EXTRACTED',completed_at=?,checkpoint_json=? WHERE batch_id=?",(now(),json.dumps({'raw':raw.relative_to(CAT).as_posix()}),batch));event(c,run,kind,'EXTRACTED',row['variation_id'],row['catalogue_leaf_id'],http);c.commit()
  except Exception as e:
   c.execute("UPDATE catalogue_leaves SET status='QA_FAILED',exception_code='SOURCE_OR_PARSER_FAILURE',evidence_notes=? WHERE catalogue_leaf_id=?",(json.dumps({'error':str(e)}),row['catalogue_leaf_id']));c.execute("UPDATE batches SET status='QA_FAILED',last_error=? WHERE batch_id=?",(str(e),batch));event(c,run,kind,'QA_FAILED',row['variation_id'],row['catalogue_leaf_id'],message=str(e));c.commit()
 c.close();write_scope_manifest();return run

def parse_product_detail(text):
 pm=re.search(r'\*\s+Part Number:\s*([^\n]+)',text,re.I);pn=clean_label(pm.group(1)) if pm else 'PART_NUMBER_NOT_DISPLAYED'
 hm=re.search(r'^#\s+(.+?)(?:\s+-\s+Mopar|\s*\()',text,re.M);tm=re.search(r'^Title:\s*(.+)$',text,re.M);title=hm.group(1) if hm else (tm.group(1) if tm else 'PART_NAME_NOT_DISPLAYED')
 desc=(re.search(r'\*\s+Description:\s*\n([^\n]+)',text,re.I) or ['',''])[1].strip() or None;repl=(re.search(r'\*\s+Replaces:\s*([^\n]+)',text,re.I) or ['',''])[1].strip() or None;apps=(re.search(r'\*\s+Applications:([^\n]+)',text,re.I) or ['',''])[1].strip() or None;pos=(re.search(r'\*\s+Positions:([^\n]+)',text,re.I) or ['',''])[1].strip() or None
 fit=' | '.join(x for x in (pos,apps) if x) or None
 if not fit:
  fitlines=re.findall(r'^2017\s+(?:Chrysler|Dodge)\s+[^\r\n]+$',text,re.M)
  fit=' || '.join(fitlines) or None
 # Gallery is the product image run before Genuine Mopar Parts; exclude site chrome.
 head=text[:text.find('**Genuine Mopar Parts**') if '**Genuine Mopar Parts**' in text else min(len(text),8000)];imgs=list(dict.fromkeys(re.findall(r'https://cdn-product-images\.revolutionparts\.io/[^\s)]+',head)))
 return {'pn':pn,'name':clean_label(title),'description':desc,'replaces':repl,'fitment':fit,'images':imgs}

def crawl_products(limit=None,retry_failed=False,refresh=False):
 init_db();c=con();run=sid('run','product',now());states="('NOT_STARTED','QA_FAILED')" if retry_failed else "('NOT_STARTED')";rows=c.execute(f"SELECT source_url,min(catalogue_leaf_id) leaf FROM catalogue_leaves WHERE leaf_type='PRODUCT_DETAIL' AND status IN {states} GROUP BY source_url ORDER BY source_url").fetchall();rows=rows[:limit] if limit else rows
 for x in rows:
  leaves=c.execute("SELECT * FROM catalogue_leaves WHERE leaf_type='PRODUCT_DETAIL' AND source_url=?",(x['source_url'],)).fetchall();raw=RAW/'product'/f"{h(x['source_url'].encode())}.md"
  try:
   for row in leaves:
    c.execute("UPDATE catalogue_leaves SET status='IN_PROGRESS' WHERE catalogue_leaf_id=?",(row['catalogue_leaf_id'],));c.execute("UPDATE batches SET status='IN_PROGRESS',attempt_count=attempt_count+1,started_at=?,last_error=NULL WHERE batch_id=?",(now(),sid('batch',row['catalogue_leaf_id'],'product')))
   c.commit()
   if raw.exists() and not refresh:text=raw.read_text(encoding='utf-8');http=200
   else:r,text,_=source_get(x['source_url']);http=r.status_code;save_raw(raw,text)
   d=parse_product_detail(text);b=raw.read_bytes()
   recs=c.execute('SELECT * FROM part_records WHERE part_detail_url=?',(x['source_url'],)).fetchall()
   for rec in recs:
    oldid=rec['record_id'];newpn=rec['oem_part_number_source'] if d['pn']=='PART_NUMBER_NOT_DISPLAYED' else d['pn'];newname=rec['part_name_source'] if d['name']=='PART_NAME_NOT_DISPLAYED' else d['name'];exc=rec['exception_code']
    if newpn!='PART_NUMBER_NOT_DISPLAYED' and exc=='PART_NUMBER_NOT_DISPLAYED':exc=None
    c.execute('''UPDATE part_records SET part_name_source=?,part_name_normalized=?,part_description_source=COALESCE(?,part_description_source),oem_part_number_source=?,oem_part_number_normalized=?,superseded_part_number_source=COALESCE(?,superseded_part_number_source),fitment_notes_source=COALESCE(?,fitment_notes_source),fitment_normalized=COALESCE(?,fitment_normalized),source_verification_status='SOURCE_VERIFIED',fitment_audit_status='FITMENT_SOURCE_CAPTURED',exception_code=? WHERE record_id=?''',(newname,newname.lower(),d['description'],newpn,norm(newpn),d['replaces'],d['fitment'],clean_label(d['fitment']).lower() if d['fitment'] else None,exc,oldid))
   for row in leaves:
    relrecs=c.execute('SELECT record_id FROM part_records WHERE variation_id=? AND part_detail_url=?',(row['variation_id'],x['source_url'])).fetchall()
    for rr in relrecs:
     for img in d['images']:image_observe(c,row['catalogue_leaf_id'],rr['record_id'],'PRODUCT_IMAGE',img,x['source_url'])
     if not d['images'] and c.execute("SELECT count(*) FROM image_observations WHERE record_id=? AND image_role NOT LIKE 'STATIC_%'",(rr['record_id'],)).fetchone()[0]==0:c.execute("UPDATE part_records SET image_verification_status='NO_OEM_IMAGE_AVAILABLE',exception_code=COALESCE(exception_code,'NO_OEM_IMAGE_AVAILABLE') WHERE record_id=?",(rr['record_id'],))
    obs=c.execute('SELECT count(*) FROM image_observations WHERE catalogue_leaf_id=?',(row['catalogue_leaf_id'],)).fetchone()[0];c.execute("UPDATE catalogue_leaves SET status='EXTRACTED',http_status=?,source_accessed_at=?,source_byte_sha256=?,source_lf_sha256=?,raw_path=?,visible_row_expected=?,extracted_record_count=?,image_observation_count=?,evidence_notes=? WHERE catalogue_leaf_id=?",(http,now(),h(b),h(lf_bytes(b.decode('utf-8'))),raw.relative_to(CAT).as_posix(),len(relrecs),len(relrecs),obs,json.dumps({'product_detail':d}),row['catalogue_leaf_id']));c.execute("UPDATE batches SET status='EXTRACTED',completed_at=?,checkpoint_json=? WHERE batch_id=?",(now(),json.dumps({'raw':raw.relative_to(CAT).as_posix()}),sid('batch',row['catalogue_leaf_id'],'product')));event(c,run,'PRODUCT_DETAIL','EXTRACTED',row['variation_id'],row['catalogue_leaf_id'],http)
   c.commit()
  except Exception as e:
   for row in leaves:
    c.execute("UPDATE catalogue_leaves SET status='QA_FAILED',exception_code='SOURCE_OR_PARSER_FAILURE',evidence_notes=? WHERE catalogue_leaf_id=?",(json.dumps({'error':str(e)}),row['catalogue_leaf_id']));c.execute("UPDATE batches SET status='QA_FAILED',last_error=? WHERE batch_id=?",(str(e),sid('batch',row['catalogue_leaf_id'],'product')))
   c.commit()
 c.close();write_scope_manifest();return run

def image_download(url):
 r=S.get(url,timeout=120);r.raise_for_status();data=r.content;ct=(r.headers.get('content-type') or '').split(';')[0].lower()
 if 'html' in ct or len(data)<100:raise RuntimeError(f'invalid image content type={ct} bytes={len(data)}')
 with Image.open(io.BytesIO(data)) as im:im.verify()
 with Image.open(io.BytesIO(data)) as im:w,hh,fmt=im.width,im.height,im.format
 mime=Image.MIME.get(fmt,ct or 'application/octet-stream');sha=h(data);ext=Path(urlparse(r.url).path).suffix.lower() or mimetypes.guess_extension(mime) or '.bin';dst=IMAGES/sha[:2]/f'{sha}{ext}';dst.parent.mkdir(parents=True,exist_ok=True)
 if not dst.exists():dst.write_bytes(data)
 return {'sha':sha,'path':dst.relative_to(CAT).as_posix(),'mime':mime,'bytes':len(data),'width':w,'height':hh,'final':r.url}
def acquire_images(limit=None):
 init_db();c=con();urls=[r[0] for r in c.execute("SELECT DISTINCT image_source_url FROM image_observations WHERE acquisition_status IN ('NOT_STARTED','FAILED') AND image_role NOT LIKE 'STATIC_%' ORDER BY image_source_url")];urls=urls[:limit] if limit else urls;c.close();results={}
 with ThreadPoolExecutor(max_workers=8) as ex:
  fut={ex.submit(image_download,u):u for u in urls}
  for f in as_completed(fut):
   u=fut[f]
   try:results[u]=(f.result(),None)
   except Exception as e:results[u]=(None,str(e))
 c=con()
 for u,(d,err) in results.items():
  if err:c.execute("UPDATE image_observations SET acquisition_status='FAILED',exception_code='INVALID_OR_UNAVAILABLE_IMAGE',evidence_notes=? WHERE image_source_url=?",(json.dumps({'error':err}),u));continue
  c.execute('INSERT INTO image_assets VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(image_sha256) DO NOTHING',(d['sha'],d['path'],d['mime'],d['bytes'],d['width'],d['height'],'DECODED_OK',now()));c.execute("UPDATE image_observations SET image_final_resolved_url=?,image_sha256=?,acquisition_status='IMAGE_ACQUIRED' WHERE image_source_url=?",(d['final'],d['sha'],u));c.execute("UPDATE part_records SET image_source_url=COALESCE(image_source_url,?),image_final_resolved_url=COALESCE(image_final_resolved_url,?),local_image_path=COALESCE(local_image_path,?),image_mime_type=COALESCE(image_mime_type,?),image_byte_size=COALESCE(image_byte_size,?),image_width=COALESCE(image_width,?),image_height=COALESCE(image_height,?),image_sha256=COALESCE(image_sha256,?),image_verification_status='IMAGE_ACQUIRED' WHERE record_id IN (SELECT record_id FROM image_observations WHERE image_source_url=? AND record_id IS NOT NULL)",(u,d['final'],d['path'],d['mime'],d['bytes'],d['width'],d['height'],d['sha'],u))
 c.commit();c.close();return {'urls':len(urls),'failed':sum(bool(e) for _,e in results.values())}
def verify_images(limit=None):
 init_db();c=con();rows=c.execute("SELECT DISTINCT image_source_url,image_sha256 FROM image_observations WHERE acquisition_status='IMAGE_ACQUIRED' ORDER BY image_source_url").fetchall();rows=rows[:limit] if limit else rows;c.close()
 def vf(row):
  try:r=S.get(row['image_source_url'],timeout=120);r.raise_for_status();return row['image_source_url'],h(r.content)==row['image_sha256'],h(r.content)
  except Exception as e:return row['image_source_url'],False,str(e)
 results=[]
 with ThreadPoolExecutor(max_workers=4) as ex:
  for x in as_completed([ex.submit(vf,r) for r in rows]):results.append(x.result())
 c=con()
 for u,ok,actual in results:
  st='IMAGE_VERIFIED_BYTE_EXACT' if ok else 'SOURCE_IMAGE_CHANGED';c.execute('UPDATE image_observations SET verification_status=?,association_status=? WHERE image_source_url=?',(st,'ASSOCIATION_VERIFIED' if ok else 'REQUIRES_MANUAL_REVIEW',u));c.execute("UPDATE part_records SET image_verification_status=? WHERE record_id IN (SELECT record_id FROM image_observations WHERE image_source_url=? AND record_id IS NOT NULL)",(st,u))
 c.commit();c.close();return {'verified':sum(ok for _,ok,_ in results),'failed':sum(not ok for _,ok,_ in results)}
def rebuild_fts():
 c=con();c.execute('DELETE FROM catalogue_fts');c.execute('''INSERT INTO catalogue_fts SELECT r.record_id,veh.project_label,v.variation_source_label,r.category_source_label,COALESCE(r.subcategory_source_label,''),COALESCE(r.diagram_title_source,''),COALESCE(r.diagram_callout_source,''),r.oem_part_number_source,r.part_name_source,COALESCE(r.part_description_source,''),COALESCE(r.fitment_notes_source,''),r.part_detail_url FROM part_records r JOIN variations v ON v.variation_id=r.variation_id JOIN vehicles veh ON veh.vehicle_id=r.vehicle_id''');c.commit();c.close()
def write_scope_manifest():
 if not DB.exists():return
 c=con();data={'generated_at':now(),'variations':[]}
 for v in c.execute('SELECT * FROM variations ORDER BY variation_id'):
  counts={k:c.execute('SELECT count(*) FROM catalogue_leaves WHERE variation_id=? AND '+q,(v['variation_id'],)).fetchone()[0] for k,q in {'categories':"leaf_type='CATEGORY_INDEX'",'diagrams':"leaf_type='DIAGRAM'",'products':"leaf_type='PRODUCT_DETAIL'",'qa_passed':"status='QA_PASSED'",'blocked':"status='BLOCKED_EXTERNAL'",'nonterminal':"status NOT IN ('QA_PASSED','BLOCKED_EXTERNAL')"}.items()};data['variations'].append({'variation_id':v['variation_id'],'source_label':v['variation_source_label'],'route':v['source_url'],'validation_status':v['validation_status'],**counts})
 data['totals']={'leaves':c.execute('SELECT count(*) FROM catalogue_leaves').fetchone()[0],'records':c.execute('SELECT count(*) FROM part_records').fetchone()[0],'image_observations':c.execute('SELECT count(*) FROM image_observations').fetchone()[0],'image_assets':c.execute('SELECT count(*) FROM image_assets').fetchone()[0],'open_critical':c.execute("SELECT count(*) FROM defects WHERE severity='CRITICAL' AND status!='RESOLVED'").fetchone()[0],'open_major':c.execute("SELECT count(*) FROM defects WHERE severity='MAJOR' AND status!='RESOLVED'").fetchone()[0]};c.close();(CAT/'manifests'/'master_expected_scope.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
def export_all():
 init_db();rebuild_fts();c=con();EXPORTS.mkdir(parents=True,exist_ok=True)
 queries={'variations.csv':'SELECT * FROM variations ORDER BY variation_id','taxonomy.csv':'SELECT * FROM taxonomy_nodes ORDER BY variation_id,ordinal,node_type','leaves.csv':'SELECT * FROM catalogue_leaves ORDER BY variation_id,leaf_type,source_url','part_records.csv':'SELECT * FROM part_records ORDER BY variation_id,category_source_label,diagram_title_source,diagram_callout_source,oem_part_number_normalized','image_provenance.csv':'SELECT o.*,a.local_image_path,a.image_mime_type,a.image_byte_size,a.image_width,a.image_height FROM image_observations o LEFT JOIN image_assets a ON a.image_sha256=o.image_sha256 ORDER BY o.catalogue_leaf_id,o.record_id,o.image_role','defects.csv':'SELECT * FROM defects ORDER BY severity,created_at'}
 for name,sql in queries.items():
  rows=c.execute(sql).fetchall();p=EXPORTS/name
  with p.open('w',encoding='utf-8-sig',newline='') as f:
   if rows:w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows([dict(r) for r in rows])
 status={'generated_at':now(),'vehicles':c.execute('SELECT count(*) FROM vehicles').fetchone()[0],'variations':c.execute('SELECT count(*) FROM variations').fetchone()[0],'taxonomy_nodes':c.execute('SELECT count(*) FROM taxonomy_nodes').fetchone()[0],'leaves':c.execute('SELECT count(*) FROM catalogue_leaves').fetchone()[0],'records':c.execute('SELECT count(*) FROM part_records').fetchone()[0],'unique_displayed_part_numbers':c.execute("SELECT count(DISTINCT oem_part_number_normalized) FROM part_records WHERE oem_part_number_source!='PART_NUMBER_NOT_DISPLAYED'").fetchone()[0],'part_number_not_displayed':c.execute("SELECT count(*) FROM part_records WHERE oem_part_number_source='PART_NUMBER_NOT_DISPLAYED'").fetchone()[0],'image_observations':c.execute('SELECT count(*) FROM image_observations').fetchone()[0],'unique_images':c.execute('SELECT count(*) FROM image_assets').fetchone()[0],'verified_images':c.execute("SELECT count(*) FROM image_observations WHERE verification_status='IMAGE_VERIFIED_BYTE_EXACT'").fetchone()[0],'no_oem_image':c.execute("SELECT count(*) FROM part_records WHERE image_verification_status='NO_OEM_IMAGE_AVAILABLE'").fetchone()[0],'fts_rows':c.execute('SELECT count(*) FROM catalogue_fts').fetchone()[0]};(EXPORTS/'status.json').write_text(json.dumps(status,indent=2),encoding='utf-8');c.close();write_scope_manifest();return status
def search(q,limit=20):
 rebuild_fts();c=con();rows=c.execute('SELECT *,bm25(catalogue_fts) rank FROM catalogue_fts WHERE catalogue_fts MATCH ? ORDER BY rank LIMIT ?',(q,limit)).fetchall();print(json.dumps([dict(r) for r in rows],indent=2));c.close()
def status():print(json.dumps(export_all(),indent=2))

def main():
 p=argparse.ArgumentParser();sp=p.add_subparsers(dest='cmd',required=True);sp.add_parser('init');d=sp.add_parser('discover');d.add_argument('--refresh',action='store_true')
 for cmd in ('crawl-categories','crawl-diagrams','crawl-products'):
  x=sp.add_parser(cmd);x.add_argument('--limit',type=int);x.add_argument('--retry-failed',action='store_true');x.add_argument('--refresh',action='store_true')
 for cmd in ('acquire-images','verify-images'):
  x=sp.add_parser(cmd);x.add_argument('--limit',type=int)
 sp.add_parser('export');sp.add_parser('status');s=sp.add_parser('search');s.add_argument('query');s.add_argument('--limit',type=int,default=20)
 a=p.parse_args()
 if a.cmd=='init':init_db();write_scope_manifest();print(DB)
 elif a.cmd=='discover':print(discover(a.refresh))
 elif a.cmd=='crawl-categories':print(crawl_leaves('CATEGORY_INDEX',a.limit,a.retry_failed,a.refresh))
 elif a.cmd=='crawl-diagrams':print(crawl_leaves('DIAGRAM',a.limit,a.retry_failed,a.refresh))
 elif a.cmd=='crawl-products':print(crawl_products(a.limit,a.retry_failed,a.refresh))
 elif a.cmd=='acquire-images':print(json.dumps(acquire_images(a.limit)))
 elif a.cmd=='verify-images':print(json.dumps(verify_images(a.limit)))
 elif a.cmd=='export':print(json.dumps(export_all(),indent=2))
 elif a.cmd=='status':status()
 elif a.cmd=='search':search(a.query,a.limit)
if __name__=='__main__':main()
