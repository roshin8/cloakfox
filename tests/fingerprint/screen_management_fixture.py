"""Isolated exact-origin TLS fixture; never routes a test to production."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
from threading import Thread
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

CHROME = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'
FIREFOX = 'Mozilla/5.0 (X11; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0'
HOSTS = ['app.testdome.com', 'other.testdome.invalid', 'app.testdome.com.evil.invalid', 'sub.app.testdome.com']
PAGE = '''<!doctype html><meta charset="utf-8"><title>Local virtual screen fixture</title>
<script>window.firstSupport = {method: typeof getScreenDetails, detailed: typeof ScreenDetailed,
details: typeof ScreenDetails, extended: 'isExtended' in screen, ua:navigator.userAgent};
window.presentation = () => ({width:screen.width,height:screen.height,left:screen.left,top:screen.top,
availWidth:screen.availWidth,availHeight:screen.availHeight,availLeft:screen.availLeft,availTop:screen.availTop,
depth:screen.colorDepth,pixelDepth:screen.pixelDepth,dpr:devicePixelRatio,
orientation:screen.orientation.type,angle:screen.orientation.angle});
window.firstNativeResult = typeof getScreenDetails === 'function' ?
  getScreenDetails().then(d=>({count:d.screens.length,frozen:Object.isFrozen(d.screens)}),e=>({error:e.name})) : Promise.resolve({absent:true});
window.addEventListener('pageshow',e=>{if(parent!==window)parent.postMessage({fixturePageshow:true,persisted:e.persisted},'*')});</script>'''

class ScreenManagementFixture:
    def __init__(self, binary=None, headful=False):
        self.binary = binary or os.environ['CLOAKFOX_BIN']
        self.headful = headful
        self.servers = []
        self.driver = None
        capability='({method:typeof getScreenDetails,details:typeof ScreenDetails,detailed:typeof ScreenDetailed})'
        self.routes = {'/': (PAGE, {}), '/worker.js': ('postMessage'+capability+';', {}),
            '/shared.js': ('onconnect=e=>{const p=e.ports[0];p.postMessage'+capability+';};', {}),
            '/service.js': ('oninstall=()=>skipWaiting();onactivate=e=>e.waitUntil(clients.claim());onmessage=e=>e.ports[0].postMessage'+capability+';', {}),
            '/child.html': (PAGE+'<script>parent.postMessage({probe:1,type:typeof getScreenDetails},"*")</script>', {})}

        self.requests = []
        self.report_path = Path(os.environ.get('REPORT_DIR') or tempfile.mkdtemp(prefix='cloakfox-screen-reports-'))
        self.report_path.mkdir(parents=True, exist_ok=True)

    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cloakfox-screen-fixture-')
        root = Path(self.temp.name)
        try:
            key, cert = root/'key.pem', root/'cert.pem'
            subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                '-subj','/CN=app.testdome.com','-addext','subjectAltName='+','.join('DNS:'+h for h in HOSTS),
                '-keyout',str(key),'-out',str(cert)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            fixture = self
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    host = self.headers.get('Host','').split(':')[0]
                    path = self.path.split('?')[0]
                    fixture.requests.append((host, path))
                    if host not in HOSTS or path not in fixture.routes:
                        self.send_error(404); return
                    body, headers = fixture.routes[path]
                    self.send_response(200)
                    self.send_header('Content-Type','text/javascript' if path.endswith('.js') else 'text/html; charset=utf-8')
                    for name,value in headers.items(): self.send_header(name,value)
                    self.end_headers(); self.wfile.write(body.encode())
                def log_message(self,*_): pass
            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            tls.load_cert_chain(cert,key)
            ports = []
            for secure in [True, False, True]:
                server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
                if secure: server.socket = tls.wrap_socket(server.socket,server_side=True)
                self.servers.append(server)
                ports.append(server.server_port)
                Thread(target=server.serve_forever,daemon=True).start()
            self.https_port, self.http_port, self.alternate_port = ports
            self.origin = f'https://app.testdome.com:{self.https_port}'
            opts=Options(); opts.binary_location=self.binary; opts.accept_insecure_certs=True
            (root/'profile').mkdir()
            opts.add_argument('-profile'); opts.add_argument(str(root/'profile'))
            if not self.headful: opts.add_argument('-headless')
            for name,value in {'network.dns.localDomains':','.join(HOSTS),'network.trr.mode':5,
                'cloakfox.enabled':True,'cloakfox.compat.screen_management':True,
                'cloakfox.compat.screen_management.origins':json.dumps([self.origin]),
                'cloakfox.compat.screen_management.screen_count':1,'privacy.resistFingerprinting.letterboxing':False,
                'dom.security.https_only_mode':False,'dom.security.https_first':False,
                'media.autoplay.default':0,'media.autoplay.blocking_policy':0}.items(): opts.set_preference(name,value)
            self.driver=webdriver.Firefox(options=opts,service=Service(
                executable_path=os.environ.get('GECKODRIVER') or shutil.which('geckodriver'),
                service_args=['--allow-system-access'],log_output=str(self.report_path/'gecko.log')))
            self.driver.set_script_timeout(45)
            self.default_handle = self.driver.current_window_handle
            self.set_config(0, {'navigator.userAgent':CHROME,'screen.width':1366,'screen.height':768,
                'screen.availLeft':0,'screen.availTop':0,'screen.availWidth':1300,'screen.availHeight':728,
                'screen.colorDepth':24,'screen.pixelDepth':24,'window.devicePixelRatio':1,'screen:orientation:type':'landscape-primary'})
            return self
        except BaseException:
            self.__exit__(None,None,None); raise

    def __exit__(self,*_):
        if self.driver:
            self.driver.quit(); self.driver=None
        for server in self.servers:
            server.shutdown(); server.server_close()
        self.servers=[]
        if hasattr(self,'temp'):
            for dump in Path(self.temp.name).rglob('*.dmp'):
                shutil.copy2(dump,self.report_path/dump.name)
            self.temp.cleanup()

    def chrome(self,script,*args):
        self.driver.set_context('chrome')
        try: return self.driver.execute_script(script,*args)
        finally: self.driver.set_context('content')

    def chrome_async(self,script,*args):
        self.driver.set_context('chrome')
        try: return self.driver.execute_async_script(script,*args)
        finally: self.driver.set_context('content')

    def pref(self,name,value):
        kind='Bool' if isinstance(value,bool) else 'Int' if isinstance(value,int) else 'String'
        # Wrong-type controls deliberately replace this disposable process's
        # default branch too: Firefox otherwise prevents changing a pref's type.
        self.chrome('''const [name,type]=arguments;const existing=Services.prefs.getPrefType(name);
          if(existing&&existing!==type){Services.prefs.getDefaultBranch('').deleteBranch(name);
            Services.prefs.clearUserPref(name)}''',name,{'Bool':128,'Int':64,'String':32}[kind])
        self.chrome(f'Services.prefs.set{kind}Pref(arguments[0],arguments[1])',name,value)

    def set_config(self,container,updates):
        self.chrome('''const key='cloakfox.s.cloak_cfg_'+arguments[0];
          let cfg={};try{cfg=JSON.parse(Services.prefs.getStringPref(key))}catch{}
          Object.assign(cfg,arguments[1]);Services.prefs.setStringPref(key,JSON.stringify(cfg));''',container,updates)

    def set_master(self,value): self.pref('cloakfox.enabled',value)
    def set_feature(self,value): self.pref('cloakfox.compat.screen_management',value)
    def set_origins(self,values): self.pref('cloakfox.compat.screen_management.origins',json.dumps(values))
    def set_screen_count(self,value): self.pref('cloakfox.compat.screen_management.screen_count',value)

    def open(self,path='/',host='app.testdome.com',scheme='https',container=0,port=None):
        if port is None: port = self.https_port if scheme == 'https' else self.http_port
        url=f'{scheme}://{host}'+(f':{port}' if port else '')+path
        if container:
            before=set(self.driver.window_handles)
            handle=self.chrome('''const tab=gBrowser.addTab(arguments[0],{userContextId:arguments[1],
              triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
              gBrowser.selectedTab=tab;return tab.linkedBrowser.browsingContext.id.toString();''',url,container)
            # WebDriver's handle is the outer-window ID, so find by loading URL.
            from selenium.webdriver.support.ui import WebDriverWait
            def locate(_):
                for candidate in self.driver.window_handles:
                    if candidate in before: continue
                    self.driver.switch_to.window(candidate)
                    if self.driver.current_url == url: return True
                return False
            WebDriverWait(self.driver,15).until(locate)
        else:
            self.driver.switch_to.window(self.default_handle)
            self.driver.get(url)
        from selenium.webdriver.support.ui import WebDriverWait
        WebDriverWait(self.driver,15).until(lambda d:d.execute_script('return typeof presentation')=='function')
        assert (host,path.split('?')[0]) in self.requests, 'Fixture request did not reach loopback'
        return self.driver

    def restart(self):
        """Restart this disposable profile without reapplying initial preferences."""
        self.driver.quit()
        opts=Options();opts.binary_location=self.binary;opts.accept_insecure_certs=True
        opts.add_argument('-profile');opts.add_argument(str(Path(self.temp.name)/'profile'))
        if not self.headful: opts.add_argument('-headless')
        # Selenium wrote the initial options into user.js. Remove only this
        # fixture's initial override file so prefs.js carries the user's edits.
        (Path(self.temp.name)/'profile'/'user.js').unlink(missing_ok=True)
        self.driver=webdriver.Firefox(options=opts,service=Service(
            executable_path=os.environ.get('GECKODRIVER') or shutil.which('geckodriver'),
            service_args=['--allow-system-access'],log_output=str(self.report_path/'gecko-restart.log')))
        self.driver.set_script_timeout(45)
        self.default_handle=self.driver.current_window_handle
        return self.driver
