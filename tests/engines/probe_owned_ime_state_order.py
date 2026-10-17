"""Delay a real renderer while another origin gains password focus.

Owned loopback fixtures only. A short busy section in the original renderer
establishes ordering without test branches in the native implementation.
"""
import argparse
import http.server
import json
from pathlib import Path
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests/engines'))
from engines.shared.persona_config import PersonaStore
from test_offscreen_rendering import Windowless


class Deferred(Windowless):
    def __init__(self, *args, **kwargs):
        self.saved = []
        super().__init__(*args, **kwargs)

    def wait(self, match, timeout=30, allow_crash=False):
        for packet in list(self.saved):
            if match(packet):
                self.saved.remove(packet)
                return packet
        def capture(packet):
            if match(packet):
                return True
            if (packet.get('event') == 'ownedImeInvalidated' or 'id' in packet) and len(self.saved) < 64:
                self.saved.append(packet)
            return False
        return super().wait(capture, timeout, allow_crash)


class Fixture(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == '/blocked':
            self.server.blocked.set()
            body = b'ok'
        else:
            password = 'password' if self.headers.get('Host', '').startswith('localhost:') else 'text'
            parent = json.dumps('http://127.0.0.1:' + str(self.server.server_port))
            body = ('<!doctype html><style>html,body{margin:0}input{position:absolute;left:0;top:0}</style>'
                    '<input id=field type=' + password + '><script>onmessage=e=>{if(e.origin===' + parent +
                    "&&e.data==='focus')field.focus()}</script>").encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    args = parser.parse_args()
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    server.blocked = threading.Event()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-stale-frame-') as folder:
            root = Path(folder)
            app = Deferred(args.binary, root)
            try:
                config = PersonaStore(root / 'personas').get('1', 'chromium')
                assert app.rpc('applyConfig', config=config)['ok']
                browser = app.open('1', f'http://127.0.0.1:{server.server_port}/', configRevision=1)
                child = f'http://localhost:{server.server_port}/child'
                app.evaluate(browser, "new Promise(resolve=>{window.frame=document.createElement('iframe');"
                             "frame.style='position:absolute;left:0;top:100px;width:300px;height:150px;border:0';"
                             "frame.onload=()=>resolve(true);frame.src=" + json.dumps(child) +
                             ";document.body.append(frame)})")
                app.evaluate(browser, 'field.focus();true')
                deadline = time.monotonic() + 2
                while True:
                    first = app.rpc('textInputState', browser=browser, configRevision=1).get('state')
                    if first and first['editable']:
                        break
                    assert time.monotonic() < deadline, 'Focused editing metadata did not settle'
                    time.sleep(.01)
                assert not first['password'], first
                blocked_at=time.monotonic()
                app.evaluate(browser, "setTimeout(()=>{fetch('/blocked');const stop=Date.now()+2000;"
                             "while(Date.now()<stop){}},50);true")
                assert server.blocked.wait(2), 'Main renderer did not enter owned busy section'
                assert time.monotonic()-blocked_at<.75, 'Busy marker arrived too late to establish ordering'
                app.serial += 1
                stale = app.serial
                app.process.stdin.write(json.dumps({'version': 1, 'id': stale, 'command': 'textInputState',
                                                    'browser': browser, 'configRevision': 1}) + '\n')
                app.process.stdin.flush()
                for kind in ['mouseDown', 'mouseUp']:
                    assert app.rpc('input', browser=browser, configRevision=1, kind=kind, x=30, y=110)['ok']
                time.sleep(.1)
                deadline=time.monotonic()+2
                while True:
                    newer = app.rpc('textInputState', browser=browser, configRevision=1)
                    if newer.get('state', {}).get('password') is True:
                        break
                    assert time.monotonic()<deadline, ('Password focus failed', newer)
                    time.sleep(.01)
                assert newer['state']['field']['document'] != first['field']['document']
                old = app.wait(lambda packet: packet.get('id') == stale)
                assert old['applied'] is False and 'state' not in old, ('Stale frame metadata returned', old)
                print('PASS: delayed query rejected after cross-origin password frame focus')
            finally:
                app.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
