import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../../additions/browser/components/cloakfox/CloakfoxPrivacyPolicy.sys.mjs',import.meta.url),'utf8').replaceAll('export function','function').replaceAll('export const','const');
const context=vm.createContext({URL,Date,Services:{eTLD:{getBaseDomainFromHost:h=>{if(!h.includes('.'))throw Error('insufficient levels');return h.split('.').slice(-2).join('.');}}}});
vm.runInContext(source+'\nthis.api={validatePrivacyPolicy,policyAllows,applyPrivacyPolicy};',context);
const {validatePrivacyPolicy,policyAllows}=context.api;
const policy={version:1,preset:'standard',exceptions:[{site:'https://example.com',vectors:['geometry'],expiresAt:2000}]};
test('exceptions follow top-level schemeful site, vector and expiry independently',()=>{
 const p=validatePrivacyPolicy(policy);
 assert.equal(policyAllows(p,'geometry','(https,example.com,f)',1000),false);
 for(const [vector,site,time] of [['canvas','(https,example.com)',1000],['geometry','(http,example.com)',1000],['geometry','(https,other.com)',1000],['geometry','(https,example.com)',2000]])assert.equal(policyAllows(p,vector,site,time),true);
});
test('invalid and excessively broad exceptions rejected',()=>{
 for(const site of ['*','https://example.com/path','https://user@example.com','http://localhost','https://example.com:443'])assert.throws(()=>validatePrivacyPolicy({...policy,exceptions:[{...policy.exceptions[0],site}]}));
 for(const vectors of [[],['fonts'],['canvas','canvas']])assert.throws(()=>validatePrivacyPolicy({...policy,exceptions:[{...policy.exceptions[0],vectors}]}));
 assert.throws(()=>validatePrivacyPolicy({...policy,secret:'no'}));
});
test('presets only alter specified vectors and strict API flags',()=>{
 assert.equal(policyAllows({version:1,preset:'compatibility',exceptions:[]},'geometry','(https,x.com)',1),false);
 assert.equal(policyAllows({version:1,preset:'compatibility',exceptions:[]},'canvas','(https,x.com)',1),true);
});
