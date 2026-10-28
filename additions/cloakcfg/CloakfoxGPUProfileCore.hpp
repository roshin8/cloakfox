/* MPL-2.0: bounded virtual GPU resource profiles, independent of host hardware. */
#pragma once
#include "CloakfoxSiteSeedCore.hpp"
#include "CloakfoxGPUCatalog.hpp"
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
inline std::optional<Limits> Decode(uint32_t code) {
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
