/* MPL-2.0: resolve a validated profile from the exact owning content global. */
#pragma once
#include "CloakfoxGPUProfileCore.hpp"
#include "CloakfoxSiteSeed.hpp"
#include "mozilla/StaticPrefs_cloakfox.h"
namespace CloakfoxGPUProfile {
struct Descriptor { uint32_t code; std::string renderer,vendor,config; };
inline bool Requested(nsIGlobalObject* global) {
 const auto principal=global?global->PrincipalOrNull():nullptr;
 return principal&&!principal->IsSystemPrincipal()&&mozilla::StaticPrefs::cloakfox_enabled()&&mozilla::StaticPrefs::cloakfox_opt_container_rendering_profiles();
}
inline std::optional<Descriptor> ForGlobal(nsIGlobalObject* global) {
 if(!Requested(global)||!mozilla::StaticPrefs::cloakfox_experimental_canvas_pipeline())return std::nullopt;
 const auto principal=global->PrincipalOrNull();const auto owner=principal->OriginAttributesRef().mUserContextId;
 const auto cfg=CloakfoxSiteSeed::ExactConfig(owner);
 const auto it=cfg.find("rendering:gpu_profile");
 if(it==cfg.end()||!it->is_object())return std::nullopt;
 const auto& p=*it;
 if(!p.contains("owner")||!p["owner"].is_number_unsigned()||p["owner"].get<uint64_t>()!=owner)return std::nullopt;
 for(const char* key:{"renderer","vendor","family"})if(!p.contains(key)||!p[key].is_string())return std::nullopt;
 const auto renderer=p["renderer"].get<std::string>(),vendor=p["vendor"].get<std::string>();
 if(renderer.size()>512||vendor.empty()||vendor.size()>256||!cfg.contains("webGl:renderer")||cfg["webGl:renderer"]!=p["renderer"]||!cfg.contains("webGl:vendor")||cfg["webGl:vendor"]!=p["vendor"])return std::nullopt;
 const auto family=Family(renderer);
 constexpr const char* families[]={"","apple","intel","amd","nvidia"};
 if(!family||p["family"]!=families[family])return std::nullopt;
 const bool reference=cfg.contains("rendering:gpu_reference")&&cfg["rendering:gpu_reference"].is_boolean()&&cfg["rendering:gpu_reference"].get<bool>();
 const auto eligible=reference?EligibleReferences(cfg,family):EligibleCatalog(cfg,family);
 if(reference?!ReferenceDescriptorMatches(p,eligible):!DescriptorCatalogMatches(p,eligible))return std::nullopt;
 auto* settings=CloakfoxSiteSeed::SettingsForGlobal(global);if(!settings)return std::nullopt;
 // Profile identity is independent of readback exception policy. The HMAC
 // domain is separate from canvas noise; select a whole eligible cohort.
 nsAutoString partition;
 if(NS_FAILED(settings->GetPartitionKey(partition)))return std::nullopt;
 const auto seedValue=cfg.find("canvas:seed");
 if(seedValue==cfg.end()||!seedValue->is_number_unsigned()||seedValue->get<uint64_t>()>UINT32_MAX)return std::nullopt;
 const auto input=IdentityMessage(seedValue->get<uint32_t>(),std::string(NS_ConvertUTF16toUTF8(partition).get()));
 if(input.empty()||!cfg.contains("fingerprint:secret")||!cfg["fingerprint:secret"].is_string())return std::nullopt;
 const auto secret=cfg["fingerprint:secret"].get<std::string>();
 if(!CloakfoxSiteSeed::ValidSecret(secret))return std::nullopt;
 mozilla::HMAC hmac;
 if(NS_FAILED(hmac.Begin(SEC_OID_SHA256,mozilla::Span(reinterpret_cast<const uint8_t*>(secret.data()),secret.size())))||NS_FAILED(hmac.Update(reinterpret_cast<const uint8_t*>(input.data()),input.size())))return std::nullopt;
 nsTArray<uint8_t> digest;
 if(NS_FAILED(hmac.End(digest))||digest.Length()!=32)return std::nullopt;
 const uint32_t catalogId=eligible[digest[0]%eligible.size()];
 return Descriptor{reference?catalogId:(family<<8)|catalogId,renderer,vendor,cfg.dump()};
}
}
