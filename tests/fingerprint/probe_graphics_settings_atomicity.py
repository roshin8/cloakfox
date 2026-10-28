"""Real privileged Settings preflight must never partially apply rejected edits.

No mocks or synthetic API implementations. The real browser module operates on
its disposable profile. Snapshot comparison stays in chrome; no secrets exported.
Catches moving validation after pref writes, skipping an owner, or bypassing the
canonical backend prerequisite. No native UI, public network or GPU allocation.
"""
import json
import os
import tempfile
from pathlib import Path
from probe_daily_defaults import launch

SCRIPT = r"""
const o=ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs');
const p=ChromeUtils.importESModule('resource:///modules/CloakfoxPersonas.sys.mjs');
const {ContextualIdentityService:cis}=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
const ids=['Atomic A','Atomic B'].map(n=>cis.create(n,'fingerprint','blue').userContextId);
const checks=[];function check(ok,name){checks.push({pass:!!ok,name});if(!ok)throw Error(name);}
function snapshot(){return JSON.stringify(Services.prefs.getChildList('cloakfox.').sort().map(k=>[k,Services.prefs.getPrefType(k)===128?Services.prefs.getBoolPref(k):Services.prefs.getPrefType(k)===64?Services.prefs.getIntPref(k):Services.prefs.getStringPref(k)]));}
function rejectedWithoutWrites(fn,label){
 const before=snapshot();let rejected=false;
 try{fn();}catch{rejected=true;}
 check(rejected,label+' is rejected');check(snapshot()===before,label+' leaves every saved preference unchanged');
}
try{
 check(Services.prefs.getBoolPref('cloakfox.enabled'),'privacy master enabled');
 Services.prefs.setBoolPref('cloakfox.opt.container_rendering_profiles',false);
 Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',true);
 const keys=Services.prefs.getChildList('cloakfox.s.cloak_cfg_').filter(k=>/^cloakfox\.s\.cloak_cfg_\d+$/.test(k));
 for(const key of keys){const id=Number(key.slice('cloakfox.s.cloak_cfg_'.length)),old=JSON.parse(Services.prefs.getStringPref(key)),next=p.fillPersonaKeys('B'.repeat(43)+'=',id,{os:'windows',hardware:'nvidia'});for(const [k,v]of Object.entries(old))if(/seed|secret/i.test(k))next[k]=v;Services.prefs.setStringPref(key,JSON.stringify(next));}
 check(keys.length>=3,'multiple real owners take part in preflight');
 const badKey='cloakfox.s.cloak_cfg_'+ids[1],saved=Services.prefs.getStringPref(badKey);
 for(const value of [null,[],{'3379':4095},{'3386':[4096,100]},{'3379':'8192'}]){
  const invalid=JSON.parse(saved);invalid['webGl:parameters']=value;
  Services.prefs.setStringPref(badKey,JSON.stringify(invalid));
  rejectedWithoutWrites(()=>o.setContainerGPUProfilesEnabled(true),'invalid capability table '+JSON.stringify(value));
  check(!Services.prefs.getBoolPref('cloakfox.opt.container_rendering_profiles'),'rejected activation keeps global toggle off');
 }
 Services.prefs.setStringPref(badKey,saved);
 Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',false);
 rejectedWithoutWrites(()=>o.setContainerGPUProfilesEnabled(true),'missing canonical backend');
 Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',true);
 o.setContainerGPUProfilesEnabled(true);
 check(Services.prefs.getBoolPref('cloakfox.opt.container_rendering_profiles'),'valid activation positive control succeeds');
 rejectedWithoutWrites(()=>o.setOverrides(ids[0],{'navigator.platform':'Atomic sentinel','webGl:renderer':'SwiftShader'}),'multi-field incompatible persona preset');
 rejectedWithoutWrites(()=>o.setOverrides(ids[0],{'navigator.platform':'Atomic sentinel','navigator.hardwareConcurrency':1.5}),'multi-field invalid integer preset');
 // Successful single-field update proves the real override path writes normally.
 o.setOverrides(ids[0],{'navigator.platform':'Win32'});
 check(o.readOverrides(ids[0])['navigator.platform']==='Win32','valid override positive control persists');
 return {checks};
}catch(error){return {checks,error:String(error)};}
"""

def main():
 out=Path(os.environ.get('REPORT_DIR','/tmp/cloakfox-settings-atomicity'));out.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='cloakfox-settings-atomicity-') as temp:
  profile=Path(temp)/'profile';profile.mkdir();d=launch(profile,out/'gecko.log')
  try:result=d.execute_script(SCRIPT)
  finally:d.quit()
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 for check in result['checks']:print(('PASS ' if check['pass'] else 'FAIL ')+check['name'],flush=True)
 assert 'error' not in result,result
 return 0
if __name__=='__main__':raise SystemExit(main())
