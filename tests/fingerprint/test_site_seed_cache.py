"""Exercise production Derive: cache hits must preserve policy and owner boundaries."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class SiteSeedCache(unittest.TestCase):
    def test_derivation_cache_is_scoped_and_invalidates(self):
        source = (ROOT / 'additions/cloakcfg/CloakfoxSiteSeed.hpp').read_text()
        # Compile real lookup, policy and derivation against small Gecko/NSS adapters.
        start = source.index('// MaskConfig\'s legacy')
        end = source.index('inline std::optional<std::array<uint64_t, 2>> OwnerKey')
        code = r'''
#include "json.hpp"
#include "CloakfoxSiteSeedCore.hpp"
#if __has_include("CloakfoxSiteSeedCache.hpp")
#include "CloakfoxSiteSeedCache.hpp"
#endif
#include <cassert>
#include <map>
#include <vector>
#include <thread>
thread_local std::map<uint32_t,std::string> overlays;
thread_local int hmacCalls=0;
thread_local int64_t now=1000;
std::string CloakConfigOverlay_Get(uint32_t owner){return overlays[owner];}
using nsAutoString=std::string;
struct NS_ConvertUTF16toUTF8 {std::string value; NS_ConvertUTF16toUTF8(std::string v):value(v){} const char* get(){return value.c_str();}};
struct nsICookieJarSettings {std::string key;int failure=0;int GetPartitionKey(std::string& out){out=key;return failure;}};
bool NS_FAILED(int code){return code!=0;}
int64_t PR_Now(){return now*1000;}
constexpr int PR_USEC_PER_MSEC=1000, SEC_OID_SHA256=1;
template<class T> struct nsTArray:std::vector<T>{size_t Length(){return this->size();}const T* Elements(){return this->data();}};
namespace mozilla {
struct Span {const uint8_t* data;size_t size;Span(const uint8_t* d,size_t s):data(d),size(s){}};
struct HMAC {
 uint32_t hash=2166136261u;
 int Begin(int,Span key){++hmacCalls;return Update(key.data,key.size);}
 int Update(const uint8_t* data,size_t size){for(size_t i=0;i<size;i++)hash=(hash^data[i])*16777619u;return 0;}
 int End(nsTArray<uint8_t>& out){out.resize(32);for(int i=0;i<4;i++)out[i]=hash>>(24-8*i);return 0;}
};
}
namespace CloakfoxSiteSeed {
''' + source[start:end] + r'''
}
using namespace CloakfoxSiteSeed;
int main(){
 auto cfg=nlohmann::json{{"canvas:seed",42u},{"audio:seed",43u},{"fingerprint:secret",std::string(43,'A')+"="}};
 overlays[0]=overlays[44]=cfg.dump();
 nsICookieJarSettings amazon{"(https,amazon.com)"}, other{"(https,example.org)"};
 auto first=Derive(44,"canvas:seed",&amazon,"geometry");assert(first);
 for(int i=0;i<1000;i++)assert(Derive(44,"canvas:seed",&amazon,"geometry")==first);
 assert(hmacCalls==1); // Removing caching must fail here.
 assert(Derive(0,"canvas:seed",&amazon,"geometry")==first);assert(hmacCalls==2);
 auto second=Derive(44,"canvas:seed",&other,"geometry");assert(second!=first);assert(hmacCalls==3);
 assert(Derive(44,"canvas:seed",&amazon,"geometry")==first);assert(hmacCalls==3);
 assert(Derive(44,"audio:seed",&amazon)!=first);assert(hmacCalls==4);
 // Ancestor normalization is the same site, not a new identity.
 amazon.key="(https,amazon.com,f)";assert(Derive(44,"canvas:seed",&amazon,"geometry")==first);assert(hmacCalls==4);
 amazon.key="(https,amazon.com)";
 cfg["canvas:seed"]=99u;overlays[44]=cfg.dump();
 assert(Derive(44,"canvas:seed",&amazon,"geometry")!=first);assert(hmacCalls==5);
 cfg["canvas:seed"]=42u;cfg["fingerprint:secret"]=std::string(43,'B')+"=";overlays[44]=cfg.dump();
 auto rotated=Derive(44,"canvas:seed",&amazon,"geometry");assert(rotated!=first);assert(hmacCalls==6);
 cfg["privacy:policy"]={{"version",1},{"preset","standard"},{"exceptions",nlohmann::json::array({{{"site","https://amazon.com"},{"expiresAt",1001},{"vectors",{"geometry"}}}})}};
 overlays[44]=cfg.dump();
 assert(Derive(44,"canvas:seed",&amazon,"geometry")==0);assert(hmacCalls==6);
 // Same bytes, different clock: do not cache an exception past expiry.
 now=1001;assert(Derive(44,"canvas:seed",&amazon,"geometry")==rotated);assert(hmacCalls==7);
 now=1000;assert(Derive(44,"canvas:seed",&amazon,"geometry")==0);assert(hmacCalls==7);
 assert(Derive(44,"canvas:seed",&amazon,"canvas")==rotated);assert(hmacCalls==7);
 cfg["privacy:policy"]["preset"]="compatibility";overlays[44]=cfg.dump();now=9999;
 assert(Derive(44,"canvas:seed",&amazon,"geometry")==0);
 for(auto invalid:{"", "{broken", "[]", "null"}){overlays[44]=invalid;assert(Derive(44,"canvas:seed",&amazon,"geometry")==0);}
 cfg.erase("privacy:policy");cfg["canvas:seed"]=0u;overlays[44]=cfg.dump();assert(Derive(44,"canvas:seed",&amazon)==0);
 cfg["canvas:seed"]=42u;overlays[44]=cfg.dump();assert(Derive(44,"canvas:seed",&amazon)==rotated);
 amazon.failure=1;assert(Derive(44,"canvas:seed",&amazon)==0);amazon.failure=0;
 amazon.key="";assert(Derive(44,"canvas:seed",&amazon)==0);amazon.key="(https,amazon.com)";
 assert(Derive(44,"canvas:seed",nullptr)==0);
 // Eviction must not change outputs or alias new owners/sites.
 for(uint32_t owner=1;owner<200;owner++){overlays[owner]=cfg.dump();assert(Derive(owner,"canvas:seed",&amazon)==rotated);}
 for(int i=0;i<200;i++){other.key="(https,site"+std::to_string(i)+".test)";assert(Derive(44,"canvas:seed",&other));}
 assert(Derive(44,"canvas:seed",&amazon)==rotated);
 // Workers use independent caches, not another thread's snapshot.
 std::thread worker([&]{overlays[44]=cfg.dump();assert(hmacCalls==0);assert(Derive(44,"canvas:seed",&amazon)==rotated);assert(hmacCalls==1);});worker.join();
 assert(Derive(0,"canvas:seed",&amazon)==first);
}
'''
        with tempfile.TemporaryDirectory(prefix='cloakfox-site-cache-') as temp:
            p=Path(temp);(p/'test.cpp').write_text(code)
            build=subprocess.run(['clang++','-std=c++17','-pthread','-I',str(ROOT/'additions/cloakcfg'),str(p/'test.cpp'),'-o',str(p/'test')],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            run=subprocess.run([str(p/'test')],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)

    def test_snapshot_reuse_replacement_and_bounded_lifetime(self):
        code=r'''
#include "CloakfoxSiteSeedCache.hpp"
#include <cassert>
using namespace CloakfoxSiteSeed;
int main(){
 SiteSeedCache cache;
 auto first=cache.Get(0,R"({"canvas:seed":42})");
 for(int i=0;i<1000;i++) assert(cache.Get(0,R"({"canvas:seed":42})")==first);
 assert(cache.Get(44,R"({"canvas:seed":42})")!=first);
 auto replacement=cache.Get(0,R"({"canvas:seed":43})");
 assert(replacement!=first);assert(first->Config()["canvas:seed"]==42);
 assert(replacement->Config()["canvas:seed"]==43);
 int computes=0;
 assert(first->Seed("message",[&]{++computes;return 0u;})==0);
 assert(first->Seed("message",[&]{++computes;return 7u;})==7);
 assert(first->Seed("message",[&]{++computes;return 8u;})==7);assert(computes==2);
 for(int i=0;i<1000;i++)first->Seed(std::to_string(i),[]{return 9u;});
 assert(first->Seed("message",[&]{++computes;return 7u;})==7);assert(computes==3);
 std::weak_ptr<ConfigSnapshot> evicted=replacement;replacement.reset();
 for(int i=1;i<100;i++)cache.Get(i,"{}");
 assert(evicted.expired());
 assert(first->Config()["canvas:seed"]==42); // in-flight references survive eviction
 assert(cache.Get(0,"{invalid")->Config().empty());
 assert(cache.Get(0,"[]")->Config().empty());
 assert(cache.Get(0,"{}")->Config().empty());
}
'''
        with tempfile.TemporaryDirectory(prefix='cloakfox-snapshot-cache-') as temp:
            p=Path(temp);(p/'test.cpp').write_text(code)
            build=subprocess.run(['clang++','-std=c++17','-I',str(ROOT/'additions/cloakcfg'),str(p/'test.cpp'),'-o',str(p/'test')],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            run=subprocess.run([str(p/'test')],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
