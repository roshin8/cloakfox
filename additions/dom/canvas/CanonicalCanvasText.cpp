/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
#include "CanonicalCanvasText.h"
#include "hb-ot.h"
#include <cmath>
#include <limits>

namespace mozilla::dom {
namespace {
using Command = CanonicalCanvasText::Command;
struct Outline {
  CanonicalCanvasText::Run& run;
  float scale, x = 0, y = 0;
  bool exhausted = false;
  void Add(Command::Kind kind, float x1 = 0, float y1 = 0, float x2 = 0,
           float y2 = 0, float x3 = 0, float y3 = 0) {
    if (run.commands.size() >= 1024 * 1024) {
      exhausted = true;
      return;
    }
    Command cmd{kind};
    if (kind != Command::Kind::Close) {
      cmd.p[0] = x + x1 * scale;
      cmd.p[1] = y - y1 * scale;
      if (kind == Command::Kind::Quadratic || kind == Command::Kind::Cubic) {
        cmd.p[2] = x + x2 * scale;
        cmd.p[3] = y - y2 * scale;
      }
      if (kind == Command::Kind::Cubic) {
        cmd.p[4] = x + x3 * scale;
        cmd.p[5] = y - y3 * scale;
      }
    }
    run.commands.push_back(cmd);
  }
};
void Move(hb_draw_funcs_t*, void* d, hb_draw_state_t*, float x, float y,
          void*) {
  static_cast<Outline*>(d)->Add(Command::Kind::Move, x, y);
}
void Line(hb_draw_funcs_t*, void* d, hb_draw_state_t*, float x, float y,
          void*) {
  static_cast<Outline*>(d)->Add(Command::Kind::Line, x, y);
}
void Quadratic(hb_draw_funcs_t*, void* d, hb_draw_state_t*, float cx, float cy,
               float x, float y, void*) {
  static_cast<Outline*>(d)->Add(Command::Kind::Quadratic, cx, cy, x, y);
}
void Cubic(hb_draw_funcs_t*, void* d, hb_draw_state_t*, float cx, float cy,
           float dx, float dy, float x, float y, void*) {
  static_cast<Outline*>(d)->Add(Command::Kind::Cubic, cx, cy, dx, dy, x, y);
}
void Close(hb_draw_funcs_t*, void* d, hb_draw_state_t*, void*) {
  static_cast<Outline*>(d)->Add(Command::Kind::Close);
}
}  // namespace

CanonicalCanvasText::CanonicalCanvasText(const char* aBytes, size_t aLength,
                                         hb_unicode_funcs_t* aUnicode) {
  mUnicode = hb_unicode_funcs_reference(aUnicode);
  if (!aBytes || !aLength || aLength > std::numeric_limits<unsigned>::max())
    return;
  hb_blob_t* blob = hb_blob_create(aBytes, static_cast<unsigned>(aLength),
                                   HB_MEMORY_MODE_DUPLICATE, nullptr, nullptr);
  hb_face_t* face = hb_face_create(blob, 0);
  hb_blob_destroy(blob);
  InitFace(face);
  hb_face_destroy(face);
}

CanonicalCanvasText::CanonicalCanvasText(hb_face_t* aFace,
                                         hb_unicode_funcs_t* aUnicode,
                                         bool aAllowColorOutlines) {
  mUnicode = hb_unicode_funcs_reference(aUnicode);
  if (aFace) InitFace(aFace, aAllowColorOutlines);
}

void CanonicalCanvasText::InitFace(hb_face_t* face, bool aAllowColorOutlines) {
  // HB_NO_PAINT is used by Gecko. Never send color/SVG glyphs to a native
  // platform renderer and then label them as canonical outlines.
  bool color = false;
  for (hb_tag_t tag :
       {HB_TAG('C', 'O', 'L', 'R'), HB_TAG('S', 'V', 'G', ' ')}) {
    hb_blob_t* table = hb_face_reference_table(face, tag);
    color |= hb_blob_get_length(table) != 0;
    hb_blob_destroy(table);
  }
  if ((!color || aAllowColorOutlines) && hb_face_get_glyph_count(face) &&
      hb_face_get_upem(face)) {
    mFont = hb_font_create(face);
    hb_ot_font_set_funcs(mFont);
    int upem = static_cast<int>(hb_face_get_upem(face));
    hb_font_set_scale(mFont, upem, upem);
    hb_font_set_variations(mFont, nullptr, 0);
    hb_font_make_immutable(mFont);
  }
}
CanonicalCanvasText::~CanonicalCanvasText() {
  if (mFont) hb_font_destroy(mFont);
  hb_unicode_funcs_destroy(mUnicode);
}

bool CanonicalCanvasText::Shape(const char16_t* aText, size_t aLength,
                                float aSize, Run& aRun) const {
  return Shape(aText, aLength, aSize, aRun, ShapeOptions{});
}

bool CanonicalCanvasText::Shape(const char16_t* aText, size_t aLength,
                                float aSize, Run& aRun,
                                const ShapeOptions& aOptions) const {
  aRun = Run{};
  if (!mFont || !std::isfinite(aSize) || aSize <= 0 || aSize > 4096 ||
      aLength > 4096 || (!aText && aLength))
    return false;
  // Variation coordinates live on a per-run HB font, never on the immutable
  // cached font or a host scaled-font object.
  hb_font_t* font = hb_font_reference(mFont);
  if (!aOptions.variations.empty()) {
    hb_font_destroy(font);
    font = hb_font_create(hb_font_get_face(mFont));
    hb_ot_font_set_funcs(font);
    const int upem = hb_face_get_upem(hb_font_get_face(font));
    hb_font_set_scale(font, upem, upem);
    hb_font_set_variations(font, aOptions.variations.data(),
                           aOptions.variations.size());
  }
  hb_buffer_t* buffer = hb_buffer_create();
  hb_buffer_set_unicode_funcs(buffer, mUnicode);
  hb_buffer_add_utf16(buffer, reinterpret_cast<const uint16_t*>(aText),
                      static_cast<int>(aLength), 0, static_cast<int>(aLength));
  hb_buffer_set_direction(buffer, aOptions.direction);
  hb_buffer_set_script(buffer, aOptions.script);
  hb_buffer_set_language(buffer, aOptions.language == HB_LANGUAGE_INVALID
                                     ? hb_language_from_string("und", -1)
                                     : aOptions.language);
  // Guess only unset properties; Mozilla bidi/script itemization supplies
  // explicit properties for mixed-direction or mixed-script paragraphs.
  hb_buffer_guess_segment_properties(buffer);
  std::vector<hb_feature_t> features = aOptions.features;
  if (aOptions.letterSpacing != 0) {
    features.push_back({HB_TAG('l', 'i', 'g', 'a'), 0, 0, unsigned(-1)});
    features.push_back({HB_TAG('c', 'l', 'i', 'g'), 0, 0, unsigned(-1)});
  }
  if (aOptions.glyphId == unsigned(-1)) {
    hb_shape(font, buffer, features.data(), features.size());
  } else {
    hb_buffer_clear_contents(buffer);
    hb_buffer_set_content_type(buffer, HB_BUFFER_CONTENT_TYPE_GLYPHS);
    hb_buffer_add(buffer, aOptions.glyphId, 0);
    hb_glyph_position_t* position =
        hb_buffer_get_glyph_positions(buffer, nullptr);
    if (position)
      position[0].x_advance =
          hb_font_get_glyph_h_advance(font, aOptions.glyphId);
  }
  unsigned count = 0;
  auto* infos = hb_buffer_get_glyph_infos(buffer, &count);
  auto* positions = hb_buffer_get_glyph_positions(buffer, nullptr);
  hb_draw_funcs_t* draw = hb_draw_funcs_create();
  hb_draw_funcs_set_move_to_func(draw, Move, nullptr, nullptr);
  hb_draw_funcs_set_line_to_func(draw, Line, nullptr, nullptr);
  hb_draw_funcs_set_quadratic_to_func(draw, Quadratic, nullptr, nullptr);
  hb_draw_funcs_set_cubic_to_func(draw, Cubic, nullptr, nullptr);
  hb_draw_funcs_set_close_path_func(draw, Close, nullptr, nullptr);
  hb_draw_funcs_make_immutable(draw);
  const float scale = aSize / hb_face_get_upem(hb_font_get_face(font));
  hb_font_extents_t extents{};
  bool ok = hb_buffer_allocation_successful(buffer) &&
            hb_font_get_h_extents(font, &extents);
  Outline outline{aRun, scale};
  double advance = 0;
  size_t imageBytes = 0;
  for (unsigned i = 0; ok && i < count; ++i) {
    outline.x = static_cast<float>(advance + positions[i].x_offset * scale);
    outline.y = -positions[i].y_offset * scale;
    const hb_codepoint_t glyph = infos[i].codepoint;
    hb_blob_t* png = hb_ot_color_glyph_reference_png(font, glyph);
    unsigned pngLength = 0;
    const char* pngBytes = hb_blob_get_data(png, &pngLength);
    if (pngLength > 16 * 1024 * 1024 ||
        imageBytes + pngLength > 32 * 1024 * 1024) {
      hb_blob_destroy(png);
      ok = false;
      break;
    }
    if (glyph && pngLength) {
      imageBytes += pngLength;
      hb_glyph_extents_t bounds{};
      ok = hb_font_get_glyph_extents(font, glyph, &bounds);
      if (ok) {
        Image image;
        image.png.assign(pngBytes, pngBytes + pngLength);
        image.x = outline.x + bounds.x_bearing * scale;
        image.y = outline.y - bounds.y_bearing * scale;
        image.width = bounds.width * scale;
        image.height = -bounds.height * scale;
        image.commandOffset = aRun.commands.size();
        ok = image.width > 0 && image.height > 0;
        if (ok) aRun.images.push_back(std::move(image));
      }
    } else {
      ok = glyph && hb_font_draw_glyph_or_fail(font, glyph, draw, &outline);
    }
    hb_blob_destroy(png);
    ok = ok && !outline.exhausted;
    advance += positions[i].x_advance * scale;
    if (i + 1 == count || infos[i].cluster != infos[i + 1].cluster) {
      advance += aOptions.letterSpacing;
      if (infos[i].cluster < aLength && aText[infos[i].cluster] == u' ')
        advance += aOptions.wordSpacing;
    }
  }
  hb_draw_funcs_destroy(draw);
  hb_buffer_destroy(buffer);
  hb_font_destroy(font);
  if (!ok) {
    aRun = Run{};
    return false;
  }
  aRun.advance = advance;
  aRun.ascent = extents.ascender * scale;
  aRun.descent = -extents.descender * scale;
  return true;
}
}  // namespace mozilla::dom
