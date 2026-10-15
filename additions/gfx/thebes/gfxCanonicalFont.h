/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
#ifndef GFX_CANONICAL_FONT_H
#define GFX_CANONICAL_FONT_H
#include "gfxFont.h"
#include "gfxFontEntry.h"

// Entries are distinct from native entries, so the existing gfxFontCache key
// (entry + style + unicode-range) cannot alias native and canonical instances.
// Only bundled entries may be process-cached; author wrappers stay font-group
// owned and retain the original sanitized author face throughout their
// lifetime.
class gfxCanonicalFontEntry final : public gfxFontEntry {
 public:
  static already_AddRefed<gfxCanonicalFontEntry> Bundled(
      const nsACString& aName);
  static already_AddRefed<gfxCanonicalFontEntry> Author(gfxFontEntry* aSource);
  gfxFontEntry* Clone() const override;
  bool IsCanonicalFontEntry() const override { return true; }
  AutoHBFace GetHBFace() override {
    return AutoHBFace(hb_face_reference(mFace));
  }
  nsresult ReadCMAP(FontInfoData* = nullptr) override;

 protected:
  gfxFont* CreateFontInstance(const gfxFontStyle*) override;
  hb_blob_t* GetFontTableInternal(uint32_t aTag) override;
  FontTableCache* GetFontTableCache(bool) override { return nullptr; }
  bool HasVariationsInternal() override;
  void GetVariationAxesInternal(nsTArray<gfxFontVariationAxis>&) override;

 private:
  gfxCanonicalFontEntry(const nsACString& aName, hb_face_t* aFace,
                        gfxFontEntry* aSource = nullptr);
  ~gfxCanonicalFontEntry() override;
  hb_face_t* mFace;
  RefPtr<gfxFontEntry> mAuthorSource;
};
#endif
