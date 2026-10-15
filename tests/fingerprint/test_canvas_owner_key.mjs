import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';
import {createHmac} from 'node:crypto';
test('native canvas owner token preserves 128 bits and separates disabled seed and canonical top site',()=>{
 const dir=mkdtempSync(`${tmpdir()}/canvas-owner-`),include=fileURLToPath(new URL('../../additions/cloakcfg',import.meta.url));
 const message='cloakfox-canvas-owner-v1\n0\n(https,example.com)',digest=createHmac('sha256','test').update(message).digest();
 try {
  writeFileSync(`${dir}/owner.cpp`,`#include "CloakfoxSiteSeedCore.hpp"
#include <cassert>
using namespace CloakfoxSiteSeed;
int main(){
 assert(CanvasOwnerMessage(0,"(https,example.com,f)")=="cloakfox-canvas-owner-v1\\n0\\n(https,example.com)");
 assert(CanvasOwnerMessage(1,"(https,example.com)")!=CanvasOwnerMessage(0,"(https,example.com)"));
 assert(CanvasOwnerMessage(0,"(http,example.com)")!=CanvasOwnerMessage(0,"(https,example.com)"));
 assert(CanvasOwnerMessage(0,"https://frame.example.com").empty());
 const uint8_t digest[]={${[...digest].join(',')}};
 auto owner=CanvasOwnerFromDigest(digest,sizeof(digest));assert(owner);
 assert((*owner)[0]==${digest.readBigUInt64BE(0)}ull && (*owner)[1]==${digest.readBigUInt64BE(8)}ull);
 uint8_t zero[32]={};assert(!CanvasOwnerFromDigest(zero,32));assert(!CanvasOwnerFromDigest(nullptr,32));assert(!CanvasOwnerFromDigest(digest,8));
 uint8_t other[32]={};other[15]=1;assert(CanvasOwnerFromDigest(other,32));
}`);
  execFileSync('c++',['-std=c++17','-I',include,`${dir}/owner.cpp`,'-o',`${dir}/owner`]);execFileSync(`${dir}/owner`,[]);
 } finally {rmSync(dir,{recursive:true,force:true});}
});
