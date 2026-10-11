"""Exercise native owner/error branches and platform inputs from applied source."""
from pathlib import Path
from types import SimpleNamespace as N
import ast
import io
import os
import sys
import unittest
import xml.etree.ElementTree as ET
from test_upstream_hardening import SRC, block, cpp


class CamoufoxFollowup(unittest.TestCase):
    def test_webgl_uses_owner_principal_for_detached_and_offscreen_canvases(self):
        method = block((SRC/'dom/canvas/ClientWebGLContext.cpp').read_text(),
                       'uint32_t ClientWebGLContext::GetUserContextId() const')
        cpp(r'''
#include <cassert>
#include <cstdint>
struct Attr { uint32_t mUserContextId; };
struct Principal { Attr attrs; const Attr& OriginAttributesRef() { return attrs; } };
struct BrowsingContext { Attr attrs; const Attr& OriginAttributesRef() { return attrs; } };
struct Document { BrowsingContext* bc; BrowsingContext* GetBrowsingContext(){return bc;} };
struct Canvas { Document* doc; Principal* p; Document* OwnerDoc(){return doc;} Principal* NodePrincipal(){return p;} };
struct nsPIDOMWindowInner { BrowsingContext* bc; BrowsingContext* GetBrowsingContext(){return bc;} };
struct nsIGlobalObject { nsPIDOMWindowInner* win; Principal* p; Principal* PrincipalOrNull(){return p;} };
template<class T> using nsCOMPtr=T*;
nsPIDOMWindowInner* do_QueryInterface(nsIGlobalObject* g){return g->win;}
struct Offscreen { nsIGlobalObject* g; nsIGlobalObject* GetRelevantGlobal(){return g;} };
struct WorkerPrivate { Attr attrs; const Attr& GetOriginAttributes(){return attrs;} };
WorkerPrivate* worker=nullptr;
WorkerPrivate* GetCurrentThreadWorkerPrivate(){return worker;}
struct ClientWebGLContext { Canvas* mCanvasElement=nullptr; Offscreen* mOffscreenCanvas=nullptr; uint32_t GetUserContextId() const; };
''' + method + r'''
int main(){
 Principal owner{{7}}, other{{11}}; BrowsingContext stale{{99}};
 Document attached{&stale}, detached{nullptr}; Canvas c{&detached,&owner};
 ClientWebGLContext ctx; ctx.mCanvasElement=&c;
 assert(ctx.GetUserContextId()==7);
 c.doc=&attached; assert(ctx.GetUserContextId()==7);
 c.p=&other; assert(ctx.GetUserContextId()==11);
 ctx.mCanvasElement=nullptr;
 nsPIDOMWindowInner win{nullptr}; nsIGlobalObject global{&win,&owner}; Offscreen off{&global};
 ctx.mOffscreenCanvas=&off; assert(ctx.GetUserContextId()==7);
 WorkerPrivate wp{{11}}; worker=&wp; global.win=nullptr; global.p=&other;
 assert(ctx.GetUserContextId()==11);
 global.p=nullptr; assert(ctx.GetUserContextId()==11);
 worker=nullptr; assert(ctx.GetUserContextId()==0);
 ctx.mOffscreenCanvas=nullptr; assert(ctx.GetUserContextId()==0);
}
''')

    def test_voice_errors_are_suppressed_only_for_active_configured_voices(self):
        method=block((SRC/'dom/media/webspeech/synth/nsSynthVoiceRegistry.cpp').read_text(),
                     'nsSynthVoiceRegistry::NotifyVoicesError(')
        prefix=method[method.index('{')+1:method.index('  if (XRE_IsParentProcess())')]
        cpp(r'''
#include <cassert>
#include <optional>
#define LOG(...) ((void)0)
#define NS_OK 0
namespace StaticPrefs { bool enabled=true; bool cloakfox_enabled(){return enabled;} }
namespace MaskConfig { bool configured=false; std::optional<int> MVoices(){return configured?std::optional<int>(0):std::nullopt;} }
namespace mozilla { namespace StaticPrefs=::StaticPrefs; }
int notify(){
''' + prefix + r'''
return 1;
}
int main(){
 for(bool enabled:{false,true}) for(bool configured:{false,true}) {
  StaticPrefs::enabled=enabled; MaskConfig::configured=configured;
  assert(notify()==(enabled&&configured?0:1));
 }
}
''')

    def test_analyser_copy_preserves_state_with_no_seed_and_allocation_failure(self):
        body=block((SRC/'dom/media/webaudio/AnalyserNode.cpp').read_text(),
                   'const float* AnalyserNode::NoisedOutput(')
        cpp(r'''
#include <cassert>
#include <cstdint>
#include <vector>
#include <algorithm>
const int fallible=0;
template<class T> struct AlignedTArray : std::vector<T> {
 bool fail=false;
 bool SetLength(size_t n,int){if(fail)return false;this->resize(n);return true;}
 size_t Length()const{return this->size();}
 T* Elements(){return this->data();}
 const T* Elements()const{return this->data();}
};
void PodCopy(float* out,const float* in,size_t n){std::copy(in,in+n,out);}
struct Attr {uint32_t mUserContextId;};
struct BrowsingContext {Attr OriginAttributesRef(){return {7};}};
struct nsPIDOMWindowInner {BrowsingContext bc; BrowsingContext* GetBrowsingContext(){return &bc;} void* GetExtantDoc(){return this;}};
struct nsIGlobalObject {nsPIDOMWindowInner win; nsPIDOMWindowInner* GetAsInnerWindow(){return &win;}};
struct AudioContext {nsIGlobalObject global; nsIGlobalObject* GetParentObject(){return &global;}};
struct WorkerPrivate {Attr GetOriginAttributes(){return {11};}};
WorkerPrivate* GetCurrentThreadWorkerPrivate(){return nullptr;}
namespace CloakfoxSiteSeed {
uint32_t seed=123;
uint32_t ForContext(uint32_t id,const char*,void* doc){assert(id==7&&doc);return seed;}
}
namespace AudioFingerprintManager {
void ApplyTransformation(float* out,size_t n,uint32_t seed){assert(seed==123); for(size_t i=0;i<n;i++)out[i]*=1.004f;}
}
struct AnalyserNode {
 AlignedTArray<float> mOutputBuffer; mutable AudioContext context;
 AudioContext* GetParentObject()const{return &context;}
 const float* NoisedOutput(AlignedTArray<float>&)const;
};
''' + body + r'''
int main(){
 AnalyserNode node; node.mOutputBuffer.assign({1.f,2.f,3.f});
 const auto original=node.mOutputBuffer;
 for(int i=0;i<200;i++) {
  AlignedTArray<float> scratch;
  const float* out=node.NoisedOutput(scratch);
  assert(out!=node.mOutputBuffer.Elements());
  assert(out[0]==1.004f && node.mOutputBuffer==original);
 }
 AlignedTArray<float> scratch; scratch.fail=true;
 assert(node.NoisedOutput(scratch)==node.mOutputBuffer.Elements());
 assert(node.mOutputBuffer==original);
 scratch.fail=false; CloakfoxSiteSeed::seed=0;
 assert(node.NoisedOutput(scratch)==node.mOutputBuffer.Elements());
 assert(scratch.empty() && node.mOutputBuffer==original);
}
''')

    def test_windows_application_manifest_preserves_stock_privileges(self):
        target=SRC/'browser/app/cloakfox.exe.manifest'
        self.assertTrue(target.exists(), 'renamed executable has no matching manifest')
        self.assertEqual(target.read_bytes(), (SRC/'browser/app/firefox.exe.manifest').read_bytes())
        xml=ET.parse(target)
        ns={'a':'urn:schemas-microsoft-com:asm.v3'}
        privileges=xml.find('.//a:requestedExecutionLevel',ns)
        self.assertEqual(privileges.attrib,{'level':'asInvoker','uiAccess':'false'})

    def test_crash_page_resources_exist_with_reporter_disabled(self):
        sys.path.insert(0,str(SRC/'python/mozbuild'))
        from mozbuild.preprocessor import Preprocessor
        output=io.StringIO()
        pp=Preprocessor(); pp.out=output
        pp.do_include(str(SRC/'toolkit/crashreporter/jar.mn'))
        for suffix in ['html','js','css']:
            self.assertIn('content/global/crashes.'+suffix,output.getvalue())

    def test_rust_pc_linux_selects_unknown_without_losing_vendor_or_abi_matches(self):
        source=(SRC/'build/moz.configure/rust.configure').read_text()
        tree=ast.parse(source)
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='detect_rustc_target')
        fn.decorator_list=[]
        ns={'die':lambda msg: (_ for _ in ()).throw(ValueError(msg))}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),str(SRC/'build/moz.configure/rust.configure'),'exec'),ns)
        def target(vendor, raw_os='linux-gnu', **kw):
            return N(cpu='x86_64',endianness='little',os='GNU',kernel='Linux',abi='gnu',
                     vendor=vendor,raw_cpu='x86_64',raw_os=raw_os,
                     sub_configure_alias=f'x86_64-{vendor}-{raw_os}',alias=f'x86_64-{vendor}-{raw_os}',**kw)
        def choose(host, specs):
            candidates=[N(target=info,rust_target=info.alias) for info in specs]
            return ns['detect_rustc_target'](host,None,{(host.cpu,host.endianness,host.os):candidates})
        unknown,oe=target('unknown'),target('oe')
        self.assertEqual(choose(target('pc'),[oe,unknown]),unknown.alias)
        self.assertEqual(choose(oe,[unknown,oe]),oe.alias)
        self.assertEqual(choose(target('pc'),[unknown]),unknown.alias)
        with self.assertRaises(ValueError): choose(target('pc'),[unknown,target('unknown')])
        win=target('pc','windows-msvc'); win.os='WINNT'; win.kernel='WINNT'; win.abi='msvc'
        gnu=target('pc','windows-gnu'); gnu.os='WINNT'; gnu.kernel='WINNT'; gnu.abi='mingw'
        self.assertEqual(choose(win,[gnu,win]),win.alias)

if __name__=='__main__': unittest.main()
