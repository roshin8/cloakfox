import {test} from 'node:test';
import assert from 'node:assert/strict';
import {normalizeObservedIP,matchingIPRecords} from '../../additions/browser/components/cloakfox/CloakfoxIPConflicts.sys.mjs';
test('only literal IP addresses accepted and IPv6 canonicalized',()=>{
 assert.equal(normalizeObservedIP('2001:0db8::1'),'2001:db8::1');
 assert.equal(normalizeObservedIP('192.0.2.1'),'192.0.2.1');
 for(const value of ['example.com','999.1.1.1','1.2.3','http://1.2.3.4','::1%lo','<script>',null]) assert.throws(()=>normalizeObservedIP(value));
});
test('compare fresh different containers only; unknown is not a conflict-free measurement',()=>{
 const current={ucid:1,ip:'192.0.2.1',expires:200};
 const rows=[current,{ucid:2,ip:current.ip,expires:200},{ucid:3,ip:current.ip,expires:99},{ucid:4,ip:null,expires:200},{ucid:5,ip:'192.0.2.2',expires:200}];
 assert.deepEqual(matchingIPRecords(current,rows,100).map(r=>r.ucid),[2]);
 assert.deepEqual(matchingIPRecords({...current,ip:null},rows,100),[]);
 assert.deepEqual(matchingIPRecords(current,rows,201),[]);
});

import * as monitor from '../../additions/browser/components/cloakfox/CloakfoxIPConflicts.sys.mjs';
test('website rules match exact hosts and subdomains without suffix confusion',()=>{
 assert.equal(typeof monitor.websiteMatches,'function');
 assert.equal(monitor.websiteMatches('https://login.example.com/path',['example.com']),true);
 assert.equal(monitor.websiteMatches('https://notexample.com',['example.com']),false);
 assert.equal(monitor.websiteMatches('about:blank',['example.com']),false);
 assert.throws(()=>monitor.normalizeDomain('https://example.com/path'));
});
const prefs=new Map();
globalThis.Services={prefs:{getStringPref:(k,d)=>prefs.get(k)??d,setStringPref:(k,v)=>prefs.set(k,v),getBoolPref:(k,d)=>prefs.get(k)??d,setBoolPref:(k,v)=>prefs.set(k,v),savePrefFile(){}},obs:{notifyObservers(){}}};
test('history records bounded URLs, supports reassignment, deletion and IP exceptions',()=>{
 assert.equal(typeof monitor.recordIPAccess,'function');
 monitor.clearIPHistory();
 for(let i=0;i<12;i++) monitor.recordIPAccess('192.0.2.1',1,'https://example.com/'+i+'?secret=token#private');
 let row=monitor.ipHistory()[0];assert.equal(row.accessCount,12);assert.equal(row.urls.length,10);
 assert.ok(row.urls.every(url=>!url.includes('?')&&!url.includes('#')));
 monitor.reassignIP('192.0.2.1',2);assert.equal(monitor.ipHistory()[0].ucid,2);
 monitor.setIPException('192.0.2.1',true);assert.ok(monitor.ipExceptions().includes('192.0.2.1'));
 monitor.setIPException('192.0.2.1',false);assert.equal(monitor.ipExceptions().length,0);
 monitor.clearIPHistory('192.0.2.1');assert.equal(monitor.ipHistory().length,0);
});
test('temporary allowance expires and website exclusions take precedence',()=>{
 assert.equal(typeof monitor.shouldCheckWebsite,'function');
 monitor.setIPRules({mode:'selected',include:['example.com'],exclude:['accounts.example.com']},1);
 assert.equal(monitor.shouldCheckWebsite(1,'https://example.com'),true);
 assert.equal(monitor.shouldCheckWebsite(1,'https://accounts.example.com'),false);
 assert.equal(monitor.shouldCheckWebsite(1,'https://elsewhere.test'),false);
 monitor.allowIPOnce(1,1000);assert.equal(monitor.hasTemporaryIPAllowance(1,30999),true);
 assert.equal(monitor.hasTemporaryIPAllowance(1,31000),false);
});
test('container visits remain separate and expired history is removed from storage',()=>{
 monitor.clearIPHistory();monitor.recordIPAccess('192.0.2.8',1,'https://example.com');monitor.recordIPAccess('192.0.2.8',2,'https://example.com');
 assert.deepEqual(monitor.ipHistory().map(row=>row.ucid).sort(),[1,2]);assert.ok(monitor.ipHistory().every(row=>row.accessCount===1));
 prefs.set('cloakfox.ip_conflicts.history',JSON.stringify([{ip:'192.0.2.8',ucid:1,lastAccessed:Date.now()-31*86400000}]));
 assert.equal(monitor.ipHistory().length,0);assert.equal(prefs.get('cloakfox.ip_conflicts.history'),'[]');
});
test('invalid website rules cannot overwrite the saved rules',()=>{
 const before=monitor.getIPRules(1);assert.throws(()=>monitor.setIPRules({mode:'all',include:['https://example.com'],exclude:[]},1));assert.deepEqual(monitor.getIPRules(1),before);
});

test('warnings require the same exact hostname, same IP and another container',()=>{
 monitor.clearIPHistory();
 monitor.recordIPAccess('192.0.2.10',1,'https://one.example/path');
 assert.deepEqual(monitor.conflictForIP(2,'192.0.2.10','https://two.example/'),[]);
 assert.deepEqual(monitor.conflictForIP(2,'192.0.2.10','https://sub.one.example/'),[]);
 assert.deepEqual(monitor.conflictForIP(1,'192.0.2.10','https://one.example/'),[]);
 assert.deepEqual(monitor.conflictForIP(2,'192.0.2.11','https://one.example/'),[]);
 assert.deepEqual(monitor.conflictForIP(2,'192.0.2.10','http://ONE.example:8080/elsewhere'),[1]);
 assert.deepEqual(monitor.conflictForIP(2,'192.0.2.10'),[]);
});
test('each container and hostname retains independent visits on a shared address',()=>{
 monitor.clearIPHistory();
 monitor.recordIPAccess('192.0.2.11',1,'https://one.example/');
 monitor.recordIPAccess('192.0.2.11',2,'https://two.example/');
 assert.deepEqual(monitor.conflictForIP(3,'192.0.2.11','https://two.example/'),[2]);
 monitor.recordIPAccess('192.0.2.11',2,'https://one.example/');
 assert.deepEqual(monitor.conflictForIP(1,'192.0.2.11','https://one.example/'),[2]);
 assert.deepEqual(monitor.conflictForIP(3,'192.0.2.11','https://one.example/').sort(),[1,2]);
});
test('unscoped legacy history and IP-only observations cannot imply a website visit',()=>{
 monitor.clearIPHistory();
 prefs.set('cloakfox.ip_conflicts.history',JSON.stringify([{ip:'192.0.2.12',ucid:1,lastAccessed:Date.now(),urls:['https://one.example/']}]));
 monitor.recordIPAccess('192.0.2.12',2);
 assert.deepEqual(monitor.conflictForIP(3,'192.0.2.12','https://one.example/'),[]);
});
test('legacy row actions leave scoped website visits intact',()=>{
 monitor.clearIPHistory();
 monitor.recordIPAccess('192.0.2.20',1,'https://one.example/');
 const legacy={ip:'192.0.2.20',ucid:1,lastAccessed:Date.now(),urls:[]};
 prefs.set('cloakfox.ip_conflicts.history',JSON.stringify([...monitor.ipHistory(),legacy]));
 monitor.reassignIP('192.0.2.20',2,1,'');
 assert.deepEqual(monitor.conflictForIP(3,'192.0.2.20','https://one.example/'),[1]);
 monitor.clearIPHistory('192.0.2.20',2,'');
 assert.equal(monitor.ipHistory().length,1);
 assert.equal(monitor.ipHistory()[0].hostname,'one.example');
});
