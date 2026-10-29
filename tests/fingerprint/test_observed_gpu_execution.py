"""Exercise the native bias pass on ANGLE's real parsed, typed shader AST.

This links an existing Gecko translator archive; it never rebuilds or changes
the browser/backend. Full resource plumbing and pixels are covered by the
headless observed-profile probe against the freshly built browser.
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ANGLE = ROOT / "firefox-src/third_party/angle"
HARNESS = r'''
#include "compiler/translator/Compiler.h"
#include "compiler/translator/PoolAlloc.h"
#include "compiler/translator/tree_ops/CloakfoxClampTextureBias.h"
#include "compiler/translator/tree_util/IntermTraverse.h"
#include <cassert>
#include <cstdio>
#include <string>
using namespace sh;

class Inspect final : public TIntermTraverser {
 public:
  Inspect() : TIntermTraverser(true, false, false) {}
  int clamps = 0, calls = 0, biases = 0;
  bool visitAggregate(Visit, TIntermAggregate* n) override {
    if (n->getOp() == EOpClamp) {
      ++clamps;
      const auto& args = *n->getSequence();
      assert(args.size() == 3);
      assert(args[1]->getAsConstantUnion()->getFConst(0) == -2.0f);
      assert(args[2]->getAsConstantUnion()->getFConst(0) == 2.0f);
    }
    if (n->getOp() == EOpCallFunctionInAST) ++calls;
    switch(n->getOp()) {
      case EOpTexture2DBias: case EOpTexture2DProjBias:
      case EOpTextureCubeBias: case EOpTextureBias: case EOpTextureProjBias:
      case EOpTextureOffsetBias: case EOpTextureProjOffsetBias:
        ++biases; break;
      default: break;
    }
    return true;
  }
};

void check(const char* text, int version, int wantBiases, int wantCalls,
           float limit, int wantClamps) {
  ShBuiltInResources resources;
  InitBuiltInResources(&resources);
  resources.FragmentPrecisionHigh = 1;
  resources.EXT_shader_texture_lod = 1;
  auto handle = ConstructCompiler(GL_FRAGMENT_SHADER,
      version == 100 ? SH_WEBGL_SPEC : SH_WEBGL2_SPEC, SH_ESSL_OUTPUT, &resources);
  assert(handle);
  auto* compiler = static_cast<TShHandleBase*>(handle)->getAsCompiler();
  {
    TScopedPoolAllocator pool;
    ShCompileOptions options = {};
    options.validateAST = true;
    auto* root = compiler->compileTreeForTesting(angle::Span<const char* const>(&text, 1), options);
    if (!root) { std::fprintf(stderr, "%s\n", GetInfoLog(handle).c_str()); std::abort(); }
    Inspect before;
    root->traverse(&before);
    assert(before.biases == wantBiases && before.calls == wantCalls && before.clamps == 0);
    assert(CloakfoxClampTextureBias(compiler, root, limit));
    Inspect after;
    root->traverse(&after);
    assert(after.biases == wantBiases && after.calls == wantCalls);
    assert(after.clamps == wantClamps);
    assert(compiler->validateAST(root));
  }
  Destruct(handle);
}

int main() {
  assert(Initialize());
  // The side-effecting function is used once; macros and nested bias calls are
  // resolved by the real parser before the exact production pass runs.
  const char* essl100 = R"(
precision highp float; uniform sampler2D t; uniform samplerCube c;
uniform float bias; varying vec2 uv; float state;
float nextBias() { state += 1.0; return bias + state; }
#define SAMPLE(B) texture2D(t, uv, B)
void main() { state=0.; gl_FragColor = SAMPLE(nextBias())
 + texture2DProj(t,vec3(uv,1.),8.) + textureCube(c,vec3(uv,1.),-8.)
 + SAMPLE(SAMPLE(8.).x); }
)";
  check(essl100, 100, 5, 1, 2.0f, 5);
  check(essl100, 100, 5, 1, 0.0f, 0);
  const char* essl300 = R"(#version 300 es
precision highp float; uniform sampler2D t; uniform samplerCube c;
uniform highp sampler3D t3; uniform highp sampler2DArray ta;
uniform highp sampler2DShadow shadow; uniform float bias; in vec2 uv; out vec4 color;
void main() { color = texture(t,uv,bias) + textureProj(t,vec3(uv,1.),8.)
 + textureOffset(t,uv,ivec2(0),-8.)
 + textureProjOffset(t,vec3(uv,1.),ivec2(0),bias)
 + texture(c,vec3(uv,1.),bias) + texture(t3,vec3(uv,1.),bias)
 + texture(ta,vec3(uv,0.),bias) + vec4(texture(shadow,vec3(uv,1.),bias)); }
)";
  check(essl300, 300, 8, 0, 2.0f, 8);
  check(essl300, 300, 8, 0, 0.0f, 0);
  const char* noBias = R"(#version 300 es
precision highp float; uniform sampler2D t; in vec2 uv; out vec4 color;
float texture(float b) { return b + 1.; }
void main() { color = texture(t,uv) + textureLod(t,uv,8.)
 + textureGrad(t,uv,vec2(1.),vec2(1.)) + texelFetch(t,ivec2(0),0)
 + vec4(texture(8.)); }
)";
  check(noBias, 300, 0, 1, 2.0f, 0);
  const char* extension = R"(#extension GL_EXT_shader_texture_lod : require
precision highp float; uniform sampler2D t; varying vec2 uv;
void main() { gl_FragColor = texture2DLodEXT(t,uv,8.)
 + texture2DGradEXT(t,uv,vec2(1.),vec2(1.)); }
)";
  check(extension, 100, 0, 0, 2.0f, 0);
#ifdef CLOAKFOX_RESOURCE_AVAILABLE
  // Against the rebuilt archive, exercise the production compiler entrypoint:
  // its resource enables the pass, its key changes, and compiler reuse is exact.
  std::string disabledKey;
  for (float limit : {0.0f, 2.0f}) {
    ShBuiltInResources resources;
    InitBuiltInResources(&resources);
    assert(resources.CloakfoxMaxTextureLodBias == 0.0f);
    resources.CloakfoxMaxTextureLodBias = limit;
    auto handle = ConstructCompiler(GL_FRAGMENT_SHADER, SH_WEBGL_SPEC,
                                     SH_ESSL_OUTPUT, &resources);
    assert(handle);
    const auto key = GetBuiltInResourcesString(handle);
    if (!limit) disabledKey = key;
    else assert(key != disabledKey);
    const char* source = "precision mediump float;uniform sampler2D t;"
      "uniform float b;void main(){gl_FragColor=texture2D(t,vec2(.5),b);}";
    ShCompileOptions options = {};
    options.objectCode = true;
    assert(Compile(handle, &source, 1, options));
    const auto code = GetObjectCode(handle);
    assert((code.find("clamp(") != std::string::npos) == (limit > 0.0f));
    assert(Compile(handle, &source, 1, options));
    assert(GetObjectCode(handle) == code);
    Destruct(handle);
  }
#endif
  assert(Finalize());
}
'''


class ObservedGPUExecution(unittest.TestCase):
    def test_real_typed_bias_transformation_preserves_unrelated_calls(self):
        configured = os.environ.get("ANGLE_TRANSLATOR_LIBRARY")
        libraries = ([Path(configured)] if configured else
                     list((ROOT / "firefox-src").glob("obj-*/third_party/angle/translator_gn/libtranslator_gn.a")))
        if not libraries or not libraries[0].is_file():
            self.skipTest("requires an existing Gecko ANGLE translator archive")
        library = libraries[0]
        build = library.parents[3]
        with tempfile.TemporaryDirectory(prefix="cloakfox-observed-ast-") as tmp:
            work = Path(tmp)
            (work / "test.cpp").write_text(HARNESS)
            # A pre-change archive must keep its original public ABI. Only the
            # temporary header is adjusted; the pass under test is unchanged.
            header = (ANGLE / "include/GLSLANG/ShaderLang.h").read_text()
            resource_available = b":CloakfoxMaxTextureLodBias:" in library.read_bytes()
            if not resource_available:
                header = header.replace("    float CloakfoxMaxTextureLodBias;\n", "")
            (work / "GLSLANG").mkdir()
            (work / "GLSLANG/ShaderLang.h").write_text(header)
            deps = [build / "third_party/angle" / name / ("lib" + name + ".a")
                    for name in ["preprocessor_gn", "angle_common_gn", "angle_common_shader_state_gn"]]
            sdk = Path.home() / ".mozbuild/MacOSX14.4.sdk"
            platform_flags = (["-mmacosx-version-min=14.0", "-include", "Availability.h",
                               *(["-isysroot", str(sdk)] if sdk.is_dir() else [])]
                              if sys.platform == "darwin" else [])
            command = ["clang++", "-std=c++20", "-fno-rtti", *platform_flags,
                       *(["-DCLOAKFOX_RESOURCE_AVAILABLE"] if resource_available else []),
                       "-DANGLE_DISABLE_POOL_ALLOC", "-DANGLE_ENABLE_ESSL", "-DANGLE_ENABLE_GLSL",
                       "-DANGLE_PLATFORM_EXPORT=", "-I" + str(work),
                       "-I" + str(ANGLE / "include"), "-I" + str(ANGLE / "src"),
                       "-I" + str(ANGLE / "src/common/base"),
                       "-I" + str(ANGLE / "include/GLSLANG"),
                       str(work / "test.cpp"), str(library), *map(str, deps),
                       "-L" + str(build / "dist/bin"), "-lmozglue",
                       "-Wl,-rpath," + str(build / "dist/bin"), "-o", str(work / "test")]
            compiled = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run([str(work / "test")], text=True, capture_output=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)


if __name__ == "__main__":
    unittest.main()
