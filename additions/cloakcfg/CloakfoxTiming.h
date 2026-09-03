/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

#ifndef CloakfoxTiming_h
#define CloakfoxTiming_h

#include <cstdint>

namespace CloakfoxTiming {

struct Key {
  uint32_t mHi = 0;
  uint32_t mLo = 0;

  bool IsValid() const { return mHi != 0 || mLo != 0; }
};

struct Interval {
  double mStart;
  double mEnd;

  double Duration() const { return mEnd - mStart; }
};

Key LoadKey(uint32_t aUserContextId);

double TransformTimestamp(double aRaw, const Key& aKey,
                          uint64_t aStreamId = 0);

Interval TransformInterval(double aStart, double aEnd, const Key& aKey,
                           uint64_t aStreamId = 0);

}  // namespace CloakfoxTiming

#endif  // CloakfoxTiming_h
