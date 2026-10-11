"""Owner-based virtual geometry, orientation, live pins and exclusion."""
import json
from screen_management_fixture import ScreenManagementFixture, CHROME, FIREFOX

def main():
    with ScreenManagementFixture() as f:
        d=f.open(); rows=[]
        def read(): return d.execute_script('return presentation()')
        a=read(); rows.append(a)
        assert a == dict(width=1366,height=768,left=0,top=0,availWidth=1300,availHeight=728,
            availLeft=0,availTop=0,depth=24,pixelDepth=24,dpr=1,orientation='landscape-primary',angle=0), a
        d.refresh(); assert read()==a
        f.set_config(0,{'screen.width':800,'screen.height':1200,'screen.availWidth':780,
            'screen.availHeight':1160,'screen:orientation:type':'portrait-secondary'})
        b=read(); rows.append(b)
        assert (b['width'],b['height'],b['availWidth'],b['orientation'],b['angle'])==(800,1200,780,'portrait-secondary',180),b
        f.set_config(2,{'navigator.userAgent':CHROME+' Edg/146.0.0.0','screen.width':1920,'screen.height':1080,
            'screen.availLeft':0,'screen.availTop':25,'screen.availWidth':1880,'screen.availHeight':1030,
            'screen.colorDepth':30,'window.devicePixelRatio':2,'screen:orientation:type':'landscape-primary'})
        d=f.open(container=2); c=read(); rows.append(c)
        assert (c['width'],c['availWidth'],c['availTop'],c['depth'],c['dpr'])==(1920,1880,25,30,2),c
        d=f.open(); assert read()==b,'container zero borrowed current-container pins'
        borrowed=f.chrome("""const tabs=[];
          try { const windows=[0,2].map(id=>{
            const tab=gBrowser.addTab("about:blank",{userContextId:id,forceNotRemote:true,triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});tabs.push(tab);
            const browser=tab.linkedBrowser;
            const principal=Services.scriptSecurityManager.createContentPrincipal(Services.io.newURI(arguments[0]),{userContextId:id});
            browser.docShell.createAboutBlankDocumentViewer(principal,principal);
            return browser.contentWindow;
          });
          return windows.map((window,index)=>{
            const sandbox=Cu.Sandbox(Services.scriptSecurityManager.getSystemPrincipal(),{sandboxPrototype:window,wantXrays:false});
            sandbox.otherScreen=windows[1-index].screen;
            const result=Cu.evalInSandbox("({ua:navigator.userAgent,own:screen.width,other:Object.getOwnPropertyDescriptor(Screen.prototype,'width').get.call(otherScreen),ownDepth:screen.colorDepth,otherDepth:Object.getOwnPropertyDescriptor(Screen.prototype,'colorDepth').get.call(otherScreen),secure:isSecureContext})",sandbox);
            const output={ua:result.ua,own:result.own,other:result.other,ownDepth:result.ownDepth,otherDepth:result.otherDepth,secure:result.secure};Cu.nukeSandbox(sandbox);return output;
          });
          } finally { tabs.forEach(tab=>gBrowser.removeTab(tab)) }""",f.origin)
        assert [row['own'] for row in borrowed]==[800,1920],borrowed
        assert [row['other'] for row in borrowed]==[1920,800],borrowed
        assert all(row['secure'] for row in borrowed),borrowed
        assert [row['ownDepth'] for row in borrowed]==[24,30],borrowed
        assert [row['otherDepth'] for row in borrowed]==[30,24],borrowed

        # Saved detached child must retain its own data safely.
        d.execute_async_script('''const done=arguments[0],frame=document.createElement('iframe');
          frame.src='/';frame.onload=()=>{window.retained=frame.contentWindow.screen;frame.remove();done(true)};document.body.append(frame);''')
        f.set_config(0,{'screen.width':900,'screen.availWidth':880})
        assert d.execute_script('return retained.width')==800
        assert read()['width']==900
        # Wrong types and negative values return coherent virtual defaults.
        f.set_config(0,{'screen.width':-1,'screen.height':'bad','window.devicePixelRatio':-1})
        value=read(); assert (value['width'],value['height'],value['dpr'])==(1920,1080,1),value
        # Scope gates must stop using the opt-in available rectangle immediately.
        f.set_config(0,{'screen.width':1366,'screen.height':768,'screen.availWidth':1300,'screen.availHeight':728,'window.devicePixelRatio':1})
        for disable,restore in [(lambda:f.set_master(False),lambda:f.set_master(True)),
            (lambda:f.set_feature(False),lambda:f.set_feature(True)),
            (lambda:f.set_origins([]),lambda:f.set_origins([f.origin])),
            (lambda:f.set_config(0,{'navigator.userAgent':FIREFOX}),lambda:f.set_config(0,{'navigator.userAgent':CHROME}))]:
            disable(); assert read()['availWidth']!=1300,read()
            restore(); assert read()['availWidth']==1300,read()
        for stored in ['broken','{}','[]','["https://*.testdome.com"]','["http://app.testdome.com"]']:
            f.pref('cloakfox.compat.screen_management.origins',stored)
            assert read()['availWidth']!=1300,read()
        f.set_origins([f.origin])
        f.set_config(0,{'screen.left':-100,'screen.top':-50,'screen.availLeft':-90,'screen.availTop':-30})
        value=read();assert (value['left'],value['top'],value['availLeft'],value['availTop'])==(-100,-50,-90,-30),value
        f.set_config(0,{'screen.left':2147483640,'screen.width':1366})
        value=read();assert (value['left'],value['width'],value['dpr'])==(0,1920,1),value
        f.pref('privacy.resistFingerprinting.letterboxing',True); d.refresh()
        value=read(); assert (value['width'],value['height'])==(value['availWidth'],value['availHeight']),value
        (f.report_path/'presentation.json').write_text(json.dumps(rows,indent=2))
        print('SCREEN PRESENTATION PASS')

if __name__=='__main__': main()
