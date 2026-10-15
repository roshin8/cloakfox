/* MPL-2.0: conservative canvas pixel producer provenance. */
#ifndef MOZILLA_GFX_CANVASPRIVACY_H_
#define MOZILLA_GFX_CANVASPRIVACY_H_
#include <cstdint>
namespace mozilla::gfx {
class SourceSurface;
// These describe contributors, never a certificate that extraction is safe.
// Ownership is an opaque native policy key; no origins or raw secrets are
// stored.
enum class CanvasPixelSource : uint32_t {
  Unknown=1, Software2D=2, FixedFontOutline=4, HostText=8,
  ExternalPixels=16, Media=32, GPU=64,
  CanonicalMediaDecode=128, CanonicalColorConversion=256, CanonicalGPU=512,
  CanonicalRaster=1024
};
constexpr uint32_t NormalizeCanvasPixelSources(uint32_t aSources) {
  constexpr uint32_t known = 2047;
  return aSources && !(aSources & ~known)
      ? aSources : (aSources & known) | uint32_t(CanvasPixelSource::Unknown);
}
constexpr uint32_t kCanvasPrivacyVersion = 1;
// Native-only transfer metadata. A valid owner identifies the immutable context
// policy, never a certificate that its pixels are canonical or safe to extract.
struct CanvasPrivacyMetadata {
  uint32_t version = 0;
  uint32_t userContextId = 0;
  uint64_t ownerHi = 0;
  uint64_t ownerLo = 0;
  uint32_t sources = uint32_t(CanvasPixelSource::Unknown);
  bool operator==(const CanvasPrivacyMetadata& aOther) const {
    return version == aOther.version && userContextId == aOther.userContextId &&
           ownerHi == aOther.ownerHi && ownerLo == aOther.ownerLo &&
           sources == aOther.sources;
  }
};
CanvasPrivacyMetadata NormalizeCanvasPrivacyMetadata(CanvasPrivacyMetadata);
CanvasPrivacyMetadata MergeCanvasPrivacyMetadata(CanvasPrivacyMetadata,
                                                 CanvasPrivacyMetadata);
CanvasPrivacyMetadata GetCanvasPrivacyMetadata(SourceSurface*);
// Requires actual producer markers and a retained owner, not protocol validity alone.
bool CanExtractCanonicalCanvasPixels(const CanvasPrivacyMetadata&);
// Ownerless fixed authored rasters/media contain no site-specific rendering.
// Every actual producer must verify its complete input before setting markers.
bool CanImportCanonicalCanvasPixels(const CanvasPrivacyMetadata&);
// First assignment establishes ownership; subsequent assignments can only merge
// contributors or invalidate conflicting ownership. They cannot relabel pixels.
void SetCanvasPrivacyMetadata(SourceSurface*, const CanvasPrivacyMetadata&);
void AddCanvasPixelSource(SourceSurface*, CanvasPixelSource);
uint32_t GetCanvasPixelSources(SourceSurface*);
void MergeCanvasPixelSources(SourceSurface* aDestination, SourceSurface* aSource);
} // namespace mozilla::gfx
#endif
