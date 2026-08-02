# Bundled Fonts — Phase 0 (macOS feasibility spike) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or subagent-driven-development to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Prove on the real macOS build that Cloakfox can (a) register a bundled font so it enumerates as its own family and (b) suppress the real host font families — the go/no-go gate for the full-replacement design.

**Architecture:** Inject at `CoreTextFontList::InitFontListForPlatform()` (the macOS/CoreText enumeration entry). Before the host-family loop, register a bundled font directory via `CTFontManagerRegisterFontsForURL`. Gate host-family suppression behind a spike pref so we can A/B it in one binary. Verify with a selenium probe that lists enumerable families.

**Tech Stack:** C++/Objective-C++ (Gecko gfx/thebes, CoreText), selenium+geckodriver probes, `make relink` incremental builds.

## Global Constraints

- `privacy.resistFingerprinting` MUST stay false; `privacy.userContext.enabled` MUST stay true.
- Dev build is non-packaged: rebuild changed C++ with `make relink` (mach build binaries + copy XUL into the .app). No full `./mach build` needed for one-file changes.
- Spike code is gated behind `cloakfox.fonts.bundle_spike` (bool, default false) so the default binary is unchanged; the pref is spike-only and removed in Phase 1.
- Fallback discipline: any registration/suppression failure must leave normal enumeration intact (never an empty font list).
- Font file for the spike is any distinctive non-system font already in-tree; NO Camoufox pack / network needed at this phase.

---

### Task 1: Spike probe — enumerate visible font families

**Files:**
- Create: `tests/fingerprint/probe_font_spike.py`

**Interfaces:**
- Produces: a probe that prints the set of families the page can detect from a
  fixed panel, plus booleans for a chosen bundled family and a chosen host
  family. Consumed manually (go/no-go), not by later tasks.

- [ ] **Step 1: Write the probe**

```python
"""Phase-0 spike probe: which font families are enumerable?

Detects, from a fixed panel, (a) a bundled test family that is NOT normally a
macOS system font ("Charis SIL Compact") and (b) a real host family ("Geneva").
Run against the built binary with the spike pref off, then on.

    CLOAKFOX_BIN=.../cloakfox CLOAKFOX_SPIKE=0|1 \
        python tests/fingerprint/probe_font_spike.py
"""
import os, json, time, tempfile
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

BUNDLED = "Charis SIL Compact"   # in-tree test font we will register
HOST = "Geneva"                  # a real macOS system family (should vanish when suppressed)
PANEL = [BUNDLED, HOST, "Arial", "Helvetica", "Menlo", "Times New Roman"]

PROBE = """
const P = arguments[0];
function present(f){
  const b=['monospace','sans-serif','serif'];
  const s=document.createElement('span');
  s.style.cssText='position:absolute;left:-9999px;font-size:72px';
  s.textContent='mmmwwwiiilQ'; document.body.appendChild(s);
  let d=false;
  for(const g of b){ s.style.fontFamily=g; const w=s.offsetWidth,h=s.offsetHeight;
    s.style.fontFamily='"'+f+'",'+g;
    if(s.offsetWidth!==w||s.offsetHeight!==h){d=true;break;} }
  document.body.removeChild(s); return d;
}
return JSON.stringify(P.filter(present));
"""

def main():
    spike = os.environ.get("CLOAKFOX_SPIKE","0") == "1"
    with tempfile.TemporaryDirectory() as t:
        p=os.path.join(t,"p"); Path(p).mkdir()
        Path(p,"user.js").write_text(
            'user_pref("cloakfox.enabled", true);\n'
            f'user_pref("cloakfox.fonts.bundle_spike", {"true" if spike else "false"});\n')
        o=Options(); o.binary_location=os.environ["CLOAKFOX_BIN"]
        o.add_argument("--headless"); o.add_argument("-remote-allow-system-access")
        o.add_argument("-profile"); o.add_argument(p)
        d=webdriver.Firefox(options=o, service=Service(log_path=str(Path(p)/"g.log")))
        try:
            d.set_page_load_timeout(30); d.get("https://example.com/"); time.sleep(1.5)
            found=set(json.loads(d.execute_script(PROBE, PANEL)))
        finally:
            d.quit()
    print(f"spike={'on' if spike else 'off'} present={sorted(found)}")
    print(f"  bundled '{BUNDLED}' present: {BUNDLED in found}")
    print(f"  host    '{HOST}' present:    {HOST in found}")

if __name__ == "__main__":
    if not os.environ.get("CLOAKFOX_BIN"): raise SystemExit("set CLOAKFOX_BIN")
    main()
```

- [ ] **Step 2: Run against the current binary (spike off) to capture the baseline**

Run: `CLOAKFOX_BIN=firefox-src/obj-*/dist/Cloakfox.app/Contents/MacOS/cloakfox CLOAKFOX_SPIKE=0 python tests/fingerprint/probe_font_spike.py`
Expected: `bundled 'Charis SIL Compact' present: False` (not a system font), `host 'Geneva' present: True`. This is the baseline the spike must change.

- [ ] **Step 3: Commit the probe**

```bash
git add tests/fingerprint/probe_font_spike.py
git commit -m "test(fonts): phase-0 spike probe for font enumeration"
```

---

### Task 2: Register a bundled font at CoreText init (spike-gated)

**Files:**
- Modify: `firefox-src/gfx/thebes/CoreTextFontList.cpp` (in `InitFontListForPlatform`, near line 1156)
- Create: `firefox-src/obj-*/dist/Cloakfox.app/Contents/Resources/fonts/CharisSILCompact-R.ttf` (copied in, via the build tree; Phase 1 replaces with the packaged pack)

**Interfaces:**
- Consumes: the spike pref `cloakfox.fonts.bundle_spike`.
- Produces: after this task, with the spike on, the bundled family enumerates
  (`present == True`) while host families are still present (suppression is Task 3).

- [ ] **Step 1: Stage the bundled font**

Copy an in-tree font into the app's fonts dir (spike location; Phase 1 uses the packaged `bundle/fonts/<os>/`):
```bash
APP=$(ls -d firefox-src/obj-*/dist/Cloakfox.app)
mkdir -p "$APP/Contents/Resources/fonts"
cp firefox-src/mobile/android/fonts/CharisSILCompact-R.ttf "$APP/Contents/Resources/fonts/"
```

- [ ] **Step 2: Register the fonts dir in `InitFontListForPlatform`**

At the top of `CoreTextFontList::InitFontListForPlatform()`, before the
`CTFontManagerCopyAvailableFontFamilyNames()` loop, add (guarded on the spike
pref, wrapped so any failure is non-fatal):

```cpp
// Cloakfox spike: register bundled fonts from <GRE>/fonts so they enumerate.
if (mozilla::Preferences::GetBool("cloakfox.fonts.bundle_spike", false)) {
  nsCOMPtr<nsIFile> fontsDir;
  if (NS_SUCCEEDED(NS_GetSpecialDirectory(NS_GRE_DIR, getter_AddRefs(fontsDir)))) {
    fontsDir->Append(u"fonts"_ns);
    nsAutoCString path;
    if (NS_SUCCEEDED(fontsDir->GetNativePath(path))) {
      CFURLRef url = ::CFURLCreateFromFileSystemRepresentation(
          kCFAllocatorDefault, (const UInt8*)path.get(), path.Length(), true);
      if (url) {
        ::CTFontManagerRegisterFontsForURL(
            url, kCTFontManagerScopeProcess, nullptr);
        ::CFRelease(url);
      }
    }
  }
}
```

(Verify includes: `nsDirectoryServiceDefs.h` for `NS_GRE_DIR`, `Preferences.h`,
and that CoreText is available — this file already uses CTFontManager APIs.)

- [ ] **Step 3: Rebuild**

Run: `make relink 2>&1 | tail -3`
Expected: `Your build was successful!` and `relink: deployed fresh XUL`.

- [ ] **Step 4: Re-stage font (relink may repackage) and run the probe (spike on)**

Run:
```bash
APP=$(ls -d firefox-src/obj-*/dist/Cloakfox.app); mkdir -p "$APP/Contents/Resources/fonts"
cp firefox-src/mobile/android/fonts/CharisSILCompact-R.ttf "$APP/Contents/Resources/fonts/"
CLOAKFOX_BIN="$APP/Contents/MacOS/cloakfox" CLOAKFOX_SPIKE=1 python tests/fingerprint/probe_font_spike.py
```
Expected: `bundled 'Charis SIL Compact' present: True` (registration works). Host still present (suppression is next task).

- [ ] **Step 5: Commit the C++ change**

```bash
git add firefox-src/gfx/thebes/CoreTextFontList.cpp   # NOTE: firefox-src is gitignored; instead sync into a patch — see Task 4
git commit -m "spike(fonts): register bundled fonts via CTFontManagerRegisterFontsForURL" || true
```
(If `firefox-src` is gitignored, skip the commit here; the change is captured as a patch in Task 4. Do NOT lose the edit.)

---

### Task 3: Suppress host font families (spike-gated)

**Files:**
- Modify: `firefox-src/gfx/thebes/CoreTextFontList.cpp` (`InitFontListForPlatform`, the `CTFontManagerCopyAvailableFontFamilyNames` → `AddFamily` loop, ~line 1180-1189)

**Interfaces:**
- Consumes: the spike pref + the registration from Task 2.
- Produces: with spike on, host families vanish and only bundled families remain.

- [ ] **Step 1: Skip host families when the spike is on, but keep bundled ones**

In the enumeration loop, when the spike pref is on, add only families whose font
files live under `<GRE>/fonts` (the bundled ones) and skip the rest. Simplest
spike form: track the set of family names registered from the bundle dir (from
Task 2, capture the families the registered fonts expose via
`CTFontManagerCreateFontDescriptorsFromURL`), and in the loop `continue` for any
family not in that set:

```cpp
// Cloakfox spike: with suppression on, only keep bundled families.
static nsTHashSet<nsCString> sBundledFamilies;   // filled in Task 2's block
...
for (each familyName from CTFontManagerCopyAvailableFontFamilyNames) {
  if (spikeOn && !sBundledFamilies.Contains(familyKey(familyName))) continue;
  AddFamily(familyName);
}
```

(In Task 2's block, after registering, call
`CTFontManagerCreateFontDescriptorsFromURL(url)` and record each descriptor's
`kCTFontFamilyNameAttribute` into `sBundledFamilies`, lowercased to match
`AddFamily` keying.)

- [ ] **Step 2: Rebuild**

Run: `make relink 2>&1 | tail -3`
Expected: build successful.

- [ ] **Step 3: Re-stage font + run the probe (spike on)**

Run the same command as Task 2 Step 4.
Expected: `bundled 'Charis SIL Compact' present: True`, `host 'Geneva' present: False`. Both conditions = the mechanism works.

- [ ] **Step 4: Regression — spike OFF is unchanged**

Run: `CLOAKFOX_BIN="$APP/Contents/MacOS/cloakfox" CLOAKFOX_SPIKE=0 python tests/fingerprint/probe_font_spike.py`
Expected: `bundled ... present: False`, `host 'Geneva' present: True` (default binary behavior intact).

---

### Task 4: Capture the spike as a patch + go/no-go writeup

**Files:**
- Create: `patches/cloakfox-font-bundle-spike.patch` (the `CoreTextFontList.cpp` diff; keep it OUT of `order.txt` — it is a spike, not shipped)
- Modify: `docs/superpowers/specs/2026-08-02-bundled-fonts-design.md` (append a "Phase 0 result" note)

**Interfaces:**
- Produces: a committed record of the mechanism + the go/no-go decision that
  gates whether Phases 1–4 proceed as designed.

- [ ] **Step 1: Extract the CoreTextFontList diff into a spike patch**

Diff the modified file against the pristine tarball copy (as done for other
patches) and save to `patches/cloakfox-font-bundle-spike.patch`. Do NOT add it
to `patches/order.txt` (spike-only).

- [ ] **Step 2: Append the result to the spec**

Add a short "## Phase 0 result (YYYY-MM-DD)" section: PASS/FAIL, the observed
probe output, and — if PASS — a green light to plan Phase 1; if FAIL, what broke
(registration vs suppression) and which alternative to reconsider (additive
model, or per-host-OS-only personas).

- [ ] **Step 3: Commit**

```bash
git add patches/cloakfox-font-bundle-spike.patch docs/superpowers/specs/2026-08-02-bundled-fonts-design.md
git commit -m "spike(fonts): macOS bundled-font register+suppress proof, phase-0 result"
```

---

## Self-Review

- **Spec coverage:** This plan covers only the spec's Phase 0 (macOS feasibility
  spike). Phases 1–4 are intentionally deferred to their own plans, gated on this
  spike's PASS. Registration (spec §Components 2 macOS) and host-suppression
  (spec §Model full-replacement) are both exercised.
- **Placeholders:** none — probe and C++ blocks are concrete. The suppression
  family-set capture (Task 3) is described with the exact CoreText API
  (`CTFontManagerCreateFontDescriptorsFromURL` + `kCTFontFamilyNameAttribute`).
- **Type/name consistency:** the spike pref `cloakfox.fonts.bundle_spike` and the
  bundled family `Charis SIL Compact` / host family `Geneva` are used identically
  across Tasks 1–4.
- **Known risk carried:** `firefox-src` is gitignored, so C++ edits are captured
  as a patch (Task 4), not a direct commit (noted in Task 2 Step 5).
