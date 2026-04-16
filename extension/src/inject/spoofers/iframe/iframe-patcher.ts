/**
 * Iframe Patcher - Patches iframes IMMEDIATELY when added to DOM.
 *
 * CreepJS creates hidden iframes and accesses them via window.frames[index]
 * (self[numberOfIframes]), which bypasses our contentWindow getter.
 *
 * Fix: Use MutationObserver to detect new iframes and patch their
 * prototypes BEFORE any script accesses them via window.frames.
 */

import type { AssignedProfileData, SpooferSettings } from '@/types';
import { GL, TIMEZONE_IANA } from '@/lib/constants';
import { addCanvasNoise, addAudioNoise, overridePropWithGetter, overrideMethodDirect } from '@/lib/noise';

interface IframePatchConfig {
  settings: SpooferSettings;
  assignedProfile?: AssignedProfileData;
  selectedGPU: { vendor: string; renderer: string } | null;
}

export function initIframePatcher(config: IframePatchConfig): void {
  const { settings, assignedProfile, selectedGPU } = config;

  const screen = assignedProfile?.screen;
  const ua = assignedProfile?.userAgent;
  const hc = assignedProfile?.hardwareConcurrency;
  const dm = assignedProfile?.deviceMemory;
  const langs = assignedProfile?.languages;
  const tzOffset = assignedProfile?.timezoneOffset;
  const targetTimezone = tzOffset !== undefined ? (TIMEZONE_IANA[tzOffset] || null) : null;
  const mainFrameOffset = new Date().getTimezoneOffset();

  const patchedWindows = new WeakSet<Window>();

  function patchWindow(win: Window): void {
    if (patchedWindows.has(win)) return;
    patchedWindows.add(win);

    try {
      patchWebGL(win, selectedGPU, settings);
      patchScreen(win, screen, settings);
      patchNavigator(win, ua, hc, dm, langs, settings);
      patchTimezone(win, targetTimezone, mainFrameOffset, settings);
      patchCanvas(win, settings);
      patchAudio(win, settings);
      if (screen) patchCSSScreenQuery(win, screen);
    } catch {
      // Cross-origin or detached
    }
  }

  function patchIframeElement(iframe: HTMLIFrameElement): void {
    try {
      const win = iframe.contentWindow;
      if (win) patchWindow(win);
    } catch {
      // Cross-origin
    }
  }

  // Strategy 1: MutationObserver — patches iframes BEFORE window.frames[] access
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node instanceof HTMLIFrameElement) {
          patchIframeElement(node);
        }
        // Also check children (e.g., div containing an iframe)
        if (node instanceof HTMLElement) {
          const iframes = node.getElementsByTagName('iframe');
          for (let i = 0; i < iframes.length; i++) {
            patchIframeElement(iframes[i]);
          }
        }
      }
    }
  });

  // Start observing as soon as document.body exists
  if (document.body) {
    observer.observe(document.body, { childList: true, subtree: true });
  } else {
    // document.body not ready yet — observe documentElement and wait
    const docObserver = new MutationObserver(() => {
      if (document.body) {
        docObserver.disconnect();
        observer.observe(document.body, { childList: true, subtree: true });
        // Patch any iframes that already exist
        const existing = document.getElementsByTagName('iframe');
        for (let i = 0; i < existing.length; i++) {
          patchIframeElement(existing[i]);
        }
      }
    });
    docObserver.observe(document.documentElement, { childList: true, subtree: true });
  }

  // Strategy 2: contentWindow/contentDocument getters (backup)
  const origCWDesc = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow');
  const origCDDesc = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentDocument');

  if (origCWDesc?.get) {
    Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
      get() {
        const win = origCWDesc.get!.call(this);
        if (win) patchWindow(win);
        return win;
      },
      configurable: true,
    });
  }

  if (origCDDesc?.get) {
    Object.defineProperty(HTMLIFrameElement.prototype, 'contentDocument', {
      get() {
        const doc = origCDDesc.get!.call(this);
        if (doc?.defaultView) patchWindow(doc.defaultView);
        return doc;
      },
      configurable: true,
    });
  }

  // Strategy 3: Patch innerHTML/appendChild to catch iframes created via innerHTML
  // (CreepJS uses div.innerHTML = '<iframe></iframe>')
  const origInnerHTML = Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML');
  if (origInnerHTML?.set) {
    Object.defineProperty(Element.prototype, 'innerHTML', {
      get: origInnerHTML.get,
      set(value: string) {
        origInnerHTML.set!.call(this, value);
        // After innerHTML is set, patch any new iframes
        if (typeof value === 'string' && value.includes('iframe')) {
          const iframes = this.getElementsByTagName('iframe');
          for (let i = 0; i < iframes.length; i++) {
            patchIframeElement(iframes[i]);
          }
        }
      },
      configurable: true,
      enumerable: true,
    });
  }
}

function patchWebGL(
  win: Window,
  gpu: { vendor: string; renderer: string } | null,
  settings: SpooferSettings
): void {
  if (!gpu || settings.graphics?.webgl === 'off') return;

  for (const ctxName of ['WebGLRenderingContext', 'WebGL2RenderingContext']) {
    const Ctor = (win as any)[ctxName];
    if (!Ctor?.prototype?.getParameter) continue;

    const origGP = Ctor.prototype.getParameter;
    overrideMethodDirect(Ctor.prototype, 'getParameter', function(this: any, pname: number) {
      if (pname === GL.UNMASKED_VENDOR || pname === GL.VENDOR) return gpu.vendor;
      if (pname === GL.UNMASKED_RENDERER || pname === GL.RENDERER) return gpu.renderer;
      return origGP.call(this, pname);
    });
  }
}

function patchScreen(
  win: Window,
  screen: AssignedProfileData['screen'] | undefined,
  settings: SpooferSettings
): void {
  if (!screen || settings.hardware?.screen === 'off') return;

  const props: Record<string, number> = {
    width: screen.width, height: screen.height,
    availWidth: screen.availWidth, availHeight: screen.availHeight,
    colorDepth: screen.colorDepth, pixelDepth: screen.pixelDepth,
  };

  const ScreenProto = (win as any).Screen?.prototype;
  for (const [prop, val] of Object.entries(props)) {
    overridePropWithGetter(ScreenProto, win.screen, prop, () => val);
  }

  if (screen.devicePixelRatio) {
    overridePropWithGetter(null, win, 'devicePixelRatio', () => screen.devicePixelRatio);
  }
}

function patchNavigator(
  win: Window,
  ua: AssignedProfileData['userAgent'] | undefined,
  hc: number | undefined,
  dm: number | undefined,
  langs: string[] | undefined,
  settings: SpooferSettings
): void {
  if (!ua || settings.navigator?.userAgent === 'off') return;

  const nav = (win as any).Navigator?.prototype || win.navigator;
  const props: Record<string, any> = {
    userAgent: ua.userAgent, platform: ua.platform,
    vendor: ua.vendor || '', appVersion: ua.appVersion || '',
  };
  if (hc) props.hardwareConcurrency = hc;
  if (dm) props.deviceMemory = dm;
  if (langs) {
    const frozen = Object.freeze([...langs]);
    props.languages = frozen;
    props.language = langs[0];
  }

  for (const [prop, val] of Object.entries(props)) {
    overridePropWithGetter(nav, null, prop, () => val);
  }
}

function patchTimezone(
  win: Window,
  targetTimezone: string | null,
  mainFrameOffset: number,
  settings: SpooferSettings
): void {
  if (!targetTimezone || settings.timezone?.date === 'off') return;

  const iframeDate = (win as any).Date;
  if (!iframeDate) return;

  // Patch getTimezoneOffset
  overrideMethodDirect(iframeDate.prototype, 'getTimezoneOffset', () => mainFrameOffset);

  // Patch Intl.DateTimeFormat
  const origDTF = (win as any).Intl?.DateTimeFormat;
  if (origDTF) {
    try {
      const tz = targetTimezone;
      (win as any).Intl.DateTimeFormat = function(locales?: string | string[], options?: Intl.DateTimeFormatOptions) {
        return new origDTF(locales, { ...options, timeZone: options?.timeZone || tz });
      };
      (win as any).Intl.DateTimeFormat.supportedLocalesOf = origDTF.supportedLocalesOf;
      (win as any).Intl.DateTimeFormat.prototype = origDTF.prototype;

      const origResolved = origDTF.prototype.resolvedOptions;
      origDTF.prototype.resolvedOptions = function() {
        const opts = origResolved.call(this);
        return { ...opts, timeZone: opts.timeZone || tz };
      };
    } catch {}
  }
}

function patchCanvas(win: Window, settings: SpooferSettings): void {
  if (settings.graphics?.canvas === 'off') return;
  const isBlock = settings.graphics.canvas === 'block';

  try {
    const proto = (win as any).HTMLCanvasElement?.prototype;
    if (!proto) return;

    const origToDataURL = proto.toDataURL;
    proto.toDataURL = function(this: HTMLCanvasElement, ...args: any[]): string {
      if (isBlock) return 'data:image/png;base64,';
      try { const ctx = this.getContext('2d'); if (ctx) addCanvasNoise(ctx.getImageData(0, 0, 1, 1).data); } catch {}
      return origToDataURL.apply(this, args);
    };

    const origToBlob = proto.toBlob;
    proto.toBlob = function(this: HTMLCanvasElement, cb: BlobCallback, ...args: any[]): void {
      if (isBlock) { cb(new Blob([], { type: 'image/png' })); return; }
      try { const ctx = this.getContext('2d'); if (ctx) addCanvasNoise(ctx.getImageData(0, 0, 1, 1).data); } catch {}
      origToBlob.call(this, cb, ...args);
    };

    const ctx2D = (win as any).CanvasRenderingContext2D?.prototype;
    if (ctx2D) {
      const origGID = ctx2D.getImageData;
      ctx2D.getImageData = function(this: CanvasRenderingContext2D, ...args: any[]): ImageData {
        const data = origGID.apply(this, args);
        if (!isBlock) addCanvasNoise(data.data);
        return data;
      };
    }
  } catch {}
}

function patchAudio(win: Window, settings: SpooferSettings): void {
  if (settings.audio?.audioContext === 'off') return;

  try {
    const analyser = (win as any).AnalyserNode?.prototype;
    if (analyser?.getFloatFrequencyData) {
      const orig = analyser.getFloatFrequencyData;
      analyser.getFloatFrequencyData = function(this: AnalyserNode, arr: Float32Array): void {
        orig.call(this, arr);
        addAudioNoise(arr, 0.0001);
      };
    }

    const audioBuf = (win as any).AudioBuffer?.prototype;
    if (audioBuf?.getChannelData) {
      const orig = audioBuf.getChannelData;
      audioBuf.getChannelData = function(this: AudioBuffer, ch: number): Float32Array {
        const data = orig.call(this, ch);
        addAudioNoise(data);
        return data;
      };
    }
  } catch {}
}

function patchCSSScreenQuery(
  win: Window,
  screen: AssignedProfileData['screen']
): void {
  if (!screen) return;

  try {
    const iframeCSSProto = (win as any).CSSStyleDeclaration?.prototype;
    if (!iframeCSSProto) return;

    const origGetPV = iframeCSSProto.getPropertyValue;
    iframeCSSProto.getPropertyValue = function(prop: string): string {
      const val = origGetPV.call(this, prop);
      if (prop === '--device-width' && val.trim()) return String(screen.width);
      if (prop === '--device-height' && val.trim()) return String(screen.height);
      if (prop === '--device-screen' && val.trim()) return `${screen.width} x ${screen.height}`;
      if (prop === '--device-aspect-ratio' && val.trim()) {
        const gcd = (a: number, b: number): number => b === 0 ? a : gcd(b, a % b);
        const d = gcd(screen.width, screen.height);
        return `${screen.width / d}/${screen.height / d}`;
      }
      return val;
    };
  } catch {}
}
