/* MPL-2.0: reference backend provenance; library hashes are checked separately. */
#pragma once
#include "json.hpp"
namespace CloakfoxCanonicalBackend {
struct Patch {const char* name;const char* sha256;};
inline constexpr Patch kPatches[] = {
  {"canonical-only.patch","cba763e13c4eb009b36f1988e2be50dfcc103e6f6d6a96086649f12323442c7d"},
  {"command-line-tools.patch","26482cfb46bdca6147592411326b9781187c1ba36f1e8568425d5ea16a5c991a"},
  {"reference-capacity-angle.patch","b2ded9cf1466f30d2e6a9e2d4fb693a78c35bae03bff0cf9503ea6638ed22a5a"},
  {"reference-capacity-swiftshader.patch","d3b0b552651d9a5109c1fe3edb3197986f677a32cd2f0a6ff3eba23e11e9bada"},
 };
inline bool ManifestVersionAllowed(const nlohmann::json& manifest) {
  const auto version=manifest.find("rendererVersion");
  if(version==manifest.end()||!version->is_number_integer())return false;
  if(*version==1)return true; // Existing protected backend, no reference capacity claim.
  if(*version!=2||!manifest.contains("capacityProfile")||manifest["capacityProfile"]!="reference-v1")return false;
  const auto patches=manifest.find("localPatches");
  if(patches==manifest.end()||!patches->is_object()||patches->size()!=4)return false;
  for(const auto& patch:kPatches){
    const auto value=patches->find(patch.name);
    if(value==patches->end()||!value->is_string()||*value!=patch.sha256)return false;
  }
  return true;
}
}
