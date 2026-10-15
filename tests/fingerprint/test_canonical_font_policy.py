"""Compile the production font policy gate; malformed configuration fails closed."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]

class CanonicalFontPolicy(unittest.TestCase):
    def test_actual_policy_preserves_native_chrome_and_unowned_scopes(self):
        text=(ROOT/'firefox-src/gfx/thebes/gfxTextRun.cpp').read_text()
        start=text.index('static bool CloakfoxCanonicalFontPolicy(')
        end=text.index('// End Cloakfox canonical font policy.',start)
        policy=text[start:end]
        program='#include "json.hpp"\n#include <cassert>\n'+policy+r'''
int main(){
 nlohmann::json config={{"canvas:canonical_2d",true}};
 assert(!CloakfoxCanonicalFontPolicy(config,true,true));
 assert(CloakfoxCanonicalFontPolicy(config,true,true,true));
 assert(!CloakfoxCanonicalFontPolicy(config,false,true));
 assert(!CloakfoxCanonicalFontPolicy(config,true,false));
 for(const char* input:{"null","false","1","\"true\"","[]","{}"}){
  config["canvas:canonical_2d"]=nlohmann::json::parse(input);
  assert(!CloakfoxCanonicalFontPolicy(config,true,true));
 }
 config["canvas:canonical_2d"]=true;
 assert(!CloakfoxCanonicalFontPolicy(config,true,true,false));
 config["canvas:canonical_2d"]=false;
 assert(CloakfoxCanonicalFontPolicy(config,true,true,true));
 assert(!CloakfoxCanonicalFontPolicy(nlohmann::json::object(),true,true));
 assert(CloakfoxCanonicalFontPolicy(nlohmann::json::object(),true,true,true));
 assert(!CloakfoxCanonicalFontPolicy(nlohmann::json::object(),false,true,true));
 assert(!CloakfoxCanonicalFontPolicy(nlohmann::json::object(),true,false,true));
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'policy.cpp';source.write_text(program)
            exe=Path(directory)/'policy'
            subprocess.run(['c++','-std=c++17','-I',str(ROOT/'additions/cloakcfg'),str(source),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)

if __name__=='__main__':unittest.main()
