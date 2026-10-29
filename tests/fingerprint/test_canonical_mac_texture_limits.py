"""Execute Gecko's actual macOS texture workaround and limit application."""
from pathlib import Path
import re,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
def test_canonical_context_retains_real_cpu_capacity_and_host_driver_workaround():
 source=(ROOT/'firefox-src/gfx/gl/GLContext.cpp').read_text();start=source.index('// https://bugzilla.mozilla.org/show_bug.cgi?id=1544446');block=source[start:source.index('#endif',start)]
 assert 'if (!mDesc.canonicalGpu)' in block,'Mojave physical-driver workaround must not clamp the verified canonical CPU renderer'
 start=source.index('    const auto fnLimit =');end=source.index('\n  }\n',start);limits=source[start:end]
 program=r'''
#include <algorithm>
#include <cassert>
#include <climits>
struct Desc {bool canonicalGpu;};
void Check(bool canonical,int backend,int expected){
 const Desc mDesc{canonical};int maxTexSize=INT_MAX,maxCubeSize=INT_MAX;
 int mMaxTextureSize=backend,mMaxRenderbufferSize=backend,mMaxCubeMapTextureSize=backend;
 bool mNeedsTextureSizeChecks=false;
'''+block+'\n'+limits+r'''
 assert(mMaxTextureSize==expected&&mMaxRenderbufferSize==expected&&mMaxCubeMapTextureSize==expected);
 assert(mNeedsTextureSizeChecks==(backend>expected));
}
int main(){Check(false,16384,8192);Check(true,16384,16384);Check(true,8192,8192);Check(false,4096,4096);}
'''
 with tempfile.TemporaryDirectory() as tmp:
  p=Path(tmp);(p/'test.cpp').write_text(program);subprocess.run(['clang++','-std=c++17','-Wall','-Wextra','-Werror',str(p/'test.cpp'),'-o',str(p/'test')],check=True);subprocess.run([str(p/'test')],check=True)
 provider=(ROOT/'firefox-src/gfx/gl/GLContextProviderEGL.cpp').read_text();start=provider.index('GLContextProviderEGL::CreateHeadless(');body=provider[start:provider.index('return ret.forget();',start)]
 assert 'if (desc.canonicalGpu)' in body and 'GLLibraryEGL::GetCanonical(out_failureId)' in body
 assert 'ret->RendererString().Find("SwiftShader")' in body and 'ret->RendererString().Find("Vulkan")' in body
 assert 'FEATURE_FAILURE_CANONICAL_GPU_DEVICE' in body
