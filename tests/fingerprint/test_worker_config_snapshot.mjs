import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdtempSync,rmSync,existsSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {tmpdir} from 'node:os';

test('production worker config epoch refresh handles oversized updates, removals and shutdown without IPC under lock',()=>{
 const native=new URL('../../firefox-src/dom/base/RoverfoxStorageManager.cpp',import.meta.url);
 let source;
 if(existsSync(native))source=readFileSync(native,'utf8');
 else {
  const patch=readFileSync(new URL('../../patches/cloakfox-privacy-completion.patch',import.meta.url),'utf8');
  source=patch.split('--- a/dom/base/RoverfoxStorageManager.cpp\n')[1].split('--- a/')[0].split('\n')
    .filter(line=>line.startsWith(' ')||(line.startsWith('+')&&!line.startsWith('+++'))).map(line=>line.slice(1)).join('\n');
 }
 const method=source.match(/RoverfoxStorageManager::OnStoragePrefChanged\(const char\* prefName, void\*\) \{[\s\S]*?\n\}/)?.[0];
 const lookup=source.match(/RoverfoxStorageManager::TryGetCppFirstPref\(const nsAString& key,[\s\S]*?\n\}/)?.[0];
 assert.ok(method);assert.ok(lookup);
 const dir=mkdtempSync(`${tmpdir()}/cloakfox-worker-cache-`);
 try {
  writeFileSync(`${dir}/test.cpp`, `#include <cassert>
#include <map>
#include <string>
#include <vector>
#define MOZ_ASSERT assert
struct nsCString : std::string {
 using std::string::string;
 nsCString(const std::string& s):std::string(s){}
 bool IsEmpty() const {return empty();}
 int Find(const char* s)const{auto n=find(s);return n==npos?-1:int(n);}
 const char* get() const {return c_str();}
 bool EqualsLiteral(const char* s) const {return *this==s;}
};
using nsAutoCString=nsCString; using nsDependentCString=nsCString;using nsAString=nsCString;using nsACString=nsCString;
struct Keys : std::vector<nsCString> {
 Keys Clone()const{return *this;}
 bool Contains(const nsCString& k)const{for(const auto& v:*this)if(v==k)return true;return false;}
 void AppendElement(const nsCString& k){push_back(k);}
};
struct Cache : std::map<nsCString,nsCString> {
 struct Entry {nsCString* value;explicit operator bool()const{return value;}nsCString& Data(){return *value;}};
 Entry Lookup(const nsCString& k){auto i=find(k);return {i==end()?nullptr:&i->second};}
 void Remove(const nsCString& k){erase(k);}
 void InsertOrUpdate(const nsCString& k,const nsCString& v){(*this)[k]=v;}
};
int lockDepth=0,mutex=0,calls=0;bool parent=false,shutdown=false,channel=true,mainThread=true;
bool NS_IsMainThread(){return mainThread;}bool XRE_IsParentProcess(){return parent;}
struct MutexAutoLock {MutexAutoLock(int&){++lockDepth;}~MutexAutoLock(){--lockDepth;}};
Cache authority,local,preferences;Keys watched;
struct Preferences {static void GetCString(const char* k,nsCString& v){v=(parent?authority:preferences)[k];}};
struct ContentChild {
 static ContentChild* GetSingleton(){static ContentChild child;return &child;}
 bool IsShuttingDown(){return shutdown;}bool CanSend(){return channel;}
 bool SendRoverfoxStorageGet(const nsCString& k,nsCString* v){assert(lockDepth==0);++calls;*v=authority[k];return true;}
};
struct RoverfoxStorageManager {
 static Cache& GetLocalCache(){return local;}static int& GetLocalCacheMutex(){return mutex;}
 static Keys& ObservedConfigKeys(){return watched;}
 static void EnsureCacheObserver(){}
 static nsCString MakeCppFirstPrefName(const nsAString& k){return nsCString("cloakfox.s."+k);}
 static bool TryGetCppFirstPref(const nsAString&,nsACString&);
 static void OnStoragePrefChanged(const char*,void*);
};
void ${method}
bool ${lookup}
int main(){
 const char* a="cloakfox.s.cloak_cfg_7";const char* b="cloakfox.s.cloak_cfg_8";
 watched.push_back(a);watched.push_back(b); local[a]="old";local[b]="old";
 authority[a]=std::string(12000,'x');authority[b]="updated";authority["unwarmed"]="private";
 RoverfoxStorageManager::OnStoragePrefChanged("cloakfox.font_identity_epoch",nullptr);
 assert(local[a].size()==12000);assert(local[b]=="updated");assert(calls==2);assert(local.count("unwarmed")==0);
 RoverfoxStorageManager::OnStoragePrefChanged(a,nullptr);assert(local[a].size()==12000);--calls;
 authority.erase(a);RoverfoxStorageManager::OnStoragePrefChanged("cloakfox.font_identity_epoch",nullptr);
 assert(local.count(a)==0);assert(calls==4);
 authority[a]=std::string(15000,'y');RoverfoxStorageManager::OnStoragePrefChanged("cloakfox.font_identity_epoch",nullptr);
 assert(local[a].size()==15000);assert(calls==6);
 shutdown=true;RoverfoxStorageManager::OnStoragePrefChanged("cloakfox.font_identity_epoch",nullptr);assert(calls==6);
 shutdown=false;channel=false;RoverfoxStorageManager::OnStoragePrefChanged("cloakfox.font_identity_epoch",nullptr);assert(calls==6);
 parent=true;authority[b]="parent-update";RoverfoxStorageManager::OnStoragePrefChanged("cloakfox.font_identity_epoch",nullptr);
 assert(local[b]=="parent-update");assert(calls==6);assert(lockDepth==0);
 parent=false;channel=true;preferences[a]=std::string(10000,'s');authority[a]="new authoritative policy";
 nsCString output;
 assert(RoverfoxStorageManager::TryGetCppFirstPref("cloak_cfg_7",output));
 assert(output=="new authoritative policy");assert(local[a]==output);assert(calls==7);
 mainThread=false;authority[a]="not visible until main-thread refresh";
 assert(RoverfoxStorageManager::TryGetCppFirstPref("cloak_cfg_7",output));
 assert(output=="new authoritative policy");assert(calls==7);
 mainThread=true;authority.erase(a);
 assert(!RoverfoxStorageManager::TryGetCppFirstPref("cloak_cfg_7",output));assert(local.count(a)==0);assert(calls==8);
 shutdown=true;assert(!RoverfoxStorageManager::TryGetCppFirstPref("cloak_cfg_7",output));assert(calls==8);
}`);
  execFileSync('c++',['-std=c++17',`${dir}/test.cpp`,'-o',`${dir}/test`]);execFileSync(`${dir}/test`);
 }finally{rmSync(dir,{recursive:true,force:true});}
});
