/* MPL-2.0: top-level site-bound noise; callable on document or worker threads. */
#pragma once
#include "CloakfoxSiteSeedCore.hpp"
#include "MaskConfig.hpp"
#include "ScopedNSSTypes.h"
#include "mozilla/dom/Document.h"
#include "mozilla/dom/WorkerPrivate.h"
#include "nsICookieJarSettings.h"
#include "nsString.h"
#include "nsIGlobalObject.h"
#include "nsPIDOMWindow.h"
namespace CloakfoxCanonicalGeometry {
bool Ready(mozilla::dom::Document*);
}
#include "prtime.h"

namespace CloakfoxSiteSeed {
inline nsICookieJarSettings* SettingsForGlobal(nsIGlobalObject* global) {
  if (global) {
    if (auto* win = global->GetAsInnerWindow()) {
      if (auto* doc = win->GetExtantDoc()) return doc->CookieJarSettings();
    }
  }
  if (!NS_IsMainThread()) {
    if (auto* worker = mozilla::dom::GetCurrentThreadWorkerPrivate()) return worker->CookieJarSettings();
  }
  return nullptr;
}

// MaskConfig's legacy ucid=0 API means "ambient container". Noise keys must
// instead address the owning container exactly, including the default one,
// even when layout runs while a different container has the current JS realm.
inline nlohmann::json ExactConfig(uint32_t ucid) {
  auto cfg = nlohmann::json::parse(::CloakConfigOverlay_Get(ucid), nullptr, false);
  return cfg.is_object() ? cfg : nlohmann::json::object();
}
inline std::optional<uint32_t> BaseSeed(uint32_t ucid, const char* vector) {
  const auto cfg = ExactConfig(ucid);
  auto value = cfg.find(vector);
  if (value == cfg.end() || !value->is_number_unsigned()) return std::nullopt;
  const auto number = value->get<uint64_t>();
  if (number > UINT32_MAX) return std::nullopt;
  return static_cast<uint32_t>(number);
}
// Invalid policy data never creates an exception. Expiry is checked on each
// extraction, so a stale content snapshot cannot extend an exception forever.
inline bool PolicyAllowsForSite(const nlohmann::json& cfg, const char* vector,
                                 const std::string& partitionKey, int64_t now) {
  auto policy = cfg.find("privacy:policy");
  if (policy == cfg.end() || !policy->is_object()) return true;
  auto version = policy->find("version"), preset = policy->find("preset");
  if (version == policy->end() || !version->is_number_integer() || *version != 1 ||
      preset == policy->end() || !preset->is_string()) return true;
  const auto mode = preset->get<std::string>();
  if (mode != "standard" && mode != "strict" && mode != "compatibility") return true;
  if (std::string(vector) == "geometry" && mode == "compatibility") return false;
  const auto canonical = CanonicalSiteKey(partitionKey);
  const auto comma = canonical.find(',');
  if (canonical.empty() || canonical.front() != '(' || comma == std::string::npos) return true;
  const auto site = canonical.substr(1, comma - 1) + "://" + canonical.substr(comma + 1, canonical.size() - comma - 2);
  auto exceptions = policy->find("exceptions");
  if (exceptions == policy->end() || !exceptions->is_array()) return true;
  for (const auto& exception : *exceptions) {
    if (!exception.is_object()) continue;
    auto host = exception.find("site"), expiry = exception.find("expiresAt"), vectors = exception.find("vectors");
    if (host == exception.end() || !host->is_string() || host->get<std::string>() != site ||
        expiry == exception.end() || !expiry->is_number_integer() || expiry->get<int64_t>() <= now ||
        vectors == exception.end() || !vectors->is_array()) continue;
    for (const auto& item : *vectors) if (item.is_string() && item.get<std::string>() == vector) return false;
  }
  return true;
}
inline bool PolicyAllows(const nlohmann::json& cfg, const char* vector,
                          nsICookieJarSettings* settings) {
  nsAutoString partition;
  if (settings) settings->GetPartitionKey(partition);
  return PolicyAllowsForSite(cfg, vector,
      std::string(NS_ConvertUTF16toUTF8(partition).get()),
      PR_Now() / PR_USEC_PER_MSEC);
}
inline uint32_t Derive(uint32_t ucid, const char* vector,
                       nsICookieJarSettings* settings, const char* policyVector = nullptr) {
  if (!settings) return 0;
  const auto cfg = ExactConfig(ucid);
  const char* gate = policyVector ? policyVector :
    (std::string(vector) == "canvas:seed" ? "canvas" :
     std::string(vector) == "audio:seed" ? "audio" : vector);
  if (!PolicyAllows(cfg, gate, settings)) return 0;
  auto configuredSeed = cfg.find(vector);
  if (configuredSeed == cfg.end() || !configuredSeed->is_number_unsigned() ||
      configuredSeed->get<uint64_t>() > UINT32_MAX) return 0;
  const uint32_t baseSeed = configuredSeed->get<uint32_t>();
  if (!baseSeed) return 0;
  nsAutoString partitionKey;
  if (NS_FAILED(settings->GetPartitionKey(partitionKey))) return 0;
  const auto input = Message(vector, baseSeed,
    std::string(NS_ConvertUTF16toUTF8(partitionKey).get()));
  auto secretValue = cfg.find("fingerprint:secret");
  if (secretValue == cfg.end() || !secretValue->is_string()) return 0;
  const auto secret = secretValue->get<std::string>();
  if (input.empty() || !ValidSecret(secret)) return 0;
  mozilla::HMAC hmac;
  if (NS_FAILED(hmac.Begin(SEC_OID_SHA256,
      mozilla::Span(reinterpret_cast<const uint8_t*>(secret.data()), secret.size()))) ||
      NS_FAILED(hmac.Update(reinterpret_cast<const uint8_t*>(input.data()), input.size()))) return 0;
  nsTArray<uint8_t> digest;
  if (NS_FAILED(hmac.End(digest)) || digest.Length() != 32) return 0;
  return SeedFromDigest(digest.Elements());
}
inline std::optional<std::array<uint64_t, 2>> OwnerKey(
    uint32_t ucid, nsICookieJarSettings* settings) {
  if (!settings) return std::nullopt;
  const auto cfg = ExactConfig(ucid);
  auto secretValue = cfg.find("fingerprint:secret");
  auto seedValue = cfg.find("canvas:seed");
  if (secretValue == cfg.end() || !secretValue->is_string() ||
      seedValue == cfg.end() || !seedValue->is_number_unsigned() ||
      seedValue->get<uint64_t>() > UINT32_MAX) return std::nullopt;
  const auto secret = secretValue->get<std::string>();
  if (!ValidSecret(secret)) return std::nullopt;
  nsAutoString partition;
  if (NS_FAILED(settings->GetPartitionKey(partition))) return std::nullopt;
  const auto message = CanvasOwnerMessage(seedValue->get<uint32_t>(),
      std::string(NS_ConvertUTF16toUTF8(partition).get()));
  if (message.empty()) return std::nullopt;
  mozilla::HMAC hmac;
  if (NS_FAILED(hmac.Begin(SEC_OID_SHA256,
      mozilla::Span(reinterpret_cast<const uint8_t*>(secret.data()), secret.size()))) ||
      NS_FAILED(hmac.Update(reinterpret_cast<const uint8_t*>(message.data()), message.size())))
    return std::nullopt;
  nsTArray<uint8_t> digest;
  if (NS_FAILED(hmac.End(digest))) return std::nullopt;
  return CanvasOwnerFromDigest(digest.Elements(), digest.Length());
}
inline uint32_t Configured(uint32_t ucid, const char* vector,
                           nsICookieJarSettings* settings) {
  return Derive(ucid, vector, settings);
}
inline std::optional<uint32_t> ForDocument(mozilla::dom::Document* doc,
                                           const char* vector) {
  if (!doc) return 0;
  return Configured(doc->NodePrincipal()->OriginAttributesRef().mUserContextId,
                    vector, doc->CookieJarSettings());
}
inline uint32_t Geometry(uint32_t ucid, const char* vector,
                         nsICookieJarSettings* settings) {
  return Derive(ucid, vector, settings, "geometry");
}
inline std::optional<uint32_t> GeometryForDocument(mozilla::dom::Document* doc,
                                                  const char* vector) {
  if (!doc) return 0;
  if (CloakfoxCanonicalGeometry::Ready(doc)) return 0;
  return Geometry(doc->NodePrincipal()->OriginAttributesRef().mUserContextId,
                  vector, doc->CookieJarSettings());
}
inline uint32_t ForContext(uint32_t ucid, const char* vector,
                           mozilla::dom::Document* doc = nullptr) {
  if (doc) return Derive(ucid, vector, doc->CookieJarSettings());
  if (!NS_IsMainThread()) {
    if (auto* worker = mozilla::dom::GetCurrentThreadWorkerPrivate()) {
      return Derive(worker->GetOriginAttributes().mUserContextId, vector,
                    worker->CookieJarSettings());
    }
  }
  return 0;
}
} // namespace CloakfoxSiteSeed
