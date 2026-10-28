import copy,importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('gpu_catalog_generator',ROOT/'scripts/generate-gpu-profile-catalog.py');generator=importlib.util.module_from_spec(spec);spec.loader.exec_module(generator)
class GPUCatalogGenerator(unittest.TestCase):
 def test_generated_cpp_and_js_match_catalog(self):
  data=json.loads((ROOT/'additions/cloakcfg/gpu-profile-catalog.json').read_text());js,cpp=generator.render(data)
  self.assertEqual((ROOT/'additions/browser/components/cloakfox/CloakfoxGPUCatalog.sys.mjs').read_text(),js)
  self.assertEqual((ROOT/'additions/cloakcfg/CloakfoxGPUCatalog.hpp').read_text(),cpp)
 def test_malformed_and_incoherent_catalogs_rejected(self):
  source=json.loads((ROOT/'additions/cloakcfg/gpu-profile-catalog.json').read_text())
  for field,value in [('texture',6144),('vertexUniforms',13),('combinedTexUnits',1),('bufferBytes',1),('storageBytes',2**32),('id',True)]:
   data=copy.deepcopy(source);data['profiles'][0][field]=value
   with self.subTest(field=field),self.assertRaises(ValueError):generator.render(data)
