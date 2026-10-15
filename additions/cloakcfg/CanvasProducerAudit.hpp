/* MPL-2.0: actual producers observed while rasterizing an SVG document. */
#pragma once
#include <cstdint>
namespace Cloakfox {
// Synchronous rendering nests on one thread; each thread has an independent
// stack. No document, font or author data survives the rendering scope.
class CanvasProducerAudit final {
 public:
  explicit CanvasProducerAudit(uint32_t aContext = 0, uint64_t aOwnerHi = 0,
                              uint64_t aOwnerLo = 0)
      : mPrevious(sCurrent), mContext(aContext), mOwnerHi(aOwnerHi),
        mOwnerLo(aOwnerLo) {
    sCurrent = this;
  }
  ~CanvasProducerAudit() {
    sCurrent = mPrevious;
    Observe(mSucceeded, mSources, mContext, mOwnerHi, mOwnerLo);
  }
  CanvasProducerAudit(const CanvasProducerAudit&) = delete;
  CanvasProducerAudit& operator=(const CanvasProducerAudit&) = delete;
  static void Observe(bool aCanonical, uint32_t aSources,
                      uint32_t aContext = 0, uint64_t aOwnerHi = 0,
                      uint64_t aOwnerLo = 0) {
    if (!sCurrent) return;
    const bool foreign = (aOwnerHi || aOwnerLo) &&
        (aContext != sCurrent->mContext || aOwnerHi != sCurrent->mOwnerHi ||
         aOwnerLo != sCurrent->mOwnerLo);
    sCurrent->mSucceeded &= aCanonical && !foreign;
    sCurrent->mSources |= aSources;
  }
  bool Succeeded() const { return mSucceeded; }
  uint32_t Sources() const { return mSources; }
 private:
  inline static thread_local CanvasProducerAudit* sCurrent = nullptr;
  CanvasProducerAudit* const mPrevious;
  const uint32_t mContext;
  const uint64_t mOwnerHi, mOwnerLo;
  uint32_t mSources = 0;
  bool mSucceeded = true;
};
}  // namespace Cloakfox
