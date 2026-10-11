/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
#ifndef mozilla_net_CloakfoxNetworkProfile_h
#define mozilla_net_CloakfoxNetworkProfile_h

#include "mozilla/Preferences.h"
#include "mozilla/StaticPrefs_cloakfox.h"
#include "nsString.h"

namespace mozilla::net {
// Gecko adapter metadata, carried by the existing socket/IPC TLS flags field.
// NSS security provider bits occupy bits 0–6; leave them unchanged. This bit
// also partitions NSS peer IDs and connection hash keys. A future Chromium
// adapter must consume the engine-independent intent through its own metadata.
inline constexpr uint32_t kCloakfoxChromeTlsFlag = 0x40000000u;

inline constexpr uint32_t kCloakfoxGenerationMask = 0x3fffff00u;
inline uint32_t CloakfoxNetworkStateForContainer(uint32_t aUserContextId) {
  nsAutoCString key;
  key.AppendPrintf("cloakfox.container.%u.network_state", aUserContextId);
  // Exact owner 0 means owner 0, never an ambient container fallback.
  const int32_t state = Preferences::GetInt(key.get(), 0);
  // Negative is exhaustion, never recycle a prior generation.
  if (state < 0 || state > 0x7ffffd) return 0x7ffffe;
  const uint32_t captured = static_cast<uint32_t>(state);
  return StaticPrefs::cloakfox_enabled() ? captured : (captured & ~1u);
}
}  // namespace mozilla::net
#endif
