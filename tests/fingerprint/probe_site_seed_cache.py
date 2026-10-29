"""Live cache invalidation/isolation and geometry cost; disposable headless profile.

No external connections required. Uses real NSS, document ownership and clocks.
"""
import json
import os
import statistics
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from probe_daily_defaults import launch
from probe_container_workflows import chrome, open_site

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body=b'<!doctype html><div id="target" style="position:absolute;left:20px;top:20px;width:123px;height:45px">Probe</div>'
        self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass

READ="""const e=document.getElementById('target');const b=e.getBoundingClientRect(),c=e.getClientRects()[0];return {bound:[b.x,b.y,b.width,b.height],client:[c.x,c.y,c.width,c.height]};"""

def main():
    report={'checks':[],'binary':os.environ['CLOAKFOX_BIN']}
    out=Path(os.environ.get('REPORT_DIR','tests/fingerprint/reports/site-seed-cache'));out.mkdir(parents=True,exist_ok=True)
    def check(name,condition):
        report['checks'].append({'name':name,'pass':bool(condition)})
        assert condition,name
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-site-cache-') as temp:
            d=launch(Path(temp),out/'gecko.log',purge_caches=True)
            try:
                report['buildID']=chrome(d,'return Services.appinfo.appBuildID;')
                chrome(d,"Services.prefs.setBoolPref('cloakfox.enabled',true);Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',false);Services.prefs.setBoolPref('dom.security.https_only_mode',false);")
                a,b=chrome(d,"return [cis.create('Cache A','fingerprint','blue').userContextId,cis.create('Cache B','fingerprint','red').userContextId];")
                cfg={'canvas:seed':123456,'fingerprint:secret':'A'*43+'=','privacy:policy':{'version':1,'preset':'standard','exceptions':[]}}
                # Realistic large persona payload, same protected geometry.
                full=dict(cfg,**{f'ignored:fixture:{i}':'value'*10 for i in range(90)})
                def configure(owner,value):
                    chrome(d,"Services.prefs.setStringPref('cloakfox.s.cloak_cfg_'+arguments[0],arguments[1]);",owner,json.dumps(value) if isinstance(value,dict) else value)
                    d.set_context('content')
                def read():return d.execute_script(READ)
                url=f'http://127.0.0.1:{server.server_port}/'
                _,owner=open_site(d,url,a);check('real container A ownership',owner==a)
                configure(a,full);first=read();check('bounding/client equality',first['bound']==first['client']);check('protected dimensions',first['bound'][2]!=123)
                check('hot cache stable',all(read()==first for _ in range(10)))
                d.refresh();check('reload stable',read()==first)
                configure(a,cfg);check('same protected geometry with smaller payload',read()==first)
                timings={}
                for name,config in [('full',full),('minimal',cfg),('full-repeat',full)]:
                    configure(a,config);read();values=[]
                    for _ in range(5):
                        start=time.perf_counter();width=d.execute_script("let sum=0;const e=document.getElementById('target');for(let i=0;i<2000;i++)sum+=e.getBoundingClientRect().width;return sum;")
                        values.append(round((time.perf_counter()-start)*1000,2));check(name+' identical output',width==first['bound'][2]*2000)
                    timings[name]={'wallMs':values,'medianMs':statistics.median(values)}
                report['timings']=timings
                configure(a,dict(cfg,**{'canvas:seed':654321}));check('seed rotation invalidates',read()!=first)
                configure(a,dict(cfg,**{'fingerprint:secret':'B'*43+'='}));check('secret rotation invalidates',read()!=first)
                configure(a,cfg);check('restoring config restores output',read()==first)
                exception=dict(cfg,**{'privacy:policy':{'version':1,'preset':'standard','exceptions':[{'site':'http://127.0.0.1','expiresAt':int(time.time()*1000)+1500,'vectors':['geometry']}]}})
                configure(a,exception);check('new exception overrides warm cache',read()['bound'][2]==123)
                time.sleep(1.6);check('exception expires without changing bytes',read()==first)
                configure(a,'{broken');check('invalid config does not reuse secret',read()['bound'][2]==123)
                configure(a,cfg);check('valid recovery',read()==first)
                chrome(d,"Services.prefs.setBoolPref('cloakfox.enabled',false);");d.set_context('content');check('master off invalidates',read()['bound'][2]==123)
                chrome(d,"Services.prefs.setBoolPref('cloakfox.enabled',true);");d.set_context('content');check('master on restores',read()==first)
                d.get(url.replace('127.0.0.1','localhost'));check('different site differs',read()!=first)
                d.get(url);check('return to site restores',read()==first)
                _,owner=open_site(d,url+"?owner=b",b);check('real container B ownership',owner==b)
                configure(b,dict(cfg,**{'canvas:seed':222222}));check('other owner differs',read()!=first)
                open_site(d,url+"?return=a",a);check('owner A survived owner B',read()==first)
                open_site(d,url+"?owner=default",0);configure(0,dict(cfg,**{'canvas:seed':333333}));check('default owner independent',read()!=first)
                open_site(d,url+"?return=again",a);check('owner A survived default owner',read()==first)
            finally:d.quit()
    finally:
        server.shutdown();server.server_close();(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'checks':len(report['checks']),'failed':sum(not x['pass'] for x in report['checks']),'timings':report['timings']},indent=2))

if __name__=='__main__':main()
