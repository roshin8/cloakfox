import {test} from 'node:test';
import assert from 'node:assert/strict';
import {proxyIndicatorState} from '../../additions/browser/components/cloakfox/CloakfoxProxyIndicator.sys.mjs';
test('MAC proxy status describes configuration without disclosing credentials',()=>{
 const s=proxyIndicatorState({mode:0}, {type:'http',host:'pr.oxylabs.io',port:7777,proxyAuthorizationHeader:'Basic secret'});
 assert.equal(s.label,'Proxy');assert.match(s.tooltip,/pr\.oxylabs\.io:7777/);assert.match(s.tooltip,/Authentication configured/);assert.doesNotMatch(JSON.stringify(s),/secret|successfully connected/i);
});
test('native blocked route overrides MAC and direct has no proxy badge',()=>{
 assert.equal(proxyIndicatorState({mode:2},{type:'http',host:'proxy',port:80}).label,'Blocked');
 assert.equal(proxyIndicatorState({mode:0},null),null);
 assert.equal(proxyIndicatorState({mode:0},{type:'direct'}),null);
});
test('native proxy takes priority and URLs never expose credentials',()=>{
 const s=proxyIndicatorState({mode:1,proxyURL:'http://private:secret@localhost:8080'}, {type:'http',host:'other',port:80});
 assert.match(s.tooltip,/localhost:8080/);assert.doesNotMatch(s.tooltip,/secret|private|other/);
});
