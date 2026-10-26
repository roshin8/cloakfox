import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildMACProxy,readMACCredentials} from '../../additions/browser/components/cloakfox/CloakfoxContainerProxyEditor.sys.mjs';
test('HTTP credentials round-trip special characters and Unicode',()=>{
 for(const password of ['a=b:c@d /%','päss🔒']){
  const proxy=buildMACProxy('http://proxy.example:7777','customer-city-chicago',password,'test-key');
  assert.match(proxy.proxyAuthorizationHeader,/^Basic /);
  assert.deepEqual(readMACCredentials(proxy),{username:'customer-city-chicago',password});
  assert.equal(proxy.username,undefined);assert.equal(proxy.password,undefined);
 }
});
test('editing server preserves loaded auth and explicit clearing removes it',()=>{
 const saved=buildMACProxy('http://old.example:7777','customer','p=ss','old');
 const {username,password}=readMACCredentials(saved);
 const changed=buildMACProxy('https://new.example:8888',username,password,'new');
 assert.equal(changed.proxyAuthorizationHeader,saved.proxyAuthorizationHeader);
 assert.equal(changed.host,'new.example');assert.equal(changed.connectionIsolationKey,'new');
 const cleared=buildMACProxy('http://new.example:7777','','','clear');
 assert.equal(cleared.proxyAuthorizationHeader,undefined);
});
test('SOCKS authentication uses native username/password fields',()=>{
 const proxy=buildMACProxy('socks://proxy.example:1080','user','p=ss','key');
 assert.equal(proxy.password,'p=ss');assert.equal(proxy.proxyAuthorizationHeader,undefined);
 assert.deepEqual(readMACCredentials(proxy),{username:'user',password:'p=ss'});
});
test('invalid input is rejected instead of silently changing the proxy',()=>{
 for(const server of ['proxy.example:7777','ftp://proxy.example:7777','http://user:pass@proxy.example:7777','http://proxy.example:99999','http://proxy.example/path','http://proxy.example?secret=1']){
  assert.throws(()=>buildMACProxy(server,'u','p','key'));
 }
 assert.throws(()=>buildMACProxy('http://proxy.example:7777','u:bad','p','key'));
 assert.throws(()=>buildMACProxy('http://proxy.example:7777','','password','key'));
 assert.throws(()=>readMACCredentials({proxyAuthorizationHeader:'Bearer unsupported'}));
 assert.throws(()=>readMACCredentials({proxyAuthorizationHeader:'Basic !!!'}));
});
