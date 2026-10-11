"""Same-global timing option changes and delayed field reads, local only."""
import json
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from selenium.webdriver.support.ui import WebDriverWait
from probe_daily_defaults import launch


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'''<!doctype html><div containertiming="local-container" style="font-size:50px">Timing container</div>
          <script>window.containers=[];new PerformanceObserver(l=>containers.push(...l.getEntries()))
          .observe({type:'container',buffered:true});</script>'''
        self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(body)
    def log_message(self, *args): pass


def main():
    server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/'
    with tempfile.TemporaryDirectory(prefix='cloakfox-timing-controls-') as temp:
        profile = Path(temp)/'profile'; profile.mkdir()
        d = launch(profile, Path(temp)/'gecko.log'); d.set_script_timeout(20)
        def chrome(script, *args):
            d.set_context('chrome')
            try: return d.execute_script(script, *args)
            finally: d.set_context('content')
        try:
            chrome("Services.prefs.setBoolPref('dom.security.https_only_mode',false);Services.prefs.setBoolPref('dom.enable_resource_timing',true);Services.prefs.setBoolPref('dom.enable_container_timing',true)")
            report = {}
            for pref in ('cloakfox.opt.timer_high_precision_jitter','cloakfox.enabled'):
                chrome("Services.prefs.setBoolPref('cloakfox.enabled',true);Services.prefs.setBoolPref('cloakfox.opt.timer_high_precision_jitter',true)")
                d.get(url)
                d.execute_async_script('''const done=arguments[0];fetch('/resource?'+Math.random()).then(r=>r.text()).then(()=>setTimeout(done,50));''')
                WebDriverWait(d, 10).until(lambda x: x.execute_script('return containers.length>0'))
                initial = d.execute_script('''window.entry=performance.getEntriesByType('resource').find(e=>e.name.includes('/resource?'));
                  window.container=containers[0];window.start=entry.startTime;window.paint=container.startTime;
                  return {start,paint};''')
                chrome("Services.prefs.setBoolPref(arguments[0],false)", pref)
                result = d.execute_script('''const xs=Array.from({length:10000},()=>performance.now());
                  return {start:entry.startTime,end:entry.responseEnd,duration:entry.duration,
                    paint:container.startTime,first:container.firstRenderTime,
                    fractional:xs.some(x=>x%1!==0),monotonic:xs.every((x,i)=>i===0||x>=xs[i-1])};''')
                assert result['start'] == initial['start'] and result['paint'] == initial['paint'], result
                assert result['end']%1 != 0 and result['first']%1 != 0, ('Delayed getter changed presentation mode',result)
                assert result['end'] >= result['start'] and result['duration'] >= 0, result
                assert abs(result['duration']-(result['end']-result['start']))<1e-9, result
                assert result['fractional'] and result['monotonic'], ('Existing clock mode changed',result)
                # New globals must respect the changed switches.
                d.refresh()
                native = d.execute_script('return Array.from({length:1000},()=>performance.now()).every(x=>x%1===0)')
                assert native, 'Reload did not apply disabled presentation'
                report[pref] = {'existingGlobalStable':True,'delayedFieldsStable':True,'reloadApplies':True}
            print(json.dumps(report,indent=2)); print('PASS: immutable global timing mode, delayed container/resource fields, monotonic clock and reload controls')
        finally: d.quit(); server.shutdown(); server.server_close()


if __name__=='__main__':main()
