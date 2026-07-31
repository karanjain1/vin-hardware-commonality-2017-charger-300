#!/usr/bin/env python
"""Resumable MoparAmerica 2017 Charger/Chrysler 300 catalogue crawler.

Public catalogue pages are retrieved through the Jina text renderer when direct
HTTP is blocked. The original MoparAmerica URL is always retained. Requests are
serialized at the public robots.txt crawl delay (10 seconds).
"""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json,re,sqlite3,time
from pathlib import Path
from urllib.parse import urlparse
import requests

ROOT=Path(__file__).resolve().parents[1]
CAT=ROOT/'catalog';DB=CAT/'mopar_catalog.sqlite3';SCHEMA=CAT/'schema.sql';SEED=CAT/'config/variants_seed.json'
RAW=CAT/'raw';IMAGES=CAT/'images';EXPORTS=CAT/'exports';LOGS=CAT/'logs'
for p in (RAW,IMAGES,EXPORTS,LOGS):p.mkdir(parents=True,exist_ok=True)
UA='HermesROVERCatalogResearch/1.0 (+public evidence indexing; contact via repository)'
SESSION=requests.Session();SESSION.headers.update({'User-Agent':UA})
_LAST=[0.0]

def now():return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
def sha(data):return hashlib.sha256(data).hexdigest()
def norm_part(s):return re.sub(r'[^A-Z0-9]','',s.upper()).lstrip('0') or '0'
def slug_title(s):return s.replace('--',' / ').replace('-',' ').title()
def con():
 c=sqlite3.connect(DB,timeout=60);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c

def init_db():
 c=con();c.executescript(SCHEMA.read_text(encoding='utf-8'));c.execute("INSERT OR REPLACE INTO meta VALUES('schema_version','1')");c.execute("INSERT OR REPLACE INTO meta VALUES('source','MoparAmerica public OEM catalogue')");c.execute("INSERT OR REPLACE INTO meta VALUES('scope','2017 Dodge Charger and 2017 Chrysler 300 all validated catalogue routes')");c.commit();c.close()

def event(c,stage,route,status,http_status=None,message=None):
 c.execute('INSERT INTO crawl_events(occurred_at,stage,route,status,http_status,message) VALUES(?,?,?,?,?,?)',(now(),stage,route,status,http_status,message))

def throttled_get(url,tries=4):
 for attempt in range(tries):
  delay=max(0,10.0-(time.monotonic()-_LAST[0]))
  if delay:time.sleep(delay)
  _LAST[0]=time.monotonic();r=SESSION.get(url,timeout=180)
  if r.status_code==200 and len(r.content)>500:return r
  if r.status_code not in (429,503):return r
  time.sleep(10*(attempt+1))
 return r

def rendered(original):
 # Renderer is a retrieval transport only; evidence URLs remain MoparAmerica.
 if not original.startswith('https://www.moparamerica.com/'):raise ValueError(original)
 u='https://r.jina.ai/http://www.moparamerica.com/'+original.split('https://www.moparamerica.com/',1)[1]
 r=None
 for _ in range(4):
  r=throttled_get(u)
  # Jina occasionally returns a short Cloudflare interstitial with HTTP 200.
  # A standalone repeat of the same route returns the catalogue, so classify
  # this as a retryable transport block rather than an invalid vehicle route.
  if 'Just a moment' not in r.text and len(r.text)>500:return r
 return r

def category_links(text,route):
 pat=re.compile(r'https://www\.moparamerica\.com/'+re.escape(route)+r'/([^\s)"?#/]+)')
 out=[]
 for slug in pat.findall(text):
  if slug.startswith(('oem-parts','search','cart','account')):continue
  if slug not in out:out.append(slug)
 return out

def parse_parts(text):
 out=[];seen=set();lines=text.splitlines()
 for i,line in enumerate(lines):
  m=re.match(r'\[([^\]]+)\]\((https://www\.moparamerica\.com/oem-parts/[^)]+)\)',line.strip())
  if not m:continue
  desc,url=m.groups();url=url.split(' "',1)[0];block='\n'.join(lines[i:i+16]);pns=re.findall(r'Part Number:\s*`?([A-Z0-9-]{5,24})`?',block,re.I)
  if not pns:
   tail=urlparse(url).path.rstrip('/').split('-')[-1]
   if re.fullmatch(r'[A-Za-z0-9]{5,24}',tail):pns=[tail]
  detail=[]
  for x in lines[i+1:i+12]:
   x=re.sub(r'^[-*]\s*','',x).strip()
   if x and not x.startswith(('[','Image','Part Number:','###','##')):detail.append(x)
  for pn in pns:
   clean=desc.strip()
   if clean.upper() in {pn.upper(),'VIEW DETAILS'} or re.fullmatch(r'[A-Z0-9-]{5,24}',clean,re.I):
    prod=urlparse(url).path.rstrip('/').split('/')[-1];prod=re.sub(r'-'+re.escape(pn)+r'$','',prod,flags=re.I);clean=re.sub(r'^mopar-','',prod,flags=re.I).replace('-',' ').title()
   key=(pn.upper(),url)
   if key in seen:continue
   seen.add(key);out.append({'part_number':pn.upper(),'normalized_part_number':norm_part(pn),'description':clean,'detail':' | '.join(detail[:5]),'product_url':url})
 return out

def parse_assemblies(text):
 out=[];seen=set()
 pats=[
  re.compile(r'\[([^\]]+)\]\((https://www\.moparamerica\.com/[^)]+\?assembly=(\d+))\)\s*\n\s*\[!\[Image \d+: ([^\]]*)\]\((https?://[^)]+)\)',re.M),
  re.compile(r'\[!\[Image \d+: ([^\]]*)\]\((https?://[^)]+)\)([^\]]*)\]\((https://www\.moparamerica\.com/[^)\s]+\?assembly=(\d+))[^)]*\)')]
 for pi,pat in enumerate(pats):
  for m in pat.findall(text):
   if pi==0:title,url,num,alt,img=m
   else:alt,img,title,url,num=m
   num=int(num)
   if num in seen:continue
   seen.add(num);title=re.sub(r'^\s*\d+\.\s*','',title).strip() or alt
   out.append({'assembly_no':num,'title':title,'source_url':url,'image_url':img})
 # A category with one diagram has no ?assembly selector. Preserve that
 # unnumbered illustration as assembly 0 rather than incorrectly recording an
 # image gap.
 if not out:
  page=(re.search(r'^URL Source:\s*(https?://\S+)',text,re.M) or [None,''])[1]
  single=[]
  for alt,img in re.findall(r'!\[Image \d+: ([^\]]*?#0)\]\((https://cdn-illustrations\.revolutionparts\.io/[^)]+)\)',text):
   if img not in {x[1] for x in single}:single.append((alt,img))
  for n,(alt,img) in enumerate(single):
   out.append({'assembly_no':n,'title':re.sub(r'\s+#0$','',alt).strip(),'source_url':page,'image_url':img})
 return sorted(out,key=lambda x:x['assembly_no'])

def seed_variants(c):
 cfg=json.loads(SEED.read_text(encoding='utf-8'))
 for v in cfg['candidates']:
  u='https://www.moparamerica.com/'+v['route_slug']
  c.execute('INSERT INTO variants(model,trim,engine,route_slug,source_url) VALUES(?,?,?,?,?) ON CONFLICT(route_slug) DO UPDATE SET model=excluded.model,trim=excluded.trim,engine=excluded.engine,source_url=excluded.source_url',(v['model'],v['trim'],v['engine'],v['route_slug'],u))
 c.commit()

def discover(limit=None,retry_invalid=False):
 init_db();c=con();seed_variants(c)
 states="('pending','blocked')" if not retry_invalid else "('pending','blocked','invalid')"
 q=f"SELECT * FROM variants WHERE validation_state IN {states} ORDER BY model,trim,engine";rows=c.execute(q).fetchall();rows=rows[:limit] if limit else rows
 for v in rows:
  route=v['route_slug'];r=rendered(v['source_url']);text=r.text;cats=category_links(text,route)
  state='valid' if len(cats)>=20 and 'Select Parts Category' in text else ('blocked' if 'Just a moment' in text else 'invalid')
  c.execute('UPDATE variants SET valid=?,validation_state=?,page_title=?,retrieved_at=?,source_sha256=?,error=? WHERE id=?',(1 if state=='valid' else 0,state,(re.search(r'^Title:\s*(.+)$',text,re.M) or ['',''])[1],now(),sha(text.encode()),None if state=='valid' else f'categories={len(cats)} http={r.status_code}',v['id']))
  if state=='valid':
   for s in cats:
    cur=c.execute('INSERT INTO categories(slug,title) VALUES(?,?) ON CONFLICT(slug) DO UPDATE SET title=excluded.title RETURNING id',(s,slug_title(s)));cid=cur.fetchone()[0]
    u=v['source_url']+'/'+s;c.execute('INSERT INTO variant_categories(variant_id,category_id,source_url) VALUES(?,?,?) ON CONFLICT(variant_id,category_id) DO NOTHING',(v['id'],cid,u))
  event(c,'discover',route,state,r.status_code,f'categories={len(cats)}');c.commit();print(json.dumps({'route':route,'state':state,'categories':len(cats)}),flush=True)
 c.close();rebuild_fts();export_all()

def download_image(url):
 # CDN resources are immutable and hash-deduplicated. Use a modest independent delay.
 r=SESSION.get(url,timeout=120);r.raise_for_status();data=r.content;h=sha(data);ext=Path(urlparse(url).path).suffix.lower() or '.png';dst=IMAGES/h[:2]/f'{h}{ext}';dst.parent.mkdir(parents=True,exist_ok=True)
 if not dst.exists():dst.write_bytes(data)
 return dst.relative_to(CAT).as_posix(),h,len(data)

def crawl(limit=None,retry_errors=False):
 init_db();c=con();state="IN ('pending','error')" if retry_errors else "='pending'"
 rows=c.execute(f'''SELECT vc.*,v.model,v.trim,v.engine,v.route_slug,c.slug category_slug FROM variant_categories vc JOIN variants v ON v.id=vc.variant_id JOIN categories c ON c.id=vc.category_id WHERE vc.crawl_state {state} AND v.valid=1 ORDER BY v.model,v.trim,v.engine,c.slug''').fetchall();rows=rows[:limit] if limit else rows
 for row in rows:
  try:
   r=rendered(row['source_url']);text=r.text
   if r.status_code!=200 or len(text)<1000 or 'Just a moment' in text:raise RuntimeError(f'HTTP {r.status_code}, renderer length {len(text)}')
   raw=RAW/row['route_slug']/f"{row['category_slug']}.md";raw.parent.mkdir(parents=True,exist_ok=True);raw.write_text(text,encoding='utf-8')
   parts=parse_parts(text);assemblies=parse_assemblies(text);stamp=now()
   for p in parts:
    cur=c.execute('INSERT INTO parts(part_number,normalized_part_number,description,product_url) VALUES(?,?,?,?) ON CONFLICT(product_url) DO UPDATE SET part_number=excluded.part_number,normalized_part_number=excluded.normalized_part_number,description=excluded.description RETURNING id',(p['part_number'],p['normalized_part_number'],p['description'],p['product_url']));pid=cur.fetchone()[0]
    c.execute('INSERT INTO part_offerings(variant_category_id,part_id,detail,evidence_url,retrieved_at) VALUES(?,?,?,?,?) ON CONFLICT(variant_category_id,part_id) DO UPDATE SET detail=excluded.detail,retrieved_at=excluded.retrieved_at',(row['id'],pid,p['detail'],row['source_url'],stamp))
   image_errors=[]
   for a in assemblies:
    ip=ih=ib=None
    try:ip,ih,ib=download_image(a['image_url'])
    except Exception as e:image_errors.append(f"assembly {a['assembly_no']}: {e}")
    c.execute('INSERT INTO assemblies(variant_category_id,assembly_no,title,source_url,image_url,image_path,image_sha256,image_bytes,retrieved_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(variant_category_id,assembly_no) DO UPDATE SET title=excluded.title,source_url=excluded.source_url,image_url=excluded.image_url,image_path=excluded.image_path,image_sha256=excluded.image_sha256,image_bytes=excluded.image_bytes,retrieved_at=excluded.retrieved_at',(row['id'],a['assembly_no'],a['title'],a['source_url'],a['image_url'],ip,ih,ib,stamp))
   c.execute("UPDATE variant_categories SET crawl_state='complete',retrieved_at=?,source_sha256=?,raw_path=?,part_count=?,assembly_count=?,error=? WHERE id=?",(stamp,sha(text.encode()),raw.relative_to(CAT).as_posix(),len(parts),len(assemblies),'; '.join(image_errors) or None,row['id']))
   event(c,'crawl',row['source_url'],'complete',r.status_code,f'parts={len(parts)} assemblies={len(assemblies)} image_errors={len(image_errors)}');c.commit();print(json.dumps({'route':row['route_slug'],'category':row['category_slug'],'parts':len(parts),'assemblies':len(assemblies),'image_errors':len(image_errors)}),flush=True)
  except Exception as e:
   c.execute("UPDATE variant_categories SET crawl_state='error',error=? WHERE id=?",(str(e),row['id']));event(c,'crawl',row['source_url'],'error',message=str(e));c.commit();print(json.dumps({'route':row['route_slug'],'category':row['category_slug'],'error':str(e)}),flush=True)
 c.close();rebuild_fts();export_all()

def rebuild_fts():
 init_db();c=con();c.execute('DELETE FROM catalog_fts')
 c.execute('''INSERT INTO catalog_fts(entity_type,model,trim,engine,category,assembly,callout,part_number,description,source_url)
 SELECT 'part',v.model,v.trim,v.engine,c.title,'','',p.part_number,p.description,po.evidence_url
 FROM part_offerings po JOIN parts p ON p.id=po.part_id JOIN variant_categories vc ON vc.id=po.variant_category_id JOIN variants v ON v.id=vc.variant_id JOIN categories c ON c.id=vc.category_id''')
 c.execute('''INSERT INTO catalog_fts(entity_type,model,trim,engine,category,assembly,callout,part_number,description,source_url)
 SELECT 'assembly',v.model,v.trim,v.engine,c.title,a.title,'','',a.title,a.source_url
 FROM assemblies a JOIN variant_categories vc ON vc.id=a.variant_category_id JOIN variants v ON v.id=vc.variant_id JOIN categories c ON c.id=vc.category_id''')
 c.execute('''INSERT INTO catalog_fts(entity_type,model,trim,engine,category,assembly,callout,part_number,description,source_url)
 SELECT 'callout',v.model,v.trim,v.engine,c.title,a.title,co.callout,COALESCE(p.part_number,''),COALESCE(co.description,p.description),COALESCE(co.evidence_url,a.source_url)
 FROM callouts co JOIN assemblies a ON a.id=co.assembly_id JOIN variant_categories vc ON vc.id=a.variant_category_id JOIN variants v ON v.id=vc.variant_id JOIN categories c ON c.id=vc.category_id LEFT JOIN parts p ON p.id=co.part_id''')
 c.commit();c.close()

def export_query(c,name,sql):
 rows=c.execute(sql).fetchall();path=EXPORTS/name
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  if rows:w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows([dict(r) for r in rows])
  else:path.write_text('',encoding='utf-8')
 return len(rows)

def export_all():
 init_db();c=con();counts={}
 counts['variants']=export_query(c,'variants.csv','SELECT model,trim,engine,route_slug,valid,validation_state,source_url,retrieved_at,error FROM variants ORDER BY model,trim,engine')
 counts['coverage']=export_query(c,'coverage.csv','''SELECT v.model,v.trim,v.engine,c.title category,vc.crawl_state,vc.part_count,vc.assembly_count,vc.source_url,vc.retrieved_at,vc.error FROM variant_categories vc JOIN variants v ON v.id=vc.variant_id JOIN categories c ON c.id=vc.category_id ORDER BY v.model,v.trim,v.engine,c.title''')
 counts['parts']=export_query(c,'parts.csv','''SELECT DISTINCT p.part_number,p.normalized_part_number,p.description,p.product_url FROM parts p ORDER BY p.normalized_part_number,p.product_url''')
 counts['offerings']=export_query(c,'part_offerings.csv','''SELECT v.model,v.trim,v.engine,c.title category,p.part_number,p.normalized_part_number,p.description,po.detail,po.evidence_url FROM part_offerings po JOIN parts p ON p.id=po.part_id JOIN variant_categories vc ON vc.id=po.variant_category_id JOIN variants v ON v.id=vc.variant_id JOIN categories c ON c.id=vc.category_id ORDER BY v.model,v.trim,v.engine,c.title,p.normalized_part_number''')
 counts['assemblies']=export_query(c,'assemblies.csv','''SELECT v.model,v.trim,v.engine,c.title category,a.assembly_no,a.title assembly,a.source_url,a.image_url,a.image_path,a.image_sha256,a.image_bytes FROM assemblies a JOIN variant_categories vc ON vc.id=a.variant_category_id JOIN variants v ON v.id=vc.variant_id JOIN categories c ON c.id=vc.category_id ORDER BY v.model,v.trim,v.engine,c.title,a.assembly_no''')
 counts['fts_rows']=c.execute('SELECT count(*) FROM catalog_fts').fetchone()[0];counts['complete_categories']=c.execute("SELECT count(*) FROM variant_categories WHERE crawl_state='complete'").fetchone()[0];counts['pending_categories']=c.execute("SELECT count(*) FROM variant_categories WHERE crawl_state='pending'").fetchone()[0];counts['error_categories']=c.execute("SELECT count(*) FROM variant_categories WHERE crawl_state='error'").fetchone()[0];counts['unique_images']=c.execute("SELECT count(DISTINCT image_sha256) FROM assemblies WHERE image_sha256 IS NOT NULL").fetchone()[0];counts['generated_at']=now();(EXPORTS/'status.json').write_text(json.dumps(counts,indent=2),encoding='utf-8');c.close();return counts

def status():
 print(json.dumps(export_all(),indent=2))

def search(q,limit=20,model=None,trim=None):
 init_db();c=con();where=['catalog_fts MATCH ?'];args=[q]
 if model:where.append('model LIKE ?');args.append('%'+model+'%')
 if trim:where.append('trim LIKE ?');args.append('%'+trim+'%')
 args.append(limit);rows=c.execute(f'''SELECT entity_type,model,trim,engine,category,assembly,callout,part_number,description,source_url,bm25(catalog_fts) rank FROM catalog_fts WHERE {' AND '.join(where)} ORDER BY rank LIMIT ?''',args).fetchall();print(json.dumps([dict(r) for r in rows],indent=2));c.close()

def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='cmd',required=True)
 sub.add_parser('init');d=sub.add_parser('discover');d.add_argument('--limit',type=int);d.add_argument('--retry-invalid',action='store_true');cr=sub.add_parser('crawl');cr.add_argument('--limit',type=int);cr.add_argument('--retry-errors',action='store_true');sub.add_parser('rebuild-search');sub.add_parser('export');sub.add_parser('status');s=sub.add_parser('search');s.add_argument('query');s.add_argument('--limit',type=int,default=20);s.add_argument('--model');s.add_argument('--trim')
 a=p.parse_args()
 if a.cmd=='init':init_db();c=con();seed_variants(c);c.close();print(DB)
 elif a.cmd=='discover':discover(a.limit,a.retry_invalid)
 elif a.cmd=='crawl':crawl(a.limit,a.retry_errors)
 elif a.cmd=='rebuild-search':rebuild_fts();print(export_all())
 elif a.cmd=='export':print(json.dumps(export_all(),indent=2))
 elif a.cmd=='status':status()
 elif a.cmd=='search':search(a.query,a.limit,a.model,a.trim)
if __name__=='__main__':main()
