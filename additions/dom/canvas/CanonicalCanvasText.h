/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
#ifndef mozilla_dom_CanonicalCanvasText_h
#define mozilla_dom_CanonicalCanvasText_h

#include <cstddef>
#include <vector>
#if __has_include("harfbuzz/hb.h")
#  include "harfbuzz/hb.h"
#else
#  include "hb.h"
#endif

namespace mozilla::dom {
// Platform-independent OpenType shaping and outlines. Callers provide
// byte-based bundled or sanitized author faces and visual bidi/script segments.
// No native scaled-font object or platform advance callback participates.
// Unsupported color formats/missing glyphs fail atomically before any commands
// are drawn.
class CanonicalCanvasText final {
 public:
  struct Command {
    enum class Kind { Move, Line, Quadratic, Cubic, Close } kind;
    float p[6] = {};
  };
  struct Image {
    std::vector<unsigned char> png;
    float x = 0, y = 0, width = 0, height = 0;
    size_t commandOffset = 0;
  };
  struct Run {
    std::vector<Command> commands;
    std::vector<Image> images;
    double advance = 0, ascent = 0, descent = 0;
  };
  struct ShapeOptions {
    hb_direction_t direction = HB_DIRECTION_INVALID;
    hb_script_t script = HB_SCRIPT_INVALID;
    hb_language_t language = HB_LANGUAGE_INVALID;
    std::vector<hb_feature_t> features;
    std::vector<hb_variation_t> variations;
    double letterSpacing = 0, wordSpacing = 0;
    // Already-shaped Gecko gfxTextRun glyphs use the same byte-based producer.
    hb_codepoint_t glyphId = unsigned(-1);
  };
  explicit CanonicalCanvasText(
      hb_face_t* aFace,
      hb_unicode_funcs_t* aUnicode = hb_unicode_funcs_get_default(),
      bool aAllowColorOutlines = false);
  CanonicalCanvasText(
      const char* aBytes, size_t aLength,
      hb_unicode_funcs_t* aUnicode = hb_unicode_funcs_get_default());
  ~CanonicalCanvasText();
  // Retains immutable font tables for the process resource cache; caller owns
  // the returned reference. No glyph or native raster state is shared.
  hb_face_t* ReferenceFace() const {
    return mFont ? hb_face_reference(hb_font_get_face(mFont)) : nullptr;
  }
  CanonicalCanvasText(const CanonicalCanvasText&) = delete;
  CanonicalCanvasText& operator=(const CanonicalCanvasText&) = delete;
  bool Shape(const char16_t* aText, size_t aLength, float aSize,
             Run& aRun) const;
  bool Shape(const char16_t* aText, size_t aLength, float aSize, Run& aRun,
             const ShapeOptions& aOptions) const;

 private:
  void InitFace(hb_face_t* aFace, bool aAllowColorOutlines = false);
  hb_font_t* mFont = nullptr;
  hb_unicode_funcs_t* mUnicode = nullptr;
};
}  // namespace mozilla::dom
#endif
