import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, rmSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { createHmac } from 'node:crypto';

test('production C++ protocol matches HMAC vectors, opaque keys and ancestor normalization', () => {
  const dir = mkdtempSync(`${tmpdir()}/cloakfox-site-test-`);
  const include = fileURLToPath(new URL('../../additions/cloakcfg', import.meta.url));
  const secret = Buffer.alloc(32,19).toString('base64');
  const digest = createHmac('sha256',secret).update('cloakfox-site-v1\ncanvas:seed\n42\n(https,example.co.uk)').digest();
  try {
    writeFileSync(`${dir}/test.cpp`, `#include "CloakfoxSiteSeedCore.hpp"
#include <cassert>
using namespace CloakfoxSiteSeed;
int main() {
 assert(Message("canvas:seed",42,"(https,example.co.uk,f)")=="cloakfox-site-v1\\ncanvas:seed\\n42\\n(https,example.co.uk)");
 assert(CanonicalSiteKey("(http,localhost)")=="(http,localhost)");
 assert(CanonicalSiteKey("(https,[::1],f)")=="(https,[::1])");
 assert(CanonicalSiteKey("12345678-1234-1234-1234-123456789abc.mozilla")=="12345678-1234-1234-1234-123456789abc.mozilla");
 for (const auto* key : {"", "null", "(https,)", "(https,x,garbage)", "https://tracker.com"}) assert(CanonicalSiteKey(key).empty());
 assert(Message("canvas:seed",0,"(https,example.com)").empty());
 assert(ValidSecret("${secret}")); assert(!ValidSecret("bad"));
 const uint8_t digest[] = {${[...digest].join(',')}};
 assert(SeedFromDigest(digest)==${digest.readUInt32BE(0)}u);
 const uint8_t zero[4] = {}; assert(SeedFromDigest(zero)==1);
}`);
    execFileSync('c++',['-std=c++17','-I',include,`${dir}/test.cpp`,'-o',`${dir}/test`]);
    execFileSync(`${dir}/test`,[]);
  } finally { rmSync(dir,{recursive:true,force:true}); }
});

test('native exact-container cfg lookup keeps ucid zero independent of ambient JS', () => {
  const source=readFileSync(new URL('../../additions/cloakcfg/CloakfoxSiteSeed.hpp',import.meta.url),'utf8');
  const helpers=source.slice(source.indexOf('// MaskConfig\'s legacy'),source.indexOf('// Invalid policy data'));
  const dir=mkdtempSync(`${tmpdir()}/cloakfox-exact-config-`);
  const include=fileURLToPath(new URL('../../additions/cloakcfg',import.meta.url));
  try {
    writeFileSync(`${dir}/test.cpp`, `#include "json.hpp"
#include "CloakfoxSiteSeedCache.hpp"
using namespace CloakfoxSiteSeed;
#include <cassert>
#include <optional>
#include <cstdint>
#include <string>
std::string CloakConfigOverlay_Get(uint32_t id) {
 if(id==999) return "";
 return id==0 ? R"({"canvas:seed":0,"fingerprint:secret":"default-secret"})" : R"({"canvas:seed":999,"fingerprint:secret":"other-secret"})";
}
namespace MaskConfig { nlohmann::json GetJson(){ return {{"canvas:seed",777},{"fingerprint:secret","global"}}; } }
namespace Site { ${helpers} }
int main(){
 assert(Site::BaseSeed(0,"canvas:seed").value()==0);
 assert(Site::BaseSeed(7,"canvas:seed").value()==999);
 assert(Site::ExactConfig(0)["fingerprint:secret"]=="default-secret");
 assert(!Site::BaseSeed(0,"missing:seed"));
 assert(Site::ExactConfig(999).empty());
 assert(!Site::BaseSeed(999,"canvas:seed"));
}`);
    execFileSync('c++',['-std=c++17','-I',include,`${dir}/test.cpp`,'-o',`${dir}/test`]);
    execFileSync(`${dir}/test`,[]);
  } finally { rmSync(dir,{recursive:true,force:true}); }
});
