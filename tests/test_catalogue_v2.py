import contextlib,importlib.util,io,json,shutil,sqlite3,tempfile,unittest
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
cv2=load('catalogue_v2',ROOT/'scripts'/'catalogue_v2.py')
aud=load('catalogue_auditors',ROOT/'scripts'/'catalogue_auditors.py')
qa=load('catalogue_qa',ROOT/'scripts'/'catalogue_qa.py')
DIAGRAM=ROOT/'catalog'/'v2'/'evidence'/'source'/'challenger-rt-57-gas'/'diagram'/'82dca3b0735fd12996a6bb09ff1ab61849f453f00c409693302c1401c10381d3.md'
PARTIAL=ROOT/'catalog'/'v2'/'evidence'/'source'/'product'/'37fc7ad3abdc781cf4769e95b39969895b417d29a2b44a4592fb67edb5b03f79.md'
class ManifestAndSkills(unittest.TestCase):
 def test_exact_six_variations(self):
  m=json.loads((ROOT/'catalog'/'manifests'/'variation_manifest.json').read_text());vs=[(v,x) for v in m['vehicles'] for x in v['variations']];self.assertEqual(len(vs),6);self.assertEqual({v['vehicle_id'] for v,x in vs},{'2017-chrysler-300c','2017-dodge-challenger'});self.assertEqual({v['vehicle_id']:len(v['variations']) for v in m['vehicles']},{'2017-chrysler-300c':3,'2017-dodge-challenger':3})
 def test_ten_project_skills(self):
  files=list((ROOT/'catalog'/'skills').glob('*/SKILL.md'));self.assertEqual(len(files),10)
  for p in files:self.assertIn('## Tests',p.read_text(encoding='utf-8'))
class ParserRegression(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.text=DIAGRAM.read_text(encoding='utf-8')
 def test_duplicate_visible_callout_occurrences_are_preserved(self):
  a=cv2.active_diagram(self.text,1);rows=cv2.callout_rows(self.text,a);self.assertEqual(len(rows),6);dup=[x for x in rows if x['anchor']=='#part_row_0_4_0'];self.assertEqual([x['ordinal'] for x in dup],[1,2])
 def test_detailed_table_rows_are_bounded_and_exact(self):
  rows=cv2.table_rows(self.text);self.assertEqual(len(rows),5);self.assertEqual(rows[0]['pn'],'6101831');self.assertEqual(rows[1]['pn'],'5090026AA');self.assertNotIn('5090026AA',rows[0]['snippet'])
 def test_adjacent_product_cannot_supply_missing_number(self):
  u1='https://www.moparamerica.com/oem-parts/mopar-model-300-bracket-a';u2='https://www.moparamerica.com/oem-parts/mopar-second-b22222'
  t='\n No. \n\n Part # / Description / Price\n\n1\n\n[![Image 1: first](https://cdn-product-images.revolutionparts.io/assets/a.webp)]('+u1+' "First")\n\n**[Model 300 Bracket]('+u1+' "Model 300 Bracket")**\n\n2\n\n[![Image 2: second](https://cdn-product-images.revolutionparts.io/assets/b.webp)]('+u2+' "Second - Part No B22222")\n\n**[Second]('+u2+' "Second")**\n\n[B22222]('+u2+')\n'
  rows=cv2.table_rows(t);self.assertEqual(rows[0]['pn'],'PART_NUMBER_NOT_DISPLAYED');self.assertEqual(rows[0]['name'],'Model 300 Bracket');self.assertEqual(rows[1]['pn'],'B22222')
 def test_wrong_assembly_response_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'wrong assembly'):cv2.parse_leaf(self.text,'DIAGRAM',2)
 def test_every_structural_product_link_is_accounted(self):
  parsed=cv2.parse_leaf(self.text,'DIAGRAM',1);self.assertEqual(len(parsed['rows']),11);self.assertEqual(parsed['structural']['callout_markers'],6)
 def test_partial_product_renderer_is_not_no_image_evidence(self):
  d=cv2.parse_product_detail(PARTIAL.read_text(encoding='utf-8'));self.assertFalse(d['complete']);self.assertFalse(d['images'])
 def test_complete_product_structure_and_gallery(self):
  t='Title: Example\nURL Source: https://www.moparamerica.com/oem-parts/x\n# Example - Mopar (0012-AB)\n![Image 1: OEM](https://cdn-product-images.revolutionparts.io/a.webp)\n**Genuine Mopar Parts**\n* Part Number: 0012-AB\n* Description: Exact\n'
  d=cv2.parse_product_detail(t);self.assertTrue(d['complete']);self.assertEqual(d['pn'],'0012-AB');self.assertEqual(len(d['images']),1)
class SchemaAndImage(unittest.TestCase):
 def db(self):
  td=tempfile.TemporaryDirectory();p=Path(td.name)/'x.sqlite3';c=sqlite3.connect(p);c.executescript((ROOT/'catalog'/'schema_v2.sql').read_text());return td,c
 def test_schema_compiles(self):
  td,c=self.db();self.assertEqual(c.execute('pragma integrity_check').fetchone()[0],'ok');c.close();td.cleanup()
 def test_context_trigger_rejects_cross_variation_taxonomy_parent(self):
  td,c=self.db();c.execute("insert into vehicles values('a',2017,'Dodge','Challenger')");c.execute("insert into variations values('v1','a','SXT / 3.6L V6 / Gas','SXT','3.6L V6','Gas','r1','u1','d','e',1,'VALIDATED',null,null)");c.execute("insert into variations values('v2','a','R/T / 5.7L V8 / Gas','R/T','5.7L V8','Gas','r2','u2','d','e',1,'VALIDATED',null,null)");c.execute("insert into taxonomy_nodes values('p','v1',null,'CATEGORY','P','P','p','u',1,'DISCOVERED',null)")
  with self.assertRaisesRegex(sqlite3.IntegrityError,'parent variation'):c.execute("insert into taxonomy_nodes values('x','v2','p','SUBCATEGORY','X','X','x','u',1,'DISCOVERED',null)")
  c.close();td.cleanup()
 def test_image_classifier_rejects_uniform_placeholder(self):
  im=Image.new('RGBA',(64,64),(255,255,255,255));b=io.BytesIO();im.save(b,format='PNG');m=cv2.classify_image_bytes(b.getvalue());self.assertEqual(m['placeholder'],'PLACEHOLDER_SUSPECT')
 def test_image_classifier_records_content_pixels(self):
  im=Image.new('RGB',(64,64),'white');im.putpixel((2,2),(0,0,0));b=io.BytesIO();im.save(b,format='PNG');m=cv2.classify_image_bytes(b.getvalue());self.assertEqual(m['placeholder'],'CONTENT_IMAGE');self.assertEqual(m['width'],64)
class FailClosedQualityTests(unittest.TestCase):
 def copydb(self,td):
  p=Path(td)/'qa.sqlite3';shutil.copy2(ROOT/'catalog'/'v2'/'checkpoints'/'v3_parser_validation.sqlite3',p);return p
 def test_current_scope_revalidation_is_stable_and_controls_1069_categories(self):
  r=json.loads((ROOT/'catalog'/'v2'/'manifests'/'route_revalidation.json').read_text());self.assertTrue(all(x['sets_identical'] for x in r['variations']));self.assertEqual(sum(x['current_count'] for x in r['variations']),1069)
 def test_agent9_never_promotes_nonterminal_rows(self):
  with tempfile.TemporaryDirectory() as td:
   db=self.copydb(td);old_db,old_out=qa.DB,qa.OUT;qa.DB=db;qa.OUT=Path(td)/'reports'
   try:
    with contextlib.redirect_stdout(io.StringIO()):self.assertFalse(qa.final())
    c=sqlite3.connect(db);self.assertEqual(c.execute("select count(*) from catalogue_leaves where status='QA_PASSED'").fetchone()[0],0);c.close()
   finally:qa.DB,qa.OUT=old_db,old_out
 def test_manual_defect_is_never_auto_resolved(self):
  with tempfile.TemporaryDirectory() as td:
   db=self.copydb(td);c=sqlite3.connect(db);c.execute("insert into defects(defect_id,origin,check_code,severity,responsible_agent,affected_record_ids,description,observed_result,expected_result,source_evidence,reproduction_steps,required_correction,same_pattern_search_requirement,retest_requirements,status,created_at) values('manual-x','MANUAL','EXACT_CHECK','MAJOR','AGENT_9','[]','d','o','e','s','r','c','all','retest','OPEN','2026-08-01T00:00:00Z')");c.commit();c.close();old=qa.DB;qa.DB=db
   try:qa.persist('r',[],{'EXACT_CHECK'});c=sqlite3.connect(db);self.assertEqual(c.execute("select status from defects where defect_id='manual-x'").fetchone()[0],'OPEN');c.close()
   finally:qa.DB=old
 def test_source_auditor_detects_tampered_image_locator(self):
  with tempfile.TemporaryDirectory() as td:
   db=self.copydb(td);c=sqlite3.connect(db);c.execute("update image_observations set source_locator='markdown:char:0-1' where image_observation_id=(select image_observation_id from image_observations limit 1)");c.commit();c.close();old=aud.DB;aud.DB=db
   try:
    with contextlib.redirect_stdout(io.StringIO()):self.assertFalse(aud.source_audit())
    c=sqlite3.connect(db);self.assertGreater(c.execute("select count(*) from defects where check_code='ROW_EVIDENCE_ASSOCIATION' and status='OPEN'").fetchone()[0],0);c.close()
   finally:aud.DB=old
if __name__=='__main__':unittest.main(verbosity=2)
