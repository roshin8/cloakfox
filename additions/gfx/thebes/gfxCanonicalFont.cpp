/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
#include "gfxCanonicalFont.h"
#include "../../dom/canvas/CanonicalCanvasText.h"
#include "ImageOps.h"
#include "gfxHarfBuzzShaper.h"
#include "harfbuzz/hb-ot.h"
#include "imgIContainer.h"
#include "mozilla/StaticMutex.h"
#include "mozilla/gfx/gfxVars.h"
#include "nsIFile.h"
#include "nsStringStream.h"
#include "prio.h"
#include <map>
#include <string>

using namespace mozilla;
using namespace mozilla::gfx;
using mozilla::dom::CanonicalCanvasText;
extern "C" hb_unicode_funcs_t* mozilla_harfbuzz_glue_set_up_unicode_funcs();

namespace {
void AppendOutline(PathBuilder* aBuilder, const CanonicalCanvasText::Run& aRun,
                   Point aOrigin) {
  for (const auto& command : aRun.commands) {
    const float* p = command.p;
    auto point = [&](int i) { return Point(p[i], p[i + 1]) + aOrigin; };
    switch (command.kind) {
      case CanonicalCanvasText::Command::Kind::Move:
        aBuilder->MoveTo(point(0));
        break;
      case CanonicalCanvasText::Command::Kind::Line:
        aBuilder->LineTo(point(0));
        break;
      case CanonicalCanvasText::Command::Kind::Quadratic:
        aBuilder->QuadraticBezierTo(point(0), point(2));
        break;
      case CanonicalCanvasText::Command::Kind::Cubic:
        aBuilder->BezierTo(point(0), point(2), point(4));
        break;
      case CanonicalCanvasText::Command::Kind::Close:
        aBuilder->Close();
        break;
    }
  }
}

class CanonicalScaledFont final : public ScaledFont {
 public:
  MOZ_DECLARE_REFCOUNTED_VIRTUAL_TYPENAME(CanonicalScaledFont, override)
  CanonicalScaledFont(gfxFontEntry* aEntry, float aSize,
                      const gfxFontStyle& aStyle)
      : ScaledFont(nullptr),
        mEntry(aEntry),
        mSize(aSize),
        mProducer(aEntry->GetHBFace(),
                  mozilla_harfbuzz_glue_set_up_unicode_funcs(), true) {
    nsTArray<gfxFontVariation> variations;
    aEntry->GetVariationsForStyle(variations, aStyle);
    for (const auto& variation : variations)
      mOptions.variations.push_back({variation.tag, variation.value});
  }
  FontType GetType() const override { return FontType::UNKNOWN; }
  Float GetSize() const override { return mSize; }
  bool IsCanonicalFont() const override { return true; }
  AntialiasMode GetDefaultAAMode() override { return AntialiasMode::GRAY; }
  bool UseSubpixelPosition() const override { return true; }
  already_AddRefed<Path> GetPathForGlyphs(const GlyphBuffer& aBuffer,
                                          const DrawTarget* aTarget) override {
    RefPtr<PathBuilder> builder = aTarget->CreatePathBuilder();
    if (!builder) return nullptr;
    CopyGlyphsToBuilder(aBuffer, builder, nullptr);
    return builder->Finish();
  }
  void CopyGlyphsToBuilder(const GlyphBuffer& aBuffer, PathBuilder* aBuilder,
                           const Matrix*) override {
    for (uint32_t i = 0; i < aBuffer.mNumGlyphs; ++i) {
      auto options = mOptions;
      options.glyphId = aBuffer.mGlyphs[i].mIndex;
      CanonicalCanvasText::Run run;
      if (mProducer.Shape(u"", 0, mSize, run, options))
        AppendOutline(aBuilder, run, aBuffer.mGlyphs[i].mPosition);
    }
  }
  Maybe<Rect> GetCanonicalGlyphBounds(const GlyphBuffer& aBuffer) override {
    Rect bounds;
    for (uint32_t i = 0; i < aBuffer.mNumGlyphs; ++i) {
      auto options = mOptions;
      options.glyphId = aBuffer.mGlyphs[i].mIndex;
      CanonicalCanvasText::Run run;
      if (!mProducer.Shape(u"", 0, mSize, run, options)) return Nothing();
      RefPtr<PathBuilder> builder =
          Factory::CreatePathBuilder(BackendType::SKIA, FillRule::FILL_WINDING);
      if (!builder) return Nothing();
      AppendOutline(builder, run, aBuffer.mGlyphs[i].mPosition);
      RefPtr<Path> path = builder->Finish();
      bounds = bounds.Union(path->GetBounds());
      for (const auto& image : run.images)
        bounds = bounds.Union(Rect(image.x + aBuffer.mGlyphs[i].mPosition.x,
                                   image.y + aBuffer.mGlyphs[i].mPosition.y,
                                   image.width, image.height));
    }
    return Some(bounds);
  }
  bool DrawCanonicalGlyphs(DrawTarget* aTarget, const GlyphBuffer& aBuffer,
                           const Pattern& aPattern,
                           const StrokeOptions* aStroke,
                           const DrawOptions& aOptions) override {
    // All errors are handled here. Returning true forbids fallback to native
    // SkTypeface rasterization even if allocation or font data is invalid.
    for (uint32_t i = 0; i < aBuffer.mNumGlyphs; ++i) {
      auto options = mOptions;
      options.glyphId = aBuffer.mGlyphs[i].mIndex;
      CanonicalCanvasText::Run run;
      if (!mProducer.Shape(u"", 0, mSize, run, options)) return true;
      if (!run.commands.empty()) {
        RefPtr<PathBuilder> builder = aTarget->CreatePathBuilder();
        if (!builder) return true;
        AppendOutline(builder, run, aBuffer.mGlyphs[i].mPosition);
        RefPtr<Path> path = builder->Finish();
        if (aStroke)
          aTarget->Stroke(path, aPattern, *aStroke, aOptions);
        else
          aTarget->Fill(path, aPattern, aOptions);
      }
      for (const auto& image : run.images) {
        nsCOMPtr<nsIInputStream> input;
        if (NS_FAILED(NS_NewByteInputStream(
                getter_AddRefs(input),
                Span(reinterpret_cast<const char*>(image.png.data()),
                     image.png.size()),
                NS_ASSIGNMENT_DEPEND)))
          return true;
        RefPtr<SourceSurface> surface = image::ImageOps::DecodeToSurface(
            input.forget(), "image/png"_ns,
            imgIContainer::FLAG_DECODE_TO_SRGB_COLORSPACE);
        if (!surface) return true;
        const Point p = aBuffer.mGlyphs[i].mPosition;
        aTarget->DrawSurface(
            surface,
            Rect(image.x + p.x, image.y + p.y, image.width, image.height),
            Rect(0, 0, surface->GetSize().width, surface->GetSize().height),
            DrawSurfaceOptions(SamplingFilter::LINEAR), aOptions);
      }
    }
    return true;
  }

 private:
  RefPtr<gfxFontEntry> mEntry;
  float mSize;
  CanonicalCanvasText mProducer;
  CanonicalCanvasText::ShapeOptions mOptions;
};

class CanonicalFont final : public gfxFont {
 public:
  CanonicalFont(gfxFontEntry* aEntry, const gfxFontStyle* aStyle)
      : gfxFont(nullptr, aEntry, aStyle, kAntialiasGrayscale) {
    mApplySyntheticBold = aStyle->NeedsSyntheticBold(aEntry);
    // All primary and derived metrics originate in the same OpenType tables
    // and variation coordinates as shaping and the outline producer.
    if (!InitMetricsFromSfntTables() || !mIsValid) return;
    auto face = aEntry->GetHBFace();
    mHBFont = hb_font_create(face);
    hb_ot_font_set_funcs(mHBFont);
    const int upem = hb_face_get_upem(face);
    hb_font_set_scale(mHBFont, upem, upem);
    nsTArray<gfxFontVariation> variations;
    aEntry->GetVariationsForStyle(variations, *aStyle);
    hb_font_set_variations(
        mHBFont, reinterpret_cast<const hb_variation_t*>(variations.Elements()),
        variations.Length());
    auto glyphAdvance = [&](uint32_t ch, bool vertical) -> double {
      hb_codepoint_t gid;
      if (!hb_font_get_nominal_glyph(mHBFont, ch, &gid)) return -1.0;
      return (vertical ? -hb_font_get_glyph_v_advance(mHBFont, gid)
                       : hb_font_get_glyph_h_advance(mHBFont, gid)) *
             mFUnitsConvFactor;
    };
    auto setWidths = [&] {
      mMetrics.spaceWidth = std::max(0.0, glyphAdvance(' ', false));
      mMetrics.zeroWidth = glyphAdvance('0', false);
      mMetrics.ideographicWidth = glyphAdvance(kWaterIdeograph, false);
      hb_glyph_extents_t bounds;
      hb_codepoint_t gid;
      if (mMetrics.xHeight <= 0 &&
          hb_font_get_nominal_glyph(mHBFont, 'x', &gid) &&
          hb_font_get_glyph_extents(mHBFont, gid, &bounds))
        mMetrics.xHeight = -bounds.height * mFUnitsConvFactor;
      if (mMetrics.capHeight <= 0 &&
          hb_font_get_nominal_glyph(mHBFont, 'H', &gid) &&
          hb_font_get_glyph_extents(mHBFont, gid, &bounds))
        mMetrics.capHeight = -bounds.height * mFUnitsConvFactor;
    };
    setWidths();
    if (FontSizeAdjust::Tag(mStyle.sizeAdjustBasis) !=
            FontSizeAdjust::Tag::None &&
        mStyle.sizeAdjust >= 0 && GetAdjustedSize() > 0) {
      double metric = 0;
      switch (FontSizeAdjust::Tag(mStyle.sizeAdjustBasis)) {
        case FontSizeAdjust::Tag::ExHeight:
          metric = mMetrics.xHeight;
          break;
        case FontSizeAdjust::Tag::CapHeight:
          metric = mMetrics.capHeight;
          break;
        case FontSizeAdjust::Tag::ChWidth:
          metric = mMetrics.zeroWidth < 0 ? GetAdjustedSize() * .5
                                          : mMetrics.zeroWidth;
          break;
        case FontSizeAdjust::Tag::IcWidth:
          metric = mMetrics.ideographicWidth;
          break;
        case FontSizeAdjust::Tag::IcHeight:
          metric = glyphAdvance(kWaterIdeograph, true);
          break;
        case FontSizeAdjust::Tag::None:
          break;
      }
      if (metric <= 0) metric = GetAdjustedSize();
      mAdjustedSize = mStyle.GetAdjustedSize(metric / GetAdjustedSize());
      mFUnitsConvFactor = mAdjustedSize / upem;
      mMetrics = {};
      if (!InitMetricsFromSfntTables() || !mIsValid) return;
      setWidths();
    }
    mMetrics.emHeight = GetAdjustedSize();
    CalculateDerivedMetrics();
    SanitizeMetrics(aEntry->mIsBadUnderlineFont);
  }
  ~CanonicalFont() override { hb_font_destroy(mHBFont); }
  FontType GetType() const override { return FONT_TYPE_CANONICAL; }
  bool ProvidesGlyphWidths() const override { return true; }
  int32_t GetGlyphWidth(uint16_t aGlyph) override {
    if (!mHBFont) return 0;
    return int32_t(
        std::clamp(double(hb_font_get_glyph_h_advance(mHBFont, aGlyph)) *
                       mFUnitsConvFactor * 65536.0,
                   double(INT32_MIN), double(INT32_MAX)));
  }
  bool ShouldHintMetrics() const override { return false; }
  bool ShouldRoundXOffset(cairo_t*) const override { return false; }
  bool GetGlyphBounds(uint16_t aGlyph, gfxRect* aBounds, bool) override {
    hb_glyph_extents_t bounds;
    if (!mHBFont) return false;
    hb_face_t* face = hb_font_get_face(mHBFont);
    unsigned count =
        hb_ot_color_glyph_get_layers(face, aGlyph, 0, nullptr, nullptr);
    if (count) {
      std::vector<hb_ot_color_layer_t> layers(count);
      hb_ot_color_glyph_get_layers(face, aGlyph, 0, &count, layers.data());
      *aBounds = gfxRect();
      for (const auto& layer : layers) {
        if (!hb_font_get_glyph_extents(mHBFont, layer.glyph, &bounds)) continue;
        *aBounds = aBounds->Union(gfxRect(bounds.x_bearing * mFUnitsConvFactor,
                                          -bounds.y_bearing * mFUnitsConvFactor,
                                          bounds.width * mFUnitsConvFactor,
                                          -bounds.height * mFUnitsConvFactor));
      }
    } else {
      if (!hb_font_get_glyph_extents(mHBFont, aGlyph, &bounds)) return false;
      *aBounds = gfxRect(bounds.x_bearing * mFUnitsConvFactor,
                         -bounds.y_bearing * mFUnitsConvFactor,
                         bounds.width * mFUnitsConvFactor,
                         -bounds.height * mFUnitsConvFactor);
    }
    return true;
  }
  already_AddRefed<ScaledFont> GetScaledFont(
      const TextRunDrawParams&) override {
    if (ScaledFont* cached = mAzureScaledFont) return do_AddRef(cached);
    RefPtr<ScaledFont> created =
        new CanonicalScaledFont(mFontEntry, GetAdjustedSize(), mStyle);
    InitializeScaledFont(created);
    if (mAzureScaledFont.compareExchange(nullptr, created.get()))
      created.forget().leak();
    ScaledFont* cached = mAzureScaledFont;
    return do_AddRef(cached);
  }

 private:
  hb_font_t* mHBFont = nullptr;
};
}  // namespace

gfxCanonicalFontEntry::gfxCanonicalFontEntry(const nsACString& aName,
                                             hb_face_t* aFace,
                                             gfxFontEntry* aSource)
    : gfxFontEntry(aName),
      mFace(hb_face_reference(aFace)),
      mAuthorSource(aSource) {
  if (aSource)
    SetFamilyName(aSource->FamilyName());
  else
    SetFamilyName(nsCString(aName));
  mWeightRange = WeightRange(FontWeight::NORMAL);
  if (!aSource && hb_ot_var_has_data(mFace)) SetupVariationRanges();
  if (aSource) {
    mWeightRange = aSource->Weight();
    mWidthRange = aSource->Width();
    mStyleRange = aSource->SlantStyle();
    mIsDataUserFont = aSource->mIsDataUserFont;
    mIsLocalUserFont = aSource->mIsLocalUserFont;
    mFeatureSettings = aSource->mFeatureSettings.Clone();
    mVariationSettings = aSource->mVariationSettings.Clone();
    mSizeAdjust = aSource->mSizeAdjust;
    mFixedPitch = aSource->mFixedPitch;
    mAscentOverride = aSource->mAscentOverride;
    mDescentOverride = aSource->mDescentOverride;
    mLineGapOverride = aSource->mLineGapOverride;
    mLanguageOverride = aSource->mLanguageOverride;
  }
}
gfxCanonicalFontEntry::~gfxCanonicalFontEntry() { hb_face_destroy(mFace); }
gfxFontEntry* gfxCanonicalFontEntry::Clone() const {
  return new gfxCanonicalFontEntry(Name(), mFace, mAuthorSource);
}
hb_blob_t* gfxCanonicalFontEntry::GetFontTableInternal(uint32_t aTag) {
  hb_blob_t* blob = hb_face_reference_table(mFace, aTag);
  if (!hb_blob_get_length(blob)) {
    hb_blob_destroy(blob);
    return nullptr;
  }
  return blob;
}
bool gfxCanonicalFontEntry::HasVariationsInternal() {
  return hb_ot_var_has_data(mFace);
}
void gfxCanonicalFontEntry::GetVariationAxesInternal(
    nsTArray<gfxFontVariationAxis>& aAxes) {
  unsigned count = hb_ot_var_get_axis_count(mFace);
  std::vector<hb_ot_var_axis_info_t> axes(count);
  hb_ot_var_get_axis_infos(mFace, 0, &count, axes.data());
  for (const auto& axis : axes)
    aAxes.AppendElement(gfxFontVariationAxis{axis.tag, nsCString(),
                                             axis.min_value, axis.max_value,
                                             axis.default_value});
}
nsresult gfxCanonicalFontEntry::ReadCMAP(FontInfoData*) {
  if (HasCharacterMap()) return NS_OK;
  RefPtr<gfxCharacterMap> map = new gfxCharacterMap(256);
  hb_blob_t* blob = hb_face_reference_table(mFace, HB_TAG('c', 'm', 'a', 'p'));
  unsigned length;
  const char* data = hb_blob_get_data(blob, &length);
  uint32_t uvs = 0;
  nsresult rv = gfxFontUtils::ReadCMAP(reinterpret_cast<const uint8_t*>(data),
                                       length, *map, uvs);
  hb_blob_destroy(blob);
  mUVSOffset.exchange(uvs);
  AutoWriteLock lock(mLock);
  if (mCharacterMap.compareExchange(nullptr, map.get())) map.forget().leak();
  return rv;
}
gfxFont* gfxCanonicalFontEntry::CreateFontInstance(const gfxFontStyle* aStyle) {
  return new CanonicalFont(this, aStyle);
}
already_AddRefed<gfxCanonicalFontEntry> gfxCanonicalFontEntry::Author(
    gfxFontEntry* aSource) {
  if (!aSource || !aSource->IsUserFont() || aSource->IsLocalUserFont())
    return nullptr;
  auto face = aSource->GetHBFace();
  RefPtr<gfxCanonicalFontEntry> entry =
      new gfxCanonicalFontEntry(aSource->Name(), face, aSource);
  return entry.forget();
}
already_AddRefed<gfxCanonicalFontEntry> gfxCanonicalFontEntry::Bundled(
    const nsACString& aName) {
  static StaticMutex mutex;
  StaticMutexAutoLock lock(mutex);
  static std::map<std::string, RefPtr<gfxCanonicalFontEntry>> cache;
  const std::string name(PromiseFlatCString(aName).get());
  if (auto found = cache.find(name); found != cache.end())
    return do_AddRef(found->second);
  // Caller supplies only fixed internal file names, never page-controlled
  // paths.
  const nsString& gre = gfxVars::GREDirectory();
  if (gre.IsEmpty()) return nullptr;
  nsCOMPtr<nsIFile> file;
  if (NS_FAILED(NS_NewLocalFile(gre, getter_AddRefs(file))) ||
      NS_FAILED(file->Append(u"fonts"_ns)) ||
      NS_FAILED(file->Append(NS_ConvertUTF8toUTF16(aName))))
    return nullptr;
  int64_t size = 0;
  if (NS_FAILED(file->GetFileSize(&size)) || size <= 0 ||
      size > 32 * 1024 * 1024)
    return nullptr;
  PRFileDesc* fd = nullptr;
  if (NS_FAILED(file->OpenNSPRFileDesc(PR_RDONLY, 0, &fd))) return nullptr;
  std::vector<char> bytes(size);
  size_t done = 0;
  while (done < bytes.size()) {
    int32_t n = PR_Read(fd, bytes.data() + done, bytes.size() - done);
    if (n <= 0) break;
    done += n;
  }
  PR_Close(fd);
  if (done != bytes.size()) return nullptr;
  hb_blob_t* blob = hb_blob_create(bytes.data(), bytes.size(),
                                   HB_MEMORY_MODE_DUPLICATE, nullptr, nullptr);
  hb_face_t* face = hb_face_create(blob, 0);
  hb_blob_destroy(blob);
  if (!hb_face_get_glyph_count(face)) {
    hb_face_destroy(face);
    return nullptr;
  }
  RefPtr<gfxCanonicalFontEntry> entry = new gfxCanonicalFontEntry(aName, face);
  hb_face_destroy(face);
  cache.emplace(name, entry);
  return entry.forget();
}
