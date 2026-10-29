"""Wire baselines must not silently launch the user's installed browser."""
import ast,os,tempfile
from pathlib import Path
from unittest.mock import patch
import unittest
ROOT=Path(__file__).resolve().parents[2]
class StockReference(unittest.TestCase):
 def test_only_explicit_or_owned_stock_binary_is_selected(self):
  source=ROOT/'tests/fingerprint/probe_network_wire.py';tree=ast.parse(source.read_text())
  node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='stock_firefox_binary')
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory).resolve();scope={'Path':Path,'os':os,'__file__':str(root/'tests/fingerprint/probe_network_wire.py')}
   exec(compile(ast.Module(body=[node],type_ignores=[]),'stock-reference','exec'),scope)
   fn=scope[node.name]
   with patch.dict(os.environ,{},clear=True):
    self.assertIsNone(fn())
    own=root/'firefox-src/.tools159/stock159/Firefox.app/Contents/MacOS/firefox';own.parent.mkdir(parents=True);own.write_text('fixture')
    self.assertEqual(fn(),str(own))
   custom=root/'explicit-firefox';custom.write_text('fixture')
   with patch.dict(os.environ,{'FIREFOX_BIN':str(custom)},clear=True):self.assertEqual(fn(),str(custom))
