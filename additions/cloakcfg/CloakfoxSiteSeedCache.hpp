/* MPL-2.0: bounded, thread-owned memoization of exact-owner site seeds. */
#pragma once
#include "json.hpp"
#include <cstdint>
#include <memory>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace CloakfoxSiteSeed {
// Policy decisions are deliberately not cached. Callers must evaluate the
// current clock/policy before looking up a cryptographic derivation.
class ConfigSnapshot {
 public:
  explicit ConfigSnapshot(std::string bytes)
      : mBytes(std::move(bytes)), mConfig(Parse(mBytes)) {}
  bool Matches(const std::string& bytes) const { return mBytes == bytes; }
  const nlohmann::json& Config() const { return mConfig; }

  template <typename Compute>
  uint32_t Seed(const std::string& message, Compute compute) {
    auto found = mSeeds.find(message);
    if (found != mSeeds.end()) return found->second;
    const auto seed = compute();
    // Failed derivations are retried, never frozen into the cache.
    if (seed) {
      if (mSeeds.size() >= 64) mSeeds.clear();
      mSeeds.emplace(message, seed);
    }
    return seed;
  }

 private:
  static nlohmann::json Parse(const std::string& bytes) {
    auto config = nlohmann::json::parse(bytes, nullptr, false);
    return config.is_object() ? config : nlohmann::json::object();
  }
  const std::string mBytes;
  const nlohmann::json mConfig;
  // The message contains vector, base seed and canonical top-level site.
  // The secret belongs to this immutable config, not a global cache key.
  std::unordered_map<std::string, uint32_t> mSeeds;
};

class SiteSeedCache {
 public:
  std::shared_ptr<ConfigSnapshot> Get(uint32_t owner, std::string bytes) {
    for (auto& entry : mOwners) {
      if (entry.owner != owner) continue;
      if (!entry.snapshot->Matches(bytes)) {
        entry.snapshot = std::make_shared<ConfigSnapshot>(std::move(bytes));
      }
      return entry.snapshot;
    }
    // Bound retained owners and sites. Eviction only recomputes the same seed.
    if (mOwners.size() >= 8) mOwners.erase(mOwners.begin());
    auto snapshot = std::make_shared<ConfigSnapshot>(std::move(bytes));
    mOwners.push_back({owner, snapshot});
    return snapshot;
  }
 private:
  struct Entry {
    uint32_t owner;
    std::shared_ptr<ConfigSnapshot> snapshot;
  };
  std::vector<Entry> mOwners;
};
}  // namespace CloakfoxSiteSeed
