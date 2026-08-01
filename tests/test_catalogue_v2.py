import importlib.util,json,sqlite3,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('catalogue_v2',ROOT/'scripts'/'catalogue_v2.py')
cv2=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(cv2)
QSPEC=importlib.util.spec_from_file_location('catalogue_qa',ROOT/'scripts'/'catalogue_qa.py')
qa=importlib.util.module_from_spec(QSPEC);QSPEC.loader.exec_module(qa)

class SkillAndManifestTests(unittest.TestCase):
 def test_ten_project_skills_are_narrow_and_testable(self):
  files=sorted((ROOT/'catalog'/'skills').glob('*/SKILL.md'))
  self.assertEqual(len(files),10)
  for p in files:
   t=p.read_text(encoding='utf-8')
   self.assertIn('version: 1.0.0',t);self.assertIn('## Procedure',t);self.assertIn('## Tests',t);self.assertIn('## Completion Gate',t)
 def test_exact_six_variations(self):
  m=json.loads((ROOT/'catalog'/'manifests'/'variation_manifest.json').read_text(encoding='utf-8'))
  self.assertEqual(len(m['vehicles']),2);self.assertEqual([len(v['variations']) for v in m['vehicles']],[3,3])
  routes=[x['route_slug'] for v in m['vehicles'] for x in v['variations']]
  self.assertEqual(len(routes),len(set(routes)))
  self.assertTrue(all(x.startswith('v-2017-') for x in routes))

class ParserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.door=(ROOT/'evidence/mopar/mvsa_44114_research/raw/challenger/front-door__assembly-01.md').read_text(encoding='utf-8')
  cls.belts=(ROOT/'evidence/mopar/mvsa_44114_research/raw/challenger/seat-belts__assembly-01.md').read_text(encoding='utf-8')
 def test_fixture_taxonomy_and_callouts(self):
  self.assertEqual([x['assembly_no'] for x in cv2.assembly_selectors(self.door,'https://www.moparamerica.com/x')],[1,2,3])
  mapping,empty,total=cv2.callout_map(self.door,1)
  self.assertEqual(total,18);self.assertEqual(empty,[]);self.assertGreaterEqual(len(mapping),30)
 def test_every_fixture_product_has_displayed_number_and_image(self):
  cards=cv2.product_cards(self.door)
  self.assertEqual(len(cards),56)
  self.assertTrue(all(v['oem_part_number_source']!='PART_NUMBER_NOT_DISPLAYED' for v in cards.values()))
  self.assertTrue(all(v['images'] for v in cards.values()))
 def test_part_numbers_remain_strings_with_zero_hyphen_suffix(self):
  u='https://www.moparamerica.com/oem-parts/example'
  text=f'[![Image 1: Example](https://cdn-product-images.revolutionparts.io/assets/x.webp)]({u} "Example - Part No 0012-AB")\n**[Example]({u})**\n[0012-AB]({u} "Left.")\n**Description:** Exact.'
  card=cv2.product_cards(text)[u]
  self.assertEqual(card['oem_part_number_source'],'0012-AB')
  self.assertEqual(card['fitment_notes_source'],'Left.')
 def test_absent_number_is_not_guessed_from_url(self):
  u='https://www.moparamerica.com/oem-parts/mopar-example-68123456aa'
  card=cv2.product_cards(f'**[Example]({u})**')[u]
  self.assertEqual(card['oem_part_number_source'],'PART_NUMBER_NOT_DISPLAYED')
 def test_single_diagram_fixture(self):
  t='# Example for 2017 Dodge Challenger\n![Image 1: Example #0](https://cdn-illustrations.revolutionparts.io/a/b.png)'
  a=cv2.assembly_selectors(t,'https://www.moparamerica.com/example')
  self.assertEqual(len(a),1);self.assertEqual(a[0]['assembly_no'],0)

class SchemaTests(unittest.TestCase):
 def test_schema_compiles_and_rejects_orphan(self):
  c=sqlite3.connect(':memory:');c.executescript((ROOT/'catalog'/'schema_v2.sql').read_text(encoding='utf-8'));c.execute('PRAGMA foreign_keys=ON')
  with self.assertRaises(sqlite3.IntegrityError):c.execute("INSERT INTO variations(variation_id,vehicle_id,variation_source_label,trim_source,engine_source,route_slug,source_url,expected_category_links,validation_title,validation_status) VALUES('x','missing','x','x','x','x','https://x',1,'x','NOT_STARTED')")
 def test_deterministic_ids(self):
  self.assertEqual(cv2.sid('record','a','b'),cv2.sid('record','a','b'))
  self.assertNotEqual(cv2.sid('record','a','b'),cv2.sid('record','a','c'))

class FitmentTests(unittest.TestCase):
 def test_exact_variation_fitment_is_confirmed(self):
  self.assertEqual(qa.fitment_decision('2017 Dodge Challenger R/T Scat Pack 6.4L V8 - Gas',2017,'Dodge','Challenger','R/T Scat Pack / 6.4L V8 / Gas')[1],'FITMENT_AUDITED')
 def test_same_model_wrong_variation_is_conflict(self):
  self.assertEqual(qa.fitment_decision('2017 Dodge Challenger SXT 3.6L V6 - Gas',2017,'Dodge','Challenger','R/T / 5.7L V8 / Gas')[1],'FITMENT_CONFLICT')
 def test_configured_route_remains_evidence_without_contradiction(self):
  self.assertEqual(qa.fitment_decision('Engines: 3.6L V6; 5.7L V8',2017,'Dodge','Challenger','R/T / 5.7L V8 / Gas')[0],'APPLICABLE_CONFIGURED_ROUTE')

class IndependentQualitySeedTests(unittest.TestCase):
 def test_quality_gate_catches_seeded_major_failures(self):
  import shutil
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'seeded.sqlite3';shutil.copy2(ROOT/'catalog'/'v2'/'checkpoints'/'preproduction_validation.sqlite3',db);c=sqlite3.connect(db)
   leaf=c.execute("SELECT catalogue_leaf_id FROM catalogue_leaves WHERE status='EXTRACTED' AND visible_row_expected IS NOT NULL LIMIT 1").fetchone()[0]
   c.execute("UPDATE catalogue_leaves SET visible_row_expected=visible_row_expected+1,status='QA_PASSED' WHERE catalogue_leaf_id=?",(leaf,))
   rid=c.execute('SELECT record_id FROM part_records LIMIT 1').fetchone()[0];c.execute("UPDATE part_records SET oem_part_number_source='WRONG999',oem_part_number_normalized='WRONG999' WHERE record_id=?",(rid,))
   sha=c.execute('SELECT image_sha256 FROM image_assets LIMIT 1').fetchone()[0];c.execute("UPDATE image_assets SET local_image_path='v2/images/missing.bin' WHERE image_sha256=?",(sha,))
   oid=c.execute("SELECT image_observation_id FROM image_observations WHERE image_role NOT LIKE 'STATIC_%' LIMIT 1").fetchone()[0];c.execute("UPDATE image_observations SET image_source_url='https://cdn-product-images.revolutionparts.io/assets/wrong-seeded.webp' WHERE image_observation_id=?",(oid,));c.commit();c.close()
   old=qa.DB;qa.DB=db
   try:
    _,fails=qa.run_checks(final=True);codes={x['code'] for x in fails}
   finally:qa.DB=old
   self.assertIn('ROW_COUNT_MISMATCH',codes);self.assertIn('SOURCE_RECORD_ASSOCIATION',codes);self.assertIn('IMAGE_ASSET_INTEGRITY',codes);self.assertIn('WRONG_IMAGE_ASSOCIATION',codes)

if __name__=='__main__':unittest.main(verbosity=2)
