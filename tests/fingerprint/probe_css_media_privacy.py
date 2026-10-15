"""CSS/native matchMedia coherence, own-container policy; disposable local fixture.

No device capture or external network. REPORT_DIR retains all observations even
when an installed pre-repair browser fails. Run against CLOAKFOX_BIN serially.
"""
import json
from screen_management_fixture import ScreenManagementFixture

QUERIES = ['(color: 8)', '(color: 10)', '(8 <= color <= 8)',
    '(color-gamut: srgb)', '(color-gamut: p3)', '(color-gamut: rec2020)',
    '(prefers-reduced-motion: reduce)', '(prefers-reduced-transparency: reduce)',
    '(prefers-contrast: more)', '(inverted-colors: inverted)', '(forced-colors: active)',
    '(dynamic-range: high)', '(video-dynamic-range: high)',
    '(color-gamut: p3) and (min-width: 1px)',
    'not all and (color-gamut: p3)',
    '(color-gamut: p3), (min-width: 99999px)',
    '(color-gamut: p3) or (color: 8)', '(resolution: 1dppx)']
READ = r'''const done=arguments[0];
Promise.all([document.fonts.ready,new Promise(r=>setTimeout(r,120))]).then(()=>{
 requestAnimationFrame(()=>requestAnimationFrame(()=>{
 const css=getComputedStyle(document.documentElement);
 done({depth:screen.colorDepth,pixelDepth:screen.pixelDepth,
   matches:window.queries.map(q=>matchMedia(q).matches),
   styles:window.queries.map((q,i)=>css.getPropertyValue('--q'+i).trim()==='yes')});
 }));});'''


def main():
    failures=[]; report={}
    def check(ok, message):
        if not ok: failures.append(message)
    with ScreenManagementFixture() as f:
        css=':root {'+''.join(f'--q{i}:no;' for i in range(len(QUERIES)))+'}\n'
        css+='\n'.join(f'@media {q} {{ :root {{ --q{i}:yes }} }}' for i,q in enumerate(QUERIES))
        # Inline styles are parsed before any matchMedia script executes.
        page='<!doctype html><style>'+css+'</style><script>window.queries='+json.dumps(QUERIES)+';window.presentation=()=>({});</script><body>CSS policy fixture'
        f.routes['/css.html']=(page,{})
        f.pref('cloakfox.compat.screen_management',False)
        f.pref('privacy.resistFingerprinting.letterboxing',False)
        f.pref('gfx.color_management.hdr.force_enabled',True)
        f.pref('ui.prefersReducedMotion',1)
        f.pref('layout.css.prefers-reduced-transparency.enabled',True)
        f.pref('layout.css.inverted-colors.enabled',True)
        def configure(ucid, cfg):
            f.chrome("Services.prefs.setStringPref('cloakfox.s.cloak_cfg_'+arguments[0],JSON.stringify(arguments[1]));",ucid,cfg)
        def observe(label,container=0,frames=False):
            d=f.open('/css.html',container=container)
            row=d.execute_async_script(READ)
            report[label]=row
            check(row['matches']==row['styles'],f'{label}: JS/CSS mismatch {row}')
            if frames:
                for name,host in [('same','app.testdome.com'),('cross','other.testdome.invalid')]:
                    url=f'https://{host}:{f.https_port}/css.html'
                    d.execute_async_script('''const [url,done]=arguments;const frame=document.createElement('iframe');
                      frame.src=url;frame.onload=()=>done(true);document.body.append(frame);''',url)
                    d.switch_to.frame(d.find_elements('tag name','iframe')[-1])
                    child=d.execute_async_script(READ);report[label+'-'+name]=child
                    check(child==row,f'{label}: {name}-origin frame policy mismatch {child}')
                    d.switch_to.default_content()
            return row
        def verify(row,gamut,depth=24,reduced=False,preferences=False):
            expected={0:depth//3==8,1:depth//3==10,2:depth//3==8,
                3:True,4:gamut>=1,5:gamut>=2,6:reduced,7:preferences,8:preferences,9:preferences,
                11:False,12:False,13:gamut>=1,14:gamut<1,15:gamut>=1,
                16:True,17:True}
            check(row['depth']==depth and row['pixelDepth']==depth,f'Screen depth mismatch {row}')
            for i,value in expected.items():check(row['matches'][i]==value,f'{QUERIES[i]} expected {value}: {row}')
        try:
            for os,platform,gamut in [('windows','Win32',0),('macos','MacIntel',1)]:
                cfg={'navigator.platform':platform,'screen.colorDepth':24,'screen.pixelDepth':24,
                    'mediaFeature:colorGamut':gamut,'mediaFeature:resolution':1,
                    'mediaFeature:prefersReducedMotion':False,'mediaFeature:prefersContrast':0}
                configure(0,cfg);verify(observe(os,frames=True),gamut)
            # Unlike an OS-derived actor pin, exact config permits any gamut.
            configure(0,{'screen.colorDepth':30,'mediaFeature:colorGamut':2,'mediaFeature:resolution':1})
            configure(2,{'screen.colorDepth':24,'mediaFeature:colorGamut':0,'mediaFeature:resolution':1})
            verify(observe('default-rec2020'),2,30)
            verify(observe('other-srgb',container=2,frames=True),0)
            # Trigger CSS evaluation with no page-script getter on the stack.
            d=f.driver
            d.execute_async_script('''const done=arguments[0];setTimeout(()=>{
              const style=document.createElement('style');
              style.textContent='@media (color-gamut:p3){body{--async-p3:yes}}';
              document.head.append(style);requestAnimationFrame(()=>done(true));},30);''')
            async_value=d.execute_script("return getComputedStyle(document.body).getPropertyValue('--async-p3').trim()")
            report['async-other-p3']=async_value;check(async_value!='yes','Default gamut leaked into asynchronous other-container CSS')
            configure(0,{})
            verify(observe('missing-config'),0)
            configure(0,{'screen.colorDepth':-1,'mediaFeature:colorGamut':'bad','mediaFeature:resolution':-1})
            verify(observe('invalid-config'),0)
            f.set_master(False)
            native=observe('master-off')
            check(native['matches'][6], 'Master-off did not preserve forced native reduced motion')
            check(native['matches'][12], 'Master-off did not preserve forced native HDR')
            f.pref('browser.display.document_color_use',2)
            accessible_native=observe('accessibility-native')
            f.set_master(True)
            configure(0,{'screen.colorDepth':24,'mediaFeature:colorGamut':0,
                         'mediaFeature:prefersReducedMotion':False})
            accessible=observe('accessibility-protected')
            check(accessible['matches'][10]==accessible_native['matches'][10],
                  'Protection changed native accessibility forced-colors')
            chrome_motion=f.chrome("return Services.wm.getMostRecentWindow('navigator:browser').matchMedia('(prefers-reduced-motion:reduce)').matches")
            report['chrome-reduced-motion']=chrome_motion
            check(chrome_motion,'Persona media policy altered browser UI accessibility')
            f.pref('browser.display.document_color_use',0)
            f.set_master(False)
            # Master-off ignores contradictory persona fields.
            configure(0,{'screen.colorDepth':15,'mediaFeature:colorGamut':2,'mediaFeature:prefersReducedMotion':False})
            check(observe('master-off-configured')==native,'Master-off still consumes persona config')
            f.set_master(True)
            configure(0,{'screen.colorDepth':24,'mediaFeature:colorGamut':0,'mediaFeature:prefersReducedMotion':True})
            verify(observe('explicit-reduced-motion'),0,reduced=True)
            configure(0,{'screen.colorDepth':24,'mediaFeature:colorGamut':0,
                'mediaFeature:prefersReducedMotion':True,'mediaFeature:prefersReducedTransparency':True,
                'mediaFeature:prefersContrast':2,'mediaFeature:invertedColors':True})
            verify(observe('explicit-preferences',frames=True),0,reduced=True,preferences=True)
        finally:
            (f.report_path/'css-media.json').write_text(json.dumps({'observations':report,'failures':failures},indent=2))
        assert not failures, '\n'.join(failures)
        print('PASS: own-container CSS/media depth, grammar, frames, defaults and master-off')

if __name__=='__main__':main()
