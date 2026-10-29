/* MPL-2.0: immutable per-document canonical layout admission. */
#pragma once
#include "json.hpp"
#include "CloakfoxSiteSeedCore.hpp"
#include <cstdint>
namespace CloakfoxCanonicalGeometry {
// UA styles use -moz-platform for intrinsic control and ruby metrics as well
// as decoration. Select one platform for the captured layout generation;
// callers outside that generation retain their actual host platform.
template <typename Platform>
constexpr Platform LayoutPlatform(bool canonical, Platform host,
                                  Platform canonicalPlatform) {
  return canonical ? canonicalPlatform : host;
}

// Omitted descriptor selects the single shipped profile. If provided, every
// field is validated, including exact ownership of the default container.
inline bool Requested(const nlohmann::json& cfg, uint32_t ucid) {
  const auto request = cfg.find("geometry:canonical");
  const auto secret = cfg.find("fingerprint:secret");
  const auto seed = cfg.find("canvas:seed");
  if (request == cfg.end() || !request->is_boolean() || !request->get<bool>() ||
      secret == cfg.end() || !secret->is_string() ||
      !CloakfoxSiteSeed::ValidSecret(secret->get<std::string>()) ||
      seed == cfg.end() || !seed->is_number_unsigned() ||
      seed->get<uint64_t>() == 0 || seed->get<uint64_t>() > UINT32_MAX) return false;
  const auto profile = cfg.find("rendering:geometry_profile");
  if (profile == cfg.end()) return true;
  if (!profile->is_object() || profile->size() != 3) return false;
  auto version=profile->find("version"), id=profile->find("id"), owner=profile->find("owner");
  return version != profile->end() && version->is_number_integer() && *version == 1 &&
         id != profile->end() && id->is_string() && *id == "canonical-v1" &&
         owner != profile->end() && owner->is_number_integer() &&
         owner->get<int64_t>() >= 0 && owner->get<uint64_t>() == ucid;
}
// A presentation owns exactly one normalization generation. Revocation cannot
// re-admit frames, path caches or text runs built before a live policy change.
// New admission requires a fresh nsPresContext (normally document reload).
class Lifecycle {
 public:
  void Capture(bool enabled) { if (!mCaptured) { mCaptured=true; mNormalized=enabled; } }
  void BeginLayout() { mReady=false; }
  void Complete(bool prerequisites) { if (mNormalized && !mRevoked && prerequisites) mReady=true; }
  void Revoke() { mRevoked=true; mReady=false; }
  bool Normalized() const { return mNormalized; }
  bool Valid() const { return mNormalized && !mRevoked; }
  bool Ready() const { return mReady && Valid(); }
 private:
  bool mCaptured=false, mNormalized=false, mReady=false, mRevoked=false;
};
} // namespace CloakfoxCanonicalGeometry
