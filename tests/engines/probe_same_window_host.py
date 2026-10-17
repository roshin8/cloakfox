"""Native Gecko viewport acceptance with an owned Chromium fixture only."""
import argparse
import http.server
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import os
import signal
import subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from engines.shared.persona_config import PersonaStore
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from test_offscreen_rendering import Fixture


class HostFixture(Fixture):
    def do_GET(self):
        self.server.requests.append(self.path)
        if self.path=='/video-start':
            self.server.videoStart.wait(20)
            self.send_response(204);self.end_headers();return
        body=b"""<!doctype html><style>html,body{margin:0;background:rgb(13,37,91)}body{height:3000px}</style>
<input id="field"><select id="choice" style="position:absolute;left:40px;top:60px;width:200px"><option>First</option><option>Second</option><option>Third</option></select><script>field.oninput=()=>fetch('/typed',{method:'POST',body:field.value});
choice.onchange=()=>fetch('/selected',{method:'POST',body:choice.value});
fetch('/first-script',{method:'POST',body:JSON.stringify({ua:navigator.userAgent,cpu:navigator.hardwareConcurrency,language:navigator.language})});
onscroll=()=>fetch('/scrolled',{method:'POST',body:String(scrollY)});
</script>"""
        if self.server.passwordField:
            body=body.replace(b'<input id="field">',b'<input id="field" type="password">')
        if self.server.testVideo:
            body+=b"""<script>
(async()=>{await fetch('/video-start');
const source=document.createElement('canvas');source.width=source.height=64;
const context=source.getContext('2d');const colors=['rgb(20,80,140)','rgb(180,40,70)'];let index=0;
function draw(){context.fillStyle=colors[index++%2];context.fillRect(0,0,64,64)}draw();
const stream=source.captureStream(10);const video=document.createElement('video');
video.muted=true;video.playsInline=true;video.srcObject=stream;
video.style='position:fixed;inset:0;width:100%;height:100%;object-fit:fill';document.body.append(video);
let frames=0;const count=()=>{frames++;video.requestVideoFrameCallback(count)};video.requestVideoFrameCallback(count);
const timer=setInterval(draw,150);await video.play();
await new Promise(resolve=>setTimeout(resolve,2200));clearInterval(timer);
const state={frames,width:video.videoWidth,height:video.videoHeight};
stream.getTracks().forEach(track=>track.stop());video.remove();
await fetch('/video-state',{method:'POST',body:JSON.stringify(state)});
})().catch(error=>fetch('/video-state',{method:'POST',body:JSON.stringify({error:String(error)})}));
</script>"""
        self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_POST(self):
        self.server.requests.append(self.path)
        size=int(self.headers.get('Content-Length','0'))
        if size>1024:self.send_error(413);return
        value=self.rfile.read(size).decode('utf-8')
        if self.path=='/first-script':self.server.firstScript.append(json.loads(value))
        elif self.path=='/typed':self.server.nativeInputs.append(value)
        elif self.path=='/scrolled':self.server.scrollPositions.append(float(value))
        elif self.path=='/selected':self.server.selectedValues.append(value)
        elif self.path=='/video-state':self.server.videoStates.append(json.loads(value))
        self.send_response(204);self.end_headers()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--gecko-binary',type=Path,required=True)
    parser.add_argument('--chromium-binary',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--hold',type=int,default=0)
    parser.add_argument('--hold-resize',type=int,default=0)
    parser.add_argument('--hold-chrome',type=int,default=0)
    parser.add_argument('--gecko-compositor',action='store_true',default=True)
    parser.add_argument('--native-view',dest='gecko_compositor',action='store_false',help='Explicit legacy native-view diagnostic comparison')
    parser.add_argument('--presentation',choices=['same-window','separate-window'],default='same-window')
    parser.add_argument('--test-epoch-clear',action='store_true')
    parser.add_argument('--test-large-viewport',action='store_true')
    parser.add_argument('--expect-typed')
    parser.add_argument('--expect-typed-sequence',help='JSON array of successive /typed values that must all arrive in order')
    parser.add_argument('--password-field',action='store_true',help='Owned fixture password-input acceptance only')
    parser.add_argument('--expect-single-click',action='store_true')
    parser.add_argument('--expect-chrome-input')
    parser.add_argument('--expect-scroll',action='store_true')
    parser.add_argument('--expect-selection')
    parser.add_argument('--test-video',action='store_true')
    parser.add_argument('--test-native-window-close',action='store_true')
    parser.add_argument('--test-startup-cancel',action='store_true')
    parser.add_argument('--expect-network-gate-rejection',action='store_true')
    parser.add_argument('--test-input-state',action='store_true')
    parser.add_argument('--expect-input-state-rejection',action='store_true')
    args=parser.parse_args()
    typed_sequence=None
    if args.expect_typed_sequence is not None:
        typed_sequence=json.loads(args.expect_typed_sequence)
        assert (isinstance(typed_sequence,list) and typed_sequence and
                all(isinstance(value,str) for value in typed_sequence)),'--expect-typed-sequence must be a non-empty JSON array of strings'
        # The typing window is only polled under --hold; requiring it avoids
        # asserting before the caller has finished typing.
        if not args.hold:
            parser.error('--expect-typed-sequence requires --hold')
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),HostFixture)
    server.requests=[]
    server.nativeInputs=[]
    server.scrollPositions=[]
    server.selectedValues=[]
    server.testVideo=args.test_video
    server.passwordField=args.password_field
    server.videoStart=threading.Event()
    server.videoStates=[]
    server.firstScript=[]
    threading.Thread(target=server.serve_forever,daemon=True).start()
    driver=None
    owned_tokens=[]
    temporary=tempfile.TemporaryDirectory(prefix='cloakfox-same-window-')
    directory=temporary.name
    try:
        root=Path(directory);profile=root/'gecko';profile.mkdir(mode=0o700)
        chromium=root/'chromium';chromium.mkdir(mode=0o700)
        config=PersonaStore(root/'personas').get('1','chromium')
        options=Options();options.binary_location=str(args.gecko_binary.resolve())
        for arg in ('-no-remote','-purgecaches','-profile',str(profile)):options.add_argument(arg)
        options.set_preference('cloakfox.enabled',True)
        options.set_preference('browser.search.suggest.enabled',False)
        options.set_preference('browser.urlbar.suggest.searches',False)
        options.set_preference('cloakfox.engine_host.test.enabled',True)
        driver=webdriver.Firefox(options=options,service=Service(service_args=['--allow-system-access'],log_output=str(root/'geckodriver.log')))
        driver.set_window_size(1200,900);driver.set_script_timeout(60)
        driver.set_context('chrome')
        assert driver.execute_script("return '@cloakfox.org/engine-host;1' in Cc"),'Native Gecko viewport host is not registered'
        guards=driver.execute_script('return {pref:Services.prefs.getBoolPref("cloakfox.engine_host.test.enabled",false),system:window.document.nodePrincipal.isSystemPrincipal,sameDoc:gBrowser.selectedBrowser.ownerDocument===window.document,cloakfoxEnabled:Services.prefs.getBoolPref("cloakfox.enabled",false),resistFingerprinting:Services.prefs.getBoolPref("privacy.resistFingerprinting",false),buildID:Services.appinfo.appBuildID,version:Services.appinfo.version}')
        assert guards['pref'] and guards['system'] and guards['sameDoc'] and guards['cloakfoxEnabled'] and guards['resistFingerprinting'] is False,guards
        print('Native host guards:',json.dumps(guards),flush=True)
        script="""
const done=arguments[arguments.length-1];
window.hostService=ChromeUtils.importESModule('resource:///modules/CloakfoxEngineHost.sys.mjs').CloakfoxEngineHost;
window.hostService.openFixture(window,gBrowser.selectedBrowser,...arguments[0])
.then(token=>done({token}),e=>done({error:String(e)}));
"""
        if args.test_startup_cancel:
            cancelled=root/'cancelled';cancelled.mkdir(mode=0o700)
            result=driver.execute_async_script("""
const done=arguments[arguments.length-1];
const host=ChromeUtils.importESModule('resource:///modules/CloakfoxEngineHost.sys.mjs').CloakfoxEngineHost;
const tab=gBrowser.addTab('about:blank',{triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
const pending=host.openFixture(window,tab.linkedBrowser,...arguments[0]);
gBrowser.removeTab(tab,{animate:false});
pending.then(async token=>{await host.close(token);done({cancelled:false})},()=>done({cancelled:true}));
""",[str(args.chromium_binary.resolve()),str(cancelled),json.dumps(config),f'http://127.0.0.1:{server.server_port}/'])
            assert result.get('cancelled') is True,'Closing the startup owner did not cancel its native launch'
            deadline=time.monotonic()+3
            while True:
                commands=subprocess.check_output(['ps','-axo','command='],text=True)
                leaked=[line for line in commands.splitlines() if str(cancelled) in line or str(cancelled.resolve()) in line]
                if not leaked or time.monotonic()>=deadline:break
                time.sleep(.025)
            assert not leaked,'Cancelled startup left an owned helper process running'

        opened=driver.execute_async_script(script,[str(args.chromium_binary.resolve()),str(chromium),json.dumps(config),f'http://127.0.0.1:{server.server_port}/',args.gecko_compositor,args.presentation])
        if args.expect_network_gate_rejection or args.expect_input_state_rejection:
            expected='Native editing-state invalidation is unavailable' if args.expect_input_state_rejection else 'Native fixture network gate is unavailable'
            assert expected in opened.get('error',''),opened
            assert not server.requests,server.requests
            assert driver.execute_script('return !gBrowser.selectedBrowser.parentElement.querySelector("canvas[data-cloakfox-native-viewport]")'),'Rejected helper installed a surface'
            deadline=time.monotonic()+3
            while True:
                commands=subprocess.check_output(['ps','-axo','command='],text=True)
                leaked=[line for line in commands.splitlines() if str(chromium) in line or str(chromium.resolve()) in line]
                if not leaked or time.monotonic()>=deadline:break
                time.sleep(.025)
            assert not leaked,'Rejected helper did not retire'
            report={'status':'passed','scope':'Owned local fixture only','presentation':args.presentation,
                    'legacyNetworkGateRefused':args.expect_network_gate_rejection,'legacyInputStateGateRefused':args.expect_input_state_rejection,'fixtureRequests':len(server.requests),'gecko':guards}
            args.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return
        assert 'error' not in opened,opened
        token=opened['token'];owned_tokens.append(token)
        duplicate=root/'duplicate';duplicate.mkdir(mode=0o700)
        other_config=PersonaStore(root/'other-personas').get('2','chromium')
        second=driver.execute_async_script(script,[str(args.chromium_binary.resolve()),str(duplicate),json.dumps(other_config),f'http://127.0.0.1:{server.server_port}/'])
        if 'token' in second:owned_tokens.append(second['token'])
        assert 'error' in second and 'already owns' in second['error'], 'Duplicate browser owner was accepted'
        if args.presentation=='separate-window':
            state=driver.execute_script('return window.hostService.state(arguments[0])',token)
            assert state['presentation']=='separate-window' and state['topLevelWindow'] is True,state
            assert state['configRevision']==config['revision'] and state['helperPid']>0,state
            deadline=time.monotonic()+10
            while not server.firstScript and time.monotonic()<deadline:time.sleep(.025)
            assert server.firstScript,'The separate Chromium window did not execute the owned fixture'
            first=server.firstScript[-1]
            assert 'Chrome/154.' in first['ua'],first
            assert first['cpu']==config['persona']['presentation']['hardwareConcurrency'],first
            assert first['language']==config['persona']['presentation']['languages'][0],first
            assert driver.execute_script('return !gBrowser.selectedBrowser.parentElement.querySelector("canvas[data-cloakfox-native-viewport]")'),'Separate presentation installed an overlay'
            pid=state['helperPid']
            if args.test_native_window_close:
                args.report.with_suffix('.live.json').write_text(json.dumps({**state,'phase':'close-separate-native-window'}))
                retired=False;deadline=time.monotonic()+60
                while time.monotonic()<deadline:
                    retired=driver.execute_script('try{window.hostService.state(arguments[0]);return false}catch{return true}',token)
                    if retired:break
                    time.sleep(.1)
                assert retired,'Closing the native window did not retire its Gecko session'
            driver.execute_async_script('const done=arguments[arguments.length-1];window.hostService.close(arguments[0]).then(()=>done());',token)
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                try:os.kill(pid,0)
                except ProcessLookupError:break
                time.sleep(.025)
            else:raise AssertionError('Closing the owner left its separate helper running')
            report={'status':'passed','scope':'Owned local fixture only; production privacy parity remains pending','gecko':guards,'presentation':state,'duplicateOwnerRejected':True,'ownerCloseRetiredHelper':not args.test_native_window_close,'nativeWindowCloseRetiredHelper':args.test_native_window_close,'firstScript':first}
            args.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return
        deadline=time.monotonic()+30;state=None
        while time.monotonic()<deadline:
            state=driver.execute_script('return window.hostService.state(arguments[0])',token)
            if state.get('painted'):break
            time.sleep(.05)
        assert state and state.get('painted'),state
        if args.gecko_compositor:
            assert state.get('presentation')=='gecko-compositor','Owned surface is not in the Gecko compositor'
            composited=driver.execute_script('const c=gBrowser.selectedBrowser.parentElement.querySelector("canvas[data-cloakfox-native-viewport]");return c?{system:c.ownerDocument.nodePrincipal.isSystemPrincipal,pixel:Array.from(c.getContext("2d").getImageData(c.width-1,c.height-1,1,1).data)}:null')
            assert composited and composited['system'] is True and composited['pixel']==[13,37,91,255],composited
        if args.test_input_state:
            editing=driver.execute_script("""
const token=arguments[0];const service=Cc['@cloakfox.org/engine-host;1'].getService(Ci.nsICloakfoxEngineHost);
const route=JSON.parse(service.state(token));
const state={field:{document:'a'.repeat(32),node:7},editable:true,password:false,selection:[0,0],composition:null,caret:[4,8,0,18]};
service.setInputState(token,route.configRevision,route.viewportRevision,JSON.stringify(state));
const ready=JSON.parse(service.state(token)).inputClientReady;
let rejected=0;
for(const invalid of [{...state,value:'private text'},{...state,editable:1},{...state,caret:[0,0,4097,18]},{...state,selection:[2,1]}]) {
 try{service.setInputState(token,route.configRevision,route.viewportRevision,JSON.stringify(invalid))}catch{rejected++}
}
try{service.setInputState(token,route.configRevision,route.viewportRevision+1,JSON.stringify(state))}catch{rejected++}
const preserved=JSON.parse(service.state(token)).inputClientReady;
let invalidationRejected=false;
try{service.invalidateInputState(token,route.configRevision+1,route.viewportRevision)}catch{invalidationRejected=true}
service.invalidateInputState(token,route.configRevision,route.viewportRevision);
const invalidated=!JSON.parse(service.state(token)).inputClientReady;
service.setInputState(token,route.configRevision,route.viewportRevision,JSON.stringify(state));
service.setInputState(token,route.configRevision,route.viewportRevision,JSON.stringify({field:null,editable:false,password:false,selection:null,composition:null,caret:null}));
return {ready,preserved,rejected,invalidationRejected,invalidated,cleared:!JSON.parse(service.state(token)).inputClientReady};
""",token)
            assert editing=={'ready':True,'preserved':True,'rejected':5,'invalidationRejected':True,'invalidated':True,'cleared':True},editing
        if args.test_epoch_clear:
            assert args.gecko_compositor,'Epoch clear requires the compositor presentation'
            # Advance native ownership without informing CEF. Every old-epoch
            # paint is rejected, so this samples before any replacement paint.
            cleared=driver.execute_script("""
const service=Cc['@cloakfox.org/engine-host;1'].getService(Ci.nsICloakfoxEngineHost);
const c=gBrowser.selectedBrowser.parentElement.querySelector('canvas[data-cloakfox-native-viewport]');
const r=gBrowser.selectedBrowser.getBoundingClientRect();
service.updateViewport(arguments[0],Math.round(r.x),Math.round(r.y),c.width+1,c.height,true);
return Array.from(c.getContext('2d').getImageData(c.width-1,c.height-1,1,1).data);
""",token)
            assert cleared==[0,0,0,0],f'Stale viewport pixels survived epoch change: {cleared}'
            driver.execute_script('window.dispatchEvent(new Event("resize"))')
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                state=driver.execute_script('return window.hostService.state(arguments[0])',token)
                if state.get('painted'):break
                time.sleep(.025)
            assert state.get('painted'),'The owner failed to repaint after an epoch clear'
        assert state['cornerBGRA']==[91,37,13,255],state
        assert state['nativeWindowMatches'] is True and state['topLevelWindow'] is False,state
        assert state['configRevision']==config['revision'],state
        assert state['helperPid']>0 and state['nativeWindowId']>0,state
        if args.hold:
            args.report.with_suffix('.live.json').write_text(json.dumps(state))
            deadline=time.monotonic()+min(args.hold,120)
            while time.monotonic()<deadline:
                state=driver.execute_script('return {...window.hostService.state(arguments[0]),ownerSelected:gBrowser.selectedBrowser===document.activeElement,activeElement:document.activeElement?.localName,windowActive:Services.focus.activeWindow===window,modal:window.windowUtils.isInModalState()}',token)
                args.report.with_suffix('.live.json').write_text(json.dumps({**state,'nativeInputs':list(server.nativeInputs),'scrollPositions':list(server.scrollPositions),'selectedValues':list(server.selectedValues)}))
                typed_ready=args.expect_typed is None or bool(server.nativeInputs and server.nativeInputs[-1]==args.expect_typed)
                sequence_ready=typed_sequence is None or server.nativeInputs[:len(typed_sequence)]==typed_sequence
                scroll_ready=not args.expect_scroll or any(y>0 for y in server.scrollPositions)
                selection_ready=args.expect_selection is None or bool(server.selectedValues and server.selectedValues[-1]==args.expect_selection)
                if (args.expect_typed is not None or typed_sequence is not None or args.expect_scroll or args.expect_selection is not None) and typed_ready and sequence_ready and scroll_ready and selection_ready:break
                time.sleep(.2)
        if args.expect_typed is not None:
            assert server.nativeInputs and server.nativeInputs[-1]==args.expect_typed,server.nativeInputs
        if typed_sequence is not None:
            # Intermediate values matter: a final Select All + replacement can
            # hide a dropped accent/dead-key commit, so every step must arrive.
            # Use distinct expected steps so adjacent duplicates cannot fill a
            # dropped slot; entries after the prefix (the replacement) are left
            # to --expect-typed.
            assert server.nativeInputs[:len(typed_sequence)]==typed_sequence,('Intermediate typed text missing',list(server.nativeInputs))
        if args.expect_scroll:
            assert any(y>0 for y in server.scrollPositions),'Native scroll did not reach the owned page'
        if args.expect_selection is not None:
            assert server.selectedValues and server.selectedValues[-1]==args.expect_selection,server.selectedValues
        video_colors=[]
        if args.test_video:
            server.videoStart.set()
            seen=set();deadline=time.monotonic()+8
            while time.monotonic()<deadline:
                state=driver.execute_script('return window.hostService.state(arguments[0])',token)
                pixel=state.get('cornerBGRA',[])
                for index,color in enumerate(([140,80,20,255],[70,40,180,255])):
                    if len(pixel)==4 and all(abs(actual-expected)<=5 for actual,expected in zip(pixel,color)):
                        seen.add(index)
                        if pixel not in video_colors:video_colors.append(pixel)
                if len(seen)==2 and server.videoStates and pixel==[91,37,13,255]:break
                time.sleep(.025)
            assert len(seen)==2,'Two native video colors did not reach Gecko: '+str(video_colors)
            assert server.videoStates and server.videoStates[-1].get('frames',0)>=2,server.videoStates
            assert server.videoStates[-1].get('width')==64 and server.videoStates[-1].get('height')==64,server.videoStates
            assert state['cornerBGRA']==[91,37,13,255],'Video disposal did not restore the owned page'
        if args.expect_single_click:
            assert state.get('pointerEvents')==1 and state.get('keyboardEvents',0)>=1,state
        if args.expect_chrome_input:
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                state=driver.execute_script('return window.hostService.state(arguments[0])',token)
                chrome_input=driver.execute_script('return gURLBar.inputField.value')
                args.report.with_suffix('.live.json').write_text(json.dumps({**state,'nativeInputs':list(server.nativeInputs),'phase':'chrome-input','chromeInput':chrome_input}))
                if chrome_input==args.expect_chrome_input:break
                time.sleep(.2)
            assert chrome_input==args.expect_chrome_input,'Keyboard shortcut failed to focus the address bar'
            assert server.nativeInputs[-1]==args.expect_typed,'Address-bar input was delivered to the page'
            if args.hold_chrome:
                args.report.with_suffix('.live.json').write_text(json.dumps({**state,'phase':'chrome-popup','chromeInput':chrome_input,'nativeInputs':list(server.nativeInputs)}))
                time.sleep(min(args.hold_chrome,30))

        # Match native geometry/clipping to the real Gecko letterbox. A changed
        # surface size requires a new owned frame; a clip-only change does not.
        resized=[]
        for width,height in ((760,580),(1280,880)):
            previous_sequence=state['sequence'];previous_size=(state.get('viewWidth'),state.get('viewHeight'))
            driver.set_window_size(width,height)
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                state=driver.execute_script('return window.hostService.state(arguments[0])',token)
                geometry=driver.execute_script('const r=gBrowser.selectedBrowser.getBoundingClientRect(),p=gBrowser.selectedBrowser.parentElement.getBoundingClientRect();return {width:Math.round(r.width),height:Math.round(r.height),clipWidth:Math.round(Math.max(0,Math.min(r.right,p.right)-Math.max(r.left,p.left))),clipHeight:Math.round(Math.max(0,Math.min(r.bottom,p.bottom)-Math.max(r.top,p.top)))}')
                if (state.get('painted') and state.get('sequence',0)>=previous_sequence and
                    state.get('viewWidth')==geometry['width'] and state.get('viewHeight')==geometry['height'] and
                    state.get('clipWidth')==geometry['clipWidth'] and state.get('clipHeight')==geometry['clipHeight']):break
                time.sleep(.05)
            assert state.get('viewWidth')==geometry['width'] and state.get('viewHeight')==geometry['height'],state
            assert state['painted'] and state['sequence']>=previous_sequence and state['cornerBGRA']==[91,37,13,255],state
            assert state.get('clipWidth')==geometry['clipWidth'] and state.get('clipHeight')==geometry['clipHeight'],state
            if previous_size!=(state['viewWidth'],state['viewHeight']):
                assert state['sequence']>previous_sequence,'Changed surface size has no new frame'
            assert state['nativeWindowMatches'] and state['topLevelWindow'] is False,state
            if args.gecko_compositor:
                canvas_state=driver.execute_script('const b=gBrowser.selectedBrowser,r=b.getBoundingClientRect(),c=b.parentElement.querySelector("canvas[data-cloakfox-native-viewport]"),p=c.getBoundingClientRect();return {dx:p.x-r.x,dy:p.y-r.y,dw:p.width-r.width,dh:p.height-r.height,width:c.width,height:c.height,pixel:Array.from(c.getContext("2d").getImageData(c.width-1,c.height-1,1,1).data)}')
                assert all(abs(canvas_state[k])<.1 for k in ('dx','dy','dw','dh')),canvas_state
                assert (canvas_state['width'],canvas_state['height'])==(state['viewWidth'],state['viewHeight']),canvas_state
                assert canvas_state['pixel']==[13,37,91,255],canvas_state
            resized.append(geometry)
            if len(resized)==1 and args.hold_resize:
                args.report.with_suffix('.live.json').write_text(json.dumps({**state,'phase':'small-window','geometry':geometry}))
                time.sleep(min(args.hold_resize,30))

        if args.test_large_viewport:
            # The physical display need not be 4K: lay out an oversized owned
            # viewport and verify clipped one-to-one native/compositor geometry.
            driver.execute_script("window.originalBrowserStyle=gBrowser.selectedBrowser.getAttribute('style');gBrowser.selectedBrowser.style.cssText+=';width:2560px!important;min-width:2560px!important;max-width:2560px!important;height:800px!important;min-height:800px!important;max-height:800px!important';window.dispatchEvent(new Event('resize'))")
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                state=driver.execute_script('return window.hostService.state(arguments[0])',token)
                large=driver.execute_script('const b=gBrowser.selectedBrowser,c=b.parentElement.querySelector("canvas[data-cloakfox-native-viewport]"),r=b.getBoundingClientRect(),p=c?.getBoundingClientRect();return {browserWidth:r.width,canvasWidth:p?.width,canvasHeight:p?.height,pixel:c?Array.from(c.getContext("2d").getImageData(c.width-1,c.height-1,1,1).data):null}')
                if state.get('painted') and state.get('viewWidth')==2560:break
                time.sleep(.05)
            assert state['viewWidth']==2560 and large['browserWidth']==2560,(state,large)
            if args.gecko_compositor:
                assert large['canvasWidth']==state['viewWidth'] and large['canvasHeight']==state['viewHeight'],large
                assert large['pixel']==[13,37,91,255],large
            driver.execute_script("if(window.originalBrowserStyle===null)gBrowser.selectedBrowser.removeAttribute('style');else gBrowser.selectedBrowser.setAttribute('style',window.originalBrowserStyle);window.dispatchEvent(new Event('resize'))")
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                state=driver.execute_script('return window.hostService.state(arguments[0])',token)
                if state.get('painted') and state.get('viewWidth')<2560:break
                time.sleep(.05)
            assert state.get('painted') and state['viewWidth']<2560,state

        # Switching Gecko tabs must hide this native viewport immediately.
        driver.execute_script("window.hostOwnerTab=gBrowser.selectedTab;window.otherTab=gBrowser.addTab('about:blank',{triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});gBrowser.selectedTab=window.otherTab")
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            hidden=driver.execute_script('return window.hostService.state(arguments[0]).visible',token)
            if hidden is False:break
            time.sleep(.025)
        assert hidden is False,'Native Chromium pixels remained over another tab'
        hidden_state=driver.execute_script('return window.hostService.state(arguments[0])',token)
        assert (hidden_state['viewWidth'],hidden_state['viewHeight'])==(state['viewWidth'],state['viewHeight']),'Hidden tab changed renderer dimensions'
        driver.execute_script('gBrowser.selectedTab=window.hostOwnerTab')
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            restored=driver.execute_script('return window.hostService.state(arguments[0])',token)
            if restored.get('visible') and restored.get('painted'):break
            time.sleep(.025)
        assert restored.get('visible') and restored.get('painted'),'Returning to owner tab did not restore its surface'
        assert restored['helperPid']==state['helperPid'],'Returning to tab replaced its owned helper'
        os.kill(state['helperPid'],signal.SIGKILL)
        deadline=time.monotonic()+3
        revoked=False
        while time.monotonic()<deadline:
            try:driver.execute_script('return window.hostService.state(arguments[0])',token)
            except Exception:revoked=True;break
            time.sleep(.025)
        assert revoked,'Native helper death did not revoke its viewport'
        if args.gecko_compositor:
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                canvas_retired=driver.execute_script('const c=gBrowser.selectedBrowser.parentElement.querySelector("canvas[data-cloakfox-native-viewport]");return !c || Array.from(c.getContext("2d").getImageData(c.width-1,c.height-1,1,1).data).every(x=>x===0)')
                if canvas_retired:break
                time.sleep(.025)
            assert canvas_retired,'Retired helper pixels remain in the chrome compositor'
        driver.execute_script('window.hostService.close(arguments[0])',token)
        report={'status':'passed','scope':'Scripted native runtime checks; visual popup/screenshot acceptance is separate','gecko':guards,'frame':state,'wrongTabHidden':True,'helperDeathRevoked':True,'startupCancelled':args.test_startup_cancel,'duplicateOwnerRejected':True,'resizedViewports':resized,'tabRestored':True,'hiddenRendererSizePreserved':True,'epochClearTested':args.test_epoch_clear,'largeViewportTested':args.test_large_viewport,'nativeInputs':list(server.nativeInputs),'nativeScrollTested':args.expect_scroll,'scrollPositions':list(server.scrollPositions),'selectedValues':list(server.selectedValues),'nativeVideoTested':args.test_video,'nativeEditingStateTested':args.test_input_state,'typedSequenceExpected':typed_sequence,'typedSequenceVerified':typed_sequence is not None,'typedSequenceObserved':(list(server.nativeInputs[:len(typed_sequence)]) if typed_sequence is not None else None),'videoColors':video_colors,'videoStates':list(server.videoStates)}
        args.report.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        server.videoStart.set()
        try:
            if driver:
                try:
                    if owned_tokens:
                        driver.execute_async_script("const done=arguments[arguments.length-1];Promise.allSettled(arguments[0].map(token=>window.hostService.close(token))).then(()=>done());",owned_tokens)
                finally:driver.quit()
        finally:
            temporary.cleanup()
            server.shutdown();server.server_close()
if __name__=='__main__':main()
