"""Compile the exact default-framebuffer MSAA selection branch from Gecko."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
class ReferenceDefaultSamples(unittest.TestCase):
 def test_default_backing_samples_use_captured_profile_on_every_allocation(self):
  source=(ROOT/'firefox-src/dom/canvas/WebGLContext.cpp').read_text();start=source.index('bool WebGLContext::EnsureDefaultFB()');end=source.index('\n}',start)
  body=source[start:end]
  block=re.search(r'uint32_t samples = mMsaaSamples;.*?\n        mDefaultFB = gl::MozFramebuffer::Create\(\s*gl, attemptSize, samples, mOptions.depth, mOptions.stencil\);',body,re.S)
  self.assertIsNotNone(block,'Default framebuffer must bound actual allocation samples by the captured reference')
  selection=block.group().split('        mDefaultFB =')[0]
  program=r'''
#include "CloakfoxGPUProfileCore.hpp"
#include <cassert>
#include <algorithm>
#include <cstdint>
struct Options { uint16_t cloakfoxPersonaProfile; };
uint32_t Allocate(uint32_t requested,uint16_t code) {
 const auto mMsaaSamples=requested;const Options mOptions{code};
'''+selection+r'''
 return samples;
}
int main(){
 for(const auto& p:CloakfoxGPUReference::kProfiles){
  const auto cap=CloakfoxGPUReference::Cap(p.code,true,36183);
  assert(Allocate(8,p.code)==std::min(8u,cap));assert(Allocate(255,p.code)==cap);
  assert(Allocate(2,p.code)==2);assert(Allocate(0,p.code)==0);
 }
 assert(Allocate(8,0)==8&&Allocate(8,0x101)==8);
}
'''
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'test.cpp').write_text(program)
   subprocess.run(['clang++','-std=c++17','-Wall','-Wextra','-Werror','-I'+str(ROOT/'additions/cloakcfg'),str(p/'test.cpp'),'-o',str(p/'test')],check=True,capture_output=True,text=True)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
