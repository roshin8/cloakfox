"""Fixed software precision is already standardized; never invent stronger GLES."""
from pathlib import Path
import re,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
def test_actual_precision_profile_selector():
 s=(ROOT/'firefox-src/dom/canvas/WebGLContext.cpp').read_text();a=s.index('constexpr GLenum SHADER_TYPES[]');m=re.search(r'if \((desc\.options\.cloakfoxBackendProfile.*?)\) \{',s[a:],re.S);assert m;condition=m.group(1)
 code='''#include <cassert>
struct Desc{struct Options{bool cloakfoxBackendProfile,cloakfoxCanonicalGpu;}options;};
bool genericProfile(bool p,bool c){Desc desc{{p,c}};return '''+condition+''';}
int main(){assert(genericProfile(true,false));assert(!genericProfile(true,true));assert(!genericProfile(false,false));assert(!genericProfile(false,true));}
'''
 with tempfile.TemporaryDirectory()as d:
  p=Path(d)/'test.cpp';p.write_text(code);exe=Path(d)/'test';subprocess.run(['c++',str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
