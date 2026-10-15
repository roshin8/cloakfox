"""Execute the canonical decoder flag policy, including explicit no-conversion."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class ImageColor(unittest.TestCase):
 def test_decode_policy(self):
  s=(ROOT/'firefox-src/dom/canvas/CanvasUtils.cpp').read_text()
  a=s.index('uint32_t CanonicalImageDecodeFlags(');b=s.index('\n}',a)+2
  fixture='''#include <cassert>
#include <cstdint>
struct imgIContainer{enum{FLAG_DECODE_NO_COLORSPACE_CONVERSION=16,FLAG_DECODE_TO_SRGB_COLORSPACE=2048};};
'''+s[a:b]+'''
int main(){assert(CanonicalImageDecodeFlags(3,false)==3);assert(CanonicalImageDecodeFlags(3,true)==2051);assert(CanonicalImageDecodeFlags(19,true)==19);assert(CanonicalImageDecodeFlags(2051,true)==2051);}
'''
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'color.cpp';p.write_text(fixture);exe=Path(d)/'color';subprocess.run(['c++','-std=c++17',str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
