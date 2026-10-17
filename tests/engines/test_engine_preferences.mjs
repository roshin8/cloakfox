import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const path=new URL('../../additions/browser/components/cloakfox/CloakfoxEnginePreferences.sys.mjs',import.meta.url);
function fixture(){
  const values=new Map();
  const source=fs.readFileSync(path,'utf8').replace(/^export /gm,'');
  const api=vm.runInNewContext(source+'\n({getChromiumPresentation,setChromiumPresentation});',{
    Services:{prefs:{getStringPref:(key,defaultValue)=>values.get(key)??defaultValue,
      setStringPref:(key,value)=>values.set(key,value)}}});
  return {api,values};
}
test('presentation defaults to same-window and remains container-owned',()=>{
  const {api,values}=fixture();
  for(const id of [0,1,2])assert.equal(api.getChromiumPresentation(id),'same-window');
  api.setChromiumPresentation(0,'separate-window');
  assert.equal(api.getChromiumPresentation(0),'separate-window');
  assert.equal(api.getChromiumPresentation(1),'same-window');
  api.setChromiumPresentation(1,'separate-window');
  api.setChromiumPresentation(0,'same-window');
  assert.equal(api.getChromiumPresentation(1),'separate-window');
  assert.equal(values.size,2);
  assert.ok([...values.keys()].every(key=>key.endsWith('.chromium_presentation')));
});
test('invalid container IDs never alias Default or another owner',()=>{
  const {api,values}=fixture();
  for(const id of [-1,NaN,Infinity,1.5,true,false,null,undefined,'0',2147483647]) {
    assert.throws(()=>api.getChromiumPresentation(id),/container/i);
    assert.throws(()=>api.setChromiumPresentation(id,'separate-window'),/container/i);
  }
  assert.equal(values.size,0);
});
test('invalid modes cannot mutate the saved presentation or any privacy setting',()=>{
  const {api,values}=fixture();
  api.setChromiumPresentation(0,'separate-window');
  for(const mode of [null,true,0,{},'auto','windowless','same-window '])
    assert.throws(()=>api.setChromiumPresentation(0,mode),/presentation/i);
  assert.equal(api.getChromiumPresentation(0),'separate-window');
  assert.equal(values.size,1);
});
test('a malformed stored mode uses same-window without rewriting user policy',()=>{
  const {api,values}=fixture();
  api.setChromiumPresentation(0,'same-window');
  values.set([...values.keys()][0],'unsafe-fallback');
  assert.equal(api.getChromiumPresentation(0),'same-window');
  assert.equal([...values.values()][0],'unsafe-fallback');
});
