"""Real Necko routing in disposable profile; loopback origin/proxy only."""
import http.server
import json
from pathlib import Path
import select
import socket
import tempfile
import threading
from probe_daily_defaults import launch

hits = []
tunnels = []
class Origin(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        hits.append(self.path)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'origin-ok')
    def log_message(self, *args): pass

class Proxy(http.server.BaseHTTPRequestHandler):
    def do_CONNECT(self):
        tunnels.append(self.path)
        host, port = self.path.rsplit(':', 1)
        if host == 'origin.test': host = '127.0.0.1'
        with socket.create_connection((host, int(port)), timeout=5) as upstream:
            self.send_response(200, 'Connection established')
            self.end_headers()
            streams = [self.connection, upstream]
            while True:
                ready, _, _ = select.select(streams, [], [], 5)
                if not ready: return
                for source in ready:
                    data = source.recv(65536)
                    if not data: return
                    (upstream if source is self.connection else self.connection).sendall(data)
    def log_message(self, *args): pass

READ = """
const [url, ucid] = arguments, done = arguments[arguments.length - 1];
const {NetUtil} = ChromeUtils.importESModule('resource://gre/modules/NetUtil.sys.mjs');
const uri = Services.io.newURI(url);
const principal = arguments[2] === true ? Services.scriptSecurityManager.getSystemPrincipal() :
 Services.scriptSecurityManager.createContentPrincipal(uri, {userContextId: ucid});
const channel = NetUtil.newChannel({uri, loadingPrincipal: principal,
 securityFlags: Ci.nsILoadInfo.SEC_ALLOW_CROSS_ORIGIN_SEC_CONTEXT_IS_NULL,
 contentPolicyType: Ci.nsIContentPolicy.TYPE_OTHER});
channel.loadFlags |= Ci.nsIRequest.LOAD_BYPASS_CACHE;
let body = '';
channel.asyncOpen({
 onStartRequest(request) { this.proxy = request.QueryInterface(Ci.nsIProxiedChannel).proxyInfo?.host || null; },
 onDataAvailable(request, stream, offset, count) {
   body += NetUtil.readInputStreamToString(stream, count);
 },
 onStopRequest(request, status) {done({status, body, proxy:this.proxy, ucid: request.loadInfo.originAttributes.userContextId});}
});
"""
SET = """
const {setContainerNetwork} = ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkPolicy.sys.mjs');
setContainerNetwork(arguments[0], arguments[1]);
"""

def main():
    origin = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Origin)
    proxy = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Proxy)
    for server in (origin, proxy):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-routing-') as temp:
            profile = Path(temp) / 'profile'; profile.mkdir()
            driver = launch(profile, Path(temp) / 'gecko.log')
            try:
                driver.set_script_timeout(20)
                print('routing startup', driver.execute_script("""
                  const pps=Cc['@mozilla.org/network/protocol-proxy-service;1'].getService(Ci.nsIProtocolProxyService);
                  return {filters:pps.hasProxyFilterRegistered};
                """),flush=True)
                driver.execute_script("Services.prefs.setBoolPref('dom.security.https_only_mode', false); Services.prefs.setStringPref('network.dns.localDomains','origin.test');")
                base = f'http://origin.test:{origin.server_port}'
                def request(path, ucid):
                    result = driver.execute_async_script(READ, base + path, ucid)
                    assert result['ucid'] == ucid, result
                    return result
                assert request('/direct', 1)['body'] == 'origin-ok'
                driver.execute_script(SET, 2, {'mode': 1, 'proxyURL': f'http://127.0.0.1:{proxy.server_port}'})
                assert request('/proxied', 2)['body'] == 'origin-ok'
                assert tunnels, 'Configured proxy never received CONNECT'
                loopback = driver.execute_async_script(READ, f'http://127.0.0.1:{origin.server_port}/native-bypass', 2)
                assert loopback['status'] != 0 and '/native-bypass' not in hits, loopback
                # Closed local port: proxy refusal must not become a direct request.
                with socket.socket() as reserved:
                    reserved.bind(('127.0.0.1', 0)); dead_port = reserved.getsockname()[1]
                driver.execute_script(SET, 2, {'mode': 1, 'proxyURL': f'http://127.0.0.1:{dead_port}'})
                assert request('/must-not-leak', 2)['status'] != 0
                assert '/must-not-leak' not in hits, hits
                driver.execute_script(SET, 2, {'mode': 2})
                assert request('/blocked', 2)['status'] != 0
                assert '/blocked' not in hits, hits
                assert request('/other-container', 1)['body'] == 'origin-ok'
                driver.execute_script(SET, 0, {'mode':2})
                assert request('/default-blocked',0)['status'] != 0
                background = driver.execute_async_script(READ, base + '/browser-background', 0, True)
                assert background['body'] == 'origin-ok', background
                driver.execute_script("Services.prefs.setStringPref('cloakfox.container.2.network_mode','invalid');")
                assert request('/invalid-type',2)['status'] != 0
                assert '/invalid-type' not in hits and '/default-blocked' not in hits, hits
                print(json.dumps({'originRequests': hits, 'proxyTunnels': tunnels}, indent=2))
                print('PASS: real proxy routing, refusal has no fallback, blocked scope, other container unaffected')
            finally: driver.quit()
    finally:
        origin.shutdown(); proxy.shutdown()

if __name__ == '__main__': main()
