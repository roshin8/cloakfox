/* Hosted capability evidence only. This unsandboxed helper does not prove
 * browser GPU sandbox access and never changes browser configuration. */
#include <OpenGL/OpenGL.h>
#include <stdio.h>

static void sample(const char *name, int core, int accelerated) {
  CGLPixelFormatAttribute attrs[10];
  int i = 0;
  attrs[i++] = kCGLPFAAllowOfflineRenderers;
  if (accelerated) attrs[i++] = kCGLPFAAccelerated;
  if (core) {
    attrs[i++] = kCGLPFAOpenGLProfile;
    attrs[i++] = (CGLPixelFormatAttribute)kCGLOGLPVersion_3_2_Core;
  }
  attrs[i] = (CGLPixelFormatAttribute)0;
  CGLPixelFormatObj format = NULL;
  CGLContextObj context = NULL;
  GLint count = 0;
  CGLError choose = CGLChoosePixelFormat(attrs, &format, &count);
  CGLError create = format ? CGLCreateContext(format, NULL, &context) : choose;
  printf("{\"case\":\"%s\",\"pixelFormatError\":%d,\"pixelFormatMessage\":\"%s\",\"formatCount\":%d,\"contextError\":%d,\"contextMessage\":\"%s\",\"contextCreated\":%s}\n",
         name, choose, CGLErrorString(choose), count, create,
         CGLErrorString(create), context ? "true" : "false");
  if (context) CGLDestroyContext(context);
  if (format) CGLDestroyPixelFormat(format);
}
int main(void) {
  sample("core-offline", 1, 0);
  sample("compat-offline", 0, 0);
  sample("core-accelerated-offline", 1, 1);
  return 0;
}
