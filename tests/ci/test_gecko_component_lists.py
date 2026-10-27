"""Catch moz.build strict-order errors before expensive native configuration."""
import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ComponentBuildLists(unittest.TestCase):
    def test_component_install_lists_are_sorted_and_keep_existing_files(self):
        component = ROOT / 'additions/browser/components/cloakfox'
        source = (component / 'moz.build').read_text()
        lists = re.findall(r'(?ms)^([A-Z_]+(?:\.[a-z_]+)? \+= )\[(.*?)\]', source)
        self.assertGreater(len(lists), 1)
        for label, body in lists:
            names = ast.literal_eval('[' + body + ']')
            with self.subTest(list=label):
                self.assertEqual(names, sorted(names, key=str.lower))
                self.assertEqual(len(names), len(set(names)))
                for name in names:
                    self.assertTrue((component / name).is_file(), name)
