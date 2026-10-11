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
// NSS security provider bits occupy bits 0–5; leave them unchanged. This bit
// also partitions NSS peer IDs and connection hash keys. A future Chromium
// adapter must consume the engine-independent intent through its own metadata.
inline constexpr uint32_t kCloakfoxChromeTlsFlag = 0x40000000u;

inline uint32_t CloakfoxNetworkProfileForContainer(uint32_t aUserContextId) {
  if (!StaticPrefs::cloakfox_enabled()) return 0;
  nsAutoCString key;
  key.AppendPrintf("cloakfox.container.%u.network_profile", aUserContextId);
  // Exact owner 0 means owner 0, never an ambient container fallback.
  return Preferences::GetInt(key.get(), 0) == 1 ? 1 : 0;
}
}  // namespace mozilla::net
#endif
