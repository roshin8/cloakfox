import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import vm from 'node:vm';
import * as identity from '../../additions/browser/components/cloakfox/CloakfoxIdentityActions.sys.mjs';

const paths={clean:'/p/sessionstore.jsonlz4',recovery:'/p/b/recovery.jsonlz4',recoveryBackup:'/p/b/recovery.baklz4',cleanBackup:'/p/b/previous.jsonlz4',upgradeBackup:'/p/b/upgrade.jsonlz4-155',upgradeBackupPrefix:'/p/b/upgrade.jsonlz4-',backups:'/p/b',loadOrder:['clean','recovery','recoveryBackup','cleanBackup','upgradeBackup']};
const mixed=()=>({windows:[{tabs:[{userContextId:0,entries:[{url:'keep'}]},{userContextId:7,entries:[{url:'remove'}]}],selected:2}],cookies:[{originAttributes:{userContextId:7}},{originAttributes:{userContextId:0}}]});
function ioHarness(){
 const files=new Map([paths.cleanBackup,paths.recovery,'/p/b/upgrade.jsonlz4-154','/p/b/previous.js'].map(p=>[p,mixed()]));
 const writes=[];
 return {files,writes,io:{exists:async p=>files.has(p)||p===paths.backups,getChildren:async()=>[...files.keys()].filter(p=>p.startsWith(paths.backups+'/')),
  readJSON:async(p,opts)=>{assert.equal(opts.decompress,p.includes('jsonlz4')||p.includes('baklz4'));return structuredClone(files.get(p))},
  writeJSON:async(p,value,opts)=>{assert.equal(opts.tmpPath,p+'.tmp');assert.equal(opts.compress,p.includes('jsonlz4')||p.includes('baklz4'));assert.equal(opts.backupFile,undefined);files.set(p,structuredClone(value));writes.push(p)}}};
}
test('prunes supported current, previous, upgrade and legacy restore files without losing other containers',async()=>{
 assert.equal(typeof identity.pruneContainerRestoreFiles,'function');
 const h=ioHarness();await identity.pruneContainerRestoreFiles(7,paths,h.io);
 assert.equal(h.writes.length,4);
 for(const state of h.files.values()) {assert.equal(state.windows[0].tabs.length,1);assert.equal(state.windows[0].tabs[0].userContextId,0);assert.equal(state.cookies.length,1)}
});
test('backup read and atomic write failures reject instead of declaring data forgotten',async()=>{
 assert.equal(typeof identity.pruneContainerRestoreFiles,'function');
 for(const op of ['readJSON','writeJSON']) {const h=ioHarness();h.io[op]=async()=>{throw new Error('disk failure')};await assert.rejects(identity.pruneContainerRestoreFiles(7,paths,h.io),/disk failure/)}
});
test('strict SessionFile write rejects original writer failure after removing shutdown blocker', {skip: !existsSync(new URL('../../firefox-src/browser/components/sessionstore/SessionFile.sys.mjs', import.meta.url))}, async()=>{
 const source=readFileSync(new URL('../../firefox-src/browser/components/sessionstore/SessionFile.sys.mjs',import.meta.url),'utf8');
 const begin=source.indexOf('\n  write(aData',source.indexOf('var SessionFileInternal'));
 const method=source.slice(begin,source.indexOf('\n  async wipe()',begin)).trim().replace(/,$/,'');
 const events=[];const error=new Error('disk failure');
 const context=vm.createContext({lazy:{RunState:{isClosed:false,isClosing:false},sessionStoreLogger:{error(){}},SessionStore:{willAutoRestore:false}},
 IOUtils:{profileBeforeChange:{addBlocker(){events.push('add')},removeBlocker(){events.push('remove')}}},Services:{obs:{notifyObservers(){}}}});
 const owner=vm.runInContext('({'+method+'})',context);owner.getWriter=async()=>({write:async()=>{throw error}});owner._attempts=owner._failures=0;
 await assert.rejects(owner.write({}, {throwOnFailure:true}),/disk failure/);
 assert.deepEqual(events,['add','remove']);
});
test('restore-file pruning uses SessionWriter mutex and releases it after failure', {skip: !existsSync(new URL('../../firefox-src/browser/components/sessionstore/SessionWriter.sys.mjs', import.meta.url))}, async()=>{
 const source=readFileSync(new URL('../../firefox-src/browser/components/sessionstore/SessionWriter.sys.mjs',import.meta.url),'utf8');
 const events=[];let finish;
 const context=vm.createContext({XPCOMUtils:{declareLazy:()=>({})},ChromeUtils:{defineESModuleGetters(){},importESModule:()=>({pruneContainerRestoreFiles:async id=>{events.push(id);if(id===7) await new Promise((_,reject)=>{finish=()=>reject(new Error('disk failure'))})}})}});
 vm.runInContext(source.replace(/^import .*;\n/gm,'').replace('export const SessionWriter','const SessionWriter')+';globalThis.writer=SessionWriter;',context);
 const first=context.writer.pruneContainerRestoreFiles(7);
 const rejected=assert.rejects(first,/disk failure/);
 const second=context.writer.pruneContainerRestoreFiles(0);
 await new Promise(resolve=>setImmediate(resolve));
 assert.deepEqual(events,[7]);finish();await rejected;await second;
 assert.deepEqual(events,[7,0]);
});
test('restore persistence failure prevents rotation and reports partial effects',async()=>{
 const events=[];
 const deps={exists:()=>true,preflight(){},acquire:()=>()=>events.push('release'),closeTabs:async()=>{},pruneRestore:async()=>{throw new Error('disk full')},clearData:async()=>{events.push('clear');return 0},rotate:()=>events.push('rotate')};
 await assert.rejects(identity.forgetContainerData(7,{confirmed:true},deps),/Some data may already be removed.*disk full/);
 assert.deepEqual(events,['release']);
});
function workerHelper(manager) {
 const source=readFileSync(new URL('../../additions/browser/components/cloakfox/CloakfoxIdentityActions.sys.mjs',import.meta.url),'utf8');
 const context=vm.createContext({ChromeUtils:{generateQI:()=>()=>{}},Ci:{nsIServiceWorkerRegistrationInfo:{}},setTimeout,clearTimeout});
 vm.runInContext(source.replace(/^export /gm,''),context);
 return {run:()=>context.unregisterContainerWorkers(7,manager,{setTimeout,clearTimeout}),context};
}
test('waits for each target service-worker unregister callback and leaves other containers alone',async()=>{
 const regs=[0,7,7].map((id,i)=>({principal:{originAttributes:{userContextId:id}},scope:'https://example.test/'+i}));
 const callbacks=[];const manager={getAllRegistrations:()=>({length:regs.length,queryElementAt:i=>regs[i]}),propagateUnregister:(principal,cb,scope)=>{callbacks.push({principal,cb,scope})}};
 const helper=workerHelper(manager);assert.equal(typeof helper.context.unregisterContainerWorkers,'function');
 let finished=false;const pending=helper.run().then(()=>{finished=true});
 await new Promise(resolve=>setImmediate(resolve));assert.equal(callbacks.length,2);assert.equal(finished,false);
 callbacks[0].cb.unregisterSucceeded(true);await new Promise(resolve=>setImmediate(resolve));assert.equal(finished,false);
 callbacks[1].cb.unregisterSucceeded(true);await pending;
 assert.ok(callbacks.every(x=>x.principal.originAttributes.userContextId===7));
});
test('service-worker unregister failure is reported instead of treated as successful clear',async()=>{
 const manager={getAllRegistrations:()=>({length:1,queryElementAt:()=>({principal:{originAttributes:{userContextId:7}},scope:'https://example.test/'})}),propagateUnregister:(_p,cb)=>cb.unregisterFailed()};
 const helper=workerHelper(manager);assert.equal(typeof helper.context.unregisterContainerWorkers,'function');
 await assert.rejects(helper.run(),/Service worker unregister failed/);
});
test('default-container clearing preserves shared permission flags; other IDs retain exact scope',()=>{
 const flags={CLEAR_ALL:0xffffffff,CLEAR_SITE_PERMISSIONS:1,CLEAR_STORAGE_ACCESS:2,CLEAR_STORAGE_PERMISSIONS:4,CLEAR_SHUTDOWN_EXCEPTIONS:8};
 assert.equal(identity.containerClearFlags(0,flags),0xfffffff0);
 assert.equal(identity.containerClearFlags(7,flags),0xffffffff);
});
test('cookie cleanup verification rejects residual target cookies but preserves other containers',()=>{
 assert.equal(typeof identity.assertContainerCookiesCleared,'function');
 assert.throws(()=>identity.assertContainerCookiesCleared(7,[{originAttributes:{userContextId:7}}]),/cookies remain/);
 assert.doesNotThrow(()=>identity.assertContainerCookiesCleared(7,[{originAttributes:{}},{originAttributes:{userContextId:2}}]));
});
