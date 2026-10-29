"""Unavailable headless native hardware must not hide protected regressions."""
import ast
import os
from pathlib import Path
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
class HeadlessGpuOutcome(unittest.TestCase):
    def classify(self, value, native, headless):
        tree=ast.parse((ROOT/'tests/fingerprint/probe_canvas_canonical_gpu.py').read_text())
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='headless_webgpu_unavailable')
        scope={'os':os};exec(compile(ast.Module(body=[node],type_ignores=[]),'gpu-outcome','exec'),scope)
        with patch.dict(os.environ,{'MOZ_HEADLESS':'1' if headless else '0'}):
            return scope[node.name](value,native)
    def test_only_missing_native_adapter_in_headless_mode_is_inconclusive(self):
        missing={'available':False,'reason':'no adapter'}
        self.assertTrue(self.classify(missing,missing,True))
        self.assertFalse(self.classify(missing,missing,False))
        self.assertFalse(self.classify(missing,{'available':True},True))
        self.assertFalse(self.classify({'available':False,'reason':'navigator.gpu absent'},missing,True))
        self.assertFalse(self.classify({'error':'policy broken'},missing,True))
