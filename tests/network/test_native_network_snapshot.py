"""Exercise the production wildcard conversion after its owner's prefs change.

A small harness substitutes Gecko ownership/string facilities, but compiles the
actual CreateWildCard body from the freshly patched Gecko source.
The live proxy routing probes cover network exchanges separately.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class NativeNetworkSnapshot(unittest.TestCase):
    def test_proxy_wildcard_preserves_captured_network_and_security_state(self):
        native = ROOT / 'firefox-src/netwerk/protocol/http/nsHttpConnectionInfo.cpp'
        if not native.is_file():
            self.skipTest('Requires patched Gecko source; exercised in both build jobs')
        source = native.read_text()
        start = source.index('nsresult nsHttpConnectionInfo::CreateWildCard(')
        end = source.index('\n}', start) + 2
        method = source[start:end]
        compiler = shutil.which('c++')
        assert compiler
        harness = r'''
    #include <cassert>
    #include <cstdint>
    #include <memory>
    #include <string>
    using nsresult = int;
    constexpr int NS_OK=0, NS_ERROR_NOT_IMPLEMENTED=1;
    #define MOZ_ASSERT(v) assert(v)
    static uint32_t currentProfile=1, currentGeneration=1;
    std::string operator""_ns(const char* s, size_t n) { return {s,n}; }
    template<typename T> struct RefPtr {
     T* p=nullptr;
     RefPtr& operator=(T* v) { p=v; return *this; }
     T* operator->() { return p; }
     void forget(T** out) { *out=p; p=nullptr; }
    };
    struct nsHttpConnectionInfo {
     bool mUsingHttpsProxy=true, anonymous=false, privateMode=false, fallback=false, conservative=false;
     std::string mNPNToken="h2",mUsername;
     int mProxyInfo=0,mOriginAttributes=0;
     bool mIsHttp3=false,mWebTransport=false;
     uint32_t mCloakfoxProfile=currentProfile,mCloakfoxGeneration=currentGeneration,tlsFlags=0;
     nsHttpConnectionInfo() = default;
     nsHttpConnectionInfo(std::string,int,std::string,std::string,int,int,bool,bool h3,bool wt)
       :mIsHttp3(h3),mWebTransport(wt) {}
     bool GetAnonymous()const{return anonymous;} void SetAnonymous(bool v){anonymous=v;}
     bool GetPrivate()const{return privateMode;} void SetPrivate(bool v){privateMode=v;}
     bool GetFallbackConnection()const{return fallback;} void SetFallbackConnection(bool v){fallback=v;}
     bool GetBeConservative()const{return conservative;} void SetBeConservative(bool v){conservative=v;}
     uint32_t GetTlsFlags()const{return tlsFlags;} void SetTlsFlags(uint32_t v){tlsFlags=v;}
     nsresult CreateWildCard(nsHttpConnectionInfo**);
    };
    '''
        checks = r'''
    int main() {
     for(bool h3 : {false,true}) {
       nsHttpConnectionInfo original;
       original.mIsHttp3=h3;
       original.tlsFlags=0x40000103;
       currentProfile=0;currentGeneration=2;
       nsHttpConnectionInfo* wildcard=nullptr;
       assert(original.CreateWildCard(&wildcard)==NS_OK);
       assert(wildcard->mCloakfoxProfile==original.mCloakfoxProfile);
       assert(wildcard->mCloakfoxGeneration==original.mCloakfoxGeneration);
       assert(wildcard->GetTlsFlags()==original.GetTlsFlags());
       delete wildcard;
       original.conservative=true;
       original.tlsFlags=0x00000103;
       currentProfile=1;currentGeneration=3;
       assert(original.CreateWildCard(&wildcard)==NS_OK);
       assert(wildcard->GetBeConservative());
       assert(wildcard->GetTlsFlags()==original.GetTlsFlags());
       assert(wildcard->mCloakfoxGeneration==original.mCloakfoxGeneration);
       delete wildcard;
     }
    }
    '''
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'snapshot.cpp';exe=Path(tmp)/'snapshot'
            src.write_text(harness+'\n'+method+'\n'+checks)
            subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror',str(src),'-o',str(exe)],check=True,capture_output=True)
            subprocess.run([str(exe)],check=True,capture_output=True)
