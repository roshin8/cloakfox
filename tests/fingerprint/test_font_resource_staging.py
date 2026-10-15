"""Run real font staging across an existing checkout and repeat invocation."""
from pathlib import Path
import hashlib,json,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class FontStaging(unittest.TestCase):
 def test_updates_owned_lists_without_duplicate_or_unrelated_changes(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);pack=root/'pack';target=root/'source';(pack/'macos').mkdir(parents=True);(pack/'licenses').mkdir();target.mkdir()
   (pack/'macos/A.ttf').write_bytes(b'font-a');(pack/'macos/NotoColorEmoji.ttf').write_bytes(b'emoji');(pack/'licenses/Emoji.txt').write_text('license');(pack/'FONT-NOTICES.txt').write_text('notices')
   def record(rel):return {'file':rel,'sha256':hashlib.sha256((pack/rel).read_bytes()).hexdigest()}
   data={'version':1,'fonts':[record('macos/A.ttf'),record('macos/NotoColorEmoji.ttf')],'licenses':[record('licenses/Emoji.txt')],'notices':[record('FONT-NOTICES.txt')]};(pack/'font-manifest.json').write_text(json.dumps(data))
   old='''# upstream rule stays\nFINAL_TARGET_FILES.fonts += ["Upstream.ttf"]\n\n# Cloakfox: bundled open-substitute font pack (all platforms).\nDIST_SUBDIR = ""\nFINAL_TARGET_FILES.fonts += [\n    "A.ttf",\n]\n''';(target/'moz.build').write_text(old)
   cmd=[sys.executable,str(ROOT/'scripts/stage-font-resources.py'),'--bundle',str(pack),'--target',str(target)]
   p=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
   first=(target/'moz.build').read_text();self.assertEqual(first.count('"A.ttf"'),1);self.assertEqual(first.count('"NotoColorEmoji.ttf"'),1);self.assertIn('FINAL_TARGET_FILES.fonts += ["Upstream.ttf"]',first);self.assertEqual((target/'NotoColorEmoji.ttf').read_bytes(),b'emoji')
   subprocess.run(cmd,check=True,capture_output=True);self.assertEqual((target/'moz.build').read_text(),first)
   (pack/'macos/NotoColorEmoji.ttf').write_bytes(b'tampered');p=subprocess.run(cmd,capture_output=True,text=True);self.assertNotEqual(p.returncode,0);self.assertEqual((target/'NotoColorEmoji.ttf').read_bytes(),b'emoji')
if __name__=='__main__':unittest.main()
