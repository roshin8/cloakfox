"""Exercise the production byte-based shaper and outline producer (no platform font API)."""
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'additions/dom/canvas/CanonicalCanvasText.cpp'

class CanonicalText(unittest.TestCase):
    def test_advances_outlines_and_protected_fallback(self):
        self.assertTrue(SOURCE.exists(), 'canonical text producer is missing')
        program = r'''
#include "CanonicalCanvasText.h"
#include "hb-ot.h"
#include <cassert>
#include <cmath>
#include <fstream>
#include <iterator>
using mozilla::dom::CanonicalCanvasText;
int main(int argc, char** argv) {
 std::ifstream stream(argv[1], std::ios::binary);
 std::vector<char> bytes((std::istreambuf_iterator<char>(stream)), {});
 CanonicalCanvasText font(bytes.data(), bytes.size());
 CanonicalCanvasText::Run a, av, space, empty, rejected;
 assert(font.Shape(u"A", 1, 10, a));
 // DejaVu Sans regular: hmtx A advance = 1401, unitsPerEm = 2048.
 assert(std::abs(a.advance - 6.8408203125) < 0.000001);
 assert(!a.commands.empty());
 assert(font.Shape(u"AV", 2, 10, av));
 assert(av.advance < 2 * a.advance); // kerning must affect both ink and metrics
 assert(font.Shape(u" ", 1, 10, space));
 assert(space.advance > 0 && space.commands.empty());
 assert(font.Shape(u"", 0, 10, empty));
 assert(empty.advance == 0 && empty.commands.empty());
 assert(font.Shape(u"\u05d0", 1, 10, rejected)); // Hebrew uses OpenType outlines
 assert(font.Shape(u"\U0001F600", 2, 10, rejected)); // bundled monochrome outline
 assert(font.Shape(u"a\u0301", 2, 10, rejected));
 assert(!font.Shape(u"A", 1, NAN, rejected));
 std::ifstream emojiStream(argv[2], std::ios::binary);
 std::vector<char> emojiBytes((std::istreambuf_iterator<char>(emojiStream)), {});
 CanonicalCanvasText emoji(emojiBytes.data(), emojiBytes.size());
 CanonicalCanvasText::Run emojiRun;
 assert(emoji.Shape(u"\U0001F600", 2, 32, emojiRun));
 assert(emojiRun.images.size() == 1 && emojiRun.commands.empty());
 assert(emojiRun.images[0].png.size() > 8);
 assert(emojiRun.images[0].png[0] == 0x89 && emojiRun.images[0].png[1] == 'P');
 assert(emojiRun.images[0].width > 0 && emojiRun.images[0].height > 0);
 assert(emojiRun.advance > 0 && emojiRun.ascent > 0);
 // ZWJ family sequence must be one shaped color glyph, not four people.
 assert(emoji.Shape(u"\U0001F468\u200d\U0001F469\u200d\U0001F467\u200d\U0001F466", 11, 32, emojiRun));
 assert(emojiRun.images.size() == 1);
 CanonicalCanvasText bad("bad", 3);
 assert(!bad.Shape(u"A", 1, 10, rejected));
 // If pixels and metrics diverge under size/metric scaling this must fail.
 CanonicalCanvasText::Run twice;
 assert(font.Shape(u"A", 1, 20, twice));
 assert(twice.advance == a.advance * 2 && twice.ascent == a.ascent * 2);
 assert(twice.commands.size() == a.commands.size());
 for (size_t i = 0; i < a.commands.size(); ++i)
  for (int j = 0; j < 6; ++j) assert(twice.commands[i].p[j] == a.commands[i].p[j] * 2);
 // The face constructor is the native sanitized FontFace integration seam.
 hb_blob_t* blob = hb_blob_create(bytes.data(), bytes.size(), HB_MEMORY_MODE_DUPLICATE, nullptr, nullptr);
 hb_face_t* face = hb_face_create(blob, 0);
 CanonicalCanvasText author(face);
 hb_face_destroy(face); hb_blob_destroy(blob);
 CanonicalCanvasText::Run custom;
 assert(author.Shape(u"AV", 2, 10, custom));
 assert(custom.advance == av.advance && custom.commands.size() == av.commands.size());
 hb_face_t* reused = author.ReferenceFace();
 assert(reused && hb_face_get_glyph_count(reused) > 0);
 hb_font_t* lookup=hb_font_create(reused);hb_ot_font_set_funcs(lookup);
 hb_codepoint_t glyphA=0;assert(hb_font_get_nominal_glyph(lookup,'A',&glyphA));
 CanonicalCanvasText::ShapeOptions direct;direct.glyphId=glyphA;
 CanonicalCanvasText::Run directRun;
 assert(author.Shape(u"",0,10,directRun,direct));
 assert(directRun.advance==a.advance&&directRun.commands.size()==a.commands.size());
 hb_font_destroy(lookup);hb_face_destroy(reused);
 CanonicalCanvasText::ShapeOptions options;
 options.direction = HB_DIRECTION_RTL;
 options.script = HB_SCRIPT_ARABIC;
 options.language = hb_language_from_string("ar", -1);
 CanonicalCanvasText::Run arabic;
 assert(author.Shape(u"\u0633\u0644\u0627\u0645", 4, 20, arabic, options));
 assert(arabic.advance > 0 && !arabic.commands.empty());
 // Unsupported glyphs fail atomically, leaving no partial paths/metrics.
 assert(!author.Shape(u"A\uFFFF", 2, 10, rejected));
 assert(rejected.advance == 0 && rejected.commands.empty());
 CanonicalCanvasText::ShapeOptions spaced;
 spaced.features.push_back({HB_TAG('k','e','r','n'), 0, 0, (unsigned)-1});
 spaced.letterSpacing = 3;
 spaced.wordSpacing = 7;
 CanonicalCanvasText::Run styled;
 assert(author.Shape(u"AV", 2, 10, styled, spaced));
 assert(std::abs(styled.advance - (2 * a.advance + 6)) < .000001);
 assert(author.Shape(u" ", 1, 10, styled, spaced));
 assert(std::abs(styled.advance - (space.advance + 10)) < .000001);
 std::ifstream variableStream(argv[3], std::ios::binary);
 std::vector<char> variableBytes((std::istreambuf_iterator<char>(variableStream)), {});
 CanonicalCanvasText variable(variableBytes.data(), variableBytes.size());
 CanonicalCanvasText::ShapeOptions thin, thick;
 thin.variations.push_back({HB_TAG('w','g','h','t'), 100});
 thick.variations.push_back({HB_TAG('w','g','h','t'), 900});
 CanonicalCanvasText::Run thinRun, thickRun;
 assert(variable.Shape(u"W", 1, 32, thinRun, thin));
 assert(variable.Shape(u"W", 1, 32, thickRun, thick));
 assert(thinRun.advance != thickRun.advance);
 // Introduce a nonempty COLR table without changing the actual outline tables.
 auto colorBytes = bytes;
 assert(colorBytes.size() > 28);
 colorBytes[12]='C';colorBytes[13]='O';colorBytes[14]='L';colorBytes[15]='R';
 CanonicalCanvasText color(colorBytes.data(), colorBytes.size());
 assert(!color.Shape(u"A", 1, 10, rejected));
 CanonicalCanvasText::Run repeat;
 assert(font.Shape(u"AV", 2, 10, repeat));
 assert(repeat.advance == av.advance && repeat.commands.size() == av.commands.size());
 for (size_t i = 0; i < av.commands.size(); ++i) {
  assert(repeat.commands[i].kind == av.commands[i].kind);
  for (int j = 0; j < 6; ++j) assert(repeat.commands[i].p[j] == av.commands[i].p[j]);
 }
}
'''
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / 'test.cpp'
            source.write_text(program)
            flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'harfbuzz'], text=True))
            exe = Path(d) / 'test'
            subprocess.run(['c++', '-std=c++17', '-I', str(SOURCE.parent), '-I', str(ROOT / 'firefox-src/gfx/harfbuzz/src'), str(source), str(SOURCE), '-o', str(exe), *flags], check=True)
            subprocess.run([str(exe), str(ROOT / 'bundle/fonts/macos/DejaVuSans.ttf'), str(ROOT / 'bundle/fonts/macos/NotoColorEmoji.ttf'), str(ROOT / 'bundle/fonts/macos/NotoSans.ttf')], check=True)

if __name__ == '__main__':
    unittest.main()
