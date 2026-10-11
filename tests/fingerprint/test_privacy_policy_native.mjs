import test from 'node:test';import {readFileSync,writeFileSync,mkdtempSync,rmSync} from 'node:fs';import {execFileSync} from 'node:child_process';import {tmpdir} from 'node:os';import {fileURLToPath} from 'node:url';
test('production native policy gates geometry separately, schemeful site, expiry and malformed data',()=>{
 const source=readFileSync(new URL('../../additions/cloakcfg/CloakfoxSiteSeed.hpp',import.meta.url),'utf8');
 const helper=source.slice(source.indexOf('inline bool PolicyAllowsForSite'),source.indexOf('inline bool PolicyAllows('));
 const dir=mkdtempSync(`${tmpdir()}/cloakfox-policy-native-`);
 try{
 writeFileSync(`${dir}/test.cpp`,`#include "json.hpp"
#include "CloakfoxSiteSeedCore.hpp"
#include <cassert>
namespace CloakfoxSiteSeed {${helper}}
using namespace CloakfoxSiteSeed;
int main(){
 auto cfg=nlohmann::json::parse(R"({"privacy:policy":{"version":1,"preset":"standard","exceptions":[{"site":"https://example.com","vectors":["geometry"],"expiresAt":2000}]}})");
 assert(!PolicyAllowsForSite(cfg,"geometry","(https,example.com,f)",1000));
 assert(PolicyAllowsForSite(cfg,"canvas","(https,example.com)",1000));
 assert(PolicyAllowsForSite(cfg,"audio","(https,example.com)",1000));
 assert(PolicyAllowsForSite(cfg,"geometry","(http,example.com)",1000));
 assert(PolicyAllowsForSite(cfg,"geometry","(https,other.com)",1000));
 assert(PolicyAllowsForSite(cfg,"geometry","(https,example.com)",2000));
 assert(PolicyAllowsForSite(cfg,"geometry","opaque",1000));
 cfg["privacy:policy"]["preset"]="compatibility";
 assert(!PolicyAllowsForSite(cfg,"geometry","(https,other.com)",3000));
 assert(PolicyAllowsForSite(cfg,"canvas","(https,other.com)",3000));
 for(const auto bad:{R"({"preset":1})",R"({"version":2,"preset":"compatibility"})",R"({"version":1,"preset":true})"}){
  cfg["privacy:policy"]=nlohmann::json::parse(bad);
  assert(PolicyAllowsForSite(cfg,"geometry","(https,example.com)",1000));
 }
}`);
 const include=fileURLToPath(new URL('../../additions/cloakcfg',import.meta.url));execFileSync('c++',['-std=c++17','-I',include,`${dir}/test.cpp`,'-o',`${dir}/test`]);execFileSync(`${dir}/test`,[]);
 }finally{rmSync(dir,{recursive:true,force:true});}
});
