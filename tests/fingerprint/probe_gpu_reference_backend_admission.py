#!/usr/bin/env python3
"""Compare every derived scalar/range/precision requirement with staged CPU GL.

Dependency admission evidence only: this does not replace the actual Firefox159
window/worker/resource-operation probe. The display explicitly selects the pinned
Vulkan SwiftShader device and never falls back to host GPU contexts.
"""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def probe(directory):
 directory=Path(directory).resolve()
 names=['libEGL_cloakfox_canonical.dylib','libGLESv2_cloakfox_canonical.dylib','libvk_swiftshader.dylib']
 result={'directory':str(directory),'scope':'staged canonical dependency capability admission; actual Firefox159 integration remains separately required','librarySHA256':{name:hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in names},'contexts':[],'checks':[]}
 C.CDLL(str(directory/names[1]),mode=C.RTLD_LOCAL);egl=C.CDLL(str(directory/names[0]),mode=C.RTLD_LOCAL)
 def bind(name,result,*args):
  fn=getattr(egl,name);fn.restype=result;fn.argtypes=args;return fn
 proc=bind('eglGetProcAddress',C.c_void_p,C.c_char_p)
 def gl(name,result,*args):
  address=proc(name.encode());assert address,name;return C.CFUNCTYPE(result,*args)(address)
 display=bind('eglGetPlatformDisplay',C.c_void_p,C.c_uint,C.c_void_p,C.POINTER(C.c_ssize_t))(0x3202,None,(C.c_ssize_t*5)(0x3203,0x3450,0x3209,0x3487,0x3038))
 major,minor=C.c_int(),C.c_int();assert bind('eglInitialize',C.c_uint,C.c_void_p,C.POINTER(C.c_int),C.POINTER(C.c_int))(display,C.byref(major),C.byref(minor))
 config,count=C.c_void_p(),C.c_int()
 assert bind('eglChooseConfig',C.c_uint,C.c_void_p,C.POINTER(C.c_int),C.POINTER(C.c_void_p),C.c_int,C.POINTER(C.c_int))(display,(C.c_int*13)(0x3033,1,0x3040,4,0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3038),C.byref(config),1,C.byref(count)) and count.value
 assert bind('eglBindAPI',C.c_uint,C.c_uint)(0x30a0)
 create=bind('eglCreateContext',C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p,C.POINTER(C.c_int));surface_create=bind('eglCreatePbufferSurface',C.c_void_p,C.c_void_p,C.c_void_p,C.POINTER(C.c_int));current=bind('eglMakeCurrent',C.c_uint,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p)
 destroy_surface=bind('eglDestroySurface',C.c_uint,C.c_void_p,C.c_void_p);destroy_context=bind('eglDestroyContext',C.c_uint,C.c_void_p,C.c_void_p)
 catalog=json.loads((ROOT/'additions/cloakcfg/gpu-reference-executable.json').read_text())
 try:
  for version,kind in [(2,'webgl'),(3,'webgl2')]:
   context=create(display,config,None,(C.c_int*3)(0x3098,version,0x3038));assert context
   surface=surface_create(display,config,(C.c_int*5)(0x3057,8,0x3056,8,0x3038));assert surface
   try:
    assert current(display,surface,surface,context)
    renderer=gl('glGetString',C.c_char_p,C.c_uint)(0x1f01).decode();assert 'SwiftShader' in renderer and 'Vulkan' in renderer,renderer
    integer=gl('glGetIntegerv',None,C.c_uint,C.POINTER(C.c_int));floating=gl('glGetFloatv',None,C.c_uint,C.POINTER(C.c_float));integer64=gl('glGetInteger64v',None,C.c_uint,C.POINTER(C.c_int64));error=gl('glGetError',C.c_uint)
    precision=gl('glGetShaderPrecisionFormat',None,C.c_uint,C.c_uint,C.POINTER(C.c_int),C.POINTER(C.c_int))
    measurements={'kind':kind,'renderer':renderer,'profiles':[]};result['contexts'].append(measurements)
    for profile in catalog['profiles']:
     observed={'code':profile['code'],'record':profile['record'],'family':profile['family'],'scalars':{},'ranges':{},'precision':[]};measurements['profiles'].append(observed)
     for key,entry in profile['contexts'][kind]['parameters'].items():
      enum=int(key);required=entry['value']
      # Recommendation hints are not resource capacities. Timeout/index
      # semantics are enforced by native Gecko, rather than driver budgets.
      if enum in [34467,33000,33001,37447,37137,36203]:continue
      vector=isinstance(required,list)
      if enum in [33901,33902,34045,34047]:value=(C.c_float*2)();floating(enum,value)
      elif enum in [35376,35377,35379]:value=(C.c_int64*2)();integer64(enum,value)
      else:value=(C.c_int*2)();integer(enum,value)
      err=error();actual=list(value) if vector else value[0]
      if vector:ok=(actual[0]<=required[0] and actual[1]>=required[1]) if enum in [33901,33902] else all(a>=b for a,b in zip(actual,required))
      elif enum==35380:ok=actual>0 and required%actual==0
      else:ok=actual<=required if enum==35076 else actual>=required
      observed['ranges' if vector else 'scalars'][key]={'actual':actual,'required':required,'error':err}
      result['checks'].append({'pass':bool(ok and err==0),'name':profile['family']+'/'+kind+'/'+entry['name'],'actual':actual,'required':required,'error':err})
     for entry in profile['contexts'][kind]['shaderPrecisionFormats']:
      bounds=(C.c_int*2)();bits=C.c_int();precision(entry['shaderType'],entry['precisionType'],bounds,C.byref(bits));err=error();actual=[*bounds,bits.value];r=entry['shaderPrecisionFormat'];required=[r['rangeMin'],r['rangeMax'],r['precision']]
      observed['precision'].append({'shaderType':entry['shaderType'],'precisionType':entry['precisionType'],'actual':actual,'required':required,'error':err});result['checks'].append({'pass':actual==required and err==0,'name':profile['family']+'/'+kind+'/precision/'+str(entry['shaderType'])+','+str(entry['precisionType']),'actual':actual,'required':required,'error':err})
   finally:current(display,None,None,None);destroy_surface(display,surface);destroy_context(display,context)
 finally:bind('eglTerminate',C.c_uint,C.c_void_p)(display)
 return result

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',nargs='?',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args()
 if args.directory is None:
  directory=os.environ.get('CLOAKFOX_CANONICAL_GPU_DIR')
  if not directory:parser.error('directory or CLOAKFOX_CANONICAL_GPU_DIR is required')
  args.directory=Path(directory)
 if args.output is None and os.environ.get('REPORT_DIR'):
  args.output=Path(os.environ['REPORT_DIR'])/'result.json'
 result=probe(args.directory)
 if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
 failures=[x for x in result['checks'] if not x['pass']];print(json.dumps({'checks':len(result['checks']),'failures':failures,'librarySHA256':result['librarySHA256'],'output':str(args.output) if args.output else None},indent=2));raise SystemExit(bool(failures))
