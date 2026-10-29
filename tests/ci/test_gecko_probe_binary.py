"""Source-level guard: scope probes must exercise the requested build binary."""
import ast
import os
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]


class ProbeBinarySelection(unittest.TestCase):
    def test_site_data_probes_honor_explicit_binary(self):
        requested='/tmp/owned-firefox159-probe/cloakfox'
        for name in ('probe_site_data_scope.py','probe_site_data_cache_scope.py'):
            tree=ast.parse((ROOT/'tests/fingerprint'/name).read_text())
            value=next(node.value for node in ast.walk(tree) if isinstance(node,ast.Assign)
                       and any(isinstance(target,ast.Attribute) and target.attr=='binary_location' for target in node.targets))
            with self.subTest(probe=name),patch.dict(os.environ,{'CLOAKFOX_BIN':requested}):
                selected=eval(compile(ast.Expression(value),name,'eval'),{'os':os})
                self.assertEqual(selected,requested)
