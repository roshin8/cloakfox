/* MPL-2.0: protocol shared by the native and privileged actor site seeds. */
#pragma once
#include <cstdint>
#include <string>

namespace CloakfoxSiteSeed {
inline std::string CanonicalSiteKey(std::string key) {
  // CookieJarSettings has already performed PSL, IP and opaque-origin handling.
  // Never derive a fallback from a frame or worker's own tracker origin.
  if (key.size() == 44 && key.substr(36) == ".mozilla" &&
      key.substr(0, 36).find_first_not_of("0123456789abcdefABCDEF-") == std::string::npos) return key;
  if (key.size() < 5 || key.front() != '(' || key.back() != ')') return "";
  if (key.size() > 3 && key.substr(key.size() - 3) == ",f)") key.erase(key.size() - 3, 2);
  const auto comma = key.find(',');
  if (comma == std::string::npos || comma < 2 || comma + 2 >= key.size()) return "";
  const auto scheme = key.substr(1, comma - 1);
  if (scheme[0] < 'a' || scheme[0] > 'z' ||
      scheme.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789+.-") != std::string::npos) return "";
  const auto host = key.substr(comma + 1, key.size() - comma - 2);
  if (host.find_first_of("(), \t\r\n\v\f") != std::string::npos) return "";
  return key;
}
inline std::string Message(const std::string& vector, uint32_t baseSeed,
                           const std::string& partitionKey) {
  const auto site = CanonicalSiteKey(partitionKey);
  if (!baseSeed || site.empty() || vector.empty() ||
      vector.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:_-") != std::string::npos) return "";
  return "cloakfox-site-v1\n" + vector + "\n" + std::to_string(baseSeed) + "\n" + site;
}
inline bool ValidSecret(const std::string& secret) {
  return secret.size() == 44 && secret.back() == '=' &&
    secret.substr(0, 43).find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/") == std::string::npos;
}
inline uint32_t SeedFromDigest(const uint8_t* digest) {
  const auto seed = (uint32_t(digest[0]) << 24) | (uint32_t(digest[1]) << 16) |
                    (uint32_t(digest[2]) << 8) | uint32_t(digest[3]);
  return seed ? seed : 1;
}
} // namespace CloakfoxSiteSeed
