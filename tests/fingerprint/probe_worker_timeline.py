"""Dedicated/shared/service worker timing, observer and option controls."""
import json
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from probe_daily_defaults import launch

WORKER='''
async function inspect(port, url) {
  const observed=[];
  const observer=new PerformanceObserver(list=>observed.push(...list.getEntries()));
  observer.observe({entryTypes:['resource','mark']});
  const before=performance.now();
  const mark=performance.mark('clock');
  const after=performance.now();
  const explicit=performance.mark('explicit',{startTime:123.25});
  await (await fetch(url)).text();
  await new Promise(resolve=>setTimeout(resolve,100));
  const resource=performance.getEntriesByType('resource').find(e=>e.name===url);
  const now=Array.from({length:10000},()=>performance.now());
  const result={before,after,mark:mark.startTime,explicit:explicit.startTime,
    native:Function.prototype.toString.call(Performance.prototype.now),
    monotonic:now.every((t,i)=>!i||t>=now[i-1]),
    fractional:now.some(t=>t%1!==0),
    resource:resource?.toJSON(), resourceNames:performance.getEntriesByType('resource').map(e=>e.name),
    observed:observed.find(e=>e.entryType==='resource'&&e.name===url)?.toJSON()};
  observer.disconnect();port.postMessage(result);
}
'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        scripts={
          '/worker.js':WORKER+'onmessage=e=>inspect(self,e.data);',
          '/shared.js':WORKER+'onconnect=e=>{const p=e.ports[0];p.onmessage=e=>inspect(p,e.data);p.start();};',
          '/sw.js':WORKER+'onmessage=e=>inspect(e.ports[0],e.data);',
        }
        body=scripts.get(self.path,'<!doctype html><title>Local worker timing fixture</title>')
        self.send_response(200)
        self.send_header('Content-Type','application/javascript' if self.path in scripts else 'text/html')
        self.send_header('Cache-Control','no-store')
        self.end_headers();self.wfile.write(body.encode())
    def log_message(self,*args):pass


def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{server.server_port}'
    report={}
    with tempfile.TemporaryDirectory(prefix='cloakfox-worker-timeline-') as temp:
        profile=Path(temp)/'profile';profile.mkdir()
        # Production retains its resource-timing preference. Explicitly enable
        # this opt-in surface in the fixture to exercise native worker getters.
        (profile/'user.js').write_text('user_pref("dom.enable_resource_timing",true);\n')
        d=launch(profile,Path(temp)/'gecko.log');d.set_script_timeout(25)
        def content():d.set_context('content');d.get(url+'/')
        try:
            d.execute_script("Services.prefs.setBoolPref('dom.security.https_only_mode',false); Services.prefs.setBoolPref('dom.enable_resource_timing',true);")
            content()
            scripts={
              'dedicated':'''const [url,done]=arguments;const w=new Worker('/worker.js');w.onmessage=e=>{w.terminate();done(e.data);};w.postMessage(url);''',
              'shared':'''const [url,done]=arguments;const w=new SharedWorker('/shared.js');w.port.onmessage=e=>{w.port.close();done(e.data);};w.port.start();w.port.postMessage(url);''',
              'service':'''const [url,done]=arguments;
                navigator.serviceWorker.register('/sw.js').then(async reg=>{
                  await navigator.serviceWorker.ready;
                  const c=new MessageChannel();c.port1.onmessage=async e=>{await reg.unregister();done(e.data);};
                  reg.active.postMessage(url,[c.port2]);
                }).catch(e=>done({error:e.name}));''',
            }
            for label,script in scripts.items():
                result=d.execute_async_script(script,url+'/resource?'+label)
                print(json.dumps({'type':label,'result':result}),flush=True)
                assert 'error' not in result,result
                assert result['before']<=result['mark']<=result['after'],result
                assert result['explicit']==123.25 and result['monotonic'],result
                assert '[native code]' in result['native'],result
                assert result['fractional'],('Worker still uses a separate raw clock',label,result)
                resource=result['resource'];assert resource==result['observed'],result
                assert resource['responseEnd']>=resource['startTime'],resource
                assert abs(resource['duration']-(resource['responseEnd']-resource['startTime']))<1e-9,resource
                assert resource['responseEnd']%1!=0,resource
                report[label]=result
            for label,pref in [('optionOff','cloakfox.opt.timer_high_precision_jitter'),('masterOff','cloakfox.enabled')]:
                d.set_context('chrome');d.execute_script("Services.prefs.setBoolPref('cloakfox.enabled',true); Services.prefs.setBoolPref('cloakfox.opt.timer_high_precision_jitter',true); Services.prefs.setBoolPref(arguments[0],false);",pref)
                content()
                result=d.execute_async_script(scripts['dedicated'],url+'/resource?'+label)
                assert not result['fractional'],result
                assert result['resource']['responseEnd']%1==0,result
                report[label]=result
            print(json.dumps(report,indent=2))
            print('PASS: all three worker types share native timing; explicit User Timing, observer and off controls retained')
        finally:d.quit();server.shutdown();server.server_close()


if __name__=='__main__':main()
