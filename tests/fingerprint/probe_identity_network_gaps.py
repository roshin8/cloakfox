"""Loopback TLS regressions for container request identity and WebRTC setters.

No ICE gathering, public-IP discovery, external page, or capture is requested.
Synthetic documentation IPs are published only inside the disposable profile.
"""
import json
import os
from pathlib import Path
import select
import socket
import socketserver
import threading
import time
from urllib.parse import urlsplit
from screen_management_fixture import ScreenManagementFixture, FIREFOX, HOSTS

WINDOWS = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0'
PROFILES = {
    1: {'navigator.userAgent': WINDOWS, 'headers.User-Agent': WINDOWS,
        'navigator.language':'de-DE','locale:language':'de','locale:region':'DE',
        'headers.Accept-Language':'de-DE,de;q=0.9','headers.Accept-Encoding':'gzip'},
    2: {'navigator.userAgent': FIREFOX, 'headers.User-Agent': FIREFOX,
        'navigator.language':'fr-FR','locale:language':'fr','locale:region':'FR',
        'headers.Accept-Language':'fr-FR,fr;q=0.9','headers.Accept-Encoding':'br'},
}
FIRST = r'''
const names=['setWebRTCIPv4','setWebRTCIPv6'];
window.firstSetters=names.map(name=>({name,type:typeof window[name],present:name in window,
  own:Object.hasOwn(window,name),prototypeNames:(()=>{const result=[];
    for(let p=window;p;p=Object.getPrototypeOf(p))if(Object.getOwnPropertyNames(p).includes(name))result.push(name);
    return result;})()}));
window.firstNavigator={ua:navigator.userAgent,language:navigator.language,languages:Array.from(navigator.languages),
 frozen:Object.isFrozen(navigator.languages),sameRead:navigator.languages===navigator.languages};
window.presentation=()=>({});
if(parent!==window)parent.postMessage({identityFrame:true,setters:firstSetters,
 navigator:firstNavigator,headers:window.navigationHeaders},'*');
'''
WORKER = r'''
let originalLanguageArray;
async function result(label){originalLanguageArray??=navigator.languages;return {navigator:{ua:navigator.userAgent,language:navigator.language,
 languages:Array.from(navigator.languages),frozen:Object.isFrozen(navigator.languages),sameRead:navigator.languages===navigator.languages,
 sameOld:navigator.languages===originalLanguageArray},
 headers:await fetch('/identity-echo?realm='+label,{cache:'no-store'}).then(r=>r.json())};}
'''
REALMS = ['dedicated','nested','shared','service']


class ConnectProxy:
    """Owned HTTP CONNECT proxy, restricted to this fixture's loopback TLS."""
    def __init__(self, target_port):
        self.requests=[]
        fixture=self
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                upstream=None
                try:
                    self.request.settimeout(15)
                    request=b''
                    while b'\r\n\r\n' not in request and len(request)<65536:
                        chunk=self.request.recv(4096)
                        if not chunk:return
                        request+=chunk
                    head,_,pending=request.partition(b'\r\n\r\n')
                    lines=head.decode('iso-8859-1').split('\r\n')
                    method,authority,_=lines[0].split(' ',2)
                    headers=dict((name.lower().strip(),value.strip()) for name,value in
                        (line.split(':',1) for line in lines[1:] if ':' in line))
                    fixture.requests.append({'method':method,'authority':authority,'headers':headers})
                    host,_,port=authority.rpartition(':')
                    if method!='CONNECT' or host not in HOSTS or port!=str(target_port):
                        self.request.sendall(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n');return
                    upstream=socket.create_connection(('127.0.0.1',target_port),timeout=15)
                    self.request.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                    if pending:upstream.sendall(pending)
                    peers=[self.request,upstream]
                    while True:
                        ready,_,_=select.select(peers,[],[],15)
                        if not ready:return
                        for incoming in ready:
                            chunk=incoming.recv(65536)
                            if not chunk:return
                            (upstream if incoming is self.request else self.request).sendall(chunk)
                except (OSError,ValueError):
                    return
                finally:
                    if upstream:upstream.close()
        class Server(socketserver.ThreadingTCPServer):
            daemon_threads=True
            allow_reuse_address=True
        self.server=Server(('127.0.0.1',0),Handler)
        self.port=self.server.server_address[1]
    def __enter__(self):
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start();return self
    def __exit__(self,*_):
        self.server.shutdown();self.server.server_close();self.thread.join(5)


def main():
    checks=[]; observations={}
    def check(ok,name,data=None):
        checks.append({'name':name,'pass':bool(ok),'data':data})
        print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    with ScreenManagementFixture() as f:
        f.set_feature(False)
        # Leave external discovery disabled; publishing test masks below does
        # not turn on the parent module's public-IP service requests.
        f.pref('cloakfox.webrtc.external_ip_discovery',False)
        captured=[]
        for server in f.servers:
            original=server.RequestHandlerClass
            class Handler(original):
                def do_GET(self):
                    path=urlsplit(self.path).path
                    headers={name.lower():value for name,value in self.headers.items()}
                    captured.append({'path':self.path,'headers':headers})
                    if path in ('/identity-echo','/identity-redirect','/identity.html'):
                        f.requests.append((self.headers.get('Host','').split(':')[0],path))
                        if path=='/identity-redirect':
                            self.send_response(302);self.send_header('Location','/identity-echo?realm=redirected');self.end_headers();return
                        self.send_response(200);self.send_header('Cache-Control','no-store')
                        self.send_header('Content-Type','application/json' if path=='/identity-echo' else 'text/html')
                        self.end_headers()
                        body=json.dumps(headers) if path=='/identity-echo' else '<!doctype html><script>window.navigationHeaders='+json.dumps(headers)+';'+FIRST+'</script>'
                        self.wfile.write(body.encode());return
                    super().do_GET()
            server.RequestHandlerClass=Handler
        f.routes.update({
            '/identity-worker.js':(WORKER+'onmessage=e=>result(e.data).then(postMessage);',{'Cache-Control':'no-store'}),
            '/identity-nested.js':("onmessage=e=>{const w=new Worker('/identity-worker.js');w.onmessage=v=>{w.terminate();postMessage(v.data)};w.postMessage('nested')};",{'Cache-Control':'no-store'}),
            '/identity-shared.js':(WORKER+"onconnect=e=>{const p=e.ports[0];p.onmessage=e=>result('shared').then(v=>p.postMessage(v));p.start()};",{'Cache-Control':'no-store'}),
            '/identity-service.js':(WORKER+"oninstall=e=>e.waitUntil(skipWaiting());onactivate=e=>e.waitUntil(clients.claim());onmessage=e=>e.waitUntil(result('service').then(v=>e.ports[0].postMessage(v)));",{'Cache-Control':'no-store'}),
        })
        d=f.driver
        def worker(kind,tag):
            body={
                'dedicated':"const w=new Worker('/identity-worker.js?'+tag);w.onmessage=e=>{w.terminate();done(e.data)};w.onerror=e=>done({error:e.message});w.postMessage('dedicated')",
                'nested':"const w=new Worker('/identity-nested.js?'+tag);w.onmessage=e=>{w.terminate();done(e.data)};w.onerror=e=>done({error:e.message});w.postMessage('nested')",
                'shared':"const w=new SharedWorker('/identity-shared.js?'+tag);w.port.start();w.port.onmessage=e=>{w.port.close();done(e.data)};w.onerror=e=>done({error:e.message});w.port.postMessage('shared')",
                'service':"navigator.serviceWorker.register('/identity-service.js?'+tag,{scope:'/identity-scope/'+tag+'/'}).then(r=>new Promise(resolve=>{const w=r.installing||r.waiting||r.active;if(w.state==='activated')resolve(w);else w.addEventListener('statechange',()=>{if(w.state==='activated')resolve(w)})})).then(w=>{const p=new MessageChannel();p.port1.onmessage=e=>done(e.data);w.postMessage('service',[p.port2])}).catch(e=>done({error:String(e)}))",
            }[kind]
            return d.execute_async_script('const [tag,callback]=arguments;let ended=false;const done=v=>{if(ended)return;ended=true;callback(v)};setTimeout(()=>done({error:"timeout"}),12000);'+body,tag)
        def frame(host,tag):
            return d.execute_async_script('''const [url,done]=arguments;const iframe=document.createElement('iframe');
let ended=false;const finish=value=>{if(ended)return;ended=true;removeEventListener('message',listener);iframe.remove();done(value)};
const listener=e=>{if(e.source===iframe.contentWindow&&e.data.identityFrame)finish(e.data)};
addEventListener('message',listener);iframe.src=url;document.body.append(iframe);setTimeout(()=>finish({error:'timeout'}),12000);''',f'https://{host}:{f.https_port}/identity.html?frame='+tag)
        def collect(container,tag):
            f.open('/identity.html?tag='+tag,container=container)
            out=d.execute_script('return {navigator:firstNavigator,setters:firstSetters,headers:navigationHeaders}')
            out['fetch']=d.execute_async_script("const done=arguments[0];fetch('/identity-echo?realm=page',{cache:'no-store'}).then(r=>r.json()).then(done,e=>done({error:String(e)}))")
            out['redirect']=d.execute_async_script("const done=arguments[0];fetch('/identity-redirect',{cache:'no-store'}).then(r=>r.json()).then(done,e=>done({error:String(e)}))")
            out['same']=frame('app.testdome.com',tag)
            out['cross']=frame('other.testdome.invalid',tag)
            for kind in REALMS:out[kind]=worker(kind,tag)
            return out
        f.set_master(False)
        native=collect(0,'native');observations['native']=native
        for container,cfg in PROFILES.items():
            f.set_config(container,{**cfg,'network-probe:sentinel':'preserved-'+str(container)})
        f.set_master(True);time.sleep(.5)
        for enabled in (True,False):
            f.set_master(enabled);time.sleep(.5)
            for container,cfg in PROFILES.items():
                tag=str(enabled)+'-'+str(container)
                out=collect(container,tag);observations[tag]=out
                expected=cfg['navigator.userAgent'] if enabled else native['navigator']['ua']
                check(out['navigator']['ua']==expected,tag+': page navigator UA',out['navigator'])
                expected_language=cfg['navigator.language'] if enabled else native['navigator']['language']
                expected_languages=[cfg['navigator.language'],cfg['locale:language']] if enabled else native['navigator']['languages']
                for realm in ('page','same','cross',*REALMS):
                    nav=out['navigator'] if realm=='page' else out[realm].get('navigator',{})
                    check(nav.get('language')==expected_language,tag+': '+realm+' navigator language',nav)
                    check(nav.get('languages')==expected_languages,tag+': '+realm+' language list',nav)
                    check(nav.get('frozen') and nav.get('sameRead'),tag+': '+realm+' frozen cached language list',nav)
                for realm in ('page','same','cross'):
                    setters=out['setters'] if realm=='page' else out[realm].get('setters',[])
                    check(len(setters)==2 and all(s['type']=='undefined' and not s['present'] and not s['own'] and not s['prototypeNames'] for s in setters),tag+': '+realm+' first-script setters absent',setters)
                header_sets={'navigation':out['headers'],'fetch':out['fetch'],'redirect':out['redirect']}
                for realm in ('same','cross',*REALMS):
                    result=out[realm]
                    check(result.get('navigator',{}).get('ua')==expected,tag+': '+realm+' navigator UA',result)
                    header_sets[realm]=result.get('headers',{})
                for realm,headers in header_sets.items():
                    check(headers.get('user-agent')==expected,tag+': '+realm+' request UA',headers)
                    for field in ('Accept-Language','Accept-Encoding'):
                        value=cfg['headers.'+field] if enabled else native['headers'].get(field.lower())
                        check(headers.get(field.lower())==value,tag+': '+realm+' '+field,headers.get(field.lower()))
        # Retain the same window and worker globals across a config/master
        # update. A frozen binding cache must change only in the affected
        # container, including nested, shared and service worker navigators.
        f.set_master(True)
        live_handles={}
        def live_read(container, initialize=False):
            if initialize:
                f.open('/identity.html?live='+str(container),container=container)
                live_handles[container]=d.current_window_handle
                d.execute_script('''
                  window.localePeers={dedicated:new Worker('/identity-worker.js?live'),
                    nested:new Worker('/identity-live-nested.js'),
                    shared:new SharedWorker('/identity-shared.js?live')};
                  window.oldLanguageArray=navigator.languages;
                  window.localePeers.shared.port.start();
                ''')
            else:d.switch_to.window(live_handles[container])
            data=d.execute_async_script('''const done=arguments[0];
              const read=p=>new Promise(resolve=>{p.onmessage=e=>resolve(e.data);p.postMessage('live')});
              Promise.all(Object.entries(localePeers).map(async([k,w])=>[k,await read(k==='shared'?w.port:w)]))
                .then(entries=>done({page:{language:navigator.language,languages:Array.from(navigator.languages),
                    sameOld:navigator.languages===oldLanguageArray,sameRead:navigator.languages===navigator.languages,
                    frozen:Object.isFrozen(navigator.languages)},...Object.fromEntries(entries)}));''')
            data['service']=worker('service','live-'+str(container))
            return data
        f.routes['/identity-live-nested.js']=("const w=new Worker('/identity-worker.js?live-nested');w.onmessage=e=>postMessage(e.data);onmessage=e=>w.postMessage(e.data);",{})
        before_live={container:live_read(container,True) for container in (1,2)}
        updated={'navigator.language':'zh-Hant-TW','headers.Accept-Language':'en-us;q=0.9,zh-Hant-TW;q=0.8,en-US;q=0.7,fr-FR;q=0.5,*,bad!tag;q=0.1'}
        f.set_config(1,updated)
        expected_list=['zh-Hant-TW','en-US','fr-FR']
        deadline=time.monotonic()+8
        while True:
            changed=live_read(1)
            navs=[changed['page']]+[changed[k].get('navigator',{}) for k in REALMS]
            if all(n.get('languages')==expected_list for n in navs) or time.monotonic()>deadline:break
            time.sleep(.1)
        observations['live-language-update']=changed
        for realm,nav in zip(('page',*REALMS),navs):
            check(nav.get('language')=='zh-Hant-TW' and nav.get('languages')==expected_list,
                  'live config: '+realm+' canonical language, weighted list, deduplication',nav)
            check(nav.get('frozen') and nav.get('sameRead'),'live config: '+realm+' frozen stable cache',nav)
            check(not nav.get('sameOld'),'live config: '+realm+' old language cache replaced',nav)
        check(not changed['page']['sameOld'],'changed window language list cache invalidated',changed['page'])
        sibling=live_read(2);observations['live-language-sibling']=sibling
        check(sibling['page']['sameOld'] and sibling['page']['languages']==before_live[2]['page']['languages'],
              'sibling container cached window language array preserved',sibling['page'])
        for realm in REALMS:
            check(sibling[realm]['navigator']['languages']==before_live[2][realm]['navigator']['languages'] and sibling[realm]['navigator']['sameOld'],
                  'sibling '+realm+' language identity preserved',sibling[realm]['navigator'])
        f.set_master(False)
        deadline=time.monotonic()+8
        while True:
            restored=live_read(1)
            navs=[restored['page']]+[restored[k].get('navigator',{}) for k in REALMS]
            if all(n.get('languages')==native['navigator']['languages'] for n in navs) or time.monotonic()>deadline:break
            time.sleep(.1)
        for realm,nav in zip(('page',*REALMS),navs):
            check(nav.get('language')==native['navigator']['language'] and nav.get('languages')==native['navigator']['languages'],
                  'live masteroff: '+realm+' native language restored',nav)
        f.set_config(1,{k:PROFILES[1][k] for k in updated})
        # Observe the outer plaintext CONNECT independently of the encrypted
        # target request. Only an owned proxy and this fixture's TLS endpoint
        # are reachable; the existing disposable browser profile is reused.
        with ConnectProxy(f.https_port) as proxy:
            for name,value in {'network.proxy.ssl':'127.0.0.1','network.proxy.ssl_port':proxy.port,
                'network.proxy.no_proxies_on':'','network.proxy.allow_hijacking_localhost':True,
                'network.proxy.failover_direct':False,'network.proxy.type':1}.items():f.pref(name,value)
            try:
                cases=[('windows',1,True,WINDOWS),('linux',2,True,FIREFOX),
                    ('custom-header',1,True,WINDOWS+' LocalIdentityProbe'),
                    ('native-one',1,False,native['headers']['user-agent']),
                    ('native-two',2,False,native['headers']['user-agent'])]
                for tag,container,enabled,expected in cases:
                    if enabled:
                        f.set_config(container,{'headers.User-Agent':expected})
                    f.set_master(enabled);time.sleep(.3)
                    f.chrome('Services.obs.notifyObservers(null,"net:prune-all-connections");')
                    time.sleep(.3)
                    before=len(proxy.requests)
                    f.open('/identity.html?proxy='+tag,container=container)
                    target=d.execute_script('return navigationHeaders')
                    connect=[r for r in proxy.requests[before:] if r['authority']==f'app.testdome.com:{f.https_port}']
                    observations['CONNECT-'+tag]={'connect':connect,'target':target}
                    check(bool(connect) and all(r['method']=='CONNECT' for r in connect),tag+': navigation traverses owned CONNECT proxy',connect)
                    check(bool(connect) and all(r['headers'].get('user-agent')==expected for r in connect),tag+': CONNECT UA follows target container/header override',connect)
                    check(target.get('user-agent')==expected,tag+': tunneled target UA agrees with CONNECT',target)
                observations['CONNECT-requests']=proxy.requests
            finally:
                f.pref('network.proxy.type',0)
                f.set_config(1,{'headers.User-Agent':WINDOWS})
        # Canonical pref already exists and includes unrelated fields when the
        # actor installs masks. A legacy namespace copy must not win resolution.
        f.set_master(True)
        f.chrome('''Services.ppmm.sharedData.set('cloakfox-public-ipv4','192.0.2.44');
Services.ppmm.sharedData.set('cloakfox-public-ipv6','2001:db8::44');Services.ppmm.sharedData.flush();''')
        time.sleep(.5)
        for container in (1,2):
            f.open('/identity.html?mask='+str(container),container=container)
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                overlay=f.chrome('''const id=arguments[0];return {canonical:JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+id,'{}')),
legacy:Services.prefs.getStringPref('roverfox.s.cloak_cfg_'+id,'')};''',container)
                if overlay['canonical'].get('webrtc:ipv4')=='192.0.2.44' and overlay['canonical'].get('webrtc:ipv6')=='2001:db8::44':break
                time.sleep(.1)
            observations['overlay-'+str(container)]=overlay
            check(overlay['canonical'].get('webrtc:ipv4')=='192.0.2.44' and overlay['canonical'].get('webrtc:ipv6')=='2001:db8::44','container '+str(container)+': actor writes both masks to authoritative overlay',overlay)
            check(overlay['canonical'].get('network-probe:sentinel')=='preserved-'+str(container),'container '+str(container)+': unrelated overlay field preserved',overlay)
            check(not overlay['legacy'],'container '+str(container)+': no shadow legacy overlay',overlay['legacy'])
            d.refresh();time.sleep(.3)
            after=f.chrome("return JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+arguments[0],'{}'));",container)
            check(after.get('webrtc:ipv4')=='192.0.2.44' and after.get('webrtc:ipv6')=='2001:db8::44','container '+str(container)+': canonical masks retained on reload',after)
            # A pending child native-write acknowledgement must not freeze the
            # authoritative pref against later parent UI/config edits.
            other=PROFILES[2 if container==1 else 1]
            change={k:other[k] for k in ('navigator.userAgent','headers.User-Agent',
                'navigator.language','headers.Accept-Language')}
            seed_before=f.chrome("return Services.prefs.getStringPref('cloakfox.container.'+arguments[0]+'.math_seed')",container)
            f.set_config(container,change)
            changed=collect(container,'after-mask-parent-update-'+str(container))
            observations['after-mask-parent-update-'+str(container)]=changed
            for realm in ('page','same','cross',*REALMS):
                nav=changed['navigator'] if realm=='page' else changed[realm].get('navigator',{})
                check(nav.get('ua')==other['navigator.userAgent'] and nav.get('language')==other['navigator.language'],
                    'container '+str(container)+': parent identity update after masks '+realm,nav)
                headers=changed['headers'] if realm=='page' else changed[realm].get('headers',{})
                check(headers.get('user-agent')==other['headers.User-Agent'] and
                      headers.get('accept-language')==other['headers.Accept-Language'],
                    'container '+str(container)+': parent request update after masks '+realm,headers)
            final=f.chrome("return JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+arguments[0]));",container)
            check(final=={**after,**change},'container '+str(container)+': only requested identity fields changed after masks',final)
            check(f.chrome("return Services.prefs.getStringPref('cloakfox.container.'+arguments[0]+'.math_seed')",container)==seed_before,
                  'container '+str(container)+': parent identity update preserves seed')
        observations['requests']=captured
        output=Path(os.environ.get('IDENTITY_NETWORK_REPORT',str(f.report_path/'identity-network.json')))
        output.write_text(json.dumps({'checks':checks,'observations':observations},indent=2));print(output)
    return 0 if all(c['pass'] for c in checks) else 1


if __name__=='__main__':
    raise SystemExit(main())
