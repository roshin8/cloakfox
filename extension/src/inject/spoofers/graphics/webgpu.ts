/**
 * WebGPU Spoofer
 *
 * WebGPU is the next-generation graphics API that exposes
 * detailed GPU information for fingerprinting.
 *
 * This spoofer handles:
 * - GPU adapter info (vendor, architecture, device, description)
 * - GPU limits (max texture size, buffer sizes, etc.)
 * - GPU features (available extensions)
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

// Common GPU configurations that look realistic
const COMMON_GPUS = [
  {
    vendor: 'Google Inc. (Intel)',
    architecture: 'gen-12lp',
    device: 'Intel Iris Xe Graphics',
    description: 'Intel Iris Xe Graphics',
    limits: {
      maxTextureDimension1D: 16384,
      maxTextureDimension2D: 16384,
      maxTextureDimension3D: 2048,
      maxTextureArrayLayers: 2048,
      maxBindGroups: 4,
      maxBindingsPerBindGroup: 1000,
      maxDynamicUniformBuffersPerPipelineLayout: 8,
      maxDynamicStorageBuffersPerPipelineLayout: 4,
      maxSampledTexturesPerShaderStage: 16,
      maxSamplersPerShaderStage: 16,
      maxStorageBuffersPerShaderStage: 8,
      maxStorageTexturesPerShaderStage: 4,
      maxUniformBuffersPerShaderStage: 12,
      maxUniformBufferBindingSize: 65536,
      maxStorageBufferBindingSize: 134217728,
      minUniformBufferOffsetAlignment: 256,
      minStorageBufferOffsetAlignment: 256,
      maxVertexBuffers: 8,
      maxBufferSize: 268435456,
      maxVertexAttributes: 16,
      maxVertexBufferArrayStride: 2048,
      maxInterStageShaderComponents: 60,
      maxInterStageShaderVariables: 16,
      maxColorAttachments: 8,
      maxColorAttachmentBytesPerSample: 32,
      maxComputeWorkgroupStorageSize: 16384,
      maxComputeInvocationsPerWorkgroup: 256,
      maxComputeWorkgroupSizeX: 256,
      maxComputeWorkgroupSizeY: 256,
      maxComputeWorkgroupSizeZ: 64,
      maxComputeWorkgroupsPerDimension: 65535,
    },
    features: ['texture-compression-bc', 'depth-clip-control', 'depth32float-stencil8'],
  },
  {
    vendor: 'Google Inc. (NVIDIA)',
    architecture: 'ampere',
    device: 'NVIDIA GeForce RTX 3060',
    description: 'NVIDIA GeForce RTX 3060',
    limits: {
      maxTextureDimension1D: 16384,
      maxTextureDimension2D: 16384,
      maxTextureDimension3D: 2048,
      maxTextureArrayLayers: 2048,
      maxBindGroups: 4,
      maxBindingsPerBindGroup: 1000,
      maxDynamicUniformBuffersPerPipelineLayout: 15,
      maxDynamicStorageBuffersPerPipelineLayout: 8,
      maxSampledTexturesPerShaderStage: 16,
      maxSamplersPerShaderStage: 16,
      maxStorageBuffersPerShaderStage: 8,
      maxStorageTexturesPerShaderStage: 8,
      maxUniformBuffersPerShaderStage: 15,
      maxUniformBufferBindingSize: 65536,
      maxStorageBufferBindingSize: 2147483647,
      minUniformBufferOffsetAlignment: 256,
      minStorageBufferOffsetAlignment: 32,
      maxVertexBuffers: 16,
      maxBufferSize: 2147483647,
      maxVertexAttributes: 32,
      maxVertexBufferArrayStride: 2048,
      maxInterStageShaderComponents: 124,
      maxInterStageShaderVariables: 16,
      maxColorAttachments: 8,
      maxColorAttachmentBytesPerSample: 32,
      maxComputeWorkgroupStorageSize: 49152,
      maxComputeInvocationsPerWorkgroup: 1024,
      maxComputeWorkgroupSizeX: 1024,
      maxComputeWorkgroupSizeY: 1024,
      maxComputeWorkgroupSizeZ: 64,
      maxComputeWorkgroupsPerDimension: 65535,
    },
    features: [
      'texture-compression-bc',
      'depth-clip-control',
      'depth32float-stencil8',
      'timestamp-query',
      'indirect-first-instance',
      'shader-f16',
      'rg11b10ufloat-renderable',
      'bgra8unorm-storage',
      'float32-filterable',
    ],
  },
  {
    vendor: 'Google Inc. (AMD)',
    architecture: 'rdna-2',
    device: 'AMD Radeon RX 6700 XT',
    description: 'AMD Radeon RX 6700 XT',
    limits: {
      maxTextureDimension1D: 16384,
      maxTextureDimension2D: 16384,
      maxTextureDimension3D: 2048,
      maxTextureArrayLayers: 2048,
      maxBindGroups: 4,
      maxBindingsPerBindGroup: 1000,
      maxDynamicUniformBuffersPerPipelineLayout: 8,
      maxDynamicStorageBuffersPerPipelineLayout: 8,
      maxSampledTexturesPerShaderStage: 16,
      maxSamplersPerShaderStage: 16,
      maxStorageBuffersPerShaderStage: 8,
      maxStorageTexturesPerShaderStage: 8,
      maxUniformBuffersPerShaderStage: 12,
      maxUniformBufferBindingSize: 65536,
      maxStorageBufferBindingSize: 1073741824,
      minUniformBufferOffsetAlignment: 256,
      minStorageBufferOffsetAlignment: 4,
      maxVertexBuffers: 16,
      maxBufferSize: 1073741824,
      maxVertexAttributes: 32,
      maxVertexBufferArrayStride: 2048,
      maxInterStageShaderComponents: 64,
      maxInterStageShaderVariables: 16,
      maxColorAttachments: 8,
      maxColorAttachmentBytesPerSample: 32,
      maxComputeWorkgroupStorageSize: 65536,
      maxComputeInvocationsPerWorkgroup: 1024,
      maxComputeWorkgroupSizeX: 1024,
      maxComputeWorkgroupSizeY: 1024,
      maxComputeWorkgroupSizeZ: 1024,
      maxComputeWorkgroupsPerDimension: 65535,
    },
    features: [
      'texture-compression-bc',
      'depth-clip-control',
      'depth32float-stencil8',
      'timestamp-query',
      'indirect-first-instance',
    ],
  },
  {
    vendor: 'Google Inc. (Apple)',
    architecture: 'apple-m1',
    device: 'Apple M1',
    description: 'Apple M1',
    limits: {
      maxTextureDimension1D: 16384,
      maxTextureDimension2D: 16384,
      maxTextureDimension3D: 2048,
      maxTextureArrayLayers: 2048,
      maxBindGroups: 4,
      maxBindingsPerBindGroup: 1000,
      maxDynamicUniformBuffersPerPipelineLayout: 8,
      maxDynamicStorageBuffersPerPipelineLayout: 4,
      maxSampledTexturesPerShaderStage: 16,
      maxSamplersPerShaderStage: 16,
      maxStorageBuffersPerShaderStage: 8,
      maxStorageTexturesPerShaderStage: 4,
      maxUniformBuffersPerShaderStage: 12,
      maxUniformBufferBindingSize: 65536,
      maxStorageBufferBindingSize: 134217728,
      minUniformBufferOffsetAlignment: 256,
      minStorageBufferOffsetAlignment: 256,
      maxVertexBuffers: 8,
      maxBufferSize: 268435456,
      maxVertexAttributes: 16,
      maxVertexBufferArrayStride: 2048,
      maxInterStageShaderComponents: 60,
      maxInterStageShaderVariables: 16,
      maxColorAttachments: 8,
      maxColorAttachmentBytesPerSample: 32,
      maxComputeWorkgroupStorageSize: 32768,
      maxComputeInvocationsPerWorkgroup: 1024,
      maxComputeWorkgroupSizeX: 1024,
      maxComputeWorkgroupSizeY: 1024,
      maxComputeWorkgroupSizeZ: 1024,
      maxComputeWorkgroupsPerDimension: 65535,
    },
    features: ['depth-clip-control', 'depth32float-stencil8', 'texture-compression-bc'],
  },
];

/**
 * Create a spoofed GPUAdapterInfo object
 */
function createSpoofedAdapterInfo(
  gpu: (typeof COMMON_GPUS)[0]
): GPUAdapterInfo {
  return {
    vendor: gpu.vendor,
    architecture: gpu.architecture,
    device: gpu.device,
    description: gpu.description,
  };
}

/**
 * Create spoofed GPU limits
 */
function createSpoofedLimits(
  gpu: (typeof COMMON_GPUS)[0],
  originalLimits: GPUSupportedLimits
): GPUSupportedLimits {
  const spoofedLimits = gpu.limits;

  return new Proxy(originalLimits, {
    get(target, prop) {
      if (prop in spoofedLimits) {
        return spoofedLimits[prop as keyof typeof spoofedLimits];
      }
      return (target as any)[prop];
    },
  });
}

/**
 * Create spoofed GPU features set
 */
function createSpoofedFeatures(
  gpu: (typeof COMMON_GPUS)[0],
  originalFeatures: GPUSupportedFeatures
): GPUSupportedFeatures {
  const spoofedFeatures = new Set(gpu.features);

  return new Proxy(originalFeatures, {
    get(target, prop) {
      if (prop === 'has') {
        return (feature: string) => spoofedFeatures.has(feature);
      }
      if (prop === 'size') {
        return spoofedFeatures.size;
      }
      if (prop === 'forEach') {
        return (callback: (value: string) => void) =>
          spoofedFeatures.forEach(callback);
      }
      if (prop === 'keys' || prop === 'values') {
        return () => spoofedFeatures.values();
      }
      if (prop === 'entries') {
        return () => spoofedFeatures.entries();
      }
      if (prop === Symbol.iterator) {
        return () => spoofedFeatures.values();
      }
      return (target as any)[prop];
    },
  }) as GPUSupportedFeatures;
}

/**
 * Initialize WebGPU spoofing
 */
export function initWebGPUSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  if (typeof navigator === 'undefined' || !('gpu' in navigator)) return;

  const gpu = (navigator as any).gpu;
  if (!gpu) return;

  const selectedGPU = prng.pick(COMMON_GPUS);
  const originalRequestAdapter = gpu.requestAdapter?.bind(gpu);

  if (originalRequestAdapter) {
    gpu.requestAdapter = async function (
      options?: GPURequestAdapterOptions
    ): Promise<GPUAdapter | null> {
      logAccess('navigator.gpu.requestAdapter', { spoofed: mode !== 'block' });

      if (mode === 'block') {
        return null; // Pretend WebGPU is not available
      }

      const adapter = await originalRequestAdapter(options);

      if (!adapter) return null;

      // Create a comprehensive proxy to spoof all adapter properties
      const spoofedAdapter = new Proxy(adapter, {
        get(target, prop) {
          // Spoof requestAdapterInfo
          if (prop === 'requestAdapterInfo') {
            return async () => {
              logAccess('GPUAdapter.requestAdapterInfo', { spoofed: true });
              return createSpoofedAdapterInfo(selectedGPU);
            };
          }

          // Spoof info property (deprecated but still used)
          if (prop === 'info') {
            logAccess('GPUAdapter.info', { spoofed: true });
            return createSpoofedAdapterInfo(selectedGPU);
          }

          // Spoof limits
          if (prop === 'limits') {
            logAccess('GPUAdapter.limits', { spoofed: true });
            return createSpoofedLimits(selectedGPU, target.limits);
          }

          // Spoof features
          if (prop === 'features') {
            logAccess('GPUAdapter.features', { spoofed: true });
            return createSpoofedFeatures(selectedGPU, target.features);
          }

          // Spoof isFallbackAdapter
          if (prop === 'isFallbackAdapter') {
            return false;
          }

          // Wrap requestDevice to also spoof device limits/features
          if (prop === 'requestDevice') {
            return async function (
              descriptor?: GPUDeviceDescriptor
            ): Promise<GPUDevice> {
              logAccess('GPUAdapter.requestDevice', { spoofed: true });
              const device = await target.requestDevice(descriptor);

              // Proxy the device to spoof its limits and features too
              return new Proxy(device, {
                get(deviceTarget, deviceProp) {
                  if (deviceProp === 'limits') {
                    return createSpoofedLimits(selectedGPU, deviceTarget.limits);
                  }
                  if (deviceProp === 'features') {
                    return createSpoofedFeatures(
                      selectedGPU,
                      deviceTarget.features
                    );
                  }

                  const value = (deviceTarget as any)[deviceProp];
                  if (typeof value === 'function') {
                    return value.bind(deviceTarget);
                  }
                  return value;
                },
              });
            };
          }

          const value = (target as any)[prop];
          if (typeof value === 'function') {
            return value.bind(target);
          }
          return value;
        },
      });

      return spoofedAdapter;
    };
  }

}
