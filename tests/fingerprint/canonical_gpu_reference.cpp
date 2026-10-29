/* MPL-2.0: standalone hardened-runtime CPU Vulkan/JIT smoke test. */
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl31.h>
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
  const EGLint contextAttrs[] = {EGL_CONTEXT_CLIENT_VERSION, 3, EGL_CONTEXT_MINOR_VERSION_KHR, 1, EGL_NONE};
  const auto context = EGL(eglCreateContext)(display, config, EGL_NO_CONTEXT, contextAttrs);
  assert(context);
  const EGLint surfaceAttrs[] = {EGL_WIDTH, 32, EGL_HEIGHT, 32, EGL_NONE};
  const auto surface = EGL(eglCreatePbufferSurface)(display, config, surfaceAttrs);
  assert(surface);
  assert(EGL(eglMakeCurrent)(display, surface, surface, context));
  const auto* renderer = reinterpret_cast<const char*>(GL(glGetString)(GL_RENDERER));
  assert(renderer && strstr(renderer, "SwiftShader") && strstr(renderer, "Vulkan"));
  printf("%s\n", renderer);
  for(GLenum stage : {GL_VERTEX_SHADER, GL_FRAGMENT_SHADER}) {
    for(GLenum precision : {GL_LOW_FLOAT,GL_MEDIUM_FLOAT,GL_HIGH_FLOAT}) {
      GLint range[2], bits;
      GL(glGetShaderPrecisionFormat)(stage,precision,range,&bits);
      assert(range[0]==127 && range[1]==127 && bits==23);
    }
    for(GLenum precision : {GL_LOW_INT,GL_MEDIUM_INT,GL_HIGH_INT}) {
      GLint range[2], bits;
      GL(glGetShaderPrecisionFormat)(stage,precision,range,&bits);
      assert(range[0]==31 && range[1]==30 && bits==0);
    }
  }
  GLint limit = 0;
  GL(glGetIntegerv)(GL_MAX_TEXTURE_SIZE, &limit);
  assert(limit >= 16384);
  GL(glGetIntegerv)(GL_MAX_SAMPLES, &limit);
  assert(limit >= 8);
  GL(glGetIntegerv)(GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS, &limit);
  assert(limit >= 80);
  GL(glGetIntegerv)(GL_MAX_UNIFORM_BUFFER_BINDINGS, &limit);
  assert(limit >= 80);
  GL(glGetIntegerv)(GL_MAX_COMBINED_UNIFORM_BLOCKS, &limit);
  assert(limit >= 80);
  GL(glGetIntegerv)(GL_MAX_VERTEX_UNIFORM_BLOCKS, &limit);
  assert(limit >= 16);
  GL(glGetIntegerv)(GL_MAX_FRAGMENT_UNIFORM_BLOCKS, &limit);
  assert(limit >= 16);
  GLint viewportDims[2];
  GL(glGetIntegerv)(GL_MAX_VIEWPORT_DIMS, viewportDims);
  assert(viewportDims[0] >= 32767 && viewportDims[1] >= 32767);
  GL(glGetIntegerv)(GL_MAX_VARYING_VECTORS, &limit);
  assert(limit >= 32);
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


  const auto link = [&](const std::string& vs, const std::string& fs) {
    const GLuint v = shader(GL_VERTEX_SHADER,vs.c_str());
    const GLuint f = shader(GL_FRAGMENT_SHADER,fs.c_str());
    const GLuint p = GL(glCreateProgram)();
    GL(glAttachShader)(p,v); GL(glAttachShader)(p,f);
    GL(glBindAttribLocation)(p,0,"p"); GL(glLinkProgram)(p);
    GLint ok; GL(glGetProgramiv)(p,GL_LINK_STATUS,&ok);
    if(!ok) { char error[4096]; GL(glGetProgramInfoLog)(p,sizeof(error),nullptr,error); fprintf(stderr,"%s\n",error); abort(); }
    return p;
  };
  const auto readPixel = [&](int x, int y) {
    std::vector<uint8_t> pixel(4);
    GL(glReadPixels)(x,y,1,1,GL_RGBA,GL_UNSIGNED_BYTE,pixel.data());
    assert(GL(glGetError)() == GL_NO_ERROR);
    return pixel;
  };

  // Dynamic arithmetic must substantiate the promoted precision descriptors.
  // These operations fail with half mantissas/ranges or 16-bit integers.
  for(const std::string qualifier : {"lowp","mediump"}) {
    const std::string declarations = "uniform "+qualifier+" float a; uniform "+qualifier+" float b; uniform "+qualifier+" int i;";
    const std::string arithmetic = "float f=((a+b)-a)*8388608.;float n=float(i-1073741824)/3.;";
    const auto pp = link(
        "attribute vec2 p;"+declarations+"varying highp vec2 answer; void main(){"+arithmetic+"answer=vec2(f,n);gl_Position=vec4(p,0.,1.);}",
        "precision highp float;"+declarations+"varying highp vec2 answer;void main(){"+arithmetic+"gl_FragColor=vec4(answer,f,n);}");
    GL(glUseProgram)(pp);
    GL(glUniform1f)(GL(glGetUniformLocation)(pp,"a"),1.f);
    GL(glUniform1f)(GL(glGetUniformLocation)(pp,"b"),1.f/8388608.f);
    GL(glUniform1i)(GL(glGetUniformLocation)(pp,"i"),1073741827);
    GL(glDrawArrays)(GL_TRIANGLES,0,3);
    assert(readPixel(16,16)==std::vector<uint8_t>({255,255,255,255}));
  }
  // All 32 vec4 interpolators remain live: each depends on an input attribute,
  // and every component contributes to the fragment output.
  std::string vv = "attribute vec2 p;", vf = "precision highp float;";
  for(int i=0;i<32;++i) {
    vv += "varying vec4 v"+std::to_string(i)+";";
    vf += "varying vec4 v"+std::to_string(i)+";";
  }
  vv += "void main(){gl_Position=vec4(p,0.,1.);";
  vf += "void main(){vec4 r=vec4(0.);";
  for(int i=0;i<32;++i) {
    vv += "v"+std::to_string(i)+"=vec4(p,1.,1.)/64.;";
    vf += "r+=v"+std::to_string(i)+";";
  }
  vv += "}"; vf += "gl_FragColor=r;}";
  GL(glUseProgram)(link(vv,vf));
  GL(glDrawArrays)(GL_TRIANGLES,0,3);
  auto varyingPixel = readPixel(16,16);
  assert(varyingPixel[2]==128 && varyingPixel[3]==128);
  // Use a real descriptor at UBO binding79 and sample texture unit79.
  const auto bindingProgram = link(
      "#version 300 es\nin vec2 p; void main(){gl_Position=vec4(p,0.,1.);}",
      "#version 300 es\nprecision highp float; layout(std140) uniform B {vec4 color;}; uniform sampler2D image; out vec4 o; void main(){o=color*texture(image,vec2(.5));}");
  GL(glUseProgram)(bindingProgram);
  const GLuint block = GL(glGetUniformBlockIndex)(bindingProgram,"B");
  assert(block != GL_INVALID_INDEX);
  GL(glUniformBlockBinding)(bindingProgram,block,79);
  GLuint ubo, samplerTexture;
  GL(glGenBuffers)(1,&ubo);
  GL(glBindBuffer)(GL_UNIFORM_BUFFER,ubo);
  const float color[] = {1,1,1,1};
  GL(glBufferData)(GL_UNIFORM_BUFFER,sizeof(color),color,GL_STATIC_DRAW);
  GL(glBindBufferBase)(GL_UNIFORM_BUFFER,79,ubo);
  GL(glGenTextures)(1,&samplerTexture);
  GL(glActiveTexture)(GL_TEXTURE0+79);
  GL(glBindTexture)(GL_TEXTURE_2D,samplerTexture);
  const uint8_t texel[] = {23,67,109,255};
  GL(glTexImage2D)(GL_TEXTURE_2D,0,GL_RGBA8,1,1,0,GL_RGBA,GL_UNSIGNED_BYTE,texel);
  GL(glTexParameteri)(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);
  GL(glUniform1i)(GL(glGetUniformLocation)(bindingProgram,"image"),79);
  GL(glDrawArrays)(GL_TRIANGLES,0,3);
  assert(readPixel(16,16)==std::vector<uint8_t>({23,67,109,255}));
  GL(glDeleteBuffers)(1,&ubo); GL(glDeleteTextures)(1,&samplerTexture);
  GL(glActiveTexture)(GL_TEXTURE0);

  const auto sampleProgram = link(
      "#version 300 es\nin vec2 p; void main(){gl_Position=vec4(p,0.,1.);}",
      "#version 300 es\nprecision highp float;uniform sampler2D image;out vec4 o;void main(){o=texture(image,vec2(.5));}");
  GL(glUseProgram)(sampleProgram);
  GL(glUniform1i)(GL(glGetUniformLocation)(sampleProgram,"image"),0);
  GLuint compressed;
  GL(glGenTextures)(1,&compressed);
  GL(glBindTexture)(GL_TEXTURE_2D,compressed);
  GL(glTexParameteri)(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);
  struct CompressedCase {GLenum format; GLsizei size; int alpha;};
  for(const auto c : {CompressedCase{0x83f0,8,255}, {0x83f1,8,255},
                     {0x83f2,16,0}, {0x83f3,16,0}, {0x8c4c,8,255},
                     {0x8c4d,8,255}, {0x8c4e,16,0}, {0x8c4f,16,0},
                     {0x8dbb,8,255}, {0x8dbc,8,255}, {0x8dbd,16,255},
                     {0x8dbe,16,255}, {0x8e8c,16,0}, {0x8e8d,16,0},
                     {0x8e8e,16,255}, {0x8e8f,16,255}}) {
    uint8_t block[16] = {};
    if(c.format==0x8e8c || c.format==0x8e8d) block[0]=0x40; // Valid BC7 mode6
    GL(glCompressedTexImage2D)(GL_TEXTURE_2D,0,c.format,4,4,0,c.size,block);
    GL(glDrawArrays)(GL_TRIANGLES,0,3);
    auto pixel=readPixel(16,16);
    if(pixel!=std::vector<uint8_t>({0,0,0,uint8_t(c.alpha)})) {
      fprintf(stderr,"compressed format%x returned %d,%d,%d,%d\n",c.format,pixel[0],pixel[1],pixel[2],pixel[3]); abort();
    }
  }
  GL(glDeleteTextures)(1,&compressed);

  // Four independently shaded array layers exercise the OVR multiview path.
  const auto multiviewAttach = reinterpret_cast<void(*)(GLenum,GLenum,GLuint,GLint,GLint,GLsizei)>(getProc("glFramebufferTextureMultiviewOVR"));
  assert(multiviewAttach);
  const auto multiviewProgram = link(
      "#version 300 es\n#extension GL_OVR_multiview2 : require\nlayout(num_views=4) in;in vec2 p;void main(){gl_Position=vec4(p,0.,1.);}",
      "#version 300 es\n#extension GL_OVR_multiview2 : require\nprecision highp float;out vec4 o;void main(){o=vec4((float(gl_ViewID_OVR)+1.)/4.,0.,0.,1.);}");
  GLuint viewsTexture, viewsFramebuffer;
  GL(glGenTextures)(1,&viewsTexture);
  GL(glBindTexture)(GL_TEXTURE_2D_ARRAY,viewsTexture);
  GL(glTexStorage3D)(GL_TEXTURE_2D_ARRAY,1,GL_RGBA8,32,32,4);
  GL(glGenFramebuffers)(1,&viewsFramebuffer);
  GL(glBindFramebuffer)(GL_FRAMEBUFFER,viewsFramebuffer);
  multiviewAttach(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,viewsTexture,0,0,4);
  assert(GL(glCheckFramebufferStatus)(GL_FRAMEBUFFER)==GL_FRAMEBUFFER_COMPLETE);
  GL(glUseProgram)(multiviewProgram);
  GL(glDrawArrays)(GL_TRIANGLES,0,3);
  for(int view=0;view<4;++view) {
    GL(glFramebufferTextureLayer)(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,viewsTexture,0,view);
    auto pixel=readPixel(16,16);
    assert(abs(int(pixel[0])-int((view+1)*255.f/4.f+.5f))<=1 && pixel[3]==255);
  }
  GL(glBindFramebuffer)(GL_FRAMEBUFFER,0);
  GL(glDeleteFramebuffers)(1,&viewsFramebuffer);
  GL(glDeleteTextures)(1,&viewsTexture);
  // Thin targets hit the true 16k horizontal and vertical raster boundaries
  // without requiring a one-gigabyte square allocation.
  GLuint targetTexture, framebuffer;
  GL(glGenTextures)(1, &targetTexture);
  GL(glGenFramebuffers)(1, &framebuffer);
  GL(glBindFramebuffer)(GL_FRAMEBUFFER, framebuffer);
  GL(glBindTexture)(GL_TEXTURE_2D, targetTexture);
  const auto solid = shader(GL_FRAGMENT_SHADER,
      "precision highp float; void main(){gl_FragColor=vec4(1.,0.,0.,1.);}");
  const auto solidProgram = GL(glCreateProgram)();
  GL(glAttachShader)(solidProgram, vertex);
  GL(glAttachShader)(solidProgram, solid);
  GL(glBindAttribLocation)(solidProgram, 0, "p");
  GL(glLinkProgram)(solidProgram);
  GL(glGetProgramiv)(solidProgram, GL_LINK_STATUS, &status);
  assert(status);
  GL(glUseProgram)(solidProgram);
  const auto expectRed = [&](int x, int y, int red) {
    uint8_t pixel[4] = {};
    GL(glReadPixels)(x,y,1,1,GL_RGBA,GL_UNSIGNED_BYTE,pixel);
    if(!(abs(int(pixel[0])-red) <= 1 && pixel[1] == 0 && pixel[2] == 0)) fprintf(stderr,"pixel %d,%d expected red%d got %d,%d,%d,%d error%x\n",x,y,red,pixel[0],pixel[1],pixel[2],pixel[3],GL(glGetError)());
    assert(abs(int(pixel[0])-red) <= 1 && pixel[1] == 0 && pixel[2] == 0);
  };
  for (bool vertical : {false, true}) {
    const int width = vertical ? 2 : 16384;
    const int height = vertical ? 16384 : 2;
    GL(glTexImage2D)(GL_TEXTURE_2D,0,GL_RGBA8,width,height,0,GL_RGBA,GL_UNSIGNED_BYTE,nullptr);
    GL(glFramebufferTexture2D)(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,targetTexture,0);
    assert(GL(glCheckFramebufferStatus)(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE);
    GL(glViewport)(0,0,width,height);
    GL(glClearColor)(0,0,0,1);
    GL(glClear)(GL_COLOR_BUFFER_BIT);
    GL(glDrawArrays)(GL_TRIANGLES,0,3);
    expectRed(width-1,height-1,255);
    expectRed(0,0,255);
    GL(glViewport)(0,0,32767,32767);
    GL(glClear)(GL_COLOR_BUFFER_BIT);
    GL(glDrawArrays)(GL_TRIANGLES,0,3);
    expectRed(width-1,height-1,255);
    assert(GL(glGetError)() == GL_NO_ERROR);
    GL(glTexImage2D)(GL_TEXTURE_2D,0,GL_RGBA8,16385,1,0,GL_RGBA,GL_UNSIGNED_BYTE,nullptr);
    assert(GL(glGetError)() == GL_INVALID_VALUE);
  }

  const auto pointProgram = link(
      "attribute vec2 p; uniform float size; void main(){gl_Position=vec4(0.,0.,0.,1.);gl_PointSize=size;}",
      "precision highp float; void main(){gl_FragColor=vec4(1.,0.,0.,1.);}");
  GL(glTexImage2D)(GL_TEXTURE_2D,0,GL_RGBA8,2050,2,0,GL_RGBA,GL_UNSIGNED_BYTE,nullptr);
  GL(glViewport)(0,0,2050,2);
  GL(glUseProgram)(pointProgram);
  for(float size : {1024.f,2047.f}) {
    GL(glClear)(GL_COLOR_BUFFER_BIT);
    GL(glUniform1f)(GL(glGetUniformLocation)(pointProgram,"size"),size);
    GL(glDrawArrays)(GL_POINTS,0,1);
    expectRed(1025 + int(size/2)-1,0,255);
    expectRed(1025 + int(size/2)+1,0,0);
  }
  GL(glUseProgram)(solidProgram);
  const auto alphaProgram = link(
      "attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}",
      "precision highp float;void main(){gl_FragColor=vec4(1.,0.,0.,.5);}");
  GLuint msFramebuffer, renderbuffers[2];
  GL(glGenFramebuffers)(1,&msFramebuffer);
  GL(glGenRenderbuffers)(2,renderbuffers);
  GL(glBindTexture)(GL_TEXTURE_2D,targetTexture);
  GL(glTexImage2D)(GL_TEXTURE_2D,0,GL_RGBA8,32,32,0,GL_RGBA,GL_UNSIGNED_BYTE,nullptr);
  GL(glViewport)(0,0,32,32);
  // Independently exercise every sample, including samples 4..7 that could
  // silently alias or disappear if any four-element storage remains.
  for (int samples : {2,4,8}) {
    GL(glBindFramebuffer)(GL_FRAMEBUFFER,msFramebuffer);
    GL(glBindRenderbuffer)(GL_RENDERBUFFER,renderbuffers[0]);
    GL(glRenderbufferStorageMultisample)(GL_RENDERBUFFER,samples,GL_RGBA8,32,32);
    GL(glFramebufferRenderbuffer)(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_RENDERBUFFER,renderbuffers[0]);
    GL(glBindRenderbuffer)(GL_RENDERBUFFER,renderbuffers[1]);
    GL(glRenderbufferStorageMultisample)(GL_RENDERBUFFER,samples,GL_DEPTH24_STENCIL8,32,32);
    GL(glFramebufferRenderbuffer)(GL_FRAMEBUFFER,GL_DEPTH_STENCIL_ATTACHMENT,GL_RENDERBUFFER,renderbuffers[1]);
    assert(GL(glCheckFramebufferStatus)(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE);
    GLint actualSamples;
    GL(glGetIntegerv)(GL_SAMPLES,&actualSamples);
    assert(actualSamples == samples);
    for (int sample = 0; sample < samples; ++sample) {
      GL(glBindFramebuffer)(GL_FRAMEBUFFER,msFramebuffer);
      GL(glClear)(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT|GL_STENCIL_BUFFER_BIT);
      GL(glEnable)(GL_DEPTH_TEST);
      GL(glEnable)(GL_STENCIL_TEST);
      GL(glStencilFunc)(GL_ALWAYS,1,255);
      GL(glStencilOp)(GL_KEEP,GL_KEEP,GL_REPLACE);
      GL(glEnable)(GL_SAMPLE_MASK);
      GL(glSampleMaski)(0,1u<<sample);
      GL(glDrawArrays)(GL_TRIANGLES,0,3);
      GL(glDisable)(GL_SAMPLE_MASK);
      GL(glDisable)(GL_DEPTH_TEST);
      GL(glDisable)(GL_STENCIL_TEST);
      GL(glBindFramebuffer)(GL_READ_FRAMEBUFFER,msFramebuffer);
      GL(glBindFramebuffer)(GL_DRAW_FRAMEBUFFER,framebuffer);
      GL(glBlitFramebuffer)(0,0,32,32,0,0,32,32,GL_COLOR_BUFFER_BIT,GL_NEAREST);
      GL(glBindFramebuffer)(GL_FRAMEBUFFER,framebuffer);
      expectRed(16,16,255/samples);
      assert(GL(glGetError)() == GL_NO_ERROR);
    }
    GL(glBindFramebuffer)(GL_FRAMEBUFFER,msFramebuffer);
    GL(glClear)(GL_COLOR_BUFFER_BIT);
    GL(glUseProgram)(alphaProgram);
    GL(glEnable)(GL_SAMPLE_ALPHA_TO_COVERAGE);
    GL(glDrawArrays)(GL_TRIANGLES,0,3);
    GL(glDisable)(GL_SAMPLE_ALPHA_TO_COVERAGE);
    GL(glBindFramebuffer)(GL_READ_FRAMEBUFFER,msFramebuffer);
    GL(glBindFramebuffer)(GL_DRAW_FRAMEBUFFER,framebuffer);
    GL(glBlitFramebuffer)(0,0,32,32,0,0,32,32,GL_COLOR_BUFFER_BIT,GL_NEAREST);
    GL(glBindFramebuffer)(GL_FRAMEBUFFER,framebuffer);
    expectRed(16,16,128);
    GL(glUseProgram)(solidProgram);
    // Distinguish the standard eight-sample grid from duplicated four-sample
    // positions with a diagonal edge that never falls on a sample location.
    GL(glBindFramebuffer)(GL_FRAMEBUFFER,msFramebuffer);
    GL(glClear)(GL_COLOR_BUFFER_BIT);
    const float edgeVertices[] = {-1,-1,1.00390625f,-1,-1,1.00390625f};
    GL(glBufferData)(GL_ARRAY_BUFFER,sizeof(edgeVertices),edgeVertices,GL_STATIC_DRAW);
    int covered=0;
    for(int sample=0;sample<samples;++sample) {
      GLfloat location[2];
      GL(glGetMultisamplefv)(GL_SAMPLE_POSITION,sample,location);
      if(location[0]+location[1]<1.0625f) ++covered;
    }
    GL(glDrawArrays)(GL_TRIANGLES,0,3);
    GL(glBindFramebuffer)(GL_READ_FRAMEBUFFER,msFramebuffer);
    GL(glBindFramebuffer)(GL_DRAW_FRAMEBUFFER,framebuffer);
    GL(glBlitFramebuffer)(0,0,32,32,0,0,32,32,GL_COLOR_BUFFER_BIT,GL_NEAREST);
    GL(glBindFramebuffer)(GL_FRAMEBUFFER,framebuffer);
    expectRed(16,15,int(covered*255.f/samples+.5f));
    GL(glBufferData)(GL_ARRAY_BUFFER,sizeof(vertices),vertices,GL_STATIC_DRAW);
    assert(GL(glGetError)() == GL_NO_ERROR);
  }
  GL(glBindFramebuffer)(GL_FRAMEBUFFER,0);
  GL(glDeleteFramebuffers)(1,&framebuffer);
  GL(glDeleteFramebuffers)(1,&msFramebuffer);
  GL(glDeleteRenderbuffers)(2,renderbuffers);
  GL(glDeleteTextures)(1,&targetTexture);
  assert(EGL(eglMakeCurrent)(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT));
  assert(EGL(eglDestroySurface)(display, surface));
  assert(EGL(eglDestroyContext)(display, context));
  assert(EGL(eglTerminate)(display));
  puts("PASS CPU reference: 16k raster, independent 2/4/8 color/depth/stencil samples and resolves");
}
