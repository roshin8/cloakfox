"""Execute the actual native extension methods against controlled backend caps.

The small fake Gecko types let this run without a Firefox build; they do not
implement the support policy under test. Integration still needs a rebuilt binary.
"""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class ExtensionSupport(unittest.TestCase):
    def test_allowlist_cannot_create_unsupported_or_forbidden_extensions(self):
        compiler = shutil.which('clang++') or shutil.which('g++')
        if not compiler:
            self.skipTest('C++ compiler required')
        native = ROOT / 'firefox-src/dom/canvas/ClientWebGLContext.cpp'
        if not native.exists():
            self.skipTest('applied Firefox source required')
        source = native.read_text()
        start = source.index('bool ClientWebGLContext::IsSupported(')
        end = source.index('// -', source.index('void ClientWebGLContext::GetSupportedExtensions(', start))
        methods = source[start:end]
        harness = r'''
#include <algorithm>
#include <array>
#include <memory>
#include <string>
#include <vector>
#include <cassert>
using nsString = std::string;
template<class T> struct nsTArray : std::vector<T> {
  void AppendElement(const T& value) { this->push_back(value); }
};
namespace dom {
enum class CallerType { Content, System };
template<class T> struct Nullable {
 T value; bool isNull = false;
 void SetNull() { isNull = true; }
 T& SetValue() { isNull = false; return value; }
};
}
namespace webgl { struct NotLostData {}; }
template<class T> using RefPtr = std::shared_ptr<T>;
struct WebGLExtensionID { enum Enum { Supported, Unsupported, Forbidden, Max }; };
// Gecko's enum is indexed by its enumerators; this harness models that API.
using Extension = WebGLExtensionID::Enum;
const char* GetExtensionName(Extension ext) {
 static const char* names[] = {"supported", "unsupported", "forbidden"};
 return names[ext];
}
std::string NS_ConvertUTF8toUTF16(const std::string& value) { return value; }
std::array<Extension,3> MakeEnumeratedRange(Extension) {
 return {WebGLExtensionID::Supported, WebGLExtensionID::Unsupported, WebGLExtensionID::Forbidden};
}
namespace MaskConfig {
std::vector<std::string> configured;
std::vector<std::string> GetStringList(const char*) { return configured; }
}
std::vector<std::string> CloakfoxWebGLStringList(uint32_t,const char* key) {return MaskConfig::GetStringList(key);}
class ClientWebGLContext {
 public:
 uint32_t GetUserContextId()const{return 0;}
 bool mIsWebGL2 = false;
 struct Options { bool cloakfoxBackendProfile = false; } options;
 const Options& ActualContextParameters() const { return options; }
 RefPtr<webgl::NotLostData> mNotLost = std::make_shared<webgl::NotLostData>();
 struct Caps { std::array<bool,3> supportedExtensions = {true,false,true}; } caps;
 const Caps& Limits() const { return caps; }
 bool IsExtensionForbiddenForCaller(Extension ext, dom::CallerType) const {
   return ext == WebGLExtensionID::Forbidden;
 }
 bool IsSupported(Extension, dom::CallerType) const;
 void GetSupportedExtensions(dom::Nullable<nsTArray<nsString>>&, dom::CallerType) const;
};
'''
        # Match Gecko's enum spelling without changing method control flow.
        methods = methods.replace('const WebGLExtensionID ext', 'const Extension ext')
        harness += methods + r'''
int main() {
 ClientWebGLContext ctx;
 using C = dom::CallerType;
 for (bool gl2 : {false, true}) {
  ctx.mIsWebGL2 = gl2;
  MaskConfig::configured = {"unsupported", "forbidden", "supported", "unknown"};
  assert(!ctx.IsSupported(WebGLExtensionID::Unsupported, C::Content));
  assert(!ctx.IsSupported(WebGLExtensionID::Forbidden, C::Content));
  assert(ctx.IsSupported(WebGLExtensionID::Supported, C::Content));
  dom::Nullable<nsTArray<nsString>> listed;
  ctx.GetSupportedExtensions(listed, C::Content);
  assert(listed.value == std::vector<std::string>{"supported"});
  MaskConfig::configured = {"unsupported"};
  assert(!ctx.IsSupported(WebGLExtensionID::Supported, C::Content));
  listed.value.clear();
  ctx.GetSupportedExtensions(listed, C::Content);
  assert(listed.value.empty());
  ctx.options.cloakfoxBackendProfile = true;
  assert(ctx.IsSupported(WebGLExtensionID::Supported, C::Content));
  assert(!ctx.IsSupported(WebGLExtensionID::Unsupported, C::Content));
  assert(!ctx.IsSupported(WebGLExtensionID::Forbidden, C::Content));
  ctx.options.cloakfoxBackendProfile = false;
  MaskConfig::configured.clear();
  assert(ctx.IsSupported(WebGLExtensionID::Supported, C::Content));
  assert(!ctx.IsSupported(WebGLExtensionID::Unsupported, C::Content));
 }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            cpp = pathlib.Path(directory) / 'extensions.cpp'
            binary = pathlib.Path(directory) / 'extensions'
            cpp.write_text(harness)
            subprocess.run([compiler, '-std=c++17', str(cpp), '-o', str(binary)], check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
