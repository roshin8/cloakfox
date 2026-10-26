/* Unsandboxed capability evidence, using Gecko's AppKit context API and flags.
 * This does not change browser prefs or establish GPU sandbox capability. */
#import <AppKit/AppKit.h>
#import <OpenGL/OpenGL.h>
#import <OpenGL/gl3.h>
#include <stdio.h>

static NSString *glString(GLenum name) {
  const GLubyte *value = glGetString(name);
  return value ? [NSString stringWithUTF8String:(const char *)value] : @"";
}
static void sample(NSString *name, BOOL core, BOOL accelerated, BOOL offline) {
  NSOpenGLPixelFormatAttribute attrs[10]; int i = 0;
  if (offline) attrs[i++] = NSOpenGLPFAAllowOfflineRenderers;
  if (accelerated) attrs[i++] = NSOpenGLPFAAccelerated;
  if (core) { attrs[i++] = NSOpenGLPFAOpenGLProfile; attrs[i++] = NSOpenGLProfileVersion3_2Core; }
  attrs[i] = 0;
  NSOpenGLPixelFormat *format = [[NSOpenGLPixelFormat alloc] initWithAttributes:attrs];
  NSOpenGLContext *context = format ? [[NSOpenGLContext alloc] initWithFormat:format shareContext:nil] : nil;
  NSMutableDictionary *result = [NSMutableDictionary dictionaryWithDictionary:@{
    @"case":name, @"core":@(core), @"acceleratedRequired":@(accelerated),
    @"offlineAllowed":@(offline), @"pixelFormatCreated":@(format != nil),
    @"contextCreated":@(context != nil)}];
  if (context) {
    [context makeCurrentContext];
    result[@"vendor"] = glString(GL_VENDOR); result[@"renderer"] = glString(GL_RENDERER);
    result[@"version"] = glString(GL_VERSION);
    GLint actualAccelerated = 0, rendererID = 0;
    [format getValues:&actualAccelerated forAttribute:NSOpenGLPFAAccelerated forVirtualScreen:0];
    [format getValues:&rendererID forAttribute:NSOpenGLPFARendererID forVirtualScreen:0];
    result[@"accelerated"] = @(actualAccelerated); result[@"rendererID"] = @(rendererID);
    for (int clear = 0; clear < 8 && glGetError() != GL_NO_ERROR; ++clear) {}
    GLuint framebuffer = 0, texture = 0;
    glGenFramebuffers(1, &framebuffer); glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
    glGenTextures(1, &texture); glBindTexture(GL_TEXTURE_2D, texture);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 2, 2, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0);
    result[@"framebufferStatus"] = @(glCheckFramebufferStatus(GL_FRAMEBUFFER));
    glClearColor(1, 0, 0, 1); glClear(GL_COLOR_BUFFER_BIT);
    unsigned char pixel[4] = {0}; glReadPixels(0, 0, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);
    result[@"pixel"] = @[@(pixel[0]), @(pixel[1]), @(pixel[2]), @(pixel[3])];
    result[@"glError"] = @(glGetError());
    glDeleteFramebuffers(1, &framebuffer); glDeleteTextures(1, &texture);
    [NSOpenGLContext clearCurrentContext];
  }
  NSData *json = [NSJSONSerialization dataWithJSONObject:result options:0 error:nil];
  fwrite(json.bytes, 1, json.length, stdout); puts(""); fflush(stdout);
  [context release]; [format release];
}
int main(void) {
  @autoreleasepool {
    sample(@"core-offline", YES, NO, YES);
    sample(@"compat-offline", NO, NO, YES);
    sample(@"core-accelerated-offline", YES, YES, YES);
    sample(@"compat-accelerated-offline", NO, YES, YES);
    sample(@"core-accelerated-online", YES, YES, NO);
  }
  return 0;
}
