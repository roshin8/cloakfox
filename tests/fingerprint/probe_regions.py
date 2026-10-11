"""Unified regions: loopback HTTP header, window/worker locale+DST and geo permission.

Run sequentially against rebuilt CLOAKFOX_BIN. Uses disposable profile and only
loopback requests; imports existing launch and container-tab helpers. Permission
is granted/denied through Firefox's real permission manager, not fake coordinates.
"""
import http.server
import json
import tempfile
import threading
from pathlib import Path
from selenium.webdriver.support.ui import WebDriverWait
from probe_daily_defaults import launch
from probe_container_workflows import open_site, switch_content

HEADERS = {}
MEASURE = """
const measure = () => ({languages:Array.from(navigator.languages), language:navigator.language,
 locale:new Intl.DateTimeFormat().resolvedOptions().locale,
 timezone:new Intl.DateTimeFormat().resolvedOptions().timeZone,
 explicit:new Intl.DateTimeFormat('ja-JP').resolvedOptions().locale,
 winter:new Date('2026-01-15T12:00:00Z').getTimezoneOffset(),
 summer:new Date('2026-07-15T12:00:00Z').getTimezoneOffset()});
"""

PAGE = """<!doctype html><title>Region probe</title>
<button id="measure">Measure region</button><button id="location">Read location</button>
<script>""" + MEASURE + """
document.getElementById('measure').addEventListener('click', () => {
  document.body.removeAttribute('data-region');
  const worker = new Worker('/worker.js');
  worker.onmessage = e => {
    worker.terminate();
    document.body.setAttribute('data-region', JSON.stringify({window:measure(),worker:e.data}));
  };
  worker.onerror = e => document.body.setAttribute('data-region', JSON.stringify({error:e.message}));
  worker.postMessage('measure');
});
document.getElementById('location').addEventListener('click', () => {
  document.body.removeAttribute('data-location');
  const done = result => document.body.setAttribute('data-location', JSON.stringify(result));
  navigator.geolocation.getCurrentPosition(p => done({latitude:p.coords.latitude,longitude:p.coords.longitude,accuracy:p.coords.accuracy}),
    e => done({error:e.code}), {timeout:8000,maximumAge:0});
});
</script>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        HEADERS[self.path] = self.headers.get('Accept-Language')
        body = (MEASURE + 'onmessage=()=>postMessage(measure());').encode() if self.path.startswith('/worker') else PAGE.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/javascript' if self.path.startswith('/worker') else 'text/html')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def page_result(driver, button, attribute):
    # All measurements execute in functions parsed by the page itself. Selenium
    # has a separate sandbox realm with its own host Date and Intl intrinsics.
    driver.execute_script("document.getElementById(arguments[0]).click()", button)
    raw = WebDriverWait(driver, 15).until(lambda d: d.execute_script(
        "return document.body.getAttribute(arguments[0])", attribute))
    return json.loads(raw)


def measure(driver):
    return page_result(driver, 'measure', 'data-region')


def location(driver):
    return page_result(driver, 'location', 'data-location')


def permission(driver, url, ucid, action):
    driver.set_context('chrome')
    driver.execute_script("""
const principal=Services.scriptSecurityManager.createContentPrincipal(Services.io.newURI(arguments[0]),{userContextId:arguments[1]});
Services.perms.addFromPrincipal(principal,'geo',arguments[2] === 'allow' ? Services.perms.ALLOW_ACTION : Services.perms.DENY_ACTION);
""", url, ucid, action)
    driver.set_context('content')


def main():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    regions = [
        dict(locale='de-DE', languages=['de-DE', 'de', 'en-US'], timezone='Europe/Berlin', geolocation=dict(latitude=52.52, longitude=13.4, accuracy=10000)),
        dict(locale='ja-JP', languages=['ja-JP', 'en-US'], timezone='Asia/Tokyo', geolocation=dict(latitude=35.68, longitude=139.76, accuracy=10000)),
    ]
    results = []
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-regions-') as temp:
            profile = Path(temp) / 'profile'; profile.mkdir()
            driver = launch(profile, Path(temp) / 'gecko.log')
            try:
                driver.set_script_timeout(20)
                ids = driver.execute_script("""
const {ContextualIdentityService:cis}=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
const {setRegion}=ChromeUtils.importESModule('resource:///modules/CloakfoxRegions.sys.mjs');
const {setContainerNetwork}=ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkPolicy.sys.mjs');
return arguments[0].map((region,i)=>{const id=cis.create('Region '+i,'fingerprint','blue').userContextId;setContainerNetwork(id,{mode:0,proxyURL:'',webrtcMode:2});setRegion(id,region);return id;});
""", regions)
                handles = []
                for i, (ucid, region) in enumerate(zip(ids, regions)):
                    url = f'{base}/region-{i}'
                    handle, actual_id = open_site(driver, url, ucid)
                    assert actual_id == ucid
                    handles.append(handle)
                    data = measure(driver)
                    assert 'error' not in data, data
                    for surface in data.values():
                        assert surface['languages'] == region['languages'], data
                        assert surface['language'] == region['languages'][0], data
                        assert surface['locale'] == region['locale'], data
                        assert surface['timezone'] == region['timezone'], data
                        assert surface['explicit'] == 'ja-JP', data
                        assert (surface['winter'], surface['summer']) == ((-60, -120) if i == 0 else (-540, -540)), data
                    expected_header = ','.join(tag if j == 0 else f'{tag};q={1-j/10:.1f}' for j, tag in enumerate(region['languages']))
                    assert HEADERS[f'/region-{i}'] == expected_header, HEADERS
                    assert HEADERS['/worker.js'] == expected_header, HEADERS
                    permission(driver, url, ucid, 'deny')
                    denied = location(driver); assert denied == {'error': 1}, denied
                    permission(driver, url, ucid, 'allow')
                    allowed = location(driver); assert allowed == region['geolocation'], allowed
                    results.append(dict(container=ucid, observed=data, denied=denied, allowed=allowed))
                # Return to A after reading B to catch ambient/cached cross-container reuse.
                switch_content(driver, handles[0])
                assert location(driver) == regions[0]['geolocation']
                assert measure(driver)['window']['locale'] == regions[0]['locale']
                assert HEADERS['/worker.js'] == 'de-DE,de;q=0.9,en-US;q=0.8', HEADERS
                print(json.dumps(results, indent=2))
            finally:
                driver.quit()
    finally:
        server.shutdown(); server.server_close()


if __name__ == '__main__':
    main()
