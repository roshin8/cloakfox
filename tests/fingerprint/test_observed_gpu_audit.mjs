import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const available=fs.existsSync('tests/fingerprint/reports/library-fixtures/creepjs/src/webgl/index.ts');
test('complete original Windows and Apple reference records are recognized before execution admission',{skip:!available},()=>{
 const {rows}=require('../../scripts/audit-observed-gpu-profiles.cjs');
 for(const id of ['165cf47b5f7d3a73e3c6d237c7110db7c674356b20a41846db90263817a36363','9bc697f54e04df4da5771d3f913de083019fe449929b97a94dd0432020ccb531','3f9b16196a1d6ff1f80adf429c8b2cfbda1539dac05aa1b2b511a5d29cd56075','27053b853db1c3399a7426ba0d80ed347f36517a6e8741a0ab5f52f86550046b']){
  const r=rows.find(r=>r.id==='sha256:'+id);assert.ok(r);assert.equal(r.original.brandKnown,true);assert.equal(r.original.capabilitiesKnown,true);
 }
});
test('source projection reproduces real saved native Apple numeric parameters',{skip:!available||!fs.existsSync('tests/fingerprint/reports/firefox159-native-reference-layout/libraries-reference-layout-1/probe_fingerprint_libraries/native-creepjs-0.json')},()=>{
 const{corpus,projection,analyze}=require('../../scripts/audit-observed-gpu-profiles.cjs');const record=corpus.records.find(r=>r.id.includes('165cf47b'));const projected=projection(record);const actual=JSON.parse(fs.readFileSync('tests/fingerprint/reports/firefox159-native-reference-layout/libraries-reference-layout-1/probe_fingerprint_libraries/native-creepjs-0.json')).fingerprint.canvasWebgl.parameters;
 for(const[k,v]of Object.entries(projected))if(typeof v!=='string')assert.deepEqual(actual[k],v,k);
 assert.deepEqual(analyze(record,projected),analyze(record,actual));
});
