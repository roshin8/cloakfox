/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

#include "CloakfoxWorkerTiming.h"

namespace CloakfoxWorkerTiming {
namespace {

uint64_t SplitMix64(uint64_t aValue) {
  aValue += 0x9e3779b97f4a7c15ULL;
  aValue = (aValue ^ (aValue >> 30)) * 0xbf58476d1ce4e5b9ULL;
  aValue = (aValue ^ (aValue >> 27)) * 0x94d049bb133111ebULL;
  return aValue ^ (aValue >> 31);
}

}  // namespace

uint64_t HashWorkerId(const char16_t* aData, size_t aLength) {
  // FNV-1a over UTF-16 code units is independent of host byte order.
  uint64_t hash = 14695981039346656037ULL;
  for (size_t i = 0; i < aLength; ++i) {
    hash ^= uint16_t(aData[i]);
    hash *= 1099511628211ULL;
  }
  return hash;
}

State::State(CloakfoxTiming::Key aKey, uint64_t aStreamId) {
  const uint64_t key = (uint64_t(aKey.mHi) << 32) | aKey.mLo;
  mState0 = SplitMix64(key ^ aStreamId);
  mState1 = SplitMix64(mState0 ^ aStreamId ^ 0xd1b54a32d192ed03ULL);
  if (mState0 == 0 && mState1 == 0) {
    mState1 = 0x9e3779b97f4a7c15ULL;
  }
}

uint64_t State::NextU64() {
  uint64_t state0 = mState0;
  const uint64_t state1 = mState1;
  mState0 = state1;
  state0 ^= state0 << 23;
  mState1 = state0 ^ state1 ^ (state0 >> 17) ^ (state1 >> 26);
  return mState1 + state1;
}

uint32_t State::NextU32() { return uint32_t(NextU64() >> 32); }

uint32_t State::NextInterruptDelayMs() {
  return kMinInterruptMs + NextU32() % (kMaxInterruptMs - kMinInterruptMs + 1);
}

bool State::ShouldYield() { return (NextU32() & 3u) != 0; }

uint32_t State::NextYieldUs() {
  return ShouldYield() ? NextU32() % (kMaxYieldUs + 1) : 0;
}

}  // namespace CloakfoxWorkerTiming
