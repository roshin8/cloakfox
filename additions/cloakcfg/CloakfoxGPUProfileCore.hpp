/* MPL-2.0: bounded virtual GPU resource profiles, independent of host hardware. */
#pragma once
#include "CloakfoxSiteSeedCore.hpp"
#include "CloakfoxGPUCatalog.hpp"
#include "CloakfoxGPUReferenceCatalog.hpp"
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <algorithm>
#include <cctype>
#include <cmath>
#include <vector>
namespace CloakfoxGPUProfile {
inline std::string IdentityMessage(uint32_t seed, const std::string& partition) {
 const auto site=CloakfoxSiteSeed::CanonicalSiteKey(partition);
 return site.empty()?std::string():"cloakfox-gpu-profile-v1\n"+std::to_string(seed)+"\n"+site;
}
inline uint32_t Family(std::string_view renderer) {
 std::string s(renderer);std::transform(s.begin(),s.end(),s.begin(),[](unsigned char c){return std::tolower(c);});
 if(s.find("swiftshader")!=s.npos||s.find("llvmpipe")!=s.npos||s.find("softpipe")!=s.npos||s.find("software")!=s.npos)return 0;
 if(s.find("apple")!=s.npos)return 1;
 if(s.find("intel")!=s.npos)return 2;
 if(s.find("amd")!=s.npos||s.find("radeon")!=s.npos||s.find("firepro")!=s.npos)return 3;
 if(s.find("nvidia")!=s.npos||s.find("geforce")!=s.npos||s.find("quadro")!=s.npos)return 4;
 return 0;
}
using Limits = CloakfoxGPUCatalog::Limits;
inline std::optional<Limits> Decode(uint32_t code, bool gl2 = true) {
 if (const auto* r=CloakfoxGPUReference::Lookup(code)) {
  using namespace CloakfoxGPUReference;
  return Limits{code,1u<<(r->family-1),Cap(code,gl2,3379),Cap(code,gl2,36347),Cap(code,gl2,36349),Cap(code,gl2,34921),Cap(code,gl2,35661),Cap(code,gl2,35660),Cap(code,gl2,34930),gl2?Cap(code,true,37154)/4:Cap(code,false,36348),gl2?Cap(code,true,37157)/4:Cap(code,false,36348),Cap(code,true,32883),Cap(code,true,35071),Cap(code,true,35375),Cap(code,true,34852),268435456,134217728};
 }

 const auto family=code>>8,id=code&255;
 if(family<1||family>4)return std::nullopt;
 for(const auto& p:CloakfoxGPUCatalog::kProfiles){
  if(p.id==id&&(p.familyMask&(1u<<(family-1))))return p;
 }
 return std::nullopt;
}
// Independent native validation: descriptor metadata cannot loosen the selected
// container's manual ceilings or introduce uncatalogued resource combinations.
template <typename Config>
inline std::vector<uint32_t> EligibleCatalog(const Config& cfg, uint32_t family) {
 std::vector<uint32_t> eligible;
 if(family<1||family>4)return eligible;
 for(const char* key:{"webGl:parameters","webGl2:parameters"}){
  if(cfg.contains(key)&&!cfg[key].is_object())return eligible;
 }
 for(const auto& p:CloakfoxGPUCatalog::kProfiles){
  if(!(p.familyMask&(1u<<(family-1))))continue;
  bool supported=true;
  for(unsigned index=0;index<2;index++){
   const char* key=index?"webGl2:parameters":"webGl:parameters";
   if(!cfg.contains(key))continue;
   const auto& table=cfg[key];
   for(const auto& requirement:CloakfoxGPUCatalog::Requirements(p)){
    if(requirement.webgl2Only&&!index)continue;
    const auto name=std::to_string(requirement.pname);
    if(!table.contains(name))continue;
    const auto& value=table[name];
    const auto meets=[&](const auto& v){
     if(!v.is_number())return false;
     const double n=v.template get<double>();
     return std::isfinite(n)&&n>=requirement.capacity;
    };
    if(requirement.components==1){supported&=meets(value);}
    else{
     if(!value.is_array()||value.size()!=requirement.components){supported=false;continue;}
     for(const auto& component:value)supported&=meets(component);
    }
   }
  }
  if(supported)eligible.push_back(p.id);
 }
 return eligible;
}
// Shared with native context creation and compiled admission tests.
inline bool ReferenceScalarSupported(const CloakfoxGPUReference::Parameter& p,double actual) {
 return std::isfinite(actual)&&(p.pname==35076?actual<=p.lo:actual>=p.lo);
}
inline bool ReferencePrecisionSupported(const CloakfoxGPUReference::Precision& p,uint32_t rangeMin,uint32_t rangeMax,uint32_t precision) {
 return rangeMin>=p.rangeMin&&rangeMax>=p.rangeMax&&precision>=p.precision;
}
// A reference code belongs to a complete immutable pair, never a bag of limits.
template <typename Config>
inline std::vector<uint32_t> EligibleReferences(const Config& cfg,uint32_t family) {
 std::vector<uint32_t> result;
 for(const auto& p:CloakfoxGPUReference::kProfiles) {
  if(p.family!=family||!cfg.contains("webGl:renderer")||cfg["webGl:renderer"]!=p.renderer||!cfg.contains("webGl:vendor")||cfg["webGl:vendor"]!=p.vendor)continue;
  const char* platform=p.family==1?"MacIntel":"Win32";
  const char* oscpu=p.family==1?"Intel Mac OS X 10.15":"Windows NT 10.0; Win64; x64";
  if(!cfg.contains("navigator.platform")||cfg["navigator.platform"]!=platform||!cfg.contains("navigator.oscpu")||cfg["navigator.oscpu"]!=oscpu)continue;
  bool ok=true;
  for(size_t gi=0;gi<2;gi++) {
   const char* key=gi?"webgl2":"webgl";
   if(!cfg.contains("rendering:gpu_reference:ceilings"))continue;
   const auto& ceilings=cfg["rendering:gpu_reference:ceilings"];
   if(!ceilings.is_object()){ok=false;break;}
   if(!ceilings.contains(key))continue;
   const auto& table=ceilings[key];if(!table.is_object()){ok=false;break;}
   const auto& context=*p.contexts[gi];
   for(size_t i=0;i<context.parameterCount;i++) {
    const auto& req=context.parameters[i];const auto name=std::to_string(req.pname);
    if(!table.contains(name))continue;const auto& value=table[name];
    const auto valid=[&](const auto& v,double capacity,bool lower){if(!v.is_number())return false;const auto n=v.template get<double>();return std::isfinite(n)&&(lower?n<=capacity:n>=capacity);};
    if(req.components==1)ok &= valid(value,req.lo,req.pname==35076);
    else if(!value.is_array()||value.size()!=2)ok=false;
    else {const bool range=req.pname==33901||req.pname==33902;ok &= valid(value[0],req.lo,range)&&valid(value[1],req.hi,false);}
   }
  }
  if(ok)result.push_back(p.code);
 }
 return result;
}
template <typename Config>
inline bool ReferenceDescriptorMatches(const Config& p,const std::vector<uint32_t>& eligible) {
 if(eligible.empty()||!p.contains("version")||!p["version"].is_number_unsigned()||p["version"]!=3||!p.contains("mode")||p["mode"]!="reference"||!p.contains("source")||p["source"]!=CloakfoxGPUReference::kSource||!p.contains("privacyPolicy")||p["privacyPolicy"]!="reference-protected-v1"||!p.contains("adaptation")||p["adaptation"]!="Firefox146-to159:canonical-renderer;deny-debug-shaders-and-timers;omit-version-specific-provoking-vertex;WebGPU-canonical-device"||!p.contains("catalog")||!p["catalog"].is_array()||p["catalog"].size()!=eligible.size())return false;
 for(size_t i=0;i<eligible.size();i++)if(!p["catalog"][i].is_number_unsigned()||p["catalog"][i]!=eligible[i])return false;
 return true;
}
template <typename Config>
inline bool DescriptorCatalogMatches(const Config& descriptor,const std::vector<uint32_t>& eligible){
 if(eligible.empty()||!descriptor.contains("version")||!descriptor["version"].is_number_unsigned())return false;
 if(descriptor["version"]==1)return !descriptor.contains("catalog");
 if(descriptor["version"]!=2||!descriptor.contains("catalog")||!descriptor["catalog"].is_array()||descriptor["catalog"].size()!=eligible.size())return false;
 for(size_t i=0;i<eligible.size();i++){
  const auto& id=descriptor["catalog"][i];
  if(!id.is_number_unsigned()||id!=eligible[i])return false;
 }
 return true;
}

}
