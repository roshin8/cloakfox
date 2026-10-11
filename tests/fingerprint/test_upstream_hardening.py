"""Behavioral checks of the actual patched native snippets and SessionStore method.
Run after applying the patch stack; runtime coverage is in probe_upstream_hardening.py.
"""
from pathlib import Path
import re
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = Path(os.environ.get("CLOAKFOX_TEST_SOURCE_ROOT", ROOT / "firefox-src"))


def block(source, marker):
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def cpp(code):
    compiler = shutil.which("clang++") or shutil.which("g++")
    if not compiler:
        raise RuntimeError("C++ compiler required")
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "test.cpp"
        source.write_text("#include <initializer_list>\n" + code.replace("CLOAKFOX_JSON_HEADER", str(ROOT / "additions/cloakcfg/json.hpp")))
        binary = Path(tmp) / "test"
        subprocess.run([compiler, "-std=c++17", str(source), "-o", str(binary)], check=True)
        result = subprocess.run([str(binary)], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)


class UpstreamHardening(unittest.TestCase):
    def test_glyph_noise_preserves_shaping_offsets_in_both_directions(self):
        source = (SRC / "gfx/thebes/gfxHarfBuzzShaper.cpp").read_text()
        body = block(source[source.index("hb_shape(mHBFont"):], "if (seed != 0)")
        cpp(r"""
#include <cassert>
#include <cstdint>
using hb_position_t = int;
struct hb_glyph_position_t { int x_advance, y_advance, x_offset, y_offset; };
hb_glyph_position_t positions[3];
void* mBuffer = nullptr;
hb_glyph_position_t* hb_buffer_get_glyph_positions(void*, uint32_t* count) {
  *count = 3; return positions;
}
int FloatToFixed(float f) { return int(f * 65536); }
void perturb(uint32_t seed, bool aVertical) {
""" + body + r"""
}
int main() {
  for (bool vertical : {false, true}) {
    for (uint32_t seed : {0u, 12345u, 98765u}) {
      for (auto& p : positions) p = {100, -100, 17, -31};
      perturb(seed, vertical);
      for (auto p : positions) {
        assert(p.x_offset == 17 && p.y_offset == -31);
        if (seed) assert(vertical ? p.y_advance < -100 : p.x_advance > 100);
        else assert(p.x_advance == 100 && p.y_advance == -100);
      }
    }
  }
}
""".replace("#include <cassert>", "#include <cassert>\n#include <initializer_list>"))

    def test_configured_voices_never_register_native_backend(self):
        source = (SRC / "dom/media/webspeech/synth/nsSynthVoiceRegistry.cpp").read_text()
        condition = re.search(r'if \((MaskConfig::GetBool\("voices:blockIfNotDefined"\).*?)\)\s*(?:\{\s*)?return NS_OK;', source, re.S).group(1)
        cpp(r"""
#include <cassert>
#include <optional>
#include <string>
namespace MaskConfig {
std::optional<bool> flag;
bool configured;
std::optional<bool> GetBool(const char*) { return flag; }
std::optional<int> MVoices() { return configured ? std::optional<int>(0) : std::nullopt; }
struct Config { bool contains(const char*) { return configured; } };
Config GetJson() { return {}; }
}
bool blocked() { if (""" + condition + r""") return true; return false; }
int main() {
  for (auto flag : {std::optional<bool>(), std::optional<bool>(false), std::optional<bool>(true)}) {
    for (bool configured : {false, true}) {
      MaskConfig::flag = flag; MaskConfig::configured = configured;
      assert(blocked() == (configured || flag.value_or(false)));
    }
  }
}
""")

    def test_font_filter_uses_owner_container_and_exempts_chrome(self):
        source = (SRC / "gfx/thebes/gfxPlatformFontList.cpp").read_text()
        applies = block(source, "bool gfxPlatformFontList::MaskedFontListAppliesTo")
        blocks = block(source, "bool gfxPlatformFontList::MaskedFontListBlocks")
        cpp(r"""
#include <cassert>
#include <cstdint>
#include <optional>
#include <string>
#include <algorithm>
#include <vector>
#include "CLOAKFOX_JSON_HEADER"
namespace MaskConfig {
 nlohmann::json config;
 const auto& GetJson() { return config; }
}
struct nsACString : std::string {
  using std::string::string;
  bool EqualsASCII(const char* s) const { return *this == s; }
  bool Equals(const nsACString& s) const { return *this == s; }
};
using nsAutoCString = nsACString;
void ToLowerCase(nsACString& s) { std::transform(s.begin(), s.end(), s.begin(), ::tolower); }
namespace StaticPrefs { bool enabled = true; bool cloakfox_enabled() { return enabled; } }
struct FontVisibilityProvider {
  bool chrome = false;
  std::optional<uint64_t> identity;
  bool IsChrome() { return chrome; }
  auto GetCloakfoxFontIdentity() { return identity; }
};
namespace mozilla::dom {
struct FontListManager {
  static uint32_t GetCurrentContext() { return 0; }
  static bool HasFontList(uint32_t id) { return id < 3; }
  static bool IsFontAllowed(uint32_t id, const nsACString& name) {
    return name == (id == 2 ? "helvetica" : "arial");
  }
};
}
struct gfxPlatformFontList {
  static bool MaskedFontListAppliesTo(FontVisibilityProvider*);
  static bool MaskedFontListBlocks(FontVisibilityProvider*, const nsACString&);
};
""" + applies + "\n" + blocks + r"""
int main() {
  FontVisibilityProvider page{false, uint64_t(2) << 32};
  assert(!gfxPlatformFontList::MaskedFontListBlocks(&page, "Helvetica"));
  assert(gfxPlatformFontList::MaskedFontListBlocks(&page, "Arial"));
  page.identity = uint64_t(1) << 32;
  assert(gfxPlatformFontList::MaskedFontListBlocks(&page, "Helvetica"));
  assert(!gfxPlatformFontList::MaskedFontListBlocks(&page, "Arial"));
  page.identity = uint64_t(7) << 32;
  assert(!gfxPlatformFontList::MaskedFontListBlocks(&page, "Arial"));
  assert(gfxPlatformFontList::MaskedFontListBlocks(&page, "Secret Host Font"));
  MaskConfig::config = {{"fonts", nlohmann::json::array({"Avenir", 123})}};
  assert(!gfxPlatformFontList::MaskedFontListBlocks(&page, "Avenir"));
  assert(gfxPlatformFontList::MaskedFontListBlocks(&page, "Arial"));
  page.chrome = true;
  assert(!gfxPlatformFontList::MaskedFontListBlocks(&page, "Secret Host Font"));
  assert(!gfxPlatformFontList::MaskedFontListBlocks(nullptr, "Secret Host Font"));
  page.chrome = false; StaticPrefs::enabled = false;
  assert(!gfxPlatformFontList::MaskedFontListBlocks(&page, "Secret Host Font"));
}
""")

    def test_generic_and_emoji_results_are_owned_by_the_requesting_provider(self):
        source = (SRC / "gfx/thebes/gfxPlatformFontList.cpp").read_text()
        method = block(source, "gfxPlatformFontList::GetPrefFontsLangGroupLocked(")
        # Accept the old pointer API to prove this fails against the pre-fix
        # source too; assertions exercise cache behavior, not the return syntax.
        old = bool(re.search(r'PrefFontList\*\s+gfxPlatformFontList::GetPrefFontsLangGroupLocked', source))
        result_type = 'PrefFontList*' if old else 'PrefFontList'
        cpp(r"""
#include <cassert>
#include <vector>
#include <memory>
#define MOZ_UNLIKELY(x) (x)
enum class StyleGenericFontFamily { None, SystemUi, MozEmoji };
using eFontPrefLang = int;
const int eFontPrefLang_Emoji = 1;
struct FontVisibilityProvider { bool masked; int owner; };
struct gfxPlatformFontList {
 struct PrefFontList : std::vector<int> { PrefFontList Clone() const { return *this; } };
 std::unique_ptr<PrefFontList> mEmojiPrefFont;
 std::unique_ptr<PrefFontList> mLangGroupPrefFonts[2][3];
 bool MaskedFontListAppliesTo(FontVisibilityProvider* p) { return p->masked; }
 void ResolveEmojiFontNames(FontVisibilityProvider* p, PrefFontList* out) { out->push_back(p->owner); }
 void ResolveGenericFontNames(FontVisibilityProvider* p, StyleGenericFontFamily, int, PrefFontList* out) {
   out->push_back(p->owner);
 }
 """ + result_type + r""" GetPrefFontsLangGroupLocked(FontVisibilityProvider*, StyleGenericFontFamily, int);
};
int first(const gfxPlatformFontList::PrefFontList& list) { return list.at(0); }
int first(const gfxPlatformFontList::PrefFontList* list) { return list->at(0); }
""" + 'gfxPlatformFontList::' + result_type + '\n' + method + r"""
int main() {
 gfxPlatformFontList list;
 FontVisibilityProvider chrome{false,99}, one{true,1}, two{true,2};
 for (auto generic : {StyleGenericFontFamily::SystemUi, StyleGenericFontFamily::MozEmoji}) {
   one.owner = 1;
   assert(first(list.GetPrefFontsLangGroupLocked(&chrome,generic,0)) == 99);
   auto a = list.GetPrefFontsLangGroupLocked(&one,generic,0);
   auto b = list.GetPrefFontsLangGroupLocked(&two,generic,0);
   assert(first(a) == 1 && first(b) == 2);
   assert(first(list.GetPrefFontsLangGroupLocked(&chrome,generic,0)) == 99);
   one.owner = 3;
   assert(first(list.GetPrefFontsLangGroupLocked(&one,generic,0)) == 3);
   assert(first(a) == 1);
 }
}
""")

    def test_sessionstore_ignores_untracked_windows_and_marks_tracked_ones(self):
        source = (SRC / "browser/components/sessionstore/SessionStore.sys.mjs").read_text()
        method = block(source[source.rindex("  maybeDontRestoreTabs(aWindow)"):], "maybeDontRestoreTabs(aWindow)")
        result = subprocess.run(["node", "--input-type=module", "-e", """
import assert from 'node:assert/strict';
class Store {
  #windows = {tracked: {}};
  get tracked() { return this.#windows.tracked; }
  """ + method + """
}
const store = new Store();
store.maybeDontRestoreTabs({});
store.maybeDontRestoreTabs({__SSi: 'gone'});
store.maybeDontRestoreTabs({__SSi: 'tracked'});
assert.equal(store.tracked._maybeDontRestoreTabs, true);
"""], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
