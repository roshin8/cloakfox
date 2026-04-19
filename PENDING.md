# Cloakfox — pending work

Living tracker of what's outstanding after the test-suite pass that landed on
`unified-maskconfig` 2026-04-19. Ordered by priority. Keep this file under
revision control so we don't lose context between sessions.

## P0 — blocks release / blocks real-site validation

### WebIDL setters don't actually persist prefs

**Symptom:** `window.setHttp2Profile("chrome")` self-destructs (proving the
method ran) but the `network.http.http2.fingerprint_profile` pref stays at
its default. Same for `setHttp3Profile`. The extension's
`content/index.ts` calls both setters from `globalSettings.http2Profile`
— it's a no-op today.

**Cause:** The C++ handler calls `Preferences::SetCString` /
`Preferences::SetUint` from content-process scope. In e10s Firefox the
parent owns the prefs DB; content-side writes don't IPC up to the parent
automatically, so they don't persist or propagate to the other content
processes that establish H2/H3 connections.

**Working path today:** `about:config` or profile `prefs.js` (set at
browser start via `opts.set_preference` in tests) — these write through
the parent. CLI-style pref override works. UI toggle does not.

**Fix path:** Expose a WebExtensions Experiment API in the
`cloakfox-shield` system addon that the background script calls. The
background runs with privileged-extension scope and can write through
`Services.prefs.setCharPref` (goes through parent). Scope: new
`experiment_apis` manifest entry + `schema.json` + `api.js` + plumbing
so the popup/options pages call `browser.cloakfoxPrefs.setProfile(...)`
instead of the (broken) WebIDL setter.

**Files touched:** `additions/browser/extensions/cloakfox-shield/manifest.json`,
new `additions/browser/extensions/cloakfox-shield/src/experiment_apis/`,
`additions/browser/extensions/cloakfox-shield/src/content/index.ts` (remove
the broken setHttp2Profile/setHttp3Profile calls), `settings/cloakfox.cfg`
(unchanged — defaultPref is still correct).

### Cold-start Sec-CH-UA race

**Symptom:** First navigation in a session doesn't emit `Sec-CH-UA`,
`Sec-CH-UA-Mobile`, `Sec-CH-UA-Platform` headers. Second navigation
onward, they fire correctly. Verified live.

**Cause:** The `webRequest` header-spoofer in `background/header-spoofer.ts`
reads `browser.storage.local[activeProfile:${tabId}]` to get the brands.
That entry is populated only after the inject script runs, post-messages
to content script, which forwards to background. On the FIRST navigation
the storage key doesn't exist yet when `onBeforeSendHeaders` fires.

**Fix path:** Have `background/index.ts` pre-assign a profile to the
default container at startup (synchronously) and write it to
`activeProfile:<tabId>` for any newly-opened tab before the first request
fires. Or: move the brands source to `settings.profile.brands` on the
container settings, so the header-spoofer doesn't depend on the activeTab
round-trip for request 0.

**Files touched:** `additions/browser/extensions/cloakfox-shield/src/background/index.ts`,
`additions/browser/extensions/cloakfox-shield/src/background/header-spoofer.ts`,
`additions/browser/extensions/cloakfox-shield/src/types/settings.ts`.

### Real-site validation with a post-all-fixes DMG

Once CI `24637464609` (or its successor) goes green on both Linux + macOS:

- Run `python tests/fingerprint/antibot_battery.py` against the new DMG,
  review the markdown + screenshots.
- Manual check that the extension popup UI actually works end-to-end —
  pick a container, toggle protection level, verify the per-container
  fingerprint changes on a refresh at `browserleaks.com`. This was never
  tested before the `jar.mn` fix because the extension wasn't loading.
- Hit 2-3 real anti-bot sites (Cloudflare challenge page, Akamai-protected
  site, PerimeterX) with `chrome` profile active, confirm they don't
  immediately challenge.

## P1 — test coverage gaps

### Cross-container uniqueness (not just cross-domain)

`test_math_constants.py::test_math_pi_differs_across_domains` covers
per-domain seeding. It does NOT cover per-container: that requires the
inject script to receive a real container-scoped seed from the background,
which in turn requires the tab to be routed through a specific container
via the Multi-Account Containers API.

**Fix path:** Either add a test-mode pref (e.g.
`cloakfox.test.force_container_seed`) that injects a specific seed via the
inject path for testing, OR use privileged Marionette to create a
container and open a URL in it, then read Math.PI.

### CreepJS trust score extraction

`antibot_battery.py` captures CreepJS screenshots fine, but emits
`trust: ?` — the selectors `.unblurred-trust-score, .trust-score` don't
match CreepJS's shadow-DOM-rendered output.

**Fix path:** Use `document.querySelectorAll` inside a `<script>` tag
appended to the page so it runs in page world (same pattern as
`test_math_constants.py`), and walk the shadow roots with
`element.shadowRoot.querySelector` to reach the score elements.

### `areyouheadless` timeouts

`antibot_battery.py` hits a 60s navigation timeout on
`arh.antoinevastel.com/bots/areyouheadless` during smoke runs. May be
site flakiness; may be the site blocking selenium-driven Firefox.

**Fix path:** Bump timeout to 90s AND/OR detect the headless-test verdict
via the `verdict_extractor` rather than waiting for full page load AND/OR
drop the site from the default battery if it's consistently flaky.

### Keyboard cadence spoofing

No integration test exists for `inject/spoofers/keyboard/cadence.ts`. The
spoofer adds jitter to `KeyboardEvent.timeStamp`. Worth a test that
synthesizes keyboard events via Marionette and asserts the timestamps
diverge from the monotonic clock.

### WebRTC SDP fingerprint

C++ patches cover WebRTC IP leak (mDNS suppression) but not SDP-level
fingerprint (media line order, fingerprint algorithm list). Worth
profiling what real Chrome/Firefox/Safari emit and spoofing it. Not yet
attempted.

## P2 — housekeeping

### `CLAUDE.md` refresh

The top-level `CLAUDE.md` still describes the pre-test architecture. It
doesn't mention:
- The `tests/fingerprint/` harness + selenium+geckodriver choice
- The 7 gotchas documented in `tests/fingerprint/README.md`
- The `defaultPref()` contract for cloakfox.cfg
- The `jar.mn` dest-path rule

Should be a short pointer block — the detailed docs live in
`tests/fingerprint/README.md`.

### Memory refresh

Session memory didn't capture the 7 bugs as anti-regression markers.
Worth writing to:
- `feedback_testing.md` — "Cloakfox extension tests need selenium+geckodriver,
  NOT Playwright (no Juggler patch)"
- `feedback_build.md` — "AutoConfig cloakfox.cfg must use defaultPref() for
  toggleable prefs; pref() clobbers on every startup"
- `architecture.md` — "Content-process WebIDL setters can't persist
  Preferences — use Experiment API from background"

### Stale Playwright commit

`8de1f2c1aa — Fingerprint test harness: Playwright + mitmproxy` is
superseded by `1d6bbec843` which rewrote to Selenium. The Playwright
test file was replaced but the commit message still mentions Playwright.
Harmless but confusing when grepping history.

## Out of scope (not pending — deliberately deferred)

- **TLS JA3/JA4 spoofing.** Requires NSS patches. Weeks of work, separate
  project scope.
- **HTTP/3 wire-level SETTINGS frame observation.** Would need
  mitmproxy-quic or wireshark integration in the test harness. The pref
  plumbing is verified; the SETTINGS emission is covered by the Rust
  unit tests in neqo-http3 that shipped with the patch.
- **HTTP/3 profile UI toggle per-container.** Same underlying problem as
  the P0 WebIDL-setter-doesn't-persist issue — the extension toggle
  needs the Experiment API path to actually work.

## How to update this file

- Move items to the completed section (or delete) as they land.
- Keep each bullet self-contained: symptom, cause, fix path, files
  touched. Future-you won't have the context you have today.
- If an item spawns subtasks, nest them in place rather than creating
  a separate file.
