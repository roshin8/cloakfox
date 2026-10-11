from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from release_update import update_xml
class UpdateXML(unittest.TestCase):
    def test_native_complete_patch(self):
        xml = update_xml('155.0.1', '20260908010101', 'https://updates.owner.net/release.mar', 50, 'a'*128)
        patch = ET.fromstring(xml).find('update/patch')
        self.assertEqual(patch.attrib['hashFunction'], 'sha512')
        self.assertEqual(patch.attrib['type'], 'complete')
    def test_unsafe_metadata(self):
        for url in ['http://updates.owner.net/a.mar', 'https://user@updates.owner.net/a.mar', 'https://updates.owner.net/a.dmg']:
            with self.assertRaises(ValueError):
                update_xml('155.0.1','20260908010101',url,10,'a'*128)
