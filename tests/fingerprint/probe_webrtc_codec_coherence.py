"""Compare permission-free RTC codec offers across owners and native controls.

No setLocalDescription, ICE gathering, public STUN/TURN or capture. Raw SDP,
ICE credentials and certificate fingerprints are never written to the report.
Catches per-container codec drift and capability/SDP contradictions; this does
not validate packet routing, real encoding or remote media delivery.
"""
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from probe_daily_defaults import launch
from probe_container_workflows import chrome, open_site

COLLECT = r"""
const pc=new RTCPeerConnection({iceServers:[]});
try {
 const capabilities={};
 for(const kind of ['audio','video']){
  pc.addTransceiver(kind,{direction:'sendrecv'});
  capabilities[kind]={send:RTCRtpSender.getCapabilities(kind).codecs,receive:RTCRtpReceiver.getCapabilities(kind).codecs};
 }
 const offer=await pc.createOffer();
 const sections=offer.sdp.split(/\r?\nm=/).slice(1).map(raw=>{
  const lines=raw.split(/\r?\n/),media=lines[0].split(' ');
  return {kind:media[0],payloads:media.slice(3),codecs:lines.filter(l=>l.startsWith('a=rtpmap:')).map(l=>{
   const [,pt,name,clock,channels]=/^a=rtpmap:(\d+) ([^/]+)\/(\d+)(?:\/(\d+))?$/.exec(l);
   return {pt,mimeType:media[0]+'/'+name.toLowerCase(),clockRate:Number(clock),channels:Number(channels||1)};
  }),parameters:lines.filter(l=>/^a=(fmtp:|rtcp-fb:|extmap:)/.test(l)).sort()};
 });
 return {capabilities,sections,signalingState:pc.signalingState,gathering:pc.iceGatheringState,localDescription:pc.localDescription};
}finally{pc.close();}
"""
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  body=b'<!doctype html><title>Local codec consistency</title>'
  self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass

def main():
 out=Path(os.environ.get('REPORT_DIR','/tmp/cloakfox-rtc-codecs'));out.mkdir(parents=True,exist_ok=True)
 report={'binary':os.environ['CLOAKFOX_BIN'],'cases':[],'checks':[],'captureOrGatheringStarted':False}
 def check(ok,label):
  report['checks'].append({'pass':bool(ok),'name':label});print(('PASS ' if ok else 'FAIL ')+label,flush=True);assert ok,label
 def signature(c):return (c['mimeType'].lower(),c['clockRate'],c.get('channels',1))
 server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with tempfile.TemporaryDirectory(prefix='cloakfox-codec-coherence-') as temp:
   profile=Path(temp)/'profile';profile.mkdir();d=launch(profile,out/'gecko.log');d.set_script_timeout(30)
   try:
    ids=chrome(d,"return ['RTC A','RTC B'].map(n=>cis.create(n,'fingerprint','blue').userContextId)")
    for label,owner,enabled in [('A',ids[0],True),('B',ids[1],True),('A-return',ids[0],True),('native-control',ids[0],False)]:
     chrome(d,"Services.prefs.setBoolPref('cloakfox.enabled',arguments[0]);",enabled)
     _,actual=open_site(d,f'http://127.0.0.1:{server.server_port}/?case={label}',owner)
     check(actual==owner,label+' uses exact container')
     data=d.execute_async_script("const done=arguments[arguments.length-1];(async()=>{"+COLLECT+"})().then(value=>done({value}),error=>done({error:String(error)}));")
     check('error' not in data,label+' creates native codec offer')
     row=data['value'];report['cases'].append({'label':label,'protected':enabled,**row})
     check(row['signalingState']=='stable' and row['gathering']=='new' and row['localDescription'] is None,label+' never starts ICE gathering')
     check({s['kind'] for s in row['sections']}=={'audio','video'},label+' offers both audio and video')
     for section in row['sections']:
      kind=section['kind'];offered={signature(c) for c in section['codecs']}
      check(bool(offered),label+'/'+kind+' has actual codec mappings')
      check({c['pt'] for c in section['codecs']}==set(section['payloads']),label+'/'+kind+' payload IDs have complete SDP mappings')
      for direction in ('send','receive'):
       caps={signature(c) for c in row['capabilities'][kind][direction]}
       check(bool(caps) and caps<=offered,label+'/'+kind+'/'+direction+' capabilities are negotiable in native SDP')
    protected=report['cases'][:3];baseline=report['cases'][3]
    for row in protected:
     check(row['capabilities']==baseline['capabilities'],row['label']+' reported codecs match native control')
     check(row['sections']==baseline['sections'],row['label']+' SDP codec parameters match native control')
    chrome(d,"Services.prefs.setBoolPref('cloakfox.enabled',true);")
   finally:d.quit()
 finally:
  server.shutdown();server.server_close();(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 return 0
if __name__=='__main__':raise SystemExit(main())
