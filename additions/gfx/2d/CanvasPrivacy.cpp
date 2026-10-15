/* MPL-2.0: conservative canvas pixel producer provenance. */
#include "CanvasPrivacy.h"
#include "2D.h"
#include "mozilla/StaticMutex.h"
namespace mozilla::gfx {
namespace {
StaticMutex sCanvasPrivacyMutex;
UserDataKey sCanvasPrivacyKey;
struct CanvasPixelSources {
  CanvasPrivacyMetadata value;
};
void DestroyCanvasPixelSources(void* aData) {
  delete static_cast<CanvasPixelSources*>(aData);
}
}  // namespace
CanvasPrivacyMetadata NormalizeCanvasPrivacyMetadata(
    CanvasPrivacyMetadata aData) {
  const bool malformedSources =
      aData.sources != NormalizeCanvasPixelSources(aData.sources);
  aData.sources = NormalizeCanvasPixelSources(aData.sources);
  if (malformedSources ||
      (aData.version != 0 && aData.version != kCanvasPrivacyVersion) ||
      (aData.version == 0 &&
       (aData.ownerHi || aData.ownerLo || aData.userContextId)) ||
      (aData.version != 0 && !(aData.ownerHi || aData.ownerLo))) {
    aData.version = aData.userContextId = 0;
    aData.ownerHi = aData.ownerLo = 0;
    aData.sources |= uint32_t(CanvasPixelSource::Unknown);
  }
  return aData;
}
bool CanExtractCanonicalCanvasPixels(const CanvasPrivacyMetadata& aInput) {
  const auto p = NormalizeCanvasPrivacyMetadata(aInput);
  const auto has = [&](CanvasPixelSource s) { return (p.sources & uint32_t(s)) != 0; };
  if (p.version != kCanvasPrivacyVersion || !(p.ownerHi || p.ownerLo) ||
      has(CanvasPixelSource::Unknown) || has(CanvasPixelSource::HostText)) return false;
  if (!has(CanvasPixelSource::Software2D) && !has(CanvasPixelSource::GPU) &&
      !has(CanvasPixelSource::Media)) return false;
  if (has(CanvasPixelSource::GPU) && !has(CanvasPixelSource::CanonicalGPU)) return false;
  if (has(CanvasPixelSource::Media) &&
      !(has(CanvasPixelSource::CanonicalMediaDecode) &&
        has(CanvasPixelSource::CanonicalColorConversion))) return false;
  return true;
}

bool CanImportCanonicalCanvasPixels(const CanvasPrivacyMetadata& aInput) {
  const auto p = NormalizeCanvasPrivacyMetadata(aInput);
  if (CanExtractCanonicalCanvasPixels(p)) return true;
  if (p.version || p.userContextId || p.ownerHi || p.ownerLo) return false;
  const auto bit = [](CanvasPixelSource s) { return uint32_t(s); };
  const uint32_t raster = bit(CanvasPixelSource::ExternalPixels) |
                          bit(CanvasPixelSource::CanonicalRaster);
  const uint32_t color = bit(CanvasPixelSource::CanonicalColorConversion);
  if ((p.sources & raster) == raster && !(p.sources & ~(raster | color))) return true;
  const uint32_t media = bit(CanvasPixelSource::Media) |
                         bit(CanvasPixelSource::CanonicalMediaDecode) | color;
  return p.sources == media;
}

CanvasPrivacyMetadata MergeCanvasPrivacyMetadata(CanvasPrivacyMetadata a,
                                                 CanvasPrivacyMetadata b) {
  a = NormalizeCanvasPrivacyMetadata(a);
  b = NormalizeCanvasPrivacyMetadata(b);
  a.sources |= b.sources;
  if (a.version != b.version || a.userContextId != b.userContextId ||
      a.ownerHi != b.ownerHi || a.ownerLo != b.ownerLo) {
    a.version = a.userContextId = 0;
    a.ownerHi = a.ownerLo = 0;
    a.sources |= uint32_t(CanvasPixelSource::Unknown);
  }
  return a;
}
void AddCanvasPixelSource(SourceSurface* aSurface, CanvasPixelSource aSource) {
  if (!aSurface) return;
  // Serialize creation as well as union updates: a racy replace could destroy a
  // node still being read by another worker. No node escapes this lock.
  StaticMutexAutoLock lock(sCanvasPrivacyMutex);
  const uint32_t sources = NormalizeCanvasPixelSources(uint32_t(aSource));
  auto* stored = static_cast<CanvasPixelSources*>(
      aSurface->GetUserData(&sCanvasPrivacyKey));
  if (stored)
    stored->value.sources |= sources;
  else
    aSurface->AddUserData(
        &sCanvasPrivacyKey,
        new CanvasPixelSources{CanvasPrivacyMetadata{0, 0, 0, 0, sources}},
        DestroyCanvasPixelSources);
}
CanvasPrivacyMetadata GetCanvasPrivacyMetadata(SourceSurface* aSurface) {
  if (!aSurface) return {};
  StaticMutexAutoLock lock(sCanvasPrivacyMutex);
  const auto* stored = static_cast<CanvasPixelSources*>(
      aSurface->GetUserData(&sCanvasPrivacyKey));
  return stored ? NormalizeCanvasPrivacyMetadata(stored->value)
                : CanvasPrivacyMetadata{};
}
void SetCanvasPrivacyMetadata(SourceSurface* aSurface,
                              const CanvasPrivacyMetadata& aMetadata) {
  if (!aSurface) return;
  StaticMutexAutoLock lock(sCanvasPrivacyMutex);
  auto* stored = static_cast<CanvasPixelSources*>(
      aSurface->GetUserData(&sCanvasPrivacyKey));
  const auto data = NormalizeCanvasPrivacyMetadata(aMetadata);
  if (stored)
    stored->value = MergeCanvasPrivacyMetadata(stored->value, data);
  else
    aSurface->AddUserData(&sCanvasPrivacyKey, new CanvasPixelSources{data},
                          DestroyCanvasPixelSources);
}
uint32_t GetCanvasPixelSources(SourceSurface* aSurface) {
  return GetCanvasPrivacyMetadata(aSurface).sources;
}
void MergeCanvasPixelSources(SourceSurface* aDestination, SourceSurface* aSource) {
  // Drop the read lock before adding, including self-merges.
  SetCanvasPrivacyMetadata(aDestination, GetCanvasPrivacyMetadata(aSource));
}
} // namespace mozilla::gfx
