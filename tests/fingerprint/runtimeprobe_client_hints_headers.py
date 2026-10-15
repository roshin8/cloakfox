"""Real local TLS echo of native low entropy hints, with no identity warmup.

Only a disposable profile and fixture-owned loopback certificates are used.
High entropy HTTP hints remain unsupported, including after Accept-CH.
"""
import json
from screen_management_fixture import ScreenManagementFixture, FIREFOX

CHROME = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36'
EDGE = CHROME + ' Edg/155.0.12.3'
SAFARI = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15'
HINTS = ('sec-ch-ua', 'sec-ch-ua-mobile', 'sec-ch-ua-platform')


def run_probe():
    checks, observations = [], {}
    def check(ok, name, data=None):
        checks.append({'name': name, 'pass': bool(ok), 'data': data})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
    with ScreenManagementFixture() as f:
        f.set_feature(False)
        f.pref('cloakfox.webrtc.ip_lookup.enabled', False)
        for server in f.servers:
            original = server.RequestHandlerClass
            class Handler(original):
                def do_GET(self):
                    path = self.path.split('?')[0]
                    headers = {name.lower(): value for name, value in self.headers.items()}
                    if path.startswith('/hints'):
                        f.requests.append((self.headers.get('Host', '').split(':')[0], path))
                        if path in ('/hints-redirect', '/hints-redirect-http', '/hints-redirect-cross'):
                            self.send_response(302)
                            target = '/hints-echo'
                            if path == '/hints-redirect-http':
                                target = f'http://app.testdome.com:{f.http_port}/hints.html'
                            elif path == '/hints-redirect-cross':
                                target = f'https://other.testdome.invalid:{f.https_port}/hints-echo'
                            self.send_header('Location', target)
                            self.end_headers()
                            return
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json' if path == '/hints-echo' else 'text/html')
                        self.send_header('Cache-Control', 'no-store')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.send_header('Accept-CH', 'Sec-CH-UA-Arch, Sec-CH-UA-Platform-Version')
                        if path == '/hints-policy-denied':
                            self.send_header('Permissions-Policy', 'ch-ua=(), ch-ua-mobile=(), ch-ua-platform=()')
                        elif path == '/hints-policy-platform-denied':
                            self.send_header('Permissions-Policy', 'ch-ua-platform=()')
                        self.end_headers()
                        body = json.dumps(headers) if path == '/hints-echo' else '<script>window.navigationHeaders=' + json.dumps(headers) + ';window.presentation=()=>({});if(parent!==window)parent.postMessage({hintFrame:true,headers:navigationHeaders},"*");</script>'
                        self.wfile.write(body.encode())
                        return
                    super().do_GET()
            server.RequestHandlerClass = Handler
        f.routes['/worker-hints.js'] = ("onmessage=()=>fetch('/hints-echo').then(r=>r.json()).then(postMessage);", {})
        f.routes['/nested-worker-hints.js'] = ("onmessage=()=>{const w=new Worker('/worker-hints.js');w.onmessage=e=>{w.terminate();postMessage(e.data)};w.postMessage(1)};", {})
        f.routes['/service-hints.js'] = ("oninstall=e=>e.waitUntil(skipWaiting());onactivate=e=>e.waitUntil(clients.claim());onmessage=e=>e.waitUntil(fetch('/hints-echo').then(r=>r.json()).then(v=>e.ports[0].postMessage(v)));", {})
        d = f.driver
        def config(container, ua):
            f.set_config(container, {'navigator.userAgent': ua, 'headers.User-Agent': ua})
        def navigate(tag, container=0, scheme='https', path='/hints.html', **kwargs):
            f.open(path + '?tag=' + tag, container=container, scheme=scheme, **kwargs)
            value = d.execute_script('return {headers:navigationHeaders,ua:navigator.userAgent,vendor:navigator.vendor,data:navigator.userAgentData?.toJSON()}')
            observations[tag] = value
            return value
        def coherent(value, name, brand='Google Chrome', platform='Windows'):
            h = value['headers']
            check(all(key in h for key in HINTS), name + ': baseline headers present', h)
            check(h.get('user-agent') == value['ua'], name + ': UA matches navigator', h)
            if 'vendor' in value:
                check(value['vendor'] == 'Google Inc.', name + ': Chromium vendor parity', value)
            expected = value.get('data')
            if expected:
                brands = ', '.join(json.dumps(v['brand']) + ';v=' + json.dumps(v['version']) for v in expected['brands'])
                check(h.get('sec-ch-ua') == brands and h.get('sec-ch-ua-mobile') == ('?1' if expected['mobile'] else '?0') and h.get('sec-ch-ua-platform') == json.dumps(expected['platform']), name + ': JS low entropy parity', value)
            check(brand in h.get('sec-ch-ua', '') and h.get('sec-ch-ua-platform') == json.dumps(platform), name + ': selected identity', h)
            check(not any(k.startswith('sec-ch-ua-') and k not in HINTS for k in h), name + ': no unsupported high entropy', h)
        config(0, CHROME)
        coherent(navigate('first-request'), 'first-request')
        config(1, EDGE)
        coherent(navigate('edge-container', 1), 'edge-container', 'Microsoft Edge')
        config(2, FIREFOX)
        value = navigate('firefox-container', 2)
        check(not any(k in value['headers'] for k in HINTS), 'Firefox container has no hints', value)
        coherent(navigate('return-default'), 'return-default')
        for path in ['/hints-echo', '/hints-redirect', '/hints-redirect-cross']:
            h = d.execute_async_script("const [url,done]=arguments;fetch(url,{cache:'no-store'}).then(r=>r.json()).then(done)", path)
            coherent({'headers': h, 'ua': CHROME}, path)
        h = d.execute_async_script("const done=arguments[0];const w=new Worker('/worker-hints.js');w.onmessage=e=>{w.terminate();done(e.data)};w.postMessage(1)")
        coherent({'headers': h, 'ua': CHROME}, 'dedicated-worker')
        h = d.execute_async_script("const done=arguments[0];navigator.serviceWorker.register('/service-hints.js',{scope:'/service-hints/'}).then(r=>new Promise(resolve=>{const w=r.installing||r.waiting||r.active;if(w.state==='activated')resolve(w);else w.addEventListener('statechange',()=>{if(w.state==='activated')resolve(w)})})).then(w=>{const p=new MessageChannel();p.port1.onmessage=e=>done(e.data);w.postMessage(1,[p.port2])}).catch(e=>done({error:String(e)}))")
        coherent({'headers': h, 'ua': CHROME}, 'service-worker')
        h = d.execute_async_script('''const [url,done]=arguments;const frame=document.createElement('iframe');const listener=e=>{if(e.source===frame.contentWindow&&e.data.hintFrame){removeEventListener('message',listener);frame.remove();done(e.data.headers)}};addEventListener('message',listener);frame.src=url;document.body.append(frame)''', f'https://other.testdome.invalid:{f.https_port}/hints.html')
        coherent({'headers': h, 'ua': CHROME}, 'cross-origin-frame')
        value = navigate('https-to-http', path='/hints-redirect-http')
        check(not any(k in value['headers'] for k in HINTS), 'HTTPS to untrusted HTTP drops synthesized hints', value)
        value = navigate('untrusted-http', scheme='http')
        check(not any(k in value['headers'] for k in HINTS), 'untrusted HTTP has no hints', value)
        coherent(navigate('trustworthy-http', scheme='http', host='localhost'), 'trustworthy-http')
        config(0, 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Mobile Safari/537.36')
        coherent(navigate('android'), 'android', platform='Android')
        check(observations['android']['headers'].get('sec-ch-ua-mobile') == '?1', 'Android mobile bit')
        config(0, CHROME)
        navigate('policy-all-denied', path='/hints-policy-denied')
        for kind in ['window', 'worker', 'nested-worker']:
            script = {
                'window': "fetch('/hints-echo').then(r=>r.json()).then(done)",
                'worker': "const w=new Worker('/worker-hints.js');w.onmessage=e=>{w.terminate();done(e.data)};w.postMessage(1)",
                'nested-worker': "const w=new Worker('/nested-worker-hints.js');w.onmessage=e=>{w.terminate();done(e.data)};w.postMessage(1)",
            }[kind]
            h = d.execute_async_script('const done=arguments[0];' + script)
            check(not any(key in h for key in HINTS), kind + ': explicit policy denial suppresses hints', h)
        h = d.execute_async_script("const done=arguments[0];const frame=document.createElement('iframe');frame.onload=()=>frame.contentWindow.fetch('/hints-echo').then(r=>r.json()).then(h=>{frame.remove();done(h)});frame.src='/hints.html';document.body.append(frame)")
        check(not any(key in h for key in HINTS), 'child frame inherits policy denial for its own fetch', h)
        navigate('policy-platform-denied', path='/hints-policy-platform-denied')
        h = d.execute_async_script("const done=arguments[0];fetch('/hints-echo').then(r=>r.json()).then(done)")
        check('sec-ch-ua-platform' not in h and 'sec-ch-ua' in h and 'sec-ch-ua-mobile' in h, 'policy denial is independent per hint', h)
        coherent(navigate('policy-cleared'), 'policy-cleared')
        for kind in ['initial-empty', 'srcdoc', 'about:blank', 'blob']:
            result = d.execute_async_script('''
                const [kind,origin,done]=arguments;
                const frame=document.createElement('iframe');
                frame.allow="ch-ua 'none';ch-ua-mobile 'none';ch-ua-platform 'none'";
                let objectURL;
                const finish=result=>{frame.remove();if(objectURL)URL.revokeObjectURL(objectURL);done(result)};
                const probe=async()=>{
                    if(kind==='srcdoc'&&frame.contentWindow.location.href!=='about:srcdoc')return;
                    if(kind==='blob'&&!frame.contentWindow.location.href.startsWith('blob:'))return;
                    try{
                        const headers=await frame.contentWindow.fetch(origin+'/hints-echo').then(r=>r.json());
                        const worker=new frame.contentWindow.Worker(origin+'/nested-worker-hints.js');
                        worker.onmessage=e=>{worker.terminate();finish({headers,worker:e.data})};
                        worker.onerror=e=>{worker.terminate();finish({error:e.message})};
                        worker.postMessage(1);
                    }catch(e){finish({error:String(e)})}
                };
                if(kind==='initial-empty'){
                    document.body.append(frame);probe();return;
                }
                frame.onload=probe;
                if(kind==='srcdoc')frame.srcdoc='<!doctype html><title>policy child</title>';
                else if(kind==='blob'){objectURL=URL.createObjectURL(new Blob(['<!doctype html><title>policy child</title>'],{type:'text/html'}));frame.src=objectURL}
                else frame.src='about:blank';
                document.body.append(frame);
            ''', kind, f.origin)
            check('headers' in result and not any(key in result['headers'] for key in HINTS), kind + ': own iframe policy denial suppresses fetch hints', result)
            check('worker' in result and not any(key in result['worker'] for key in HINTS), kind + ': nested worker inherits own iframe denial', result)
            parent = d.execute_async_script("const done=arguments[0];fetch('/hints-echo').then(r=>r.json()).then(done)")
            check(all(key in parent for key in HINTS), kind + ': child denial leaves parent allowed', parent)
        config(0, SAFARI)
        value = navigate('safari')
        check(not any(k in value['headers'] for k in HINTS), 'Safari has no hints', value)
        config(0, CHROME)
        f.set_master(False)
        value = navigate('master-off')
        check(not any(k in value['headers'] for k in HINTS), 'master off has no hints', value)
        f.set_master(True)
        f.pref('privacy.resistFingerprinting', True)
        value = navigate('rfp')
        check(not any(k in value['headers'] for k in HINTS), 'RFP has no synthesized hints', value)
        f.pref('privacy.resistFingerprinting', False)
        for invalid in [CHROME + '\r\nX-Hint-Injection: yes', CHROME + '\0suffix']:
            f.set_config(0, {'headers.User-Agent': invalid, 'navigator.userAgent': FIREFOX})
            value = navigate('invalid-UA-' + ('crlf' if '\r' in invalid else 'nul'))
            check(value['headers'].get('user-agent') == FIREFOX and 'x-hint-injection' not in value['headers'] and not any(k in value['headers'] for k in HINTS), 'invalid config UA safely falls back', value)
        config(0, CHROME.replace('155.0.0.0', '155.0"malformed'))
        value = navigate('malformed-product')
        check(not any(k in value['headers'] for k in HINTS), 'malformed product cannot inject structured fields', value)
        config(0, CHROME)
        f.chrome('''window.hintObserver={ua:arguments[0],observe(subject){const ch=subject.QueryInterface(Ci.nsIHttpChannel);if(!ch.URI.pathQueryRef.startsWith('/hints'))return;ch.setRequestHeader('User-Agent',this.ua,false);ch.setRequestHeader('Sec-CH-UA-Mobile','',false);ch.setRequestHeader('Sec-CH-UA-Platform','"Caller OS"',false)}};Services.obs.addObserver(hintObserver,'http-on-modify-request');''', EDGE)
        try:
            value = navigate('caller-overrides')
            h = value['headers']
            check(h.get('user-agent') == EDGE and 'Microsoft Edge' in h.get('sec-ch-ua', ''), 'hints refresh from final caller UA', value)
            check('sec-ch-ua-mobile' not in h and h.get('sec-ch-ua-platform') == '"Caller OS"', 'caller hint set/remove precedence', value)
        finally:
            f.chrome("Services.obs.removeObserver(hintObserver,'http-on-modify-request');delete window.hintObserver")
        f.chrome('''window.hintObserver={ua:arguments[0],observe(subject){const ch=subject.QueryInterface(Ci.nsIHttpChannel);if(ch.URI.pathQueryRef.startsWith('/hints'))ch.setRequestHeader('User-Agent',this.ua,false)}};Services.obs.addObserver(hintObserver,'http-on-before-connect');''', FIREFOX)
        try:
            value = navigate('late-firefox-override')
            check(value['headers'].get('user-agent') == FIREFOX and not any(k in value['headers'] for k in HINTS), 'late Firefox UA removes synthesized hints', value)
        finally:
            f.chrome("Services.obs.removeObserver(hintObserver,'http-on-before-connect');delete window.hintObserver")
        report = {'checks': checks, 'observations': observations, 'binary': f.binary}
        (f.report_path/'client-hints.json').write_text(json.dumps(report, indent=2))
        return report


if __name__ == '__main__':
    result = run_probe()
    raise SystemExit(0 if all(c['pass'] for c in result['checks']) else 1)
