"""Native screen API contracts, scope, topology, policy and owner lifetime."""
import json
from screen_management_fixture import ScreenManagementFixture, CHROME, FIREFOX, PAGE

COLLECT = '''const done=arguments[0];
(async()=>{
 const a=await getScreenDetails(),b=await getScreenDetails(); window.savedDetails=a;
 const count=a.screens.length;
 function require(value,message){if(!value)throw Error(message)}
 require(a===b,'details identity');require(a.screens===b.screens,'array identity');
 require(Object.isFrozen(a.screens),'frozen array');require(a.currentScreen===a.screens[0],'current index');
 require(a instanceof ScreenDetails && a.screens.every(s=>s instanceof ScreenDetailed && s instanceof Screen),'brands');
 require(getScreenDetails.toString().includes('[native code]'),'native function');
 require(Object.hasOwn(window,'getScreenDetails')===Object.hasOwn(window,'alert'),'native Window member placement');
 require(Object.prototype.toString.call(a)==='[object ScreenDetails]' && Object.prototype.toString.call(a.screens[0])==='[object ScreenDetailed]','native brands');
 for(const [C,key] of [[ScreenDetailed,'devicePixelRatio'],[ScreenDetailed,'isPrimary'],[ScreenDetails,'currentScreen'],[Screen,'isExtended']]){
  const desc=Object.getOwnPropertyDescriptor(C.prototype,key);require(desc&&typeof desc.get==='function'&&!desc.set&&desc.enumerable&&desc.configurable,'readonly descriptor '+key);
 }
 const primary=a.currentScreen;require(['width','height','left','top','availWidth','availHeight','availLeft','availTop','colorDepth','pixelDepth'].every(k=>primary[k]===screen[k]),'primary agrees with ordinary screen');
 require(primary.orientation.type===screen.orientation.type&&primary.orientation.angle===screen.orientation.angle,'primary orientation');

 for(const C of [ScreenDetails,ScreenDetailed]){let failed=false;try{new C()}catch(e){failed=e.name==='TypeError'}require(failed,'illegal construction')}
 let illegal=false;try{await getScreenDetails.call({})}catch(e){illegal=e.name==='TypeError'}require(illegal,'illegal receiver');
 let readonly=false;try{(()=>{'use strict';a.screens[0]=null})()}catch(e){readonly=e.name==='TypeError'}require(readonly,'frozen mutation');
 const rows=a.screens.map((s,i)=>({width:s.width,height:s.height,left:s.left,top:s.top,
  availWidth:s.availWidth,availHeight:s.availHeight,availLeft:s.availLeft,availTop:s.availTop,
  depth:s.colorDepth,pixelDepth:s.pixelDepth,dpr:s.devicePixelRatio,type:s.orientation.type,angle:s.orientation.angle,
  primary:s.isPrimary,internal:s.isInternal,label:s.label}));
 for(const [target,event,handler] of [[a,'screenschange','onscreenschange'],[a,'currentscreenchange','oncurrentscreenchange'],[a.screens[0],'change','onchange']]){
  let calls=0;const fn=()=>calls++;target.addEventListener(event,fn);target.dispatchEvent(new Event(event));
  target.removeEventListener(event,fn);target.dispatchEvent(new Event(event));require(calls===1,'listener removal '+event);
  target[handler]=fn;target.dispatchEvent(new Event(event));require(calls===2,'event handler '+event);target[handler]=null;
 }
 require(rows[0].dpr===devicePixelRatio,'window DPR');
 window.trustedTopology=[];
 for(const [target,event] of [[a,'screenschange'],[a,'currentscreenchange'],[a.screens[0],'change'],[screen.orientation,'change']])target.addEventListener(event,e=>{if(e.isTrusted)trustedTopology.push(event)});
 return {rows,extended:screen.isExtended,support:firstSupport,origin:location.origin,secure:isSecureContext,
  descriptor:(()=>{const d=Object.getOwnPropertyDescriptor(ScreenDetailed.prototype,'devicePixelRatio');return {getter:typeof d.get,setter:typeof d.set,enumerable:d.enumerable,configurable:d.configurable}})(),own:Object.hasOwn(window,'getScreenDetails')};
})().then(done,e=>done({error:e.name,message:e.message}));'''


QUERY = """const done=arguments[0];(async()=>{
 const status=await navigator.permissions.query({name:'window-management'});
 let result='absent';if(typeof getScreenDetails==='function'){try{await getScreenDetails();result='resolved'}catch(e){result=e.name}}
 return {state:status.state,result};
})().then(done,e=>done({error:e.name,message:e.message}));"""


def run_policy(f):
    d=f.driver
    def query(state='granted',result='resolved'):
        value=d.execute_async_script(QUERY)
        assert value=={'state':state,'result':result},value
        return value
    f.set_config(0,{'navigator.userAgent':CHROME,'permissions:spoof':True})
    f.set_master(True);f.set_feature(True);f.set_origins([f.origin]);d=f.open()
    query()
    cases=[('modern',{'Permissions-Policy':'window-management=()'},True),
      ('spaced',{'Permissions-Policy':' window-management=() '},True),
      ('dictionary',{'Permissions-Policy':'camera=(self), window-management=(), microphone=()'},True),
      ('unrelated',{'Permissions-Policy':'camera=()'},False),
      ('nonempty',{'Permissions-Policy':'window-management=(self)'},False),
      ('malformed',{'Permissions-Policy':'window-management=('},False),
      ('lookalike',{'Permissions-Policy':'x-window-management=()'},False),
      ('boolean',{'Permissions-Policy':'window-management=?0'},False),
      ('legacy',{'Feature-Policy':"window-management 'none'"},True)]
    f.pref('dom.security.featurePolicy.header.enabled',True)
    for name,headers,denied in cases:
        f.routes['/policy-'+name]=(PAGE,headers);d=f.open('/policy-'+name)
        query('denied' if denied else 'granted','NotAllowedError' if denied else 'resolved')
        if denied:
            result=d.execute_async_script("""const done=arguments[0],frame=document.createElement('iframe');frame.allow='window-management *';frame.src='/';
              frame.onload=async()=>{const win=frame.contentWindow;const state=(await win.navigator.permissions.query({name:'window-management'})).state;
                let result;try{await win.getScreenDetails();result='resolved'}catch(e){result=e.name}frame.remove();done({state,result})};document.body.append(frame);""")
            assert result=={'state':'denied','result':'NotAllowedError'},result
    f.pref('dom.security.featurePolicy.header.enabled',False);d=f.open('/policy-modern');query('denied','NotAllowedError')
    d=f.open('/policy-legacy');query()
    f.pref('dom.security.featurePolicy.header.enabled',True);d=f.open()
    dynamic=d.execute_async_script("""const done=arguments[0],frame=document.createElement('iframe');frame.src='/';
      frame.onload=async()=>{try{const win=frame.contentWindow;const before=(await win.navigator.permissions.query({name:'window-management'})).state;
       frame.allow="window-management 'none'";
       const afterAssignment=(await win.navigator.permissions.query({name:'window-management'})).state;
       frame.onload=async()=>{try{const owner=frame.contentWindow;
         const after=(await owner.navigator.permissions.query({name:'window-management'})).state;
         let result;try{await owner.getScreenDetails();result='resolved'}catch(e){result=e.name}done({before,afterAssignment,after,result});
       }catch(e){done({error:e.name,message:e.message})}finally{frame.remove()}};
       frame.src='/?updated-container-policy';
      }catch(e){frame.remove();done({error:e.name,message:e.message})}};document.body.append(frame);""")
    assert dynamic=={'before':'granted','afterAssignment':'granted','after':'denied','result':'NotAllowedError'},dynamic
    d.execute_script("window.permissionSnapshot=null")
    snapshot=d.execute_async_script("const done=arguments[0];navigator.permissions.query({name:'window-management'}).then(s=>{window.permissionSnapshot=s;done(s.state)})")
    assert snapshot=='granted'
    for disable,restore in [(lambda:f.set_master(False),lambda:f.set_master(True)),
      (lambda:f.set_feature(False),lambda:f.set_feature(True)),
      (lambda:f.set_origins([]),lambda:f.set_origins([f.origin])),
      (lambda:f.set_config(0,{'navigator.userAgent':FIREFOX}),lambda:f.set_config(0,{'navigator.userAgent':CHROME}))]:
        disable();query('denied','NotAllowedError')
        assert d.execute_script('return permissionSnapshot.state')=='granted','query-time snapshot mutated'
        d.refresh();query('denied','absent');restore();d.refresh();query()
        d.execute_async_script("const done=arguments[0];navigator.permissions.query({name:'window-management'}).then(s=>{window.permissionSnapshot=s;done(s.state)})")
    d=f.open(host='other.testdome.invalid');query('denied','absent');d=f.open()
    query_code="navigator.permissions.query({name:'window-management'}).then(s=>s.state,e=>e.name)"
    f.routes['/permission-worker.js']=(f'{query_code}.then(state=>postMessage(state));',{})
    f.routes['/permission-shared.js']=(f'onconnect=e=>{{const p=e.ports[0];{query_code}.then(state=>p.postMessage(state));}};',{})
    f.routes['/permission-service.js']=(f'oninstall=()=>skipWaiting();onactivate=e=>e.waitUntil(clients.claim());onmessage=e=>{{{query_code}.then(state=>e.ports[0].postMessage(state));}};',{})
    worker=d.execute_async_script("const done=arguments[0],w=new Worker('/permission-worker.js');w.onmessage=e=>{w.terminate();done(e.data)}")
    assert worker=='denied',worker
    shared=d.execute_async_script("const done=arguments[0],w=new SharedWorker('/permission-shared.js');w.port.onmessage=e=>{w.port.close();done(e.data)};w.port.start()")
    assert shared=='denied',shared
    service=d.execute_async_script("""const done=arguments[0];(async()=>{const registration=await navigator.serviceWorker.register('/permission-service.js');
      await navigator.serviceWorker.ready;const channel=new MessageChannel();
      const state=await new Promise(resolve=>{channel.port1.onmessage=e=>resolve(e.data);registration.active.postMessage({},[channel.port2])});
      channel.port1.close();await registration.unregister();return state})().then(done,e=>done({error:e.name,message:e.message}));""")
    assert service=='denied',service
    print('WINDOW MANAGEMENT POLICY PASS',flush=True)



def run_ancestor_orientation(f):
    """Exercise Gecko's ancestor traversal with a trusted DevTools override."""
    d=f.open(host='other.testdome.invalid')
    assert d.execute_script('return typeof getScreenDetails')=='undefined'
    d.execute_script("window.rootOrientationEvents=[];screen.orientation.addEventListener('change',e=>{if(e.isTrusted)rootOrientationEvents.push(screen.orientation.type)})")
    d.execute_async_script("""const [url,done]=arguments;const frame=document.createElement('iframe');
      frame.id='virtual-child';frame.allow='window-management *';frame.src=url;
      frame.onload=()=>done(true);document.body.append(frame);""",f.origin+'/')
    d.switch_to.frame(d.find_element('id','virtual-child'))
    before=d.execute_async_script("""const done=arguments[0];getScreenDetails().then(details=>{
      window.orientationEvents=[];window.orientationTargets=[screen.orientation,...details.screens.map(s=>s.orientation)];
      for(const [i,target] of orientationTargets.entries())target.addEventListener('change',e=>{if(e.isTrusted)orientationEvents.push(i)});
      done(orientationTargets.map(s=>[s.type,s.angle]));
    },e=>done({error:e.name}));""")
    assert isinstance(before,list),before
    d.switch_to.default_content()
    try:
        # This existing privileged Gecko API dispatches through the ancestor's
        # DispatchChangeEventToChildren, rather than synthesizing DOM events.
        f.chrome("gBrowser.selectedBrowser.browsingContext.setOrientationOverride('portrait-primary',90)")
        from selenium.webdriver.support.ui import WebDriverWait
        WebDriverWait(d,10).until(lambda d:d.execute_script('return rootOrientationEvents.length')>0)
        root=d.execute_script('return rootOrientationEvents')
        d.switch_to.frame(d.find_element('id','virtual-child'))
        value=d.execute_script('return {events:orientationEvents,values:orientationTargets.map(s=>[s.type,s.angle])}')
        assert value=={'events':[],'values':before},value
        print('ANCESTOR ORIENTATION PASS',root,value,flush=True)
    finally:
        d.switch_to.default_content()
        f.chrome('gBrowser.selectedBrowser.browsingContext.resetOrientationOverride()')
        f.open()


def main():
    reports=[]
    with ScreenManagementFixture() as f:
        d=f.open()
        def support(expected):
            actual=d.execute_script('return [typeof getScreenDetails,typeof ScreenDetails,typeof ScreenDetailed,"isExtended" in screen]')
            assert actual==(['function','function','function',True] if expected else ['undefined','undefined','undefined',False]),actual
        def collect():
            value=d.execute_async_script(COLLECT);assert 'error' not in value,value;reports.append(value);return value
        run_ancestor_orientation(f)
        support(True)  # First red: missing native bindings in the pre-change build.
        f.routes['/late']=(PAGE.replace("typeof getScreenDetails === 'function' ?", "false ?"),{})
        f.set_screen_count(1);d=f.open('/late');f.set_screen_count(3)
        assert len(collect()['rows'])==1,'count snapshot must precede the first API access'
        d=f.open()
        for count in [1,2,3,8]:
            f.set_screen_count(count);d.refresh();value=collect();rows=value['rows']
            assert len(rows)==count and value['extended']==(count>1),value
            assert d.execute_async_script('const done=arguments[0];firstNativeResult.then(done)')=={'count':count,'frozen':True}
            for i,row in enumerate(rows):
                assert row==dict(width=1366,height=768,left=i*1366,top=0,availWidth=1300,availHeight=728,
                    availLeft=i*1366,availTop=0,depth=24,pixelDepth=24,dpr=1,type='landscape-primary',angle=0,
                    primary=i==0,internal=i==0,label='Screen' if count==1 else f'Screen {i+1}'),row
            f.set_screen_count(2 if count!=2 else 3)
            unchanged=d.execute_script('return [savedDetails.screens.length,screen.isExtended,trustedTopology]')
            assert unchanged==[count,count>1,[]],unchanged
        for invalid in [0,-1,9,'wrong',True]:
            f.set_screen_count(invalid);d.refresh()
            value=collect();assert len(value['rows'])==1 and value['extended'] is False,value
        f.set_screen_count(3);d.refresh();collect()
        f.set_config(0,{'screen.left':-200,'screen.top':-100,'screen.availLeft':-180,'screen.availTop':-80,
            'screen.width':800,'screen.height':600,'screen.availWidth':760,'screen.availHeight':560})
        updated=d.execute_script('return savedDetails.screens.map(s=>[s.left,s.top,s.availLeft,s.width])')
        assert updated==[[-200,-100,-180,800],[600,-100,620,800],[1400,-100,1420,800]],updated
        f.set_config(0,{'screen.left':2147483000})
        assert d.execute_script('return savedDetails.screens.map(s=>[s.left,s.width,s.devicePixelRatio])')==[[0,1920,1],[1920,1920,1],[3840,1920,1]]
        f.set_config(0,{'screen.left':0,'screen.top':0,'screen.availLeft':0,'screen.availTop':0,
            'screen.width':1366,'screen.height':768,'screen.availWidth':1300,'screen.availHeight':728})
        f.chrome("Services.obs.notifyObservers(null,'screen-information-changed')")
        assert d.execute_script('return trustedTopology')==[]
        for ua in [CHROME,CHROME.replace('Chrome/','Chromium/'),CHROME+' Edg/146.0.0.0']:
            f.set_config(0,{'navigator.userAgent':ua});d.refresh();support(True)
        for ua in [FIREFOX,CHROME+' Firefox/146.0',CHROME.replace('146.0.0.0','bad'),CHROME+' Android',CHROME+' Mobile',CHROME+' iPhone',CHROME+' iPad',CHROME.replace('Chrome/146.0.0.0 ','')]:
            f.set_config(0,{'navigator.userAgent':ua});d.refresh();support(False)
        f.set_config(0,{'navigator.userAgent':CHROME});d.refresh();support(True)
        for disable,restore in [(lambda:f.set_master(False),lambda:f.set_master(True)),
            (lambda:f.set_feature(False),lambda:f.set_feature(True)),
            (lambda:f.set_origins([]),lambda:f.set_origins([f.origin])),
            (lambda:f.set_config(0,{'navigator.userAgent':FIREFOX}),lambda:f.set_config(0,{'navigator.userAgent':CHROME}))]:
            d.execute_script('window.savedMethod=getScreenDetails');disable()
            result=d.execute_async_script("const done=arguments[0];savedMethod().then(()=>done('resolved'),e=>done(e.name))")
            assert result=='NotAllowedError',result
            d.refresh();support(False);restore();d.refresh();support(True)
        for host in ['other.testdome.invalid','app.testdome.com.evil.invalid','sub.app.testdome.com']:
            d=f.open(host=host);support(False)
        d=f.open(scheme='http');support(False)
        d=f.open(port=f.alternate_port);support(False)
        f.set_origins([f.origin,f'https://app.testdome.com:{f.alternate_port}']);d.refresh();support(True)
        f.set_origins([f.origin]);d=f.open()
        # The nested owners are judged independently; a parent cannot grant eligibility.
        for attrs,expected in [("",True),("sandbox='allow-scripts'",False)]:
            result=d.execute_async_script('''const [attrs,done]=arguments;const f=document.createElement('iframe');
              f.srcdoc='<script>parent.postMessage({probe:1,type:typeof getScreenDetails},"*")</script>';
              if(attrs)f.setAttribute('sandbox','allow-scripts');
              const fn=e=>{if(e.source===f.contentWindow&&e.data.probe){removeEventListener('message',fn);f.remove();done(e.data.type)}};
              addEventListener('message',fn);document.body.append(f);''',attrs)
            assert result==('function' if expected else 'undefined'),result
        # Keep callbacks in the active parent: removing a frame inside its load
        # callback also discards that callback's incumbent execution context.
        attached=d.execute_async_script("""const done=arguments[0],frame=document.createElement('iframe');frame.id='retained-frame';frame.src='/';
          frame.onload=async()=>{try{const win=frame.contentWindow;window.retainedMethod=win.getScreenDetails.bind(win);
            window.retainedScreen=win.screen;window.retainedDetails=await win.getScreenDetails();done(retainedDetails.screens.length)
          }catch(e){done({error:e.name,message:e.message})}};document.body.append(frame);""")
        assert attached==3,attached
        retained=d.execute_script("document.getElementById('retained-frame').remove();return [retainedScreen.width,retainedDetails.screens.length]")
        assert retained==[1366,3],retained
        result=d.execute_async_script("const done=arguments[0];retainedMethod().then(()=>done('resolved'),e=>done(e.name))")
        assert result=='InvalidStateError',result
        worker=d.execute_async_script("const done=arguments[0],w=new Worker('/worker.js');w.onmessage=e=>{w.terminate();done(e.data)}")
        assert worker=={'method':'undefined','details':'undefined','detailed':'undefined'},worker
        shared=d.execute_async_script("const done=arguments[0],w=new SharedWorker('/shared.js');w.port.onmessage=e=>{w.port.close();done(e.data)};w.port.start()")
        assert shared==worker,shared
        service=d.execute_async_script('''const done=arguments[0];(async()=>{
          const registration=await navigator.serviceWorker.register('/service.js');
          await navigator.serviceWorker.ready;const channel=new MessageChannel();
          const result=await new Promise(resolve=>{channel.port1.onmessage=e=>resolve(e.data);registration.active.postMessage({},[channel.port2])});
          channel.port1.close();await registration.unregister();return result;
        })().then(done,e=>done({error:e.name,message:e.message}))''')
        assert service==worker,service
        child=d.execute_async_script('''const [url,done]=arguments,f=document.createElement('iframe');
          const fn=e=>{if(e.source===f.contentWindow&&e.data.probe){removeEventListener('message',fn);f.remove();done(e.data.type)}};
          addEventListener('message',fn);f.src=url;document.body.append(f)''',f'https://other.testdome.invalid:{f.https_port}/child.html')
        assert child=='undefined',child

        # Navigation creates another inner; history back either restores the
        # cached inner or creates a new one. Record which Gecko actually does.
        f.routes['/next']=(PAGE,{})
        history=d.execute_async_script("""const done=arguments[0];(async()=>{
          const frame=document.createElement('iframe');
          const load=()=>new Promise(resolve=>{const fn=e=>{if(e.source===frame.contentWindow&&e.data.fixturePageshow){removeEventListener('message',fn);resolve(e.data)}};addEventListener('message',fn)});
          let loaded=load();frame.src='/';document.body.append(frame);await loaded;
          const first=await frame.contentWindow.getScreenDetails();
          loaded=load();frame.src='/next';await loaded;
          const next=await frame.contentWindow.getScreenDetails();
          const distinct=first!==next;
          loaded=load();frame.contentWindow.history.back();const pageshow=await loaded;
          const back=await frame.contentWindow.getScreenDetails();
          const result={distinct,restored:back===first,persisted:pageshow.persisted,count:back.screens.length,retainedWidth:first.currentScreen.width};
          frame.remove();return result;
        })().then(done,e=>done({error:e.name,message:e.message}));""")
        assert history.get('distinct') and history.get('count')==3 and history.get('retainedWidth')==1366,history
        reports.append({'history':history})
        # Container 2 needs its own identity; default container Firefox doesn't revoke it.
        f.set_config(0,{'navigator.userAgent':FIREFOX});f.set_config(2,{'navigator.userAgent':CHROME})
        d=f.open(container=2);support(True);d=f.open();support(False)
        borrowed=f.chrome_async("""const [origin,done]=arguments,tabs=[];
          (async()=>{try{
            const windows=[0,2].map(id=>{const tab=gBrowser.addTab('about:blank',{userContextId:id,forceNotRemote:true,triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});tabs.push(tab);
              const p=Services.scriptSecurityManager.createContentPrincipal(Services.io.newURI(origin),{userContextId:id});tab.linkedBrowser.docShell.createAboutBlankDocumentViewer(p,p);return tab.linkedBrowser.contentWindow});
            const method=windows[1].getScreenDetails;
            const rejected=await method.call(windows[0]).then(()=> 'resolved',e=>e.name);
            const accepted=await method.call(windows[1]);
            return {rejected,count:accepted.screens.length,firefoxMethod:typeof windows[0].getScreenDetails};
          }finally{tabs.forEach(tab=>gBrowser.removeTab(tab))}})().then(done,e=>done({error:e.name,message:e.message}));""",f.origin)
        assert borrowed=={'rejected':'NotAllowedError','count':3,'firefoxMethod':'undefined'},borrowed

        run_policy(f)
        (f.report_path/'management.json').write_text(json.dumps(reports,indent=2))
        print('SCREEN MANAGEMENT PASS')

if __name__=='__main__':main()
