"""Actual canonical GL readback refusal policy, including unavailable identity."""
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]/'firefox-src'


def test_actual_missing_seed_readback_policy():
    source=(ROOT/'dom/canvas/ClientWebGLContext.cpp').read_text()
    start=source.index('static bool CloakfoxRejectUnprotectedCanonicalReadback(')
    helper=source[start:source.index('\n}\n',start)+3]
    metadata=(ROOT/'gfx/2d/CanvasPrivacy.cpp').read_text()
    metadata=metadata[metadata.index('CanvasPrivacyMetadata NormalizeCanvasPrivacyMetadata('):metadata.index('void AddCanvasPixelSource(')]
    harness='''#include <cassert>\n#include <initializer_list>\n#include "CanvasPrivacy.h"\nnamespace mozilla::gfx {\n'''+metadata+'}\nusing namespace mozilla;\n'+helper+r'''
int main(){
 const gfx::CanvasPrivacyMetadata good{1,7,123,456,64|512};
 const gfx::CanvasPrivacyMetadata unknown{1,7,123,456,64|512|1};
 const gfx::CanvasPrivacyMetadata missingOwner{0,0,0,0,64|512};
 const gfx::CanvasPrivacyMetadata native{1,7,123,456,64};
 for(auto policy:{good,unknown,missingOwner,native})for(bool canonical:{false,true})for(uint32_t seed:{0u,123u}){
  const bool expect=canonical&&!gfx::CanExtractCanonicalCanvasPixels(policy)&&!seed;
  assert(CloakfoxRejectUnprotectedCanonicalReadback(canonical,policy,seed)==expect);
 }
 assert(!CloakfoxRejectUnprotectedCanonicalReadback(true,good,0));
 assert(CloakfoxRejectUnprotectedCanonicalReadback(true,unknown,0));
 assert(!CloakfoxRejectUnprotectedCanonicalReadback(true,unknown,123));
}
'''
    with tempfile.TemporaryDirectory()as directory:
        path=Path(directory)/'missing-seed.cpp';path.write_text(harness)
        binary=Path(directory)/'missing-seed'
        subprocess.run(['c++','-std=c++17','-I',str(ROOT/'gfx/2d'),str(path),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)


def test_missing_seed_guards_run_before_pixels_or_ipc_and_reuse_capture():
    source=(ROOT/'dom/canvas/ClientWebGLContext.cpp').read_text()
    for signature,end,action in [
        ('UniquePtr<uint8_t[]> ClientWebGLContext::GetImageBuffer(', 'ClientWebGLContext::GetInputStream(', 'GetSurfaceSnapshot(&any)'),
        ('bool ClientWebGLContext::DoReadPixels(', 'ClientWebGLContext::DoReadPixelsAsync()', 'child->FlushPendingCmds()'),
        ('ClientWebGLContext::DoReadPixelsAsync()', '// ----------------', 'child->FlushPendingCmds()')]:
        start=source.index(signature)
        if signature=='ClientWebGLContext::DoReadPixelsAsync()':block=source[start:]
        else:block=source[start:source.index(end,start+len(signature))]
        assert block.index('CloakfoxRejectUnprotectedCanonicalReadback(')<block.index(action)
        assert 'noiseSeed' in block
    start=source.index('bool ClientWebGLContext::DoReadPixels(')
    synchronous=source[start:source.index('ClientWebGLContext::DoReadPixelsAsync()',start)]
    assert 'LOCAL_GL_INVALID_OPERATION' in synchronous
    assert 'CloakfoxNoiseReadPixels(desc, res, dest, noiseSeed)' in synchronous
    asynchronous=source[source.index('ClientWebGLContext::DoReadPixelsAsync()'):]
    guard=asynchronous.index('CloakfoxRejectUnprotectedCanonicalReadback(')
    assert asynchronous.index('promise->Reject(NS_ERROR_NOT_AVAILABLE',guard)<asynchronous.index('child->SendReadPixelsAsync')
