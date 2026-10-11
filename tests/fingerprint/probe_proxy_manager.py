"""Named HTTP/SOCKS authentication and failure isolation; loopback fixtures only.

Run with the project's CLOAKFOX_BIN and probe_daily_defaults launch helper.
No diagnostic provider or outside service is contacted.
"""
import base64
import http.server
import json
from pathlib import Path
import select
import socket
import socketserver
import struct
import tempfile
import threading
from probe_daily_defaults import launch
from probe_network_policy import READ

hits = []
http_attempts = []
socks_attempts = []


def relay(client, upstream):
    while True:
        ready, _, _ = select.select([client, upstream], [], [], 5)
        if not ready:
            return
        for source in ready:
            data = source.recv(65536)
            if not data:
                return
            (upstream if source is client else client).sendall(data)


class Origin(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Proxy credentials must be removed before requests inside the tunnel.
        assert not self.headers.get('Proxy-Authorization')
        hits.append(self.path)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'authenticated-route-ok')

    def log_message(self, *args):
        pass


class HTTPProxy(http.server.BaseHTTPRequestHandler):
    def do_CONNECT(self):
        expected = 'Basic ' + base64.b64encode(self.server.credential.encode()).decode()
        accepted = self.headers.get('Proxy-Authorization') == expected
        http_attempts.append((self.server.server_port, accepted))
        if not accepted:
            self.send_response(407)
            self.send_header('Proxy-Authenticate', 'Basic realm="fixture"')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        host, port = self.path.rsplit(':', 1)
        assert host == 'origin.test'
        with socket.create_connection(('127.0.0.1', int(port)), timeout=5) as upstream:
            self.send_response(200)
            self.end_headers()
            relay(self.connection, upstream)

    def log_message(self, *args):
        pass


def read_exact(sock, count):
    data = b''
    while len(data) < count:
        block = sock.recv(count - len(data))
        if not block:
            raise ConnectionError('Unexpected end of SOCKS request')
        data += block
    return data


class SOCKSProxy(socketserver.BaseRequestHandler):
    def handle(self):
        sock = self.request
        sock.settimeout(5)
        version, count = read_exact(sock, 2)
        assert version == 5
        assert 2 in read_exact(sock, count), 'Username/password not offered'
        sock.sendall(b'\x05\x02')
        version, length = read_exact(sock, 2)
        assert version == 1
        username = read_exact(sock, length)
        password = read_exact(sock, read_exact(sock, 1)[0])
        accepted = (username, password) == self.server.credentials
        socks_attempts.append(accepted)
        sock.sendall(b'\x01' + (b'\x00' if accepted else b'\x01'))
        if not accepted:
            return
        version, command, _, address_type = read_exact(sock, 4)
        assert (version, command, address_type) == (5, 1, 3), 'Destination DNS must stay at proxy'
        host = read_exact(sock, read_exact(sock, 1)[0]).decode()
        port = struct.unpack('!H', read_exact(sock, 2))[0]
        assert host == 'origin.test'
        with socket.create_connection(('127.0.0.1', port), timeout=5) as upstream:
            sock.sendall(b'\x05\x00\x00\x01\x7f\x00\x00\x01' + struct.pack('!H', port))
            relay(sock, upstream)


SAVE = """
const done=arguments[arguments.length-1];
const manager=ChromeUtils.importESModule('resource:///modules/CloakfoxProxyManager.sys.mjs');
manager.saveProxy(arguments[0]).then(entry=>done({entry}),()=>done({error:'save failed'}));
"""
BIND = """
const manager=ChromeUtils.importESModule('resource:///modules/CloakfoxProxyManager.sys.mjs');
manager.bindProxy(arguments[0],arguments[1]);
"""


def main():
    origin = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Origin)
    first = http.server.ThreadingHTTPServer(('127.0.0.1', 0), HTTPProxy)
    second = http.server.ThreadingHTTPServer(('127.0.0.1', 0), HTTPProxy)
    socks = socketserver.ThreadingTCPServer(('127.0.0.1', 0), SOCKSProxy)
    socks.daemon_threads = True
    first.credential = 'first:first-secret'
    second.credential = 'second:second-secret'
    socks.credentials = (b'socks-user', b'socks-secret')
    servers = (origin, first, second, socks)
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-proxy-manager-') as temp:
            profile = Path(temp) / 'profile'
            profile.mkdir()
            driver = launch(profile, Path(temp) / 'gecko.log')
            try:
                driver.set_script_timeout(25)
                driver.execute_script("Services.prefs.setBoolPref('dom.security.https_only_mode',false); Services.prefs.setStringPref('network.dns.localDomains','origin.test');")

                def save(name, url, username, password, proxy_id=None):
                    value = {'name': name, 'url': url, 'username': username, 'password': password}
                    if proxy_id:
                        value['id'] = proxy_id
                    result = driver.execute_async_script(SAVE, value)
                    assert 'entry' in result, result
                    assert 'password' not in result['entry'] and 'username' not in result['entry']
                    return result['entry']

                def request(path, ucid):
                    return driver.execute_async_script(READ, f'http://origin.test:{origin.server_port}{path}', ucid)

                p1 = save('First', f'http://127.0.0.1:{first.server_port}', 'first', 'first-secret')
                p2 = save('Second', f'http://127.0.0.1:{second.server_port}', 'second', 'second-secret')
                ps = save('SOCKS', f'socks5://127.0.0.1:{socks.server_address[1]}', 'socks-user', 'socks-secret')
                for ucid, proxy in ((1, p1), (2, p2), (3, ps)):
                    driver.execute_script(BIND, ucid, proxy['id'])
                    preflight = driver.execute_async_script("""
                      const ucid=arguments[0],done=arguments[arguments.length-1];
                      const m=ChromeUtils.importESModule('resource:///modules/CloakfoxProxyManager.sys.mjs');
                      m.resolveContainerProxy(ucid).then(entry=>{
                        try {
                          const pps=Cc['@mozilla.org/network/protocol-proxy-service;1'].getService(Ci.nsIProtocolProxyService);
                          const u=new URL(entry.url), type=u.protocol==='socks5:'?'socks':u.protocol.slice(0,-1);
                          const key=`cloakfox-managed:${ucid}:${entry.id}:${entry.revision}`;
                          const flags=Ci.nsIProxyInfo.TRANSPARENT_PROXY_RESOLVES_HOST|Ci.nsIProxyInfo.ALWAYS_TUNNEL_VIA_PROXY;
                          const pi=type==='socks'?pps.newProxyInfoWithAuth(type,u.hostname,Number(u.port),entry.username,entry.password,'',key,flags,0,null):
                            pps.newProxyInfo(type,u.hostname,Number(u.port),'Basic '+btoa(String.fromCharCode(...new TextEncoder().encode(`${entry.username}:${entry.password}`))),key,flags,0,null);
                          done({stage:'proxy-created',type:pi.type,credentialPresent:!!entry.username&&!!entry.password,
                            keyMatches:pi.connectionIsolationKey===key,revisionMatches:Services.prefs.getStringPref(`cloakfox.container.${ucid}.proxy_revision`,'')===entry.revision});
                        }catch(error){done({stage:'proxy-create-failed',errorName:error.name,errorCode:error.result});}
                      },async error=>{
                        const ref=m.getProxyReference(ucid),entry=m.listProxies().find(p=>p.id===ref);
                        const known=['Saved proxy is unavailable','Proxy route changed or credentials are unavailable','Proxy credentials are unavailable','Proxy credential store is ambiguous'];
                        let loginCount=-1;
                        try{loginCount=(await Services.logins.searchLoginsAsync({origin:`chrome://cloakfox-proxy-${ref}`,httpRealm:'Cloakfox named proxy'})).length;}catch(_){}
                        done({stage:'resolve-failed',errorName:error.name,errorCode:error.result,
                          reason:known.includes(error.message)?error.message:'unrecognized error',loginCount,
                          mode:Services.prefs.getIntPref(`cloakfox.container.${ucid}.network_mode`,-1),entryPresent:!!entry,
                          refMatches:entry?.id===ref,
                          urlMatches:entry?.url===Services.prefs.getStringPref(`cloakfox.container.${ucid}.proxy_url`,''),
                          revisionMatches:entry?.revision===Services.prefs.getStringPref(`cloakfox.container.${ucid}.proxy_revision`,'')});
                      });
                    """, ucid)
                    print('proxy preflight', ucid, preflight, flush=True)
                    result = request(f'/container-{ucid}', ucid)
                    print('proxy request', ucid, result, 'http-attempt-count',len(http_attempts),'socks-attempt-count',len(socks_attempts),flush=True)
                    assert result['status'] == 0 and result['body'] == 'authenticated-route-ok', result
                assert all(accepted for _, accepted in http_attempts) and socks_attempts == [True]
                # Same endpoint, different reference/credentials must not borrow an
                # established tunnel or browser-wide proxy authentication cache.
                wrong = save('Wrong identity', p1['url'], 'intruder', 'wrong-secret')
                driver.execute_script(BIND, 4, wrong['id'])
                before = len(http_attempts)
                assert request('/http-must-not-leak', 4)['status'] != 0
                assert '/http-must-not-leak' not in hits
                assert len(http_attempts) - before == 1, '407 unexpectedly retried'
                assert request('/first-still-works', 1)['status'] == 0
                save('SOCKS', ps['url'], 'socks-user', 'wrong-secret', ps['id'])
                assert request('/socks-must-not-leak', 3)['status'] != 0
                assert '/socks-must-not-leak' not in hits and socks_attempts[-1] is False
                # Restart-facing persisted bindings contain no login material.
                redacted = driver.execute_script("""
                  return Services.prefs.getChildList('cloakfox.').map(name=> {
                    try{return Services.prefs.getStringPref(name);}catch(_){return '';}
                  }).join('\\n');
                """)
                for secret in ('first-secret', 'second-secret', 'socks-secret', 'wrong-secret'):
                    assert secret not in redacted
                print(json.dumps({'originRequests':hits,'httpAttempts':len(http_attempts),'socksAttempts':len(socks_attempts)}))
                print('PASS: named HTTP/SOCKS auth, 407 no retry, DNS via SOCKS, connection isolation, no direct fallback, redaction')
            finally:
                driver.quit()
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
