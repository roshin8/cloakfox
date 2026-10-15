/* MPL-2.0: bounded virtual GPU resource profiles, independent of host hardware. */
#pragma once
#include "CloakfoxSiteSeedCore.hpp"
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <algorithm>
#include <cctype>
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
struct Limits { uint32_t texture,vertexUniforms,fragmentUniforms; };
inline std::optional<Limits> Decode(uint32_t code) {
 const auto family=code>>8,variant=code&255;
 if(family<1||family>4)return std::nullopt;
 constexpr uint32_t texture[]={0,6144,4096,7168,8192};
 return Limits{texture[family],256+variant,224+variant};
}
}
