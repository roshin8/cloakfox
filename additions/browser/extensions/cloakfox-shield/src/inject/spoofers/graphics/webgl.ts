/**
 * WebGL Spoofer - Spoofs WebGL parameters and renderer info
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideMethod, registerNative } from '@/lib/stealth';
import { GL } from '@/lib/constants';
import { logAccess, markWebGLSpoofed } from '../../monitor/fingerprint-monitor';

import type { AssignedProfileData } from '@/types';

// GPU combinations by platform — no Intel (too similar to real hardware on Macs)
const WINDOWS_GPUS = [
  { vendor: 'Google Inc. (NVIDIA)', renderer: 'ANGLE (NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0)' },
  { vendor: 'Google Inc. (NVIDIA)', renderer: 'ANGLE (NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)' },
  { vendor: 'Google Inc. (NVIDIA)', renderer: 'ANGLE (NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0)' },
  { vendor: 'Google Inc. (NVIDIA)', renderer: 'ANGLE (NVIDIA GeForce RTX 4070 Ti Direct3D11 vs_5_0 ps_5_0)' },
  { vendor: 'Google Inc. (NVIDIA)', renderer: 'ANGLE (NVIDIA GeForce RTX 4060 Direct3D11 vs_5_0 ps_5_0)' },
  { vendor: 'Google Inc. (AMD)', renderer: 'ANGLE (AMD Radeon RX 6700 XT Direct3D11 vs_5_0 ps_5_0)' },
  { vendor: 'Google Inc. (AMD)', renderer: 'ANGLE (AMD Radeon RX 7800 XT Direct3D11 vs_5_0 ps_5_0)' },
  { vendor: 'Google Inc. (AMD)', renderer: 'ANGLE (AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0)' },
];

// Firefox-on-Mac WebGL strings — what real Firefox emits.
const MAC_GPUS_FIREFOX = [
  { vendor: 'Apple Inc.', renderer: 'Apple M1' },
  { vendor: 'Apple Inc.', renderer: 'Apple M1 Pro' },
  { vendor: 'Apple Inc.', renderer: 'Apple M2' },
  { vendor: 'Apple Inc.', renderer: 'Apple M2 Pro' },
  { vendor: 'Apple Inc.', renderer: 'Apple M3' },
  { vendor: 'Apple Inc.', renderer: 'Apple M3 Pro' },
  { vendor: 'Apple Inc.', renderer: 'Apple M4' },
];

// Chrome-on-Mac WebGL strings — Chrome uses ANGLE+Metal everywhere.
// Real string format: "ANGLE (Apple, ANGLE Metal Renderer: <model>, Unspecified Version)"
// Backwards-compat alias for any external callers.
const MAC_GPUS = MAC_GPUS_FIREFOX;
const MAC_GPUS_CHROME = [
  { vendor: 'Google Inc. (Apple)', renderer: 'ANGLE (Apple, ANGLE Metal Renderer: Apple M1, Unspecified Version)' },
  { vendor: 'Google Inc. (Apple)', renderer: 'ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Pro, Unspecified Version)' },
  { vendor: 'Google Inc. (Apple)', renderer: 'ANGLE (Apple, ANGLE Metal Renderer: Apple M2, Unspecified Version)' },
  { vendor: 'Google Inc. (Apple)', renderer: 'ANGLE (Apple, ANGLE Metal Renderer: Apple M2 Pro, Unspecified Version)' },
  { vendor: 'Google Inc. (Apple)', renderer: 'ANGLE (Apple, ANGLE Metal Renderer: Apple M3, Unspecified Version)' },
  { vendor: 'Google Inc. (Apple)', renderer: 'ANGLE (Apple, ANGLE Metal Renderer: Apple M3 Pro, Unspecified Version)' },
  { vendor: 'Google Inc. (Apple)', renderer: 'ANGLE (Apple, ANGLE Metal Renderer: Apple M4, Unspecified Version)' },
];

// Safari-on-Mac WebGL strings — WebKit-style, simpler.
const MAC_GPUS_SAFARI = [
  { vendor: 'Apple Inc.', renderer: 'Apple GPU' },
];

const MOBILE_GPUS = [
  { vendor: 'Apple GPU', renderer: 'Apple A16 GPU' },
  { vendor: 'Apple GPU', renderer: 'Apple A17 Pro GPU' },
  { vendor: 'Qualcomm', renderer: 'Adreno (TM) 740' },
  { vendor: 'Qualcomm', renderer: 'Adreno (TM) 730' },
  { vendor: 'ARM', renderer: 'Mali-G710 MC10' },
];

// Firefox-on-Linux WebGL strings — what real Firefox emits with X.Org/Mesa.
const LINUX_GPUS_FIREFOX = [
  { vendor: 'X.Org', renderer: 'AMD Radeon RX 580 (polaris10, DRM 3.49.0)' },
  { vendor: 'X.Org', renderer: 'AMD Radeon RX 6700 XT (navi22, DRM 3.49.0)' },
  { vendor: 'X.Org', renderer: 'AMD Radeon RX 7800 XT (navi32, DRM 3.54.0)' },
  { vendor: 'nouveau', renderer: 'NV136' },
  { vendor: 'nouveau', renderer: 'NV167' },
];
const LINUX_GPUS = LINUX_GPUS_FIREFOX;

// Chrome-on-Linux WebGL strings — Chrome uses ANGLE on Linux too.
const LINUX_GPUS_CHROME = [
  { vendor: 'Google Inc. (NVIDIA Corporation)', renderer: 'ANGLE (NVIDIA Corporation, NVIDIA GeForce RTX 3060/PCIe/SSE2, OpenGL 4.6.0 NVIDIA 535.146.02)' },
  { vendor: 'Google Inc. (Intel)', renderer: 'ANGLE (Intel, Mesa Intel(R) UHD Graphics 630 (CFL GT2), OpenGL 4.6 (Compatibility Profile) Mesa 23.2.1-1ubuntu3)' },
  { vendor: 'Google Inc. (AMD)', renderer: 'ANGLE (AMD, AMD Radeon RX 6700 XT (RADV NAVI22), OpenGL 4.6 (Core Profile) Mesa 23.2.1-1ubuntu3)' },
];

// Module-level selected GPU so Worker spoofer can access it
let _selectedGPU: { vendor: string; renderer: string } | null = null;

export function getSelectedGPU(): { vendor: string; renderer: string } | null {
  return _selectedGPU;
}

/**
 * Select GPU matching the profile's platform (shared by WebGL and Worker spoofers)
 */
export function selectGPUForProfile(prng: PRNG, assignedProfile?: AssignedProfileData): { vendor: string; renderer: string } {
  const platform = assignedProfile?.userAgent?.platformName?.toLowerCase() || '';
  const isMobile = assignedProfile?.userAgent?.mobile ?? false;
  // Detect browser family from the UA string so we can pick the
  // matching WebGL string style. Real Chrome on every desktop platform
  // uses ANGLE (Direct3D11 on Win, Metal on Mac, NVIDIA/Mesa on Linux).
  // Real Firefox uses raw driver strings ("Apple Inc." / "X.Org"). Real
  // Safari uses minimal "Apple GPU". Mismatching the style with the UA
  // is a direct fingerprint mismatch.
  const ua = assignedProfile?.userAgent?.userAgent || '';
  const isChrome = ua.includes('Chrome/') && !ua.includes('Firefox/');
  const isSafari = !isChrome && ua.includes('Safari/') && !ua.includes('Chrome/');

  let gpuList: { vendor: string; renderer: string }[] = WINDOWS_GPUS as any;
  if (isMobile) {
    gpuList = MOBILE_GPUS;
  } else if (platform.includes('mac') || platform.includes('ios')) {
    if (isSafari) gpuList = MAC_GPUS_SAFARI;
    else if (isChrome) gpuList = MAC_GPUS_CHROME;
    else gpuList = MAC_GPUS_FIREFOX;
  } else if (platform.includes('linux')) {
    if (isChrome) gpuList = LINUX_GPUS_CHROME;
    else gpuList = LINUX_GPUS_FIREFOX;
  }
  // Windows GPUs are already ANGLE-style — Chrome's the dominant browser
  // there and Firefox-on-Windows tends to also report ANGLE-similar
  // strings since both go through D3D. Single list is fine.
  return prng.pick(gpuList);
}

/**
 * Initialize WebGL spoofing
 */
export function initWebGLSpoofer(
  webglMode: ProtectionMode,
  webgl2Mode: ProtectionMode,
  prng: PRNG,
  assignedProfile?: AssignedProfileData
): void {
  if (webglMode !== 'off') {
    markWebGLSpoofed(webglMode);
  }

  const selectedGPU = selectGPUForProfile(prng, assignedProfile);
  _selectedGPU = selectedGPU;

  const { VENDOR: GL_VENDOR, RENDERER: GL_RENDERER, UNMASKED_VENDOR: UNMASKED_VENDOR_WEBGL, UNMASKED_RENDERER: UNMASKED_RENDERER_WEBGL } = GL;

  // Strategy: three layers of override for maximum compatibility.
  // 1. Prototype-level via defineProperty
  // 2. Prototype-level via direct assignment
  // 3. Instance-level via getContext interception
  const spoofedGetParam = function getParameter(this: any, pname: GLenum) {
    if (webglMode === 'block') return null;
    if (pname === UNMASKED_VENDOR_WEBGL || pname === GL_VENDOR) return selectedGPU.vendor;
    if (pname === UNMASKED_RENDERER_WEBGL || pname === GL_RENDERER) return selectedGPU.renderer;
    return _origWGL1GetParam.call(this, pname);
  };

  const _origWGL1GetParam = WebGLRenderingContext.prototype.getParameter;
  let _origWGL2GetParam: Function | null = null;

  if (webglMode !== 'off') {
    registerNative(spoofedGetParam, 'getParameter');
    // Layer 1: defineProperty on prototype
    try {
      Object.defineProperty(WebGLRenderingContext.prototype, 'getParameter', {
        value: spoofedGetParam, writable: true, configurable: true,
      });
    } catch {}
    // Layer 2: direct assignment on prototype
    try { (WebGLRenderingContext.prototype as any).getParameter = spoofedGetParam; } catch {}
  }

  if (webgl2Mode !== 'off' && typeof WebGL2RenderingContext !== 'undefined') {
    _origWGL2GetParam = WebGL2RenderingContext.prototype.getParameter;
    const spoofedGetParam2 = function getParameter(this: any, pname: GLenum) {
      if (webgl2Mode === 'block') return null;
      if (pname === UNMASKED_VENDOR_WEBGL || pname === GL_VENDOR) return selectedGPU.vendor;
      if (pname === UNMASKED_RENDERER_WEBGL || pname === GL_RENDERER) return selectedGPU.renderer;
      return _origWGL2GetParam!.call(this, pname);
    };
    registerNative(spoofedGetParam2, 'getParameter');
    try {
      Object.defineProperty(WebGL2RenderingContext.prototype, 'getParameter', {
        value: spoofedGetParam2, writable: true, configurable: true,
      });
    } catch {}
    try { (WebGL2RenderingContext.prototype as any).getParameter = spoofedGetParam2; } catch {}
  }

  // Layer 3: intercept getContext to patch each instance directly
  if (webglMode !== 'off' || webgl2Mode !== 'off') {
    try {
      const origGetContext = HTMLCanvasElement.prototype.getContext;
      const patchCtx = (ctx: any, mode: ProtectionMode, origGP: Function) => {
        if (!ctx || ctx._csPatchedGP) return ctx;
        try {
          const bound = origGP.bind(ctx);
          ctx.getParameter = function(pname: GLenum) {
            if (mode === 'block') return null;
            if (pname === UNMASKED_VENDOR_WEBGL || pname === GL_VENDOR) return selectedGPU.vendor;
            if (pname === UNMASKED_RENDERER_WEBGL || pname === GL_RENDERER) return selectedGPU.renderer;
            return bound(pname);
          };
          ctx._csPatchedGP = true;
        } catch {}
        return ctx;
      };

      overrideMethod(HTMLCanvasElement.prototype, 'getContext', (original, thisArg, args) => {
        const ctx = original.call(thisArg, ...args);
        const id = args[0] as string;
        if (ctx && (id === 'webgl' || id === 'experimental-webgl') && webglMode !== 'off') {
          patchCtx(ctx, webglMode, _origWGL1GetParam);
        }
        if (ctx && id === 'webgl2' && webgl2Mode !== 'off' && _origWGL2GetParam) {
          patchCtx(ctx, webgl2Mode, _origWGL2GetParam);
        }
        return ctx;
      });

      // Also patch OffscreenCanvas.prototype.getContext (used by workers and fingerprinters)
      if (typeof OffscreenCanvas !== 'undefined') {
        const origOCGetCtx = OffscreenCanvas.prototype.getContext;
        OffscreenCanvas.prototype.getContext = function(this: OffscreenCanvas, id: string, ...rest: any[]) {
          const ctx = (origOCGetCtx as any).call(this, id, ...rest);
          if (ctx && (id === 'webgl' || id === 'experimental-webgl') && webglMode !== 'off') {
            patchCtx(ctx, webglMode, _origWGL1GetParam);
          }
          if (ctx && id === 'webgl2' && webgl2Mode !== 'off' && _origWGL2GetParam) {
            patchCtx(ctx, webgl2Mode, _origWGL2GetParam);
          }
          return ctx;
        } as any;
      }
    } catch {}
  }

}
