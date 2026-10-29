"""Two-peer datachannel negotiation with delayed DIRECT PAC and ICE restart.

Uses only loopback ICE/HTTP. The local answer starts ICE checks while proxy
lookup is outstanding; both peers must connect and exchange data, then do so
again after restart. No capture devices or external TURN services are used.
"""
from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import time
from probe_turn_proxy_privacy import TurnFixture
from screen_management_fixture import ScreenManagementFixture

PAIR=r'''
const [url, done] = arguments;
(async()=>{
  const config={iceServers:[{urls:url,username:'fixture',credential:'fixture'}],iceTransportPolicy:'all'};
  const a=new RTCPeerConnection(config),b=new RTCPeerConnection(config);
  const pendingA=[],pendingB=[];const errors=[];
  let finished=false;let messages=[];let answerAt,gatherDoneAt;const answersBeforeGather=[];
  const finish=value=>{if(finished)return;finished=true;a.close();b.close();done(value)};
  const fail=e=>finish({error:e.name||String(e),messages,errors,states:[a.iceConnectionState,b.iceConnectionState]});
  const sendCandidate=(pc,pending,e)=>{if(!e.candidate)return;
    if(pc.remoteDescription)pc.addIceCandidate(e.candidate).catch(e=>errors.push(e.name));else pending.push(e.candidate)};
  a.onicecandidate=e=>sendCandidate(b,pendingB,e);
  b.onicecandidate=e=>{if(!e.candidate)gatherDoneAt=performance.now();sendCandidate(a,pendingA,e)};
  let remoteChannel;
  b.ondatachannel=e=>{remoteChannel=e.channel;remoteChannel.onmessage=m=>remoteChannel.send('echo:'+m.data)};
  const channel=a.createDataChannel('queue-check');
  const receive=expected=>new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>reject(new Error('data timeout '+expected)),7000);
    channel.onmessage=e=>{messages.push(e.data);if(e.data===expected){clearTimeout(timer);resolve()}};
  });
  const negotiate=async restart=>{
    const offer=await a.createOffer({iceRestart:restart});await a.setLocalDescription(offer);
    await b.setRemoteDescription(offer);for(const c of pendingB.splice(0))await b.addIceCandidate(c);
    const answer=await b.createAnswer();await b.setLocalDescription(answer);answerAt=performance.now();answersBeforeGather.push(b.iceGatheringState!=='complete');
    await a.setRemoteDescription(answer);for(const c of pendingA.splice(0))await a.addIceCandidate(c);
  };
  setTimeout(()=>fail(new Error('connection timeout')),14000);
  try {
    const opened=new Promise((resolve,reject)=>{channel.onopen=resolve;channel.onerror=reject});
    await negotiate(false);await opened;
    let received=receive('echo:first');channel.send('first');await received;
    await negotiate(true);
    await new Promise((resolve,reject)=>{
      const end=performance.now()+6000;
      const check=()=>{if(a.iceGatheringState==='complete' && b.iceGatheringState==='complete')resolve();
        else if(performance.now()>end)reject(new Error('restart gather timeout'));else setTimeout(check,20)};
      setTimeout(check,20);
    });
    await new Promise(resolve=>setTimeout(resolve,300));
    received=receive('echo:restart');channel.send('restart');await received;
    finish({messages,errors,states:[a.iceConnectionState,b.iceConnectionState],answersBeforeGather});
  } catch(e){fail(e)}
})().catch(e=>done({error:e.name||String(e)}));
'''

def main():
    failures=[];results={}
    class Pac(BaseHTTPRequestHandler):
        def do_GET(self):
            time.sleep(.6)
            body=b"function FindProxyForURL(url,host){var end=Date.now()+250;while(Date.now()<end){} return 'DIRECT';}"
            self.send_response(200);self.send_header('Content-Type','application/x-ns-proxy-autoconfig');self.end_headers();self.wfile.write(body)
        def log_message(self,*_):pass
    pac=ThreadingHTTPServer(('127.0.0.1',0),Pac);Thread(target=pac.serve_forever,daemon=True).start()
    turn=TurnFixture()
    try:
        with ScreenManagementFixture() as f:
            d=f.driver;d.set_script_timeout(22)
            f.pref('cloakfox.webrtc.protect_proxy',True)
            f.pref('cloakfox.webrtc.protect_unready',False)
            f.pref('media.peerconnection.ice.loopback',True)
            f.pref('media.peerconnection.ice.obfuscate_host_addresses',False)
            f.pref('network.proxy.allow_hijacking_localhost',True)
            f.pref('network.proxy.no_proxies_on','')
            d.get(f.origin)
            for mode,name in [(0,'native direct negotiation'),(2,'delayed PAC local-answer negotiation')]:
                f.pref('network.proxy.autoconfig_url',f'http://127.0.0.1:{pac.server_port}/delayed-{mode}.pac')
                f.pref('network.proxy.type',mode)
                value=d.execute_async_script(PAIR,f'turn:127.0.0.1:{turn.port}?transport=udp')
                ok=value.get('messages')==['echo:first','echo:restart'] and not value.get('errors') and not value.get('error') and (mode==0 or value.get('answersBeforeGather',[False])[0])
                results[name]=value;print(('PASS ' if ok else 'FAIL ')+name+': '+json.dumps(value),flush=True)
                if not ok:failures.append(name)
            (f.report_path/'turn-proxy-negotiation.json').write_text(json.dumps(results,indent=2))
    finally:
        turn.close();pac.shutdown();pac.server_close()
    assert not failures,failures

if __name__=='__main__':main()
