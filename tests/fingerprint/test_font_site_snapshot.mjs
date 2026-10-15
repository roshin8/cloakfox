import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdtempSync,rmSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {tmpdir} from 'node:os';

test('production font seed lookup uses prepared owner identity on style threads and observes changes',()=>{
 const patch=readFileSync(new URL('../../patches/site-fingerprint-isolation.patch',import.meta.url),'utf8');
 const filePatch=patch.split('--- a/gfx/thebes/gfxTextRun.cpp\n')[1].split('--- a/')[0];
 const source=filePatch.split('\n').filter(line=>line.startsWith(' ')||(line.startsWith('+')&&!line.startsWith('+++'))).map(line=>line.slice(1)).join('\n');
 const method=source.match(/uint32_t gfxFontGroup::GetSiteSeed\(\) const \{[\s\S]*?\n\}/)?.[0];
 assert.ok(method,'Font groups need a live owner-snapshot accessor');
 const dir=mkdtempSync(`${tmpdir()}/cloakfox-font-owner-`);
 try {
  writeFileSync(`${dir}/test.cpp`, `#include <cassert>
#include <cstdint>
#include <optional>
struct Document {};
bool mainThread = false;
bool NS_IsMainThread() { return mainThread; }
struct Provider {
 std::optional<uint64_t> identity;
 std::optional<uint64_t> GetCloakfoxFontIdentity() const { return identity; }
 Document* GetDocument() { assert(mainThread); return nullptr; }
};
int fallbacks = 0;
namespace CloakfoxSiteSeed {
 uint32_t ForContext(uint32_t id, const char*, Document*) { ++fallbacks; return id + 10; }
}
struct gfxFontGroup {
 Provider* mFontVisibilityProvider;
 uint32_t mUserContextId;
 uint32_t GetSiteSeed() const;
};
${method}
int main() {
 Provider owner{(uint64_t(7)<<32)|123u};
 gfxFontGroup group{&owner,7};
 assert(group.GetSiteSeed()==123); assert(fallbacks==0);
 owner.identity=(uint64_t(7)<<32)|456u;
 assert(group.GetSiteSeed()==456); assert(fallbacks==0);
 owner.identity=(uint64_t(7)<<32);
 assert(group.GetSiteSeed()==0); assert(fallbacks==0);
 owner.identity.reset();
 assert(group.GetSiteSeed()==17); assert(fallbacks==1);
}`);
 execFileSync('c++',['-std=c++17',`${dir}/test.cpp`,'-o',`${dir}/test`]);
 execFileSync(`${dir}/test`);
 } finally {rmSync(dir,{recursive:true,force:true});}
});

test('production SeedSync emits one mirror refresh and scoped language invalidation without observer recursion', async()=>{
 const {default:vm}=await import('node:vm');
 const source=readFileSync(new URL('../../additions/browser/components/cloakfox/CloakfoxSeedSync.sys.mjs',import.meta.url),'utf8');
 const block=source.slice(source.indexOf('const observer = {'),source.indexOf('// Containers created AFTER startup'));
 const prefs=new Map();let publishes=0,ctx;
 ctx=vm.createContext({publish(){publishes++;},Services:{prefs:{getStringPref:(key,fallback)=>prefs.get(key)??fallback,getIntPref:(key,fallback)=>prefs.get(key)??fallback,
  setIntPref(key,value){prefs.set(key,value);ctx.observer.observe(null,'nsPref:changed',key);}}}});
 vm.runInContext(block+'\nthis.observer=observer;',ctx);
 ctx.observer.observe(null,'nsPref:changed','cloakfox.s.cloak_cfg_3');
 assert.equal(prefs.get('cloakfox.font_identity_epoch'),1);
 assert.equal(prefs.get('cloakfox.language_identity_epoch.3'),1);
 assert.equal(prefs.get('cloakfox.language_identity_epoch.0'),undefined);
 assert.equal(publishes,1);
 ctx.observer.observe(null,'nsPref:changed','cloakfox.container.3.network_mode');
 assert.equal(prefs.get('cloakfox.font_identity_epoch'),1);
 prefs.set('cloakfox.font_identity_epoch',0x7fffffff);
 ctx.observer.observe(null,'nsPref:changed','cloakfox.s.cloak_cfg_3');
 assert.equal(prefs.get('cloakfox.font_identity_epoch'),0);
});
