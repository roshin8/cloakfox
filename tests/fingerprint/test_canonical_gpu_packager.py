"""Pinned signed renderer dylibs must not be rewritten by Gecko's stripper."""
from pathlib import Path
import ast,sys,types
ROOT=Path(__file__).resolve().parents[2]
def test_actual_strip_policy_uses_original_source_for_pinned_libraries():
 p=ROOT/'firefox-src/python/mozbuild/mozpack/executables.py';tree=ast.parse(p.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='may_strip');module=ast.Module(body=[node],type_ignores=[])
 old=sys.modules.get('buildconfig');sys.modules['buildconfig']=types.SimpleNamespace(substs={'PKG_STRIP':True})
 try:
  env={'os':__import__('os')};exec(compile(module,str(p),'exec'),env);policy=env['may_strip']
  for name in ['libEGL_cloakfox_canonical.dylib','libGLESv2_cloakfox_canonical.dylib','libvk_swiftshader.dylib']:
   assert not policy('/verified/app/Contents/Resources/canonical-gpu/'+name)
  assert policy('/verified/app/Contents/MacOS/XUL')
  assert policy('/other/libEGL.dylib')
  sys.modules['buildconfig'].substs['PKG_STRIP']=False
  assert not policy('/verified/app/Contents/MacOS/XUL')
 finally:
  if old is None:sys.modules.pop('buildconfig',None)
  else:sys.modules['buildconfig']=old
 files=(ROOT/'firefox-src/python/mozbuild/mozpack/files.py').read_text();assert 'if may_strip(self.path):'in files
