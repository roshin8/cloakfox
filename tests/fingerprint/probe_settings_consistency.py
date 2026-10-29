"""Exercise maintained consistency/save guards in a disposable Gecko profile.

Loads the inspector directly from this checkout, without updating application
resources. Only temporary-profile prefs are touched; no public site is opened.
Generation accept/cancel is separately exercised by test_settings_consistency.mjs.
"""
from pathlib import Path
from screen_management_fixture import ScreenManagementFixture
import json

ROOT = Path(__file__).resolve().parents[2]

def main():
    source = (ROOT / 'additions/browser/components/cloakfox/content/settings.js').read_text()
    start = source.index('function applySettingChanges(')
    helper = source[start:source.index('// ── container enumeration', start)]
    inspector = (ROOT / 'additions/browser/components/cloakfox/CloakfoxInspector.sys.mjs').as_uri()
    with ScreenManagementFixture() as fixture:
        result = fixture.chrome('''
const [url,helper]=arguments;
const protocol=Services.io.getProtocolHandler('resource').QueryInterface(Ci.nsIResProtocolHandler);
protocol.setSubstitution('parity-audit',Services.io.newURI(url.replace(/[^/]+$/, '')));
const {confirmConsistencyChange,inspectConsistency}=ChromeUtils.importESModule('resource://parity-audit/CloakfoxInspector.sys.mjs');
const {KEY_TYPES,readOverrides,setOverrides,applyOverrides}=ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs');
const id=71, prefix=`cloakfox.container.${id}.`,cfgPref=`cloakfox.s.cloak_cfg_${id}`;
const cfg={'navigator.userAgent':'Windows Firefox/159.0','headers.User-Agent':'Windows Firefox/159.0',
 'navigator.platform':'Win32','window.devicePixelRatio':1};
Services.prefs.setBoolPref('cloakfox.opt.container_rendering_profiles',false);
Services.prefs.setStringPref(prefix+'math_seed','AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=');
Services.prefs.setStringPref(cfgPref,JSON.stringify(cfg));
const box=Cu.Sandbox(Services.scriptSecurityManager.getSystemPrincipal());
Object.assign(box,{Services,KEY_TYPES,readOverrides,setOverrides,applyOverrides,confirmConsistencyChange,
 masterSeedPref:ucid=>`cloakfox.container.${ucid}.math_seed`,getCloakCfg:()=>cfg,
 buildCloakCfg:()=>JSON.stringify(cfg),window:{confirm:()=>false}});
Cu.evalInSandbox(helper,box);
const checks=[];const check=(ok,name)=>{if(!ok)throw Error(name);checks.push(name)};
check(box.applySettingChanges(id,{'window.devicePixelRatio':'0'})===false,'cancel declined');
check(!Object.hasOwn(readOverrides(id),'window.devicePixelRatio'),'cancel writes no override');
check(Services.prefs.getStringPref(cfgPref)===JSON.stringify(cfg),'cancel keeps active config');
box.window.confirm=()=>true;
check(box.applySettingChanges(id,{'window.devicePixelRatio':'0'})===true,'accept succeeded');
check(readOverrides(id)['window.devicePixelRatio']===0,'accept retains custom zero');
check(Services.prefs.getStringPref(prefix+'math_seed')==='AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=','edits keep seed');
check(inspectConsistency({...cfg,'navigator.oscpu':'Intel Mac OS X'}).some(i=>i.code==='oscpu-os'),'new inspector loaded in Gecko');
Cu.nukeSandbox(box);
protocol.setSubstitution('parity-audit',null);
return {version:Services.appinfo.version,checks};
''', inspector, helper)
        print(json.dumps(result), flush=True)

if __name__ == '__main__':
    main()
