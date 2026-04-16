/**
 * Worker Fingerprint Spoofer
 *
 * Workers run in a separate JS context where main-thread spoofers
 * don't apply. CreepJS reads navigator/hardwareConcurrency inside
 * a Worker and compares to main thread values.
 *
 * Fix: Intercept Worker constructor, prepend spoofer overrides
 * into the Worker's script so values match the main thread.
 */

import type { ProtectionMode, AssignedProfileData } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { TIMEZONE_IANA } from '@/lib/constants';
import { logAccess } from '../../monitor/fingerprint-monitor';
import { getSelectedGPU } from '../graphics/webgl';
import { getTimezoneOffsetDiffMs } from '../timezone/intl';

export function buildWorkerPreamble(assignedProfile?: AssignedProfileData): string {
  if (!assignedProfile?.userAgent) return '';

  const ua = assignedProfile.userAgent;
  const hc = assignedProfile.hardwareConcurrency || 8;
  const dm = assignedProfile.deviceMemory || 8;
  const langs = assignedProfile.languages || ['en-US'];
  const tzOffset = assignedProfile.timezoneOffset;
  const tzName = tzOffset !== undefined ? (TIMEZONE_IANA[tzOffset] || 'UTC') : null;
  // appVersion must match main thread: profile value or derived from userAgent
  const appVersion = ua.appVersion || (ua.userAgent ? ua.userAgent.replace(/^Mozilla\//, '') : '');

  let code = `(function(){try{
var n=self.navigator.__proto__||Object.getPrototypeOf(self.navigator);
Object.defineProperty(n,'userAgent',{get:function(){return ${JSON.stringify(ua.userAgent)}}});
Object.defineProperty(n,'platform',{get:function(){return ${JSON.stringify(ua.platform)}}});
Object.defineProperty(n,'vendor',{get:function(){return ${JSON.stringify(ua.vendor || '')}}});
Object.defineProperty(n,'appVersion',{get:function(){return ${JSON.stringify(appVersion)}}});
Object.defineProperty(n,'hardwareConcurrency',{get:function(){return ${hc}}});
Object.defineProperty(n,'languages',{get:function(){return Object.freeze(${JSON.stringify(langs)})}});
Object.defineProperty(n,'language',{get:function(){return ${JSON.stringify(langs[0])}}});
try{Object.defineProperty(self.navigator,'deviceMemory',{get:function(){return ${dm}},configurable:true})}catch(e){}`;

  // Spoof oscpu for Firefox profiles
  if (ua.oscpu) {
    code += `\ntry{Object.defineProperty(n,'oscpu',{get:function(){return ${JSON.stringify(ua.oscpu)}}})}catch(e){}`;
  }

  // Spoof userAgentData (Client Hints) in Worker context
  if (ua.brands) {
    const platformName = ua.platformName || 'Windows';
    const platformVersion = ua.platformVersion || '10.0.0';
    const mobile = ua.mobile ?? false;
    code += `
try{Object.defineProperty(n,'userAgentData',{get:function(){
var b=${JSON.stringify(ua.brands)};
var m=${mobile};
var p=${JSON.stringify(platformName)};
return{brands:b,mobile:m,platform:p,
getHighEntropyValues:function(){return Promise.resolve({brands:b,mobile:m,platform:p,
architecture:'x86',bitness:'64',model:'',
platformVersion:${JSON.stringify(platformVersion)},
uaFullVersion:b[0].version+'.0.0.0',fullVersionList:b})},
toJSON:function(){return{brands:b,mobile:m,platform:p}}};
}})}catch(e){}`;
  }

  // Spoof WebGL in Worker context (CreepJS uses OffscreenCanvas in Workers)
  // Use the SAME GPU selected by the main thread WebGL spoofer (null if WebGL off)
  const gpu = getSelectedGPU();

  if (gpu) {
    const gpuVendor = gpu.vendor;
    const gpuRenderer = gpu.renderer;

    code += `
try{if(typeof OffscreenCanvas!=='undefined'){
var _origGetCtx=OffscreenCanvas.prototype.getContext;
OffscreenCanvas.prototype.getContext=function(t,a){
var ctx=_origGetCtx.call(this,t,a);
if(ctx&&(t==='webgl'||t==='webgl2')){
var _origGetParam=ctx.getParameter.bind(ctx);
ctx.getParameter=function(p){
if(p===0x9245)return ${JSON.stringify(gpuVendor)};
if(p===0x9246)return ${JSON.stringify(gpuRenderer)};
if(p===0x1F00)return ${JSON.stringify(gpuVendor)};
if(p===0x1F01)return ${JSON.stringify(gpuRenderer)};
return _origGetParam(p);
};
}
if(ctx&&t==='2d'){
var _origGID=ctx.getImageData.bind(ctx);
ctx.getImageData=function(){var d=_origGID.apply(this,arguments);if(d.data.length>0)d.data[0]=(d.data[0]+1)%256;return d};
}
return ctx;
};
}}catch(e){}`;
  }

  // Spoof timezone in Worker context — use pre-computed values from main frame
  if (tzName) {
    const spoofedOffset = new Date().getTimezoneOffset(); // Already spoofed
    const offsetDiffMs = getTimezoneOffsetDiffMs(); // From main frame's timezone spoofer

    code += `
var _tz=${JSON.stringify(tzName)};
var _origDTF=Intl.DateTimeFormat;
Intl.DateTimeFormat=function(l,o){return new _origDTF(l,Object.assign({},o,{timeZone:o&&o.timeZone||_tz}))};
Intl.DateTimeFormat.supportedLocalesOf=_origDTF.supportedLocalesOf;
try{Intl.DateTimeFormat.prototype=_origDTF.prototype}catch(e){}
var _origToStr=Date.prototype.toString;
var _origToTStr=Date.prototype.toTimeString;
var _spoofOff=${spoofedOffset};
Date.prototype.getTimezoneOffset=function(){return _spoofOff};
var _gmtSign=_spoofOff<=0?'+':'-';
var _absOff=Math.abs(_spoofOff);
var _gmtH=String(Math.floor(_absOff/60)).padStart(2,'0');
var _gmtM=String(_absOff%60).padStart(2,'0');
var _gmtStr='GMT'+_gmtSign+_gmtH+_gmtM;
var _tzAbbr=${JSON.stringify(tzName)};
Date.prototype.toString=function(){var s=_origToStr.call(this);return s.replace(/GMT[+-]\\d{4}/,_gmtStr).replace(/\\(.*\\)/,'('+_tzAbbr+')')};
Date.prototype.toTimeString=function(){var s=_origToTStr.call(this);return s.replace(/GMT[+-]\\d{4}/,_gmtStr).replace(/\\(.*\\)/,'('+_tzAbbr+')')};`;
  }

  code += `\n}catch(e){}})();\n`;
  return code;
}

export function initWorkerSpoofer(
  mode: ProtectionMode,
  prng: PRNG,
  assignedProfile?: AssignedProfileData,
  serviceWorkerMode?: ProtectionMode
): void {
  if (mode === 'off') return;

  const workerPreamble = buildWorkerPreamble(assignedProfile);

  // Hide SharedArrayBuffer in block mode
  if (mode === 'block' && typeof SharedArrayBuffer !== 'undefined') {
    try {
      Object.defineProperty(window, 'SharedArrayBuffer', { value: undefined, configurable: true });
    } catch {}
  }

  // Intercept Worker constructor to inject overrides into Worker scripts
  if (workerPreamble) {
    const OriginalWorker = window.Worker;
    const OriginalBlob = window.Blob;

    const WorkerProxy = function(this: any, scriptURL: string | URL, options?: WorkerOptions): Worker {
      logAccess('Worker.constructor', { spoofed: true, value: 'injected' });

      try {
        // Resolve relative URLs to absolute (importScripts inside blob Workers can't resolve relative paths)
        const urlStr = new URL(String(scriptURL), location.href).href;

        // For ALL non-module workers: use importScripts wrapper
        if (!options?.type || options.type !== 'module') {
          const wrapper = workerPreamble + 'importScripts(' + JSON.stringify(urlStr) + ');\n';
          const blob = new OriginalBlob([wrapper], { type: 'application/javascript' });
          const blobUrl = URL.createObjectURL(blob);
          const w = new OriginalWorker(blobUrl, options);
          setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);
          return w;
        }
      } catch {
        // Injection failed — fall through to original
      }

      // Fallback: create original Worker (no injection)
      return new OriginalWorker(scriptURL, options);
    } as unknown as typeof Worker;

    // Preserve constructor identity for detection checks
    Object.defineProperty(WorkerProxy, 'name', { value: 'Worker' });
    WorkerProxy.prototype = OriginalWorker.prototype;
    Object.setPrototypeOf(WorkerProxy, OriginalWorker);

    try {
      Object.defineProperty(window, 'Worker', { value: WorkerProxy, writable: true, configurable: true });
    } catch {}
  }

  // Also intercept SharedWorker (CreepJS tries SharedWorker if ServiceWorker fails)
  if (workerPreamble && typeof SharedWorker !== 'undefined') {
    const OriginalSharedWorker = window.SharedWorker;
    const OriginalBlob2 = window.Blob;

    const SharedWorkerProxy = function(this: any, scriptURL: string | URL, nameOrOptions?: string | WorkerOptions): SharedWorker {
      logAccess('SharedWorker.constructor', { spoofed: true, value: 'injected' });

      const urlStr = new URL(String(scriptURL), location.href).href;
      try {
        const wrapper = workerPreamble + 'importScripts(' + JSON.stringify(urlStr) + ');\n';
        const blob = new OriginalBlob2([wrapper], { type: 'application/javascript' });
        const blobUrl = URL.createObjectURL(blob);
        const w = new OriginalSharedWorker(blobUrl, nameOrOptions);
        setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);
        return w;
      } catch {
        return new OriginalSharedWorker(scriptURL, nameOrOptions);
      }
    } as unknown as typeof SharedWorker;

    Object.defineProperty(SharedWorkerProxy, 'name', { value: 'SharedWorker' });
    SharedWorkerProxy.prototype = OriginalSharedWorker.prototype;
    Object.setPrototypeOf(SharedWorkerProxy, OriginalSharedWorker);

    try {
      Object.defineProperty(window, 'SharedWorker', { value: SharedWorkerProxy, writable: true, configurable: true });
    } catch {}
  }

  // Handle ServiceWorker:
  // - Off: no interception
  // - Spoof/Block: reject SW registration → forces fallback to SharedWorker/DedicatedWorker
  //   which ARE fully spoofed with preamble injection.
  //   We can't inject into SW scripts in Firefox (filterResponseData doesn't intercept SW,
  //   blob URLs fail for SW registration). Rejecting SW is the only reliable approach.
  if ('serviceWorker' in navigator && serviceWorkerMode !== 'off') {
    try {
      navigator.serviceWorker.register = async function(): Promise<ServiceWorkerRegistration> {
        logAccess('ServiceWorker.register', { spoofed: true, value: serviceWorkerMode === 'block' ? 'blocked' : 'rejected-for-spoofed-fallback' });
        throw new DOMException('The operation is insecure.', 'SecurityError');
      };
    } catch {}
  }

  // Handle AudioWorklet
  if (typeof AudioContext !== 'undefined' && 'audioWorklet' in AudioContext.prototype) {
    try {
      const origAddModule = AudioWorklet.prototype.addModule;
      AudioWorklet.prototype.addModule = async function(url: string | URL, opts?: WorkletOptions) {
        logAccess('AudioWorklet.addModule', { spoofed: true, value: 'wrapped' });
        return origAddModule.call(this, url, opts);
      };
    } catch {}
  }
}
