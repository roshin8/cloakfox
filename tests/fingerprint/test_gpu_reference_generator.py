"""Pinned source admission metadata and deterministic generated registries."""
import importlib.util
import json
import gzip
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
class ReferenceGenerator(unittest.TestCase):
 def test_checked_in_registry_is_reproducible(self):
  subprocess.run(['python3',str(ROOT/'scripts/generate-gpu-reference-profiles.py'),'--check'],check=True)
 def test_changed_reference_bytes_are_rejected_before_any_output(self):
  spec=importlib.util.spec_from_file_location('reference_generator',ROOT/'scripts/generate-gpu-reference-profiles.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as tmp:
   directory=Path(tmp);(directory/'additions/cloakcfg').mkdir(parents=True)
   (directory/'additions/cloakcfg/gpu-reference-records.json').write_bytes((ROOT/'additions/cloakcfg/gpu-reference-records.json').read_bytes()+b' ')
   module.ROOT=directory
   with self.assertRaisesRegex(ValueError,'Immutable paired'):module.main()
   self.assertEqual(list((directory/'additions/cloakcfg').iterdir()),[directory/'additions/cloakcfg/gpu-reference-records.json'])
 def test_changed_full_source_bytes_are_rejected(self):
  spec=importlib.util.spec_from_file_location('reference_generator',ROOT/'scripts/generate-gpu-reference-profiles.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as tmp:
   directory=Path(tmp);(directory/'additions/cloakcfg').mkdir(parents=True)
   (directory/'additions/cloakcfg/gpu-full-reference-records.json.gz').write_bytes(b'changed')
   module.ROOT=directory
   with self.assertRaisesRegex(ValueError,'Immutable full GPU source'):module.load_full()
 def test_every_derivation_has_source_pair_and_precise_adaptation_provenance(self):
  derived=json.loads((ROOT/'additions/cloakcfg/gpu-reference-executable.json').read_text());source=json.loads((ROOT/'additions/cloakcfg/gpu-reference-records.json').read_text());records={r['id']:r for r in source['records']}
  self.assertEqual({r['family'] for r in derived['profiles']},{'apple','intel','amd','nvidia'})
  for profile in derived['profiles']:
   record=records[profile['record']]
   self.assertEqual((profile['renderer'],profile['vendor'],profile['os']),(record['gpu']['renderer'],record['gpu']['vendor'],record['os']))
   for context in ['webgl','webgl2']:
    self.assertEqual(profile['sourceContexts'][context],record[context])
    self.assertTrue(profile['adaptations'][context])
    self.assertEqual(profile['contexts'][context]['parameters']['3408']['value'],source['contexts'][record[context]]['staticCapabilities']['parameters']['3408']['value'])
    self.assertNotIn('3408',profile['adaptations'][context],'A measured source4 must not be promoted by an assumed canonical raster precision')
    self.assertNotIn('WEBGL_debug_shaders',profile['contexts'][context]['supportedExtensions'])
    for adaptation in profile['adaptations'][context].values():self.assertTrue(adaptation['reason'])
 def test_observed_profiles_preserve_source_numbers_precision_and_stencil_defaults(self):
  derived=json.loads((ROOT/'additions/cloakcfg/gpu-reference-executable.json').read_text())
  source=json.loads(gzip.decompress((ROOT/'additions/cloakcfg/gpu-full-reference-records.json.gz').read_bytes()))
  records={r['id']:r for r in source['records']}
  observed=derived['observedProfiles']
  self.assertEqual([p['code'] for p in observed[:3]],[36866,36867,36868])
  self.assertEqual(len(observed),9)
  for p in observed:
   if p['code']<=36868:
    legacy=next(old for old in derived['profiles'] if old['code']==p['code']-4096)
    self.assertEqual(p['record'],legacy['record'])
   for name,c in p['contexts'].items():
    original=source['contexts'][records[p['record']][name]]
    self.assertEqual(c['shaderPrecisionFormats'],original['staticCapabilities']['shaderPrecisionFormats'])
    for key,value in original['staticCapabilities']['parameters'].items():self.assertEqual(c['parameters'][key],value)
    for key in ['2963','2968','36004','36005']:self.assertEqual(c['defaults']['stencilMask'],original['observed']['params'][key]['value'])
    self.assertEqual(c['defaults']['stencilMask'],0x7fffffff)
    self.assertEqual(c['supportedExtensions'],[ext for ext in original['staticCapabilities']['supportedExtensions'] if ext not in derived['policyExclusions']])
 def test_full_admission_rejects_source_changes_and_retains_all_lineage(self):
  spec=importlib.util.spec_from_file_location('reference_generator',ROOT/'scripts/generate-gpu-reference-profiles.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  legacy=json.loads((ROOT/'additions/cloakcfg/gpu-reference-records.json').read_text())
  full=json.loads(gzip.decompress((ROOT/'additions/cloakcfg/gpu-full-reference-records.json.gz').read_bytes()))
  admitted,report=module.admit_full(full,legacy)
  self.assertEqual(len(admitted),9)
  self.assertEqual(len(report['records']),len(full['records']))
  self.assertTrue(all(p['sourceRecords'] for p in admitted))
  selected=admitted[-1]
  context=full['contexts'][selected['webgl']]
  context['staticCapabilities']['parameters']['3379']['value']+=1
  changed,_=module.admit_full(full,legacy)
  self.assertNotIn(selected['id'],[r['id'] for r in changed])
  full['source']['archive']['sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'source'):module.admit_full(full,legacy)
if __name__=='__main__':unittest.main()
