/* MPL-2.0: standalone hardened-runtime CPU Vulkan/JIT smoke test. */
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <string>
#include <vector>

int main(int argc, char** argv) {
  assert(argc == 2);
  const std::string directory = argv[1];
  assert(!directory.empty() && directory.front() == '/');
  auto* gles = dlopen((directory + "/libGLESv2_cloakfox_canonical.dylib").c_str(), RTLD_NOW | RTLD_LOCAL);
  assert(gles);
  auto* lib = dlopen((directory + "/libEGL_cloakfox_canonical.dylib").c_str(), RTLD_NOW | RTLD_LOCAL);
  assert(lib);
#define EGL(name) reinterpret_cast<decltype(&name)>(dlsym(lib, #name))
  const auto getProc = EGL(eglGetProcAddress);
  assert(getProc);
#define GL(name) reinterpret_cast<decltype(&name)>(getProc(#name))
  const EGLAttrib attrs[] = {0x3203, 0x3450, 0x3209, 0x3487, EGL_NONE};
  const auto display = EGL(eglGetPlatformDisplay)(0x3202, nullptr, attrs);
  assert(display);
  EGLint major, minor;
  assert(EGL(eglInitialize)(display, &major, &minor));
  EGLint configAttrs[] = {EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
                         EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, 8, EGL_NONE};
  EGLConfig config;
  EGLint count;
  assert(EGL(eglChooseConfig)(display, configAttrs, &config, 1, &count) && count);
  assert(EGL(eglBindAPI)(EGL_OPENGL_ES_API));
  const EGLint contextAttrs[] = {EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};
  const auto context = EGL(eglCreateContext)(display, config, EGL_NO_CONTEXT, contextAttrs);
  assert(context);
  const EGLint surfaceAttrs[] = {EGL_WIDTH, 32, EGL_HEIGHT, 32, EGL_NONE};
  const auto surface = EGL(eglCreatePbufferSurface)(display, config, surfaceAttrs);
  assert(surface);
  assert(EGL(eglMakeCurrent)(display, surface, surface, context));
  const auto* renderer = reinterpret_cast<const char*>(GL(glGetString)(GL_RENDERER));
  assert(renderer && strstr(renderer, "SwiftShader") && strstr(renderer, "Vulkan"));
  printf("%s\n", renderer);
  const auto shader = [&](GLenum kind, const char* text) {
    const auto handle = GL(glCreateShader)(kind);
    GL(glShaderSource)(handle, 1, &text, nullptr);
    GL(glCompileShader)(handle);
    GLint status;
    GL(glGetShaderiv)(handle, GL_COMPILE_STATUS, &status);
    if (!status) {
      char error[4096];
      GL(glGetShaderInfoLog)(handle, sizeof(error), nullptr, error);
      fprintf(stderr, "%s\n", error);
      abort();
    }
    return handle;
  };
  const auto vertex = shader(GL_VERTEX_SHADER, "attribute vec2 p; void main(){gl_Position=vec4(p,0.,1.);}");
  const auto fragment = shader(GL_FRAGMENT_SHADER, "precision highp float; void main(){gl_FragColor=vec4(gl_FragCoord.x/32.,gl_FragCoord.y/32.,0.25,1.);}");
  const auto program = GL(glCreateProgram)();
  GL(glAttachShader)(program, vertex);
  GL(glAttachShader)(program, fragment);
  GL(glBindAttribLocation)(program, 0, "p");
  GL(glLinkProgram)(program);
  GLint status;
  GL(glGetProgramiv)(program, GL_LINK_STATUS, &status);
  assert(status);
  GL(glUseProgram)(program);
  GL(glViewport)(0, 0, 32, 32);
  GL(glDisable)(GL_DITHER);
  const float vertices[] = {-1, -1, 3, -1, -1, 3};
  GLuint buffer;
  GL(glGenBuffers)(1, &buffer);
  GL(glBindBuffer)(GL_ARRAY_BUFFER, buffer);
  GL(glBufferData)(GL_ARRAY_BUFFER, sizeof(vertices), vertices, GL_STATIC_DRAW);
  GL(glEnableVertexAttribArray)(0);
  GL(glVertexAttribPointer)(0, 2, GL_FLOAT, GL_FALSE, 0, nullptr);
  GL(glDrawArrays)(GL_TRIANGLES, 0, 3);
  GL(glFinish)();
  std::vector<uint8_t> pixels(32 * 32 * 4);
  GL(glReadPixels)(0, 0, 32, 32, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
  assert(GL(glGetError)() == GL_NO_ERROR);
  for (int y = 0; y < 32; ++y) {
    for (int x = 0; x < 32; ++x) {
      const auto offset = (y * 32 + x) * 4;
      assert(pixels[offset] == int((x + 0.5) * 255 / 32 + 0.5));
      assert(pixels[offset + 1] == int((y + 0.5) * 255 / 32 + 0.5));
      assert(pixels[offset + 2] == 64 && pixels[offset + 3] == 255);
    }
  }
  assert(EGL(eglMakeCurrent)(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT));
  assert(EGL(eglDestroySurface)(display, surface));
  assert(EGL(eglDestroyContext)(display, context));
  assert(EGL(eglTerminate)(display));
  puts("PASS hardened CPU Vulkan shader/JIT corpus");
}
