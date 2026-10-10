#!/usr/bin/env python3
"""Local page/frame/worker audit of names, error stacks and API descriptors.

Native baseline = same binary, master masking disabled. Collection runs in
page scripts, not a WebDriver sandbox. Reports only local test observations.
"""
from __future__ import annotations

import base64
import json
import math
import struct
import os
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

from probe_focus_masking import chrome, set_pref

COLLECT = r"""
const auditToken=crypto.randomUUID();let auditCount=0;const capturedSin=Math.sin;
function collect() {
  const r={functions:{},errors:{},names:{},values:{}};
  const flags=d=>d&&({configurable:d.configurable,enumerable:d.enumerable,
    writable:d.writable,get:d.get?.name,set:d.set?.name});
  const inspect=f=>({name:f.name,length:f.length,source:Function.prototype.toString.call(f),
    properties:Object.getOwnPropertyNames(f).sort(),nameFlags:flags(Object.getOwnPropertyDescriptor(f,'name')),
    lengthFlags:flags(Object.getOwnPropertyDescriptor(f,'length')),
    prototype:typeof f.prototype,constructor:(()=>{try{Reflect.construct(f,[]);return true}catch{return false}})()});
  const capture=(key,fn)=>{try{fn();r.errors[key]=null}catch(e){r.errors[key]={name:e.name,message:e.message,stack:e.stack,fileName:e.fileName}}};
  for(const k of ['sin','cos','tan','asin','acos','atan','atan2','sinh','cosh','tanh',
                 'asinh','acosh','atanh','exp','expm1','log','log2','log10','log1p',
                 'sqrt','cbrt','hypot','pow']) {
    r.functions['Math.'+k]={...inspect(Math[k]),flags:flags(Object.getOwnPropertyDescriptor(Math,k))};
    capture('Math.'+k,()=>Math[k](Symbol('input')));
    capture('coercion.'+k,()=>Math[k]({valueOf(){throw new Error('coercion failure')}}));
  }
  r.functions.toString={...inspect(Function.prototype.toString),flags:flags(Object.getOwnPropertyDescriptor(Function.prototype,'toString'))};
  capture('toString.invalidThis',()=>Function.prototype.toString.call({}));
  for(const [key,obj] of Object.entries({global:globalThis,navigator,Math,FunctionPrototype:Function.prototype}))
    r.names[key]=Object.getOwnPropertyNames(obj).filter(k=>/cloakfox|camoufox|__cfx|^set(?:CanvasSeed|CloakConfig|WebGLVendor)/i.test(k));
  r.identity={userAgent:navigator.userAgent,appVersion:navigator.appVersion,platform:navigator.platform};
  r.values={samples:Object.values(r.functions).slice(0,23).map(f=>Math[f.name](.5,1.5)),sin:Math.sin(.5),pure:Math.sin(.5)===Math.sin(.5),sqrt:Math.sqrt(4),
    negativeZero:Object.is(Math.sin(-0),-0),nan:Number.isNaN(Math.sin(NaN)),infinity:Math.log(0)===-Infinity};
  // WebDriver sorts object keys; preserve sample order explicitly as an array.
  r.values.sampleNames=Object.keys(r.functions).slice(0,23);
  r.values.sampleBits=r.values.samples.map(v=>{
    const buf=new ArrayBuffer(8),view=new DataView(buf);
    view.setFloat64(0,v);return view.getBigUint64(0).toString(16).padStart(16,'0');
  });
  if(typeof document!=='undefined') {
    r.names.attributes=Array.from(document.documentElement.attributes,a=>a.name).filter(k=>/cloakfox|camoufox|cfx/i.test(k));
    r.names.storage=Object.keys(sessionStorage).filter(k=>/cloakfox|camoufox|cfx/i.test(k));
    r.names.navigatorKeys=Object.keys(navigator);
    r.names.mathKeys=Object.keys(Math);
    for(const [key,f] of Object.entries({getGamepads:navigator.getGamepads,
      requestMIDIAccess:navigator.requestMIDIAccess,javaEnabled:navigator.javaEnabled,
      setTimeout,setInterval,requestAnimationFrame,addEventListener:EventTarget.prototype.addEventListener,
      removeEventListener:EventTarget.prototype.removeEventListener})) {
      if(typeof f==='function')r.functions[key]=inspect(f);
    }
    capture('setTimeout.symbolDelay',()=>setTimeout(()=>{},Symbol('delay')));
    capture('setInterval.symbolDelay',()=>setInterval(()=>{},Symbol('delay')));
    capture('performance.now.invalidThis',()=>Performance.prototype.now.call({}));
    r.accessors={};
    for(const [name,proto,key] of [ ['gpu',Navigator.prototype,'gpu'], ['webdriver',Navigator.prototype,'webdriver'],
      ['cookieEnabled',Navigator.prototype,'cookieEnabled'], ['onLine',Navigator.prototype,'onLine'],
      ['pdfViewerEnabled',Navigator.prototype,'pdfViewerEnabled'], ['timeStamp',Event.prototype,'timeStamp'],
      ['matches',MediaQueryList.prototype,'matches'],
      ['now',Performance.prototype,'now'], ['hasFocus',Document.prototype,'hasFocus'],
      ['hidden',Document.prototype,'hidden'], ['visibilityState',Document.prototype,'visibilityState'],
      ['fullscreenElement',Document.prototype,'fullscreenElement'], ['historyLength',History.prototype,'length'] ]) {
      const d=Object.getOwnPropertyDescriptor(proto,key);
      r.accessors[name]={flags:flags(d),function:d?.get?inspect(d.get):typeof d?.value==='function'?inspect(d.value):null};
    }
  }
  r.lifetime={token:auditToken,count:++auditCount,sameFunction:Math.sin===capturedSin};
  r.values.capturedSin=capturedSin(.5);
  return r;
}
"""

PAGE = """<!doctype html><meta charset=utf-8><title>Identifier audit</title><script>""" + COLLECT + r"""
const label=new URLSearchParams(location.search).get('label')||'top';
const out={page:collect()};
if(label!=='top'){
  parent.postMessage({label,data:out.page},'*');
  addEventListener('message',e=>{
    if(e.data?.auditRefresh)parent.postMessage({label,data:collect(),auditRefresh:e.data.auditRefresh},'*');
  });
}
else {
  const frameReplies=new Map();let refreshSequence=0;
  window.addEventListener('message',e=>{
    if(e.data?.label){
      out[e.data.label]=e.data.data;
      frameReplies.get(e.data.auditRefresh+':'+e.data.label)?.(e.data.data);
    }
  });
  for(const label of ['same','cross']) {
    const f=document.createElement('iframe');const u=new URL(location.href);
    u.searchParams.set('label',label);if(label==='cross')u.hostname='localhost';f.src=u;document.documentElement.append(f);
  }
  const w=new Worker('/dedicated.js?'+location.search);w.onmessage=e=>{out.dedicated=e.data};
  const sw=new SharedWorker('/shared.js?'+location.search);sw.port.onmessage=e=>{out.shared=e.data};sw.port.start();
  let service;
  navigator.serviceWorker.register('/service.js?run='+new URLSearchParams(location.search).get('run')).then(async reg=>{
    let worker=reg.installing||reg.waiting||reg.active;
    if(worker.state!=='activated')await new Promise(resolve=>worker.addEventListener('statechange',()=>{if(worker.state==='activated')resolve()}));
    service=worker;
    const channel=new MessageChannel();channel.port1.onmessage=e=>{out.service=e.data;channel.port1.close()};
    worker.postMessage('collect',[channel.port2]);
  }).catch(e=>out.serviceError=String(e));
  window.refreshAudit=async()=>{
    const request=port=>new Promise(resolve=>{port.onmessage=e=>resolve(e.data);port.postMessage('collect')});
    const seq=++refreshSequence;
    const frames=Array.from(document.querySelectorAll('iframe'),frame=>{
      const label=new URL(frame.src).searchParams.get('label');
      return new Promise(resolve=>{
        const key=seq+':'+label;
        frameReplies.set(key,data=>{frameReplies.delete(key);resolve([label,data])});
        frame.contentWindow.postMessage({auditRefresh:seq},'*');
      });
    });
    const channel=new MessageChannel();
    const fromService=new Promise(resolve=>{channel.port1.onmessage=e=>{resolve(e.data);channel.port1.close()}});
    service.postMessage('collect',[channel.port2]);
    return {page:collect(),dedicated:await request(w),shared:await request(sw.port),service:await fromService,
      ...Object.fromEntries(await Promise.all(frames))};
  };
  window.addEventListener('pagehide',()=>{w.terminate();sw.port.close()});
}
window.audit=out;
</script>"""


class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        route = urlparse(self.path).path
        scripts = {
            '/dedicated.js': 'postMessage(collect());onmessage=()=>postMessage(collect());',
            '/shared.js': 'onconnect=e=>{const p=e.ports[0];p.postMessage(collect());p.onmessage=()=>p.postMessage(collect());};',
            '/service.js': "oninstall=()=>skipWaiting();onmessage=e=>e.ports[0].postMessage(collect());",
        }
        body = ((COLLECT + scripts[route]) if route in scripts else PAGE).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/javascript' if route in scripts else 'text/html')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def expected_samples(observation, seed):
    # Native log/pow are data-integrity requirements, independent of seed.
    native_methods = {"Math.log", "Math.log2", "Math.log10", "Math.log1p", "Math.pow"}
    return [bits if name in native_methods else expected_bits(bits, seed)
            for name, bits in zip(observation["values"]["sampleNames"],
                                  observation["values"]["sampleBits"])]


def expected_bits(bits, seed):
    raw = int(bits, 16)
    value = struct.unpack('>d', raw.to_bytes(8, 'big'))[0]
    if seed == 0 or not math.isfinite(value) or value.is_integer():
        return bits
    h = (raw & 0xffffffff) ^ (raw >> 32) ^ seed
    h = ((h ^ (h >> 16)) * 2246822507) & 0xffffffff
    h = ((h ^ (h >> 13)) * 3266489909) & 0xffffffff
    h ^= h >> 16
    value += (h / 4294967296 - .5) * 1e-12
    return struct.pack('>d', value).hex()


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    checks, observations = [], {}

    def check(ok, name, data=None):
        checks.append({'name': name, 'pass': bool(ok), 'data': data})
        print(('PASS' if ok else 'FAIL') + ' — ' + name, flush=True)
        if not ok and name.startswith('all '):
            print('Missing realm details: ' + str(data), flush=True)

    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-identifiers-') as temp:
            profile = Path(temp, 'profile'); profile.mkdir()
            seed = base64.b64encode(bytes(range(32))).decode()
            Path(profile, 'user.js').write_text(
                'user_pref("cloakfox.enabled", false);\n'
                f'user_pref("cloakfox.container.0.math_seed", "{seed}");\n'
                f'user_pref("cloakfox.container.2.math_seed", "{base64.b64encode(bytes(range(32,64))).decode()}");\n'
                f'user_pref("cloakfox.s.cloak_cfg_2", {json.dumps(json.dumps({"math:trig_seed": 0xabcdef01}))});\n')
            opts = Options(); opts.binary_location = os.environ['CLOAKFOX_BIN']
            opts.add_argument('-headless'); opts.add_argument('-profile'); opts.add_argument(str(profile))
            driver = webdriver.Firefox(options=opts, service=Service(
                service_args=['--allow-system-access'], log_output=temp+'/gecko.log'))
            try:
                driver.set_script_timeout(20)
                url = f'http://127.0.0.1:{server.server_port}/'
                container_handles = {0:driver.current_window_handle}
                for enabled, ucid in ((False, 0), (True, 0), (True, 2)):
                    set_pref(driver, 'cloakfox.enabled', enabled)
                    if ucid:
                        before = set(driver.window_handles)
                        chrome(driver, """
                          const tab=gBrowser.addTab(arguments[0],{userContextId:arguments[1],
                            triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
                          gBrowser.selectedTab=tab;
                        """, url+'?warm=1', ucid)
                        driver.switch_to.window(next(h for h in driver.window_handles if h not in before))
                        container_handles[ucid]=driver.current_window_handle
                    # Warm persona snapshots before the second page creates workers.
                    driver.get(url+'?warm=1'); time.sleep(1)
                    driver.get(url+'?run='+str(enabled))
                    deadline = time.monotonic()+15
                    while time.monotonic()<deadline:
                        r = driver.execute_script('return window.wrappedJSObject?.audit || window.audit')
                        if r and all(k in r for k in ('page','same','cross','dedicated','shared','service')):
                            break
                        time.sleep(.1)
                    observations[f'{enabled}:{ucid}'] = r
                    if not enabled:
                        set_pref(driver, 'cloakfox.enabled', True)
                        configs0 = chrome(driver, "return JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_0'))")
                        expected0 = expected_samples(r['page'], configs0['math:trig_seed'])
                        deadline = time.monotonic()+5
                        while True:
                            fresh = driver.execute_async_script("""
                              const done=arguments[0];(window.wrappedJSObject || window).refreshAudit().then(done);
                            """)
                            if all(data['values']['sampleBits']==expected0 for data in fresh.values()) or time.monotonic()>=deadline:
                                break
                            time.sleep(.1)
                        for realm,data in fresh.items():
                            check(data['values']['sampleBits']==expected0,
                                  f'enabling updates initially-disabled live realm ({realm})',data['values'])
                            check(data['lifetime']['token']==r[realm]['lifetime']['token'] and data['lifetime']['sameFunction'] and
                                  data['lifetime']['count']>r[realm]['lifetime']['count'],
                                  f'enabling preserves realm state and function reference ({realm})',data['lifetime'])
                        set_pref(driver, 'cloakfox.enabled', False)
                    check(r and all(k in r for k in ('page','same','cross','dedicated','shared','service')),
                          f'all page and worker realms report (enabled={enabled}, container={ucid})', r and list(r))
                # Query the SAME live workers across the master switch, rather
                # than hiding a stale wrapper behind newly created realms.
                for enabled in (False, True):
                    set_pref(driver, 'cloakfox.enabled', enabled)
                    refreshed = driver.execute_async_script("""
                      const done=arguments[0];
                      (window.wrappedJSObject || window).refreshAudit().then(done);
                    """)
                    reference = observations['True:2' if enabled else 'False:0']
                    for realm, data in refreshed.items():
                        check(data['values']['sampleBits'] == reference[realm]['values']['sampleBits'],
                              f'live master switch honored ({realm}, enabled={enabled})', data['values'])
                exported = chrome(driver, """
                  const scope=Cu.Sandbox('https://export-audit.example',{wantXrays:true});
                  const ctor=Cu.exportFunction(function Example(){this.value=42},scope);
                  const method=Cu.exportFunction(function(){return 42},scope,
                    {functionName:'exampleMethod',allowConstruct:false});
                  let constructRejected=false;
                  try{Reflect.construct(method,[])}catch(e){constructRejected=e.name==='TypeError'}
                  return {defaultConstructor:Reflect.construct(ctor,[]).value===42,
                    constructRejected,named:method.name==='exampleMethod',
                    noStrayGlobal:!Object.hasOwn(Cu.waiveXrays(scope),'exampleMethod')};
                """)
                check(all(exported.values()), 'privileged exports retain constructor defaults and support named methods', exported)
                configs = chrome(driver, "return [0,2].map(id=>JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+id)))")
                check(configs[1]['math:trig_seed'] == 0xabcdef01, 'explicit Math seed override preserved', configs)
                baseline = observations['False:0']
                for realm in ('page','same','cross','dedicated','shared','service'):
                    for ucid in (0, 2):
                        masked = observations[f'True:{ucid}']
                        if realm not in baseline or realm not in masked:
                            continue
                        b, m = baseline[realm], masked[realm]
                        check(m['values']['sin'] != b['values']['sin'], f'Math masking exercised ({realm}, container={ucid})', m['values'])
                        check(m['values']['sampleBits'] == expected_samples(b, configs[0 if ucid == 0 else 1]['math:trig_seed']),
                              f'Math uses configured seed ({realm}, container={ucid})', m['values']['sampleBits'])
                        check(m['values']['sampleBits'] == masked['page']['values']['sampleBits'],
                              f'Math matches its page ({realm}, container={ucid})', m['values']['samples'])
                        check(m['values']['sampleBits'] != observations[f'True:{2 if ucid == 0 else 0}'][realm]['values']['sampleBits'],
                              f'Math containers remain distinct ({realm}, container={ucid})', m['values']['samples'])
                        check(all(m['values'][k] for k in ('pure','negativeZero','nan','infinity')) and m['values']['sqrt']==2,
                              f'Math semantics preserved ({realm}, container={ucid})', m['values'])
                        check(m['functions'] == b['functions'], f'native function identities and descriptors ({realm}, container={ucid})', m['functions'])
                        check(not any(m['names'].values()), f'no named globals, attributes or storage markers ({realm}, container={ucid})', m['names'])
                        check(not any('cloakfox' in str(v).lower() or 'camoufox' in str(v).lower() for v in m['identity'].values()),
                              f'no product identifier in navigator ({realm}, container={ucid})', m['identity'])
                        leaked = {k:v for k,v in m['errors'].items() if v and any(
                            token in json.dumps(v).lower() for token in ('cloakfox','camoufox','resource://','chrome://'))}
                        check(not leaked, f'errors contain no internal identifiers ({realm}, container={ucid})', leaked)
                        check(all(v and v['name']==b['errors'][k]['name'] for k,v in m['errors'].items()),
                              f'exception types preserved ({realm}, container={ucid})', m['errors'])
                        if 'accessors' in m:
                            check(m['accessors']==b['accessors'], f'native accessor descriptors ({realm}, container={ucid})', m['accessors'])
                # Update config without navigation, worker termination or registration.
                for seed in (0, 0x12345678, 0xabcdef01):
                    config = {**configs[1], 'math:trig_seed':seed}
                    chrome(driver, 'Services.prefs.setStringPref(arguments[0],arguments[1]);',
                           'cloakfox.s.cloak_cfg_2',json.dumps(config))
                    expected2 = expected_samples(baseline['page'], seed)
                    deadline=time.monotonic()+5
                    while True:
                        result=driver.execute_async_script("""
                          const done=arguments[0];(window.wrappedJSObject || window).refreshAudit().then(done);
                        """)
                        if all(data['values']['sampleBits']==expected2 for data in result.values()) or time.monotonic()>=deadline:
                            break
                        time.sleep(.1)
                    for realm,data in result.items():
                        check(data['values']['sampleBits']==expected2,
                              f'live realm honors new seed ({realm},seed={seed})',data['values'])
                        previous=observations['True:2'][realm]
                        check(data['lifetime']['token']==previous['lifetime']['token'] and data['lifetime']['sameFunction'] and
                              data['lifetime']['count']>previous['lifetime']['count'],
                              f'seed update preserves realm state and function reference ({realm},seed={seed})',data['lifetime'])
                        check(data['values']['capturedSin']==data['values']['sin'],
                              f'captured Math reference uses current seed ({realm},seed={seed})',data['values'])
                    driver.switch_to.window(container_handles[0])
                    unaffected=driver.execute_async_script("""
                      const done=arguments[0];(window.wrappedJSObject || window).refreshAudit().then(done);
                    """)
                    for realm,data in unaffected.items():
                        check(data['values']['sampleBits']==observations['True:0'][realm]['values']['sampleBits'],
                              f'other container unaffected by live seed update ({realm},seed={seed})',data['values'])
                    driver.switch_to.window(container_handles[2])
                # Removal and invalid data must clear an earlier cached seed.
                for invalid in (None, '{broken', json.dumps({'math:trig_seed': -1})):
                    if invalid is None:
                        chrome(driver, "Services.prefs.clearUserPref('cloakfox.s.cloak_cfg_2');")
                    else:
                        chrome(driver, "Services.prefs.setStringPref('cloakfox.s.cloak_cfg_2',arguments[0]);", invalid)
                    deadline=time.monotonic()+5
                    while True:
                        result=driver.execute_async_script("""
                          const done=arguments[0];(window.wrappedJSObject || window).refreshAudit().then(done);
                        """)
                        if all(data['values']['sampleBits']==baseline[realm]['values']['sampleBits'] for realm,data in result.items()) or time.monotonic()>=deadline:
                            break
                        time.sleep(.1)
                    for realm,data in result.items():
                        check(data['values']['sampleBits']==baseline[realm]['values']['sampleBits'],
                              f'removal/invalid config clears live seed ({realm},config={invalid})',data['values'])
                # Change the authoritative overlay, then create new realms in
                # the existing processes. This tests cache refresh and seed 0.
                for seed in (0, 0x12345678):
                    config = {**configs[1], 'math:trig_seed': seed}
                    chrome(driver, 'Services.prefs.setStringPref(arguments[0],arguments[1]);',
                           'cloakfox.s.cloak_cfg_2', json.dumps(config))
                    driver.get(url+'?run=refresh-'+str(seed))
                    deadline = time.monotonic()+15
                    while time.monotonic()<deadline:
                        result = driver.execute_script('return window.audit')
                        if result and all(k in result for k in ('page','same','cross','dedicated','shared','service')):
                            break
                        time.sleep(.1)
                    complete = result and all(k in result for k in ('page','same','cross','dedicated','shared','service'))
                    check(complete, f'all realms report after config refresh (seed={seed})', result and list(result))
                    if complete:
                        for realm, data in result.items():
                            check(data['values']['sampleBits'] == expected_samples(baseline[realm], seed),
                                  f'new realm honors refreshed config ({realm}, seed={seed})', data['values'])
                driver.execute_async_script("""
                  const done=arguments[0];
                  navigator.serviceWorker.getRegistrations().then(async regs=>{
                    await Promise.all(regs.map(reg=>reg.unregister()));done(true);
                  });
                """)
            finally:
                driver.quit()
    finally:
        server.shutdown(); server.server_close()
    report = os.environ.get('IDENTIFIER_PROBE_REPORT','/tmp/cloakfox-identifier-results.json')
    Path(report).write_text(json.dumps({'checks':checks,'observations':observations},indent=2))
    print(f"{sum(c['pass'] for c in checks)}/{len(checks)} checks passed; {report}")
    return 0 if all(c['pass'] for c in checks) else 1


if __name__=='__main__':
    raise SystemExit(main())
