"""Real popup storage must inherit its opener's persistent/private container."""
import http.server
import json
import os
from pathlib import Path
import socketserver
import tempfile
import threading
import time
import unittest
from probe_cef_isolation import Companion


class LoopbackServer(http.server.ThreadingHTTPServer):
    def server_bind(self):
        # Avoid reverse-DNS lookup while binding this numeric owned fixture.
        socketserver.TCPServer.server_bind(self)
        self.server_name = 'localhost'
        self.server_port = self.server_address[1]


class Fixture(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'<!doctype html><title>Owned popup fixture</title>'
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class PopupIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        binary = os.environ.get('CLOAKFOX_CHROMIUM_BIN')
        if not binary:
            raise unittest.SkipTest('Set CLOAKFOX_CHROMIUM_BIN to a built companion')
        cls.binary = Path(binary).resolve()
        cls.server = LoopbackServer(('127.0.0.1', 0), Fixture)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        self.profile = tempfile.TemporaryDirectory(prefix='cloakfox-popup-')
        self.app = Companion(self.binary, Path(self.profile.name).resolve())

    def tearDown(self):
        try:
            self.app.close()
        finally:
            self.profile.cleanup()

    def popup(self, opener):
        self.app.serial += 1
        request = {'version': 1, 'id': self.app.serial, 'command': 'cdp',
                   'browser': opener, 'method': 'Runtime.evaluate',
                   'params': {'expression': f'window.open({json.dumps(self.url)}, "_blank"); true',
                              'userGesture': True}}
        self.app.process.stdin.write(json.dumps(request) + '\n')
        self.app.process.stdin.flush()
        event = self.app.wait(lambda value: value.get('event') == 'opened' and value.get('browser') != opener)
        end = time.monotonic() + 15
        while time.monotonic() < end:
            if self.app.evaluate(event['browser'], 'document.readyState + ":" + location.href') == 'complete:' + self.url:
                return event
            time.sleep(.05)
        self.fail('Popup did not finish navigating')

    def close_browser(self, browser):
        self.assertTrue(self.app.rpc('close', browser=browser)['ok'])
        self.app.wait(lambda value: value.get('event') == 'closed' and value.get('browser') == browser)

    def test_popup_inherits_persistent_container_storage(self):
        a = self.app.open('1', self.url)
        b = self.app.open('2', self.url)
        self.app.evaluate(a, 'localStorage.owner = "A"')
        self.app.evaluate(b, 'localStorage.owner = "B"')
        popup = self.popup(a)
        self.assertEqual(popup['container'], '1')
        self.assertFalse(popup['private'])
        self.assertEqual(self.app.evaluate(popup['browser'], 'localStorage.owner'), 'A')
        self.app.evaluate(popup['browser'], 'localStorage.owner = "popup-A"')
        self.close_browser(a)
        self.assertEqual(self.app.evaluate(popup['browser'], 'localStorage.owner'), 'popup-A')
        self.assertEqual(self.app.evaluate(b, 'localStorage.owner'), 'B')

    def test_private_popup_keeps_context_only_until_last_private_window_closes(self):
        persistent = self.app.open('1', self.url)
        self.app.evaluate(persistent, 'localStorage.owner = "persistent"')
        private = self.app.open('1', self.url, private=True)
        self.app.evaluate(private, 'localStorage.owner = "private"')
        popup = self.popup(private)
        self.assertEqual(popup['container'], '1')
        self.assertTrue(popup['private'])
        self.assertEqual(self.app.evaluate(popup['browser'], 'localStorage.owner'), 'private')
        self.close_browser(private)
        self.assertEqual(self.app.evaluate(popup['browser'], 'localStorage.owner'), 'private')
        self.close_browser(popup['browser'])
        reopened = self.app.open('1', self.url, private=True)
        self.assertIsNone(self.app.evaluate(reopened, 'localStorage.getItem("owner")'))
        self.assertEqual(self.app.evaluate(persistent, 'localStorage.owner'), 'persistent')


if __name__ == '__main__':
    unittest.main()
