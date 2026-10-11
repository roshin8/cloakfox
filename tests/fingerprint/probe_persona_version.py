"""Fresh and migrated identities match the engine in DOM and HTTP, without seed rotation."""
import http.server
import json
from pathlib import Path
import re
import tempfile
import threading
from probe_daily_defaults import launch

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({'ua': self.headers.get('User-Agent')}).encode()
        self.send_response(200); self.send_header('Content-Type','text/plain')
        self.end_headers(); self.wfile.write(body)
    def log_message(self, *args): pass

def main():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-persona-version-') as temp:
            profile=Path(temp)/'profile'; profile.mkdir()
            previous_seed = None
            for phase in ('fresh', 'migrated'):
                driver = launch(profile, Path(temp)/f'{phase}.log')
                try:
                    state=driver.execute_script('''
                      Services.prefs.setBoolPref('dom.security.https_only_mode', false);
                      return {version: Services.appinfo.version,
                        seed: Services.prefs.getStringPref('cloakfox.container.0.math_seed'),
                        cfg: JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_0'))};
                    ''')
                    version=f'{int(state["version"].split(".")[0])}.0'
                    assert f'Firefox/{version}' in state['cfg']['navigator.userAgent'], state
                    if previous_seed: assert state['seed'] == previous_seed
                    driver.set_context('content')
                    driver.get(f'http://127.0.0.1:{server.server_port}/{phase}')
                    observed=driver.execute_script('return {dom: navigator.userAgent, http: JSON.parse(document.body.textContent).ua};')
                    assert observed['dom'] == state['cfg']['navigator.userAgent'], observed
                    assert observed['http'] == state['cfg']['headers.User-Agent'], observed
                    print(json.dumps({'phase':phase,'engine':state['version'],'observed':observed},indent=2))
                    driver.set_context('chrome')
                    if phase == 'fresh':
                        previous_seed=state['seed']
                        driver.execute_script('''
                          const key='cloakfox.s.cloak_cfg_0', cfg=JSON.parse(Services.prefs.getStringPref(key));
                          for (const field of ['navigator.userAgent','headers.User-Agent','navigator.appVersion'])
                            cfg[field]=cfg[field].replace(/rv:[0-9.]+/g,'rv:146.0').replace(/Firefox\\/[0-9.]+/g,'Firefox/146.0');
                          Services.prefs.setStringPref(key,JSON.stringify(cfg));
                          Services.prefs.savePrefFile(null);
                        ''')
                finally: driver.quit()
        print('PASS: fresh and legacy migrated persona match engine over DOM and HTTP; seed retained')
    finally: server.shutdown()
if __name__ == '__main__': main()
