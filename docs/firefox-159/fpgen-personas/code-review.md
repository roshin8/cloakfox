# Independent fpgen implementation review

Reviewed on 2026-10-28 against baseline `c80a898c21`, with the implementation uncommitted in the Firefox159 worktree. This review covered Task 1 model/importer/sampler and Task 2 routing, source persistence, backup/template schemas, settings UI and module packaging. Concurrent Inspector and container-isolation feature changes were excluded except for the shared generation test harness and the current Inspector confirmation dependency required by settings.js. No build, installed application, personal profile or Chromium process was modified.

## Corrected finding

**Resolved P2 — Automatic browser versions must follow the selected family.** In `CloakfoxPersonas.sys.mjs` lines 721–723, the new fpgen route passes both `auto` and `random-recent` through the Firefox build major regardless of `generation.browser`. The new template editor exposes browser selection with the default `auto`, so selecting Safari generates `Version/159.0 Safari/605.1.15`; a fixed seed with `random-recent` generates `Version/157.0`. The existing browser settings advertise Safari 26. Explicit `version: "26"` produces the correct major. The correction resolves fpgen non-Firefox `auto` and `random-recent` from the sampled family's observed major. Explicit versions remain unchanged, Firefox retains the build/recent behavior, and legacy BrowserForge retains its previous output and PRNG order. The added real-model regression covers all four supported browser families, automatic/recent/explicit versions, multiple seeds, and matching navigator/header/appVersion output.

Reproduction uses the real mapper and sampler:

```js
fillPersonaKeys(seed, 7, {
  source: "fpgen", browser: "safari", os: "macos", version: "auto"
})["navigator.userAgent"]
// Before correction: ... Version/159.0 Safari/605.1.15
```

## Verified properties

- Missing source preserves BrowserForge routing and the existing PRNG consumption/output hashes; new unseeded identities prefer fpgen.
- Sampler conditions on browser/platform/GPU and complete descendant probability mass, rejects unsupported combinations without provider fallback, and retains no container sample/seed cache.
- Exhaustive supported-owner adapter checks covered 85 user-agent, 919 CPU, 1,385 screen/window and 504 GPU branch cases without adapter rejection.
- Adapter returns detached allowlisted UA, CPU, geometry and GPU label fields. Captured permissions, media identifiers, location, TLS and other unsupported observations do not flow into executable policy.
- Native privacy/admission paths remain in the existing mapper/override pipeline. Model labels do not grant executable GPU support.
- Backup v3 and template v2 persist source/filters; older formats restore BrowserForge semantics. New initialization failures are cleaned up by existing workflow rollback. Version-1 template envelopes reject version-2 entries.
- Settings refresh displays an explicitly saved provider for each owner and defaults to fpgen only when that preference is absent; the current-identity badge retains BrowserForge semantics for legacy missing-source identities.
- The current Inspector confirmation integration compares configurations without measurements, repairs or preference writes. Its module must ship with the current settings.js.
- Unsupported settings generation fails before config publication and restores the container preference snapshot.
- Complete pinned archive, license and provenance are declared for packaging; the new sampler/network module imports match their installed resource locations.

## Checks run

- Focused Node tests after correction: 81 passed, 0 failed (`test_fpgen_sampler`, `test_fpgen_routing`, `test_container_workflows`, `test_templates`, `test_persona_version`, `test_settings_consistency`).
- Inspector/shared settings integration checks: 28 passed, 0 failed.
- Python importer tests: 3 passed.
- `generate-fpgen-network.py ... --check`: all four artifacts reproduced byte-for-byte.
- Scoped `git diff --check`: passed.
- Additional exhaustive adapter checks described above: passed.

Firefox159 packaging and headless website-facing/restart acceptance were run by the coordinating agent and subsequently reviewed as recorded below. No unresolved actionable findings remain in the reviewed implementation or acceptance assertions. Approved for the reviewed scope.


## Firefox159 runtime acceptance review

Reviewed `probe_fpgen_personas.py`, `stage-app.py`, the staged-resource manifest and the final green `runtime/validation.json`. The report records Firefox `159.0-beta.1`, 59 passing checks and XUL SHA-256 `4e747b52fe248fd6e50ed4b618a233352109ee2a86d774b3404d5cda86f6d792`. All 13 staged resource hashes match both current source files and acceptance-app destinations. The manifest transparently identifies the concurrent Inspector module as the current settings UI's confirmation dependency. The staging script verifies six native/backend files against the owned baseline app and writes only into the owned acceptance app.

The probe uses a disposable profile, local fixture servers, real source/filter controls, explicit document/worker readings, server-observed HTTP User-Agent and restart snapshots. It waits for an expando reload marker to disappear before accepting post-refresh readings, preventing reuse of the old document under `page_load_strategy='none'`. Native letterboxing remains enabled; screen/available/viewport consistency is checked under that policy rather than disabling privacy protections to match persona screen data. The non-letterboxed code branch is not claimed exercised by this report. Session timing keys are appropriately excluded from identity equality because they intentionally vary each launch.

Two acceptance-assertion gaps were corrected and re-reviewed: the probe now opens a fixture website while the BrowserForge identity is active and compares native window/worker UA, platform and cores plus server-observed HTTP User-Agent; restart snapshots retain the native profile bit and exhaustion sentinel while normalizing only the changing generation portion of `network_state`. The final run passes all 59 checks with both providers exercised. These were test-coverage gaps, not observed production failures.

The regression manifest records seven additional headless probes with exit code zero: host personas, persona generation, templates, container rendering settings, identity/network gaps, container fonts and WebGL readback. Runtime acceptance is approved for the assertions exercised; these results do not claim exhaustive permission decisions, every browser-family/OS/GPU combination, or the disabled-letterboxing branch. Those scope limits do not weaken the checked default privacy policy or the independently reviewed strict sampler behavior.
