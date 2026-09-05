/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

#ifndef CloakfoxWorkerTiming_h
#define CloakfoxWorkerTiming_h

#include <cstddef>
#include <cstdint>

#include "CloakfoxTiming.h"

namespace CloakfoxWorkerTiming {

static constexpr uint32_t kMinInterruptMs = 3;
static constexpr uint32_t kMaxInterruptMs = 9;
static constexpr uint32_t kMaxYieldUs = 250;
static_assert(kMinInterruptMs > 0);
static_assert(kMinInterruptMs <= kMaxInterruptMs);
static_assert(kMaxYieldUs <= 1000);

uint64_t HashWorkerId(const char16_t* aData, size_t aLength);

class State final {
 public:
  State(CloakfoxTiming::Key aKey, uint64_t aStreamId);

  uint32_t NextInterruptDelayMs();
  uint32_t NextYieldUs();
  bool ShouldYield();

 private:
  uint64_t NextU64();
  uint32_t NextU32();

  uint64_t mState0;
  uint64_t mState1;
};

}  // namespace CloakfoxWorkerTiming

#endif  // CloakfoxWorkerTiming_h
