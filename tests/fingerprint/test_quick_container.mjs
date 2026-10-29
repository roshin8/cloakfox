import test from 'node:test';
import assert from 'node:assert/strict';
import { chooseQuickContainerOptions } from '../../additions/browser/components/cloakfox/CloakfoxQuickContainer.sys.mjs';

test('generated names avoid existing names and reuse the first available number',()=>{
  const result=chooseQuickContainerOptions([{name:'Container #01',color:'blue'},{name:'container #03',color:'red'}],['blue','red','green'],()=>0);
  assert.equal(result.name,'Container #02');
  assert.equal(result.color,'green');
});
test('random choice is limited to the least-used supported colors',()=>{
  const existing=[{name:'One',color:'blue'},{name:'Two',color:'red'},{name:'Three',color:'blue'}];
  assert.equal(chooseQuickContainerOptions(existing,['blue','red','green','teal'],()=>0).color,'green');
  assert.equal(chooseQuickContainerOptions(existing,['blue','red','green','teal'],()=>1).color,'teal');
  assert.equal(chooseQuickContainerOptions(existing,['blue','red'],()=>0).color,'red');
});
test('a missing palette fails before creating anything',()=>{
  assert.throws(()=>chooseQuickContainerOptions([],[],()=>0));
});

test('toolbar replaces the temporary-container button at the same position',async()=>{
  const {initQuickContainerButton}=await import('../../additions/browser/components/cloakfox/CloakfoxQuickContainer.sys.mjs');
  const old='_c607c8df-14a7-4f28-894f-29e8722976af_-browser-action';
  const placements=new Map([[old,{area:'TabsToolbar',position:7}]]);
  let definition,listener,migrated=false;
  const ui={AREA_TABSTRIP:'TabsToolbar',createWidget:d=>definition=d,getPlacementOfWidget:id=>placements.get(id),addWidgetToArea:(id,area,position)=>placements.set(id,{area,position}),removeWidgetFromArea:id=>placements.delete(id),addListener:l=>listener=l};
  globalThis.ChromeUtils={importESModule:()=>({CustomizableUI:ui})};
  globalThis.Services={obs:{addObserver(){}},wm:{getMostRecentWindow:()=>({gBrowserInit:{delayedStartupFinished:true}})},tm:{dispatchToMainThread:fn=>fn()},prefs:{getBoolPref:()=>migrated,setBoolPref:(_,v)=>migrated=v}};
  initQuickContainerButton();
  assert.equal(placements.has(old),false);
  assert.deepEqual(placements.get(definition.id),{area:'TabsToolbar',position:7});
  assert.equal(typeof definition.onCommand,'function');
  placements.set(old,{area:'TabsToolbar',position:8});listener.onWidgetAdded(old);
  assert.equal(placements.has(old),false);
  delete globalThis.ChromeUtils;delete globalThis.Services;
});
