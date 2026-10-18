"""Owned native screen/display fixtures; no challenge websites.

Covers the display group's first native hook: owner-provided panel geometry is
presented in Blink so `window.screen` and CSS device metrics agree instead of
exposing the host display, and a presentation without display fields keeps the
native panel (the toggle-off path).
"""
import copy
import http.server
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engines.shared.persona_config import PersonaStore
from probe_cef_isolation import Companion

READ = """async function display(){
 const s=window.screen;
 return {width:s.width,height:s.height,availWidth:s.availWidth,availHeight:s.availHeight,
  colorDepth:s.colorDepth,pixelDepth:s.pixelDepth,dpr:window.devicePixelRatio,
  color8:matchMedia("(color: 8)").matches,minColor10:matchMedia("(min-color: 10)").matches,
  hdr:matchMedia("(dynamic-range: high)").matches,
  p3:matchMedia("(color-gamut: p3)").matches,srgb:matchMedia("(color-gamut: srgb)").matches,
  deviceWidth:matchMedia("(device-width: "+s.width+"px)").matches,
  deviceHeight:matchMedia("(device-height: "+s.height+"px)").matches,
  minDeviceWidth:matchMedia("(min-device-width: "+s.width+"px)").matches};
}
"""
BASE={'hardwareConcurrency':4,'deviceMemory':4,'languages':['fr-FR','fr'],'timezone':'Europe/Paris'}
# 2560x1600 points is not a stock macOS panel size, so the native host panel
# cannot coincidentally equal the spoofed geometry.
PROFILE_A={**BASE,'screenWidth':2560,'screenHeight':1600,'screenAvailWidth':2560,'screenAvailHeight':1575}
PROFILE_B={**BASE,'screenWidth':1440,'screenHeight':900,'screenAvailWidth':1440,'screenAvailHeight':875}

class Fixture(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        raw=('<!doctype html><script>'+READ+'globalThis.firstDisplay=display();</script>').encode()
        self.send_response(200);self.send_header('Content-Type','text/html')
        self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers()
        self.wfile.write(raw)
    def log_message(self,*args):pass

class DisplayPrivacy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('CLOAKFOX_CHROMIUM_BIN'):raise unittest.SkipTest('Set CLOAKFOX_CHROMIUM_BIN')
        cls.binary=Path(os.environ['CLOAKFOX_CHROMIUM_BIN']);cls.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Fixture)
        threading.Thread(target=cls.server.serve_forever,daemon=True).start();cls.url=f'http://127.0.0.1:{cls.server.server_port}/'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
    def setUp(self):
        self.root=tempfile.TemporaryDirectory(prefix='cloakfox-display-');self.store=PersonaStore(Path(self.root.name)/'personas');self.app=Companion(self.binary,Path(self.root.name))
    def tearDown(self):self.app.close();self.root.cleanup()
    def configured(self,container='1',preset=PROFILE_A,enabled=True,**options):
        config=self.store.get(container,'chromium')
        config['persona']['presentation']=copy.deepcopy(preset)
        config['persona']['options'].update({'navigator':True,'language':True,'timezone':True,**options})
        config['enabled']=enabled
        ack=self.app.rpc('applyConfig',config=config);self.assertTrue(ack['ok'],ack)
        browser=self.app.open(container,self.url,configRevision=config['revision'])
        return browser
    def read(self,browser):return self.app.evaluate(browser,'(async()=>{'+READ+'return display()})()')
    def assert_presented(self,value,preset):
        self.assertEqual(value['width'],preset['screenWidth']);self.assertEqual(value['height'],preset['screenHeight'])
        self.assertEqual(value['availWidth'],preset['screenAvailWidth']);self.assertEqual(value['availHeight'],preset['screenAvailHeight'])
        self.assertLessEqual(value['availWidth'],value['width']);self.assertLessEqual(value['availHeight'],value['height'])
        self.assertEqual(value['colorDepth'],value['pixelDepth'])
        # An owner panel is a standard 24-bit SDR panel, so the host's 30-bit
        # HDR profile is not reported through screen or CSS colour queries.
        self.assertEqual(value['colorDepth'],24)
        self.assertTrue(value['color8']);self.assertFalse(value['minColor10'])
        self.assertFalse(value['hdr'])
        # CSS device metrics read the same native panel as window.screen.
        self.assertTrue(value['deviceWidth']);self.assertTrue(value['deviceHeight']);self.assertTrue(value['minDeviceWidth'])

    def test_owner_geometry_reaches_js_and_css_before_script(self):
        browser=self.configured('1',preset=PROFILE_A)
        first=self.app.evaluate(browser,'firstDisplay');self.assert_presented(first,PROFILE_A)
        loaded=self.read(browser);self.assertEqual(loaded,first)
        frame=self.app.evaluate(browser,"new Promise(r=>{const f=document.createElement('iframe');f.src='/';f.onload=()=>r({width:f.contentWindow.screen.width,height:f.contentWindow.screen.height});document.body.append(f)})")
        self.assertEqual((frame['width'],frame['height']),(PROFILE_A['screenWidth'],PROFILE_A['screenHeight']))

    def test_native_panel_returns_without_display_fields(self):
        browser=self.configured('2',preset=BASE)
        native=self.read(browser)
        self.assertNotEqual((native['width'],native['height']),(PROFILE_A['screenWidth'],PROFILE_A['screenHeight']),
                            'Legacy presentation must keep the native host panel, not the spoofed geometry')

    def test_screen_is_per_container(self):
        first=self.configured('1',preset=PROFILE_A);second=self.configured('2',preset=PROFILE_B)
        a=self.read(first);b=self.read(second);self.assert_presented(a,PROFILE_A);self.assert_presented(b,PROFILE_B)
        self.assertNotEqual((a['width'],a['height']),(b['width'],b['height']))

    def test_display_option_off_keeps_only_the_native_panel(self):
        browser=self.configured('4',preset=PROFILE_A,display=False)
        native=self.read(browser)
        self.assertNotEqual((native['width'],native['height']),(PROFILE_A['screenWidth'],PROFILE_A['screenHeight']),
                            'A disabled display option must keep the native host panel')
        identity=self.app.evaluate(browser,"({languages:Array.from(navigator.languages),timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,cores:navigator.hardwareConcurrency})")
        self.assertEqual(identity['languages'],PROFILE_A['languages'],'Display toggle must not disable the identity group')
        self.assertEqual(identity['timezone'],PROFILE_A['timezone'])
        self.assertEqual(identity['cores'],PROFILE_A['hardwareConcurrency'])

    def test_display_mask_hides_the_host_colour_profile(self):
        # The harness host is a 30-bit HDR panel, a rare enough profile to
        # identify the machine; the masked panel must not report it.
        spoofed=self.read(self.configured('5',preset=PROFILE_A))
        self.assert_presented(spoofed,PROFILE_A)
        host=self.read(self.configured('6',preset=BASE))
        self.assertNotEqual(host['colorDepth'],24,'Harness host is expected to be a non-24-bit panel')
        self.assertNotEqual(host['colorDepth'],spoofed['colorDepth'],
                            'Host colour depth must not be reported under the display mask')
        # Scope boundary: the retained real OS/brand keeps its display's gamut
        # and scale, because both are normal for the claimed device and forcing
        # them would either change rendering or make the profile less common.
        self.assertEqual(spoofed['p3'],host['p3']);self.assertEqual(spoofed['srgb'],host['srgb'])
        self.assertEqual(spoofed['dpr'],host['dpr'])

if __name__=='__main__':unittest.main()
