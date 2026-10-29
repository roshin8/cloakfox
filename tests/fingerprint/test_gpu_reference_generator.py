"""Pinned source admission metadata and deterministic generated registries."""
import importlib.util
import json
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
if __name__=='__main__':unittest.main()
