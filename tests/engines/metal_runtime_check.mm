#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cstdio>
int main() { @autoreleasepool {
  id<MTLDevice> device = MTLCreateSystemDefaultDevice(); if (!device) return 1;
  NSError* error = nil;
  NSString* source = @"#include <metal_stdlib>\nusing namespace metal;\nkernel void fill(device float* out [[buffer(0)]], uint id [[thread_position_in_grid]]) { out[id] = 3.0f; }";
  id<MTLLibrary> library = [device newLibraryWithSource:source options:nil error:&error];
  if (!library) { std::fprintf(stderr, "%s\n", error.description.UTF8String); return 2; }
  id<MTLComputePipelineState> pipeline = [device newComputePipelineStateWithFunction:[library newFunctionWithName:@"fill"] error:&error];
  if (!pipeline) return 3;
  id<MTLBuffer> buffer = [device newBufferWithLength:sizeof(float) options:MTLResourceStorageModeShared];
  *static_cast<float*>(buffer.contents) = 0;
  id<MTLCommandQueue> queue = [device newCommandQueue];
  id<MTLCommandBuffer> command = [queue commandBuffer];
  id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
  [encoder setComputePipelineState:pipeline]; [encoder setBuffer:buffer offset:0 atIndex:0];
  [encoder dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
  [encoder endEncoding]; [command commit]; [command waitUntilCompleted];
  if (command.status != MTLCommandBufferStatusCompleted || *static_cast<float*>(buffer.contents) != 3.0f) return 4;
  std::puts("PASS: runtime Metal shader compilation and GPU compute result 3.0");
} return 0; }
