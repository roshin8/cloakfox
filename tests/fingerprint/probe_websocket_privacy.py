"""Local TLS WebSocket policy tests. No external host, camera, or microphone."""
import asyncio,json,threading,socket
from screen_management_fixture import ScreenManagementFixture
import websockets

ATTEMPT='''async function attempt(url){return await new Promise(resolve=>{let ws;try{ws=new WebSocket(url)}catch(e){resolve({name:e.name,message:e.message});return}let finished=false;const timer=setTimeout(()=>finish({error:'timeout'}),5000);function finish(r){if(finished)return;finished=true;clearTimeout(timer);ws.close();resolve(r)}ws.onopen=()=>ws.send('privacy-test');ws.onmessage=e=>finish({echo:e.data});ws.onerror=()=>finish({error:'connection failed'})})}'''
PAGE='<!doctype html><script>window.presentation=()=>({});'+ATTEMPT+'</script>'
DEDICATED=ATTEMPT+"onmessage=e=>attempt(e.data).then(postMessage);"
SHARED=ATTEMPT+"onconnect=e=>{const p=e.ports[0];p.onmessage=e=>attempt(e.data).then(r=>p.postMessage(r));p.start()};"
SERVICE=ATTEMPT+"oninstall=e=>e.waitUntil(skipWaiting());onactivate=e=>e.waitUntil(clients.claim());onmessage=e=>e.waitUntil(attempt(e.data).then(r=>e.ports[0].postMessage(r)));"

class EchoServer:
    def __init__(self,tls):self.tls=tls;self.ready=threading.Event();self.requests=[];self.loop=None;self.error=None
    def start(self):
        def run():
            async def main():
                self.loop=asyncio.get_running_loop();self.stop=self.loop.create_future()
                async def echo(connection):
                    self.requests.append(dict(connection.request.headers));
                    async for message in connection:await connection.send(message)
                try:
                    async with websockets.serve(echo,'127.0.0.1',0,ssl=self.tls) as server:
                        self.port=server.sockets[0].getsockname()[1];self.ready.set();await self.stop
                except BaseException as error:self.error=error;self.ready.set()
            asyncio.run(main())
        self.thread=threading.Thread(target=run,daemon=True);self.thread.start();assert self.ready.wait(10)
        if self.error:raise self.error
    def close(self):
        if self.loop:self.loop.call_soon_threadsafe(self.stop.set_result,None)
        self.thread.join(10)

def main():
    failures=[]
    def check(ok,name,data):
        print(('PASS ' if ok else 'FAIL ')+name+': '+json.dumps(data),flush=True)
        if not ok:failures.append(name)
    with ScreenManagementFixture() as f:
        f.routes.update({'/socket.html':(PAGE,{}),'/socket-worker.js':(DEDICATED,{}),'/socket-preloaded.js':(DEDICATED+"postMessage({ready:true});",{}),'/socket-nested.js':("onmessage=e=>{const w=new Worker('/socket-worker.js');w.onmessage=ev=>{w.terminate();postMessage(ev.data)};w.postMessage(e.data)}",{}),'/socket-shared.js':(SHARED,{}),'/socket-service.js':(SERVICE,{})})
        server=EchoServer(f.servers[0].socket.context);server.start()
        try:
            url=f'wss://app.testdome.com:{server.port}/echo'
            f.set_config(0,{'webSocket:disabled':False})
            f.set_config(1,{'webSocket:disabled':True});f.set_config(2,{'webSocket:disabled':False,'navigator.userAgent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0','headers.User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0'})
            d=f.driver
            check(not f.chrome('return Services.prefs.getBoolPref("cloakfox.opt.websocket_disabled",false)'),'WebSockets are enabled by default',{})
            def probe(kind):
                body={
                    'page':'attempt(url).then(done)',
                    'dedicated':"const w=new Worker('/socket-worker.js');w.onmessage=e=>{w.terminate();done(e.data)};w.postMessage(url)",
                    'nested':"const w=new Worker('/socket-nested.js');w.onmessage=e=>{w.terminate();done(e.data)};w.postMessage(url)",
                    'shared':"const w=new SharedWorker('/socket-shared.js');w.port.start();w.port.onmessage=e=>{w.port.close();done(e.data)};w.port.postMessage(url)",
                    'service':"navigator.serviceWorker.register('/socket-service.js').then(()=>navigator.serviceWorker.ready).then(r=>{const p=new MessageChannel();p.port1.onmessage=e=>done(e.data);r.active.postMessage(url,[p.port2])}).catch(e=>done({error:String(e)}))",
                }[kind]
                return d.execute_async_script('const [url,done]=arguments;'+body,url)
            for container,blocked in [(1,True),(2,False)]:
                f.open('/socket.html',container=container)
                d.execute_script('document.cookie=arguments[0]',f'identity=C{container};SameSite=Lax;Secure;Path=/')
                for kind in ['page','dedicated','nested','shared','service']:
                    before=len(server.requests);result=probe(kind)
                    check(result.get('name')=='SecurityError' if blocked else result.get('echo')=='privacy-test',f'{kind} container {container} policy',result)
                    check('cloakfox' not in result.get('message','').lower(),f'{kind} neutral error',result)
                    if blocked:check(len(server.requests)==before,f'{kind} blocked before handshake',len(server.requests)-before)
                    elif result.get('echo'):
                        cookie=server.requests[-1].get('cookie','')
                        check('identity=C2' in cookie and 'identity=C1' not in cookie,f'{kind} handshake cookie isolation',cookie)
                        check(server.requests[-1].get('origin')==f.origin,f'{kind} handshake origin',server.requests[-1].get('origin'))
                        expected=d.execute_script('return navigator.userAgent')
                        check(server.requests[-1].get('user-agent')==expected,f'{kind} handshake UA agrees with page',{'expected':expected,'actual':server.requests[-1].get('user-agent')})
            f.set_config(1,{'webSocket:disabled':False})
            f.open('/socket.html',container=1)
            for kind in ['page','dedicated','nested','shared','service']:
                result=probe(kind)
                check(result.get('echo')=='privacy-test',f'{kind} works in container 1 without blocking',result)
                if result.get('echo'):check('identity=C1' in server.requests[-1].get('cookie','') and 'identity=C2' not in server.requests[-1].get('cookie',''),f'{kind} container 1 cookie isolation',server.requests[-1].get('cookie'))
            f.set_config(1,{'webSocket:disabled':True})
            f.set_config(0,{'webSocket:disabled':True})
            f.open('/socket.html',container=2)
            check(probe('dedicated').get('echo')=='privacy-test','default-container policy does not block container 2 worker',{})
            f.open('/socket.html',container=1);f.set_master(False);d.refresh()
            check(probe('dedicated').get('echo')=='privacy-test','master off restores worker connections',{})
            f.set_master(True)
            f.open('/socket.html',container=2)
            d.execute_async_script('const done=arguments[0];const w=new Worker("/socket-preloaded.js");window.proxyWorker=w;w.onmessage=e=>{if(e.data.ready)done(true)};w.onerror=e=>done({error:e.message})')
            with socket.socket() as unavailable:
                unavailable.bind(('127.0.0.1',0)) # reserved but not listening
                proxy_port=unavailable.getsockname()[1]
                for name,value in {'network.proxy.http':'127.0.0.1','network.proxy.http_port':proxy_port,'network.proxy.ssl':'127.0.0.1','network.proxy.ssl_port':proxy_port,'network.proxy.no_proxies_on':'','network.proxy.allow_hijacking_localhost':True,'network.proxy.failover_direct':False,'network.proxy.type':1}.items():f.pref(name,value)
                before=len(server.requests)
                for kind in ['page','dedicated']:
                    result=probe(kind) if kind=='page' else d.execute_async_script('const [url,done]=arguments;proxyWorker.onmessage=e=>{proxyWorker.terminate();done(e.data)};proxyWorker.postMessage(url)',url)
                    check(result.get('echo') is None and result.get('name')!='SecurityError',f'{kind} unavailable proxy fails as a network error',result)
                check(len(server.requests)==before,'failed manual proxy does not fall back to direct WebSocket handshake',len(server.requests)-before)
                f.pref('network.proxy.type',0)
            check(probe('page').get('echo')=='privacy-test','WebSocket recovers after restoring direct configuration',{})

        finally:server.close()
    assert not failures,failures
if __name__=='__main__':main()
