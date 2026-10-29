import {test} from 'node:test';
import assert from 'node:assert/strict';
import {validateSelectedTabs} from '../../additions/browser/components/cloakfox/CloakfoxContainerTabs.sys.mjs';
const win={};
const tab=(id,container,window=win)=>({id,container,window,closing:false});
const a=tab(1,8),b=tab(2,8),other=tab(3,9),otherWindow=tab(4,8,{});
const lookup=id=>[a,b,other,otherWindow].find(t=>t.id===id);
test('selected tabs are returned without including other tabs',()=>{
 assert.deepEqual(validateSelectedTabs([2,1],8,win,lookup),[b,a]);
});
test('reject unknown, foreign-container, foreign-window and duplicate tabs before closing',()=>{
 for(const ids of [[],[1,1],[99],[1,3],[4],['1']])assert.throws(()=>validateSelectedTabs(ids,8,win,lookup));
});
test('already closed tabs cannot be accidentally reused',()=>{
 assert.throws(()=>validateSelectedTabs([1],8,win,()=>({...a,closing:true})));
});
