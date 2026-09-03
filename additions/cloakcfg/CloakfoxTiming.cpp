/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

#include "CloakfoxTiming.h"

#include <algorithm>
#include <cmath>

#include "MaskConfig.hpp"

namespace CloakfoxTiming {
namespace {

uint64_t SplitMix64(uint64_t aValue) {
  aValue += 0x9e3779b97f4a7c15ULL;
  aValue = (aValue ^ (aValue >> 30)) * 0xbf58476d1ce4e5b9ULL;
  aValue = (aValue ^ (aValue >> 27)) * 0x94d049bb133111ebULL;
  return aValue ^ (aValue >> 31);
}

double UnitJitter(uint64_t aBucket, const Key& aKey, uint64_t aStreamId) {
  const uint64_t key = (uint64_t(aKey.mHi) << 32) | aKey.mLo;
  const uint64_t value =
      SplitMix64(key ^ SplitMix64(aBucket) ^ SplitMix64(aStreamId));
  return double(value >> 11) * (1.0 / 9007199254740992.0);
}

}  // namespace

Key LoadKey(uint32_t aUserContextId) {
  const auto hi =
      MaskConfig::GetUint32("timing:session_key_hi", aUserContextId);
  const auto lo =
      MaskConfig::GetUint32("timing:session_key_lo", aUserContextId);
  if (!hi || !lo) {
    return {};
  }
  return {*hi, *lo};
}

double TransformTimestamp(double aRaw, const Key& aKey, uint64_t aStreamId) {
  if (!aKey.IsValid() || !std::isfinite(aRaw) || aRaw < 0) {
    return aRaw;
  }
  const uint64_t bucket = static_cast<uint64_t>(std::floor(aRaw));
  const double fraction = aRaw - double(bucket);
  const double left = UnitJitter(bucket, aKey, aStreamId);
  const double right = UnitJitter(bucket + 1, aKey, aStreamId);
  const double offset = left + (right - left) * fraction;
  return aRaw + 0.999 * offset;
}

Interval TransformInterval(double aStart, double aEnd, const Key& aKey,
                           uint64_t aStreamId) {
  const double start = TransformTimestamp(aStart, aKey, aStreamId);
  const double end =
      TransformTimestamp(std::max(aStart, aEnd), aKey, aStreamId);
  return {start, std::max(start, end)};
}

}  // namespace CloakfoxTiming
