import {test} from 'node:test';
import assert from 'node:assert/strict';
import {validateBulkSelection,bulkProxyRows} from '../../additions/browser/components/cloakfox/CloakfoxContainerBulk.sys.mjs';
const identities=[{id:1,name:'Personal'},{id:2,name:'Work'},{id:3,name:'Other'}];
test('selection rejects default, missing, duplicate and empty IDs before mutation',()=>{
 for(const ids of [[],[0],[1,1],[99],['1']])assert.throws(()=>validateBulkSelection(ids,identities));
 assert.deepEqual(validateBulkSelection([2,1],identities).map(x=>x.name),['Work','Personal']);
});
test('bulk proxy copy preserves auth, isolates connections, leaves unselected rows intact',()=>{
 const rows=[{cookieStoreId:'firefox-container-1',proxy:{type:'http',host:'proxy',port:80,proxyAuthorizationHeader:'Basic fixture'}},{cookieStoreId:'firefox-container-3',proxy:{type:'socks',host:'other',port:1080}}];
 const result=bulkProxyRows(rows,[1,2],rows[0].proxy,id=>'key-'+id);
 assert.equal(result[0].proxy.proxyAuthorizationHeader,'Basic fixture');
 assert.equal(result.find(x=>x.cookieStoreId==='firefox-container-2').proxy.connectionIsolationKey,'key-2');
 assert.deepEqual(result.find(x=>x.cookieStoreId==='firefox-container-3'),rows[1]);
 assert.equal(rows[0].proxy.connectionIsolationKey,undefined);
});
test('remove proxy only changes selected containers',()=>{
 const rows=[{cookieStoreId:'firefox-container-1',proxy:{type:'http'}},{cookieStoreId:'firefox-container-2',proxy:{type:'http'}}];
 const result=bulkProxyRows(rows,[1],null,()=>null);
 assert.equal(result[0].proxy,null);assert.deepEqual(result[1],rows[1]);
});
