"""Privacy enforcement regression; local origin, no physical capture or STUN."""
from screen_management_fixture import ScreenManagementFixture

def main():
    failures=[]
    def check(ok,name,value):
        print(('PASS ' if ok else 'FAIL ')+name+': '+str(value),flush=True)
        if not ok: failures.append(name)
    with ScreenManagementFixture() as f:
        d=f.driver
        f.pref('cloakfox.webrtc.external_ip_discovery',False)
        f.pref('media.navigator.streams.fake',True)
        f.pref('media.navigator.permission.disabled',True)
        f.pref('geo.prompt.testing',True)
        f.pref('geo.prompt.testing.allow',False)
        f.set_config(0,{'mediaDevices:enabled':False,'geolocation:latitude':40.0,'geolocation:longitude':-70.0,'geolocation:accuracy':50})
        f.chrome("const k='cloakfox.s.cloak_cfg_0';const c=JSON.parse(Services.prefs.getStringPref(k));delete c['webrtc:ipv4'];delete c['webrtc:ipv6'];Services.prefs.setStringPref(k,JSON.stringify(c))")
        d.get(f.origin)
        devices=d.execute_async_script('const done=arguments[0];navigator.mediaDevices.enumerateDevices().then(a=>done(a.length),e=>done(e.name));')
        check(devices==0,'disabled enumeration returns empty',devices)
        capture=d.execute_async_script('const done=arguments[0];navigator.mediaDevices.getUserMedia({video:true}).then(s=>{s.getTracks().forEach(t=>t.stop());done("unexpected stream")},e=>done(e.name));')
        check(capture=='NotAllowedError','disabled capture rejects before device access',capture)
        screen=d.execute_async_script('const done=arguments[0];navigator.mediaDevices.getDisplayMedia({video:true}).then(s=>{s.getTracks().forEach(t=>t.stop());done("unexpected stream")},e=>done(e.name));')
        check(screen=='NotAllowedError','disabled screen capture rejects before chooser',screen)
        geo=d.execute_async_script('const done=arguments[0];navigator.geolocation.getCurrentPosition(p=>done("unexpected location"),e=>done(e.code),{timeout:4000});')
        check(geo==1,'location respects denied prompt',geo)
        count=d.execute_async_script('''const done=arguments[0];const pc=new RTCPeerConnection({iceServers:[]});let count=0;let finished=false;
          function finish(){if(finished)return;finished=true;pc.close();done(count)}
          pc.onicecandidate=e=>{if(e.candidate?.candidate)count++;else if(!e.candidate)finish()};pc.setConfiguration({iceServers:[],iceTransportPolicy:'all'});pc.createDataChannel('test');
          pc.createOffer().then(o=>pc.setLocalDescription(o)).catch(e=>{pc.close();done(e.name+": "+e.message)});setTimeout(finish,3000);''')
        check(count==0,'unready WebRTC exposes no direct candidates',count)
        f.pref('cloakfox.webrtc.protect_unready',False)
        optout_count=d.execute_async_script('const done=arguments[0];const pc=new RTCPeerConnection({iceServers:[]});let n=0,finished=false;function finish(){if(finished)return;finished=true;pc.close();done(n)}pc.onicecandidate=e=>{if(e.candidate?.candidate)n++;else if(!e.candidate)finish()};pc.createDataChannel("native");pc.createOffer().then(o=>pc.setLocalDescription(o)).catch(e=>done(e.name));setTimeout(finish,3000);')
        check(isinstance(optout_count,int) and optout_count>0,'startup guard opt-out restores direct ICE',optout_count)
        f.pref('cloakfox.webrtc.protect_unready',True)
        f.pref('geo.prompt.testing.allow',True)
        d.refresh()
        allowed=d.execute_async_script('const done=arguments[0];navigator.geolocation.getCurrentPosition(p=>done([p.coords.latitude,p.coords.longitude]),e=>done(e.code),{timeout:4000});')
        check(allowed==[40,-70],'approved location still returns persona coordinates',allowed)
        f.set_config(2,{'mediaDevices:enabled':True})
        f.open(container=2)
        other=d.execute_async_script('const done=arguments[0];navigator.mediaDevices.enumerateDevices().then(a=>done(a.length));')
        check(other>0,'media policy stays scoped to its container',other)
        other_capture=d.execute_async_script('const done=arguments[0];navigator.mediaDevices.getUserMedia({video:true}).then(s=>{s.getTracks().forEach(t=>t.stop());done("fake stream")},e=>done(e.name));')
        check(other_capture=='fake stream','another container retains permitted fake capture',other_capture)

        f.open()
        f.set_master(False)
        d.refresh()
        native=d.execute_async_script('const done=arguments[0];navigator.mediaDevices.getUserMedia({video:true}).then(s=>{s.getTracks().forEach(t=>t.stop());done("fake stream")},e=>done(e.name));')
        check(native=='fake stream','master off restores native capture using fake test devices',native)
        native_count=d.execute_async_script('const done=arguments[0];const pc=new RTCPeerConnection({iceServers:[]});let n=0,finished=false;function finish(){if(finished)return;finished=true;pc.close();done(n)}pc.onicecandidate=e=>{if(e.candidate?.candidate)n++;else if(!e.candidate)finish()};pc.createDataChannel("native");pc.createOffer().then(o=>pc.setLocalDescription(o)).catch(e=>done(e.name));setTimeout(finish,3000);')
        check(isinstance(native_count,int) and native_count>0,'master off restores direct ICE gathering',native_count)

        d.get('about:cloakfox')
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        external='input[data-pref="cloakfox.webrtc.external_ip_discovery"]'
        protect='input[data-pref="cloakfox.webrtc.protect_unready"]'
        WebDriverWait(d,15).until(lambda d:d.find_elements(By.CSS_SELECTOR,external))
        check(not d.find_element(By.CSS_SELECTOR,external).is_selected(),'IP discovery starts disabled in Settings',False)
        check(d.find_element(By.CSS_SELECTOR,protect).is_selected(),'startup protection starts enabled in Settings',True)
        d.execute_script('document.getElementById("sec-hardening").open=true')
        toggle=d.find_element(By.CSS_SELECTOR,external)
        d.execute_script('arguments[0].scrollIntoView({block:"center"})',toggle)
        toggle.click() # master off: exercise persistence without contacting IP services
        d=f.restart();d.get('about:cloakfox')
        WebDriverWait(d,15).until(lambda d:d.find_elements(By.CSS_SELECTOR,external))
        check(d.find_element(By.CSS_SELECTOR,external).is_selected(),'IP discovery choice survives profile restart',True)
        check(not f.chrome('return Services.prefs.getBoolPref("cloakfox.enabled")'),'restart retains master-off policy',False)

    assert not failures, failures
if __name__=='__main__':main()
