"""Execute the actual native cohort restrictions against backend limit fixtures.

Catches raising unsupported capacities, incorrect WebGL2 minima, and an omitted
host restriction (which otherwise leaves allocation/compiler validation native).
"""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class BackendProfile(unittest.TestCase):
    def test_whole_cohort_is_bounded_and_webgl2_keeps_required_minima(self):
        native = ROOT / 'firefox-src/dom/canvas/WebGLContextValidate.cpp'
        compiler = shutil.which('clang++') or shutil.which('g++')
        if not native.exists() or not compiler:
            self.skipTest('applied source and C++ compiler required')
        source = native.read_text()
        start = source.find('  // Cloakfox standardized backend cohort.')
        self.assertGreaterEqual(start, 0, 'native cohort enforcement is absent')
        end = source.index('  // End Cloakfox standardized backend cohort.', start)
        branch = source[start:end]
        harness = r'''
#include "CloakfoxGPUProfileCore.hpp"
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <string>
struct Failure { const char* id; const char* reason; };
template<class T> bool RestrictCap(T* cap, T target) {
 if(*cap < target)return false; *cap=target;return true;
}
struct Context {
 bool gl2=true;
 struct { bool cloakfoxBackendProfile=true; uint32_t cloakfoxPersonaProfile=0; } mOptions;
 struct Caps {
  uint32_t maxTexUnits=80,maxVertexAttribs=32,maxColorDrawBuffers=8,
   maxTex2dSize=16384,maxTexCubeSize=16384,maxTex3dSize=2048,
   maxTexArrayLayers=2048,maxViewportDim=16384,maxUniformBufferBindings=72;
  std::array<float,2> pointSizeRange={1,1024},lineWidthRange={1,8};
 } limits;
 uint32_t mGLMaxRenderbufferSize=16384,mGLMaxVertexTextureImageUnits=32,
  mGLMaxFragmentTextureImageUnits=32,mGLMaxVertexUniformVectors=1024,
  mGLMaxFragmentUniformVectors=1024,mGLMaxVertexOutputVectors=32,
  mGLMaxFragmentInputVectors=32;
 bool IsWebGL2()const{return gl2;}
 bool apply() { Failure failure; auto* out_failReason=&failure;
''' + branch + r'''
 return true;
 }
};
int main(){
 for(unsigned family=1;family<=4;family++)for(unsigned variant=1;variant<=2;variant++){
  Context c;c.mOptions.cloakfoxPersonaProfile=(family<<8)|variant;assert(c.apply());
  auto p=CloakfoxGPUProfile::Decode(c.mOptions.cloakfoxPersonaProfile);assert(p);
  assert(c.limits.maxTex2dSize==p->texture && c.mGLMaxVertexUniformVectors==p->vertexUniforms && c.mGLMaxFragmentUniformVectors==p->fragmentUniforms);
  assert(c.limits.maxTexUnits==p->combinedTexUnits && c.mGLMaxFragmentTextureImageUnits==p->fragmentTexUnits);
  assert(c.mGLMaxVertexOutputVectors==p->vertexOutputs && c.mGLMaxFragmentInputVectors==p->fragmentInputs);
  assert(c.limits.maxTex3dSize==p->texture3d && c.limits.maxTexArrayLayers==p->arrayLayers);
  assert(c.limits.maxColorDrawBuffers==p->drawBuffers && c.limits.maxUniformBufferBindings==p->uniformBufferBindings);
  Context weak;weak.mOptions=c.mOptions;weak.limits.maxTex2dSize=p->texture-1;assert(!weak.apply());
  Context weakShader;weakShader.mOptions=c.mOptions;weakShader.mGLMaxVertexUniformVectors=p->vertexUniforms-1;assert(!weakShader.apply());
 }
 Context invalid;invalid.mOptions.cloakfoxPersonaProfile=0x500;assert(!invalid.apply());
 Context gl2; assert(gl2.apply());
 assert(gl2.limits.maxTexUnits==32 && gl2.limits.maxVertexAttribs==16);
 assert(gl2.mGLMaxVertexTextureImageUnits==16 && gl2.mGLMaxFragmentTextureImageUnits==16);
 assert(gl2.mGLMaxVertexUniformVectors==256 && gl2.mGLMaxFragmentUniformVectors==224);
 assert(gl2.mGLMaxVertexOutputVectors==16 && gl2.mGLMaxFragmentInputVectors==15);
 assert(gl2.limits.maxTex2dSize==2048 && gl2.limits.maxTexCubeSize==2048);
 assert(gl2.mGLMaxRenderbufferSize==2048 && gl2.limits.maxViewportDim==4096);
 assert(gl2.limits.maxTex3dSize==256 && gl2.limits.maxTexArrayLayers==256);
 assert(gl2.limits.maxColorDrawBuffers==4 && gl2.limits.maxUniformBufferBindings==24);
 assert(gl2.limits.lineWidthRange[0]==1 && gl2.limits.lineWidthRange[1]==1);
 assert(gl2.limits.pointSizeRange[0]==1 && gl2.limits.pointSizeRange[1]==63);
 Context gl1; gl1.gl2=false; assert(gl1.apply());
 assert(gl1.mGLMaxVertexUniformVectors==256 && gl1.mGLMaxFragmentUniformVectors==224);
 assert(gl1.limits.maxTexUnits==32 && gl1.limits.maxVertexAttribs==16);
 assert(gl1.mGLMaxVertexTextureImageUnits==gl2.mGLMaxVertexTextureImageUnits);
 assert(gl1.mGLMaxFragmentTextureImageUnits==gl2.mGLMaxFragmentTextureImageUnits);
 assert(gl1.mGLMaxVertexOutputVectors==gl2.mGLMaxVertexOutputVectors);
 assert(gl1.mGLMaxFragmentInputVectors==gl2.mGLMaxFragmentInputVectors);
 Context absent; absent.mOptions.cloakfoxBackendProfile=false;
 absent.limits.maxTex2dSize=1024; assert(absent.apply());
 assert(absent.limits.maxTexUnits==80 && absent.limits.maxTex2dSize==1024);
 Context weak; weak.limits.maxTex2dSize=1024; assert(!weak.apply());
 assert(weak.limits.maxTex2dSize==1024); // never raise the real backend
 Context weakVertex; weakVertex.mGLMaxVertexUniformVectors=255; assert(!weakVertex.apply());
 Context badRange; badRange.limits.pointSizeRange={2,1024}; assert(!badRange.apply());
}
'''
        with tempfile.TemporaryDirectory() as directory:
            file = pathlib.Path(directory) / 'cohort.cpp'
            file.write_text(harness)
            binary = pathlib.Path(directory) / 'cohort'
            subprocess.run([compiler, '-std=c++17', '-I'+str(ROOT/'additions/cloakcfg'), str(file), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


    def test_legacy_precision_preserves_mask_and_rejects_malformed_tuple(self):
        native = ROOT / 'firefox-src/dom/canvas/ClientWebGLContext.cpp'
        compiler = shutil.which('clang++') or shutil.which('g++')
        if not native.exists() or not compiler:
            self.skipTest('applied source and C++ compiler required')
        source = native.read_text()
        start = source.find('// Cloakfox validated precision tuple.')
        self.assertGreaterEqual(start, 0, 'validated precision policy is absent')
        end = source.index('// End Cloakfox validated precision tuple.', start)
        harness = '#include <algorithm>\n#include <optional>\n#include <cassert>\n#include <cstdint>\n#include "' + str(ROOT / 'additions/cloakcfg/json.hpp') + '"\n' + r'''
namespace webgl { struct ShaderPrecisionFormat {
 uint8_t rangeMin=0,rangeMax=0,precision=0; }; }
''' + source[start:end] + r'''
int main() {
 webgl::ShaderPrecisionFormat native{127,127,23};
 auto result=CloakfoxConfiguredPrecision(native,{{"rangeMin",255},{"rangeMax",255},{"precision",255}});
 assert(result->rangeMin==255 && result->rangeMax==255 && result->precision==255);
 result=CloakfoxConfiguredPrecision(native,{{"rangeMin",14},{"rangeMax",14},{"precision",10}});
 assert(result->rangeMin==14 && result->rangeMax==14 && result->precision==10);
 for(auto bad : {nlohmann::json("wrong"), nlohmann::json::object(),
   nlohmann::json{{"rangeMin",-1},{"rangeMax",127},{"precision",23}},
   nlohmann::json{{"rangeMin",127},{"rangeMax",127},{"precision",1.5}},
   nlohmann::json{{"rangeMin",127},{"rangeMax",127},{"precision",256}}}) {
  result=CloakfoxConfiguredPrecision(native,bad);
  assert(!result);
 }
 result=CloakfoxConfiguredPrecision({24,24,0},{{"rangeMin",31},{"rangeMax",30},{"precision",0}});
 assert(result->rangeMin==31 && result->rangeMax==30 && result->precision==0);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            file = pathlib.Path(directory) / 'precision.cpp'
            file.write_text(harness)
            binary = pathlib.Path(directory) / 'precision'
            subprocess.run([compiler, '-std=c++17', '-I'+str(ROOT/'additions/cloakcfg'), str(file), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


    def test_options_ipc_structs_tie_every_byte(self):
        # Real context-option fields must not leave implicit padding in either
        # containing IPC record. This caught the new bool changing 12 to 13.
        source = (ROOT / 'firefox-src/dom/canvas/WebGLTypes.h').read_text()
        def struct(name):
            start = source.index('struct '+name+' final {')
            return source[start:source.index('\n};', start)+3]
        compiler = shutil.which('clang++') or shutil.which('g++')
        if not compiler: self.skipTest('C++ compiler required')
        harness = r'''
#include <tuple>
#include <array>
#include <cstdint>
#include <type_traits>
#include <unordered_map>
#include <string>
namespace dom { enum class WebGLPowerPreference : uint8_t { Default }; }
template<class T> auto TiedFields(const T&) {return std::tuple<>();}
''' + struct('WebGLContextOptions') + r'''
template<class T, size_t... I> constexpr size_t bytes(std::index_sequence<I...>) {
 using Fields=decltype(std::declval<T&>().MutTiedFields());
 return (sizeof(std::remove_reference_t<std::tuple_element_t<I,Fields>>) + ...);
}
template<class T> constexpr bool packed() {
 using Fields=decltype(std::declval<T&>().MutTiedFields());
 return sizeof(T)==bytes<T>(std::make_index_sequence<std::tuple_size_v<Fields>>());
}
static_assert(packed<WebGLContextOptions>());
struct uvec2 { uint32_t x,y; };
''' + struct('InitContextDesc') + r'''
static_assert(packed<InitContextDesc>());
template<class T,size_t N> struct Padded {alignas(T) std::array<uint8_t,N> raw;};
namespace gl { enum class GLVendor : uint8_t {Unknown}; }
enum class OptionalRenderableFormatBits : uint8_t {};
struct alignas(8) Limits {std::array<uint8_t,88> raw;};
namespace layers {struct SurfaceDescriptor {enum class Type {};};}
template<class T> struct EnumMask {uint64_t bits;};
using GetShaderPrecisionFormatArgs=std::tuple<unsigned,unsigned>;
struct ShaderPrecisionFormat {uint8_t min,max,precision,padding;};
template<class T> struct TupleStdHash {size_t operator()(const T&)const{return 0;}};
''' + struct('InitContextResult') + r'''
static_assert(packed<InitContextResult>());
int main() {}
'''
        with tempfile.TemporaryDirectory() as directory:
            file=pathlib.Path(directory)/'layout.cpp';file.write_text(harness)
            compiled=subprocess.run([compiler,'-std=c++17',str(file),'-o',str(pathlib.Path(directory)/'layout')],capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)


    def test_precision_cohort_accepts_gecko_desktop24_and_rejects_less(self):
        source=(ROOT/'firefox-src/dom/canvas/WebGLContext.cpp').read_text()
        start=source.find('// Cloakfox backend precision baseline.')
        self.assertGreaterEqual(start,0,'native-supported precision baseline helper missing')
        end=source.index('// End Cloakfox backend precision baseline.',start)
        compiler=shutil.which('clang++') or shutil.which('g++')
        if not compiler:self.skipTest('C++ compiler required')
        harness=r'''
#include <cstdint>
#include <cassert>
namespace webgl {struct ShaderPrecisionFormat {uint8_t rangeMin=0,rangeMax=0,precision=0;};}
''' + source[start:end] + r'''
int main(){
 webgl::ShaderPrecisionFormat out;
 assert(CloakfoxPrecisionBaseline({24,24,0},false,&out));
 assert(out.rangeMin==24 && out.rangeMax==24 && out.precision==0);
 assert(CloakfoxPrecisionBaseline({31,30,0},false,&out));
 assert(out.rangeMin==24 && out.rangeMax==24 && out.precision==0);
 assert(!CloakfoxPrecisionBaseline({23,24,0},false,&out));
 assert(!CloakfoxPrecisionBaseline({24,23,0},false,&out));
 assert(CloakfoxPrecisionBaseline({127,127,23},true,&out));
 assert(out.rangeMin==127 && out.rangeMax==127 && out.precision==23);
 assert(!CloakfoxPrecisionBaseline({127,127,22},true,&out));
}
'''
        with tempfile.TemporaryDirectory() as directory:
            file=pathlib.Path(directory)/'baseline.cpp';file.write_text(harness)
            binary=pathlib.Path(directory)/'baseline'
            subprocess.run([compiler,'-std=c++17',str(file),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)


    def test_assembled_worker_fixture_is_valid_javascript(self):
        # Checking INSPECT alone missed a parenthesis in the appended bootstrap.
        import ast
        import json
        node_binary=shutil.which('node')
        if not node_binary:self.skipTest('Node required for fixture syntax')
        path=ROOT/'tests/fingerprint/probe_webgl_backend_profile.py'
        namespace={}
        for statement in ast.parse(path.read_text()).body:
            if isinstance(statement,ast.Assign):
                exec(compile(ast.Module(body=[statement],type_ignores=[]),str(path),'exec'),namespace)
        with tempfile.TemporaryDirectory() as directory:
            worker=pathlib.Path(directory)/'worker.js';worker.write_text(namespace['WORKER_SOURCE'])
            result=subprocess.run([node_binary,'--check',str(worker)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
        for key in ['INSPECT','RASTER','READBACK','PRECISION_POLICY','WORKER_RUN']:
            result=subprocess.run([node_binary,'-e','new Function('+json.dumps(namespace[key])+');'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,key+': '+result.stderr)


    def test_exact_owner_tables_and_master_off(self):
        source=(ROOT/'firefox-src/dom/canvas/ClientWebGLContext.cpp').read_text()
        start=source.index('// Cloakfox exact-owner WebGL config.')
        end=source.index('// End Cloakfox exact-owner WebGL config.',start)
        compiler=shutil.which('clang++') or shutil.which('g++')
        if not compiler:self.skipTest('C++ compiler required')
        harness='#include <optional>\n#include <variant>\n#include <string>\n#include <vector>\n#include <map>\n#include <cassert>\n#include "'+str(ROOT/'additions/cloakcfg/json.hpp')+'"\n'+r'''
namespace StaticPrefs {bool enabled=true;bool cloakfox_enabled(){return enabled;}}
namespace CloakfoxSiteSeed {std::map<uint32_t,nlohmann::json> cfg;auto ExactConfig(uint32_t owner){return cfg[owner];}}
namespace MaskConfig {
 nlohmann::json base=nlohmann::json::object();const auto& GetJson(){return base;}
 using Value=std::variant<int64_t,bool,double,std::string,std::nullptr_t>;
 std::optional<Value> GLParam(uint32_t,bool){return {};}
}
''' + source[start:end] + r'''
int main(){
 CloakfoxSiteSeed::cfg[0]={{"webGl:parameters",{{"36347",13}}},{"webGl:renderer","zero"},{"webGl:supportedExtensions",{"zero"}}};
 CloakfoxSiteSeed::cfg[7]={{"webGl:parameters",{{"36347",19}}},{"webGl:renderer","seven"},{"webGl:supportedExtensions",{"seven"}}};
 assert(std::get<int64_t>(*CloakfoxGLParam(0,36347,false))==13);
 assert(std::get<int64_t>(*CloakfoxGLParam(7,36347,false))==19);
 assert(CloakfoxWebGLString(7,"webGl:renderer")=="seven");
 assert(CloakfoxWebGLStringList(7,"webGl:supportedExtensions")==std::vector<std::string>{"seven"});
 MaskConfig::base={{"webGl:parameters",{{"1",3}}},{"fallback","base"}};
 assert(std::get<int64_t>(*CloakfoxGLParam(7,1,false))==3);
 StaticPrefs::enabled=false;
 assert(!CloakfoxGLParam(7,36347,false));assert(!CloakfoxGLParam(7,1,false));
 assert(!CloakfoxWebGLString(7,"webGl:renderer"));
 assert(CloakfoxWebGLStringList(7,"webGl:supportedExtensions").empty());
}
'''
        with tempfile.TemporaryDirectory() as directory:
            file=pathlib.Path(directory)/'owner.cpp';file.write_text(harness)
            binary=pathlib.Path(directory)/'owner'
            subprocess.run([compiler,'-std=c++17',str(file),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)


if __name__ == '__main__':
    unittest.main()
