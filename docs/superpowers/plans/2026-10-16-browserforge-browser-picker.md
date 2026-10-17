# BrowserForge Browser Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Chameleon-style browser/version/OS/hardware identity picker that constrains BrowserForge and refuses unsupported engine combinations.

**Architecture:** A focused browser-profile catalog owns families, recent versions, confidence, and engine requirements. BrowserForge accepts an optional UA/version constraint and samples dependent fields from that root. The settings UI renders the catalog and applies a selected profile through the existing atomic identity path; backend capability gates prevent Chrome/Edge identities on Gecko.

**Tech Stack:** Firefox privileged ES modules, BrowserForge Bayesian network, about:cloakfox HTML/CSS/JavaScript, Node `node:test`, Selenium browser probes.

**Spec:** `docs/superpowers/specs/2026-10-16-browserforge-browser-picker-design.md`

## Global Constraints

- Firefox, Chrome, Edge, Chromium, Custom, and unavailable Safari are the visible families.
- Offer current through current-minus-three majors plus a weighted random-recent choice.
- Never apply Chrome/Edge/Chromium identity to Gecko or Safari without WebKit.
- Preserve cookies and site data; reload/recreate existing page and worker contexts after a successful application.
- Raw UA remains an Advanced override.
- Use existing graphite/teal tokens and system light/dark themes.

## Review Focus

- A stale saved browser/version value must fall back without changing the live identity.
- A browser family whose engine disappears between selection and apply must fail atomically.
- An OS/hardware combination with no BrowserForge mass must explain the mismatch and disable apply.
- Previous-version selection must update UA, HTTP UA, and `appVersion` together.
- Keyboard and small-window users must reach every browser choice, control, status, and action.

---

### Task 1: Browser profile catalog and BrowserForge constraints

**Files:**
- Create: `additions/browser/components/cloakfox/CloakfoxBrowserProfiles.sys.mjs`
- Modify: `additions/browser/components/cloakfox/CloakfoxBayesianNetwork.sys.mjs`
- Modify: `additions/browser/components/cloakfox/CloakfoxPersonas.sys.mjs`
- Modify: `additions/browser/components/cloakfox/moz.build`
- Test: `tests/fingerprint/test_browser_profile_catalog.mjs`

**Interfaces:**
- Produces: `listBrowserFamilies(capabilities, engineVersions)`, `listBrowserVersions(family, engineVersions)`, `normalizeBrowserSelection(value, capabilities, engineVersions)`, and BrowserForge constraints `{browser, version, os, hardware}`.
- Produces: `samplePersonaFingerprint(prng, constraints)` with optional browser/version fields.

- [ ] Write failing catalog tests for visible families, current-minus-three versions, confidence labels, disabled Safari, and unavailable Chromium families.
- [ ] Run `node --test tests/fingerprint/test_browser_profile_catalog.mjs` and verify failure.
- [ ] Implement the catalog and selection normalization without reading UI state.
- [ ] Extend BrowserForge choice filtering to parse browser family and major version from candidate UAs; reject a constraint with no matching probability mass.
- [ ] Derive the three UA fields atomically in `fillPersonaKeys`; retain the running-version normalization for automatic Firefox selection.
- [ ] Run the catalog test and existing persona/BrowserForge tests.

### Task 2: Chameleon-style settings controls

**Files:**
- Modify: `additions/browser/components/cloakfox/content/settings.html`
- Modify: `additions/browser/components/cloakfox/content/settings.css`
- Modify: `additions/browser/components/cloakfox/content/settings.js`
- Test: `tests/fingerprint/test_browser_picker_ui.mjs`

**Interfaces:**
- Consumes: Task 1 catalog and constraints.
- Produces: saved prefs `persona_browser`, `persona_version`, `persona_os`, and `persona_hardware` under `cloakfox.container.<ucid>.`.

- [ ] Write failing DOM/source tests for browser tiles, linked selects, profile preview, confidence message, advanced raw-UA placement, and accessible disabled reasons.
- [ ] Run the UI test and verify failure.
- [ ] Replace the current OS-first BrowserForge controls with browser-family tiles and linked version/OS/hardware selects.
- [ ] Update the preview on every selection without applying it; disable apply for unavailable engines or empty distributions.
- [ ] Route “Generate and apply” and deterministic previews through the existing rollback-safe identity operation.
- [ ] Add responsive, keyboard-focus, light-theme, disabled, busy, success, and error styling.
- [ ] Run UI and existing settings tests.

### Task 3: Engine capability boundary

**Files:**
- Modify: `additions/browser/components/cloakfox/CloakfoxEngineHost.sys.mjs`
- Modify: `additions/browser/components/cloakfox/content/settings.js`
- Test: `tests/engines/test_browser_picker_capabilities.mjs`

**Interfaces:**
- Produces: `CloakfoxEngineHost.capabilities()` returning immutable `{gecko:{available,version}, chromium:{available,version}, webkit:{available:false}}`.
- Consumes: Task 1 selection and Task 2 apply request.

- [ ] Write failing tests proving capabilities come from actual registered/native backend state and cannot be enabled by an ordinary preference.
- [ ] Implement the read-only capability report; Gecko uses `AppConstants.MOZ_APP_VERSION`, Chromium requires the native production host to report a valid major.
- [ ] Re-check capabilities immediately before apply and fail without mutation if the selected engine is unavailable.
- [ ] Keep Chromium/Edge disabled until the production host reports support; keep Safari disabled.
- [ ] Run capability, native-host, and persona-backend tests.

### Task 4: Runtime verification

**Files:**
- Create: `tests/fingerprint/probe_browser_profile_picker.py`
- Modify: `tests/fingerprint/run_daily_driver.py`
- Modify: `tests/fingerprint/README.md`

**Interfaces:**
- Consumes: completed picker, catalog, BrowserForge generator, and capability report.

- [ ] Add a Selenium probe that selects Firefox/current/Windows, generates a profile, and verifies UA, HTTP UA, `appVersion`, platform, `oscpu`, and preview consistency.
- [ ] Assert Firefox previous-version selection carries its lower-confidence label and remains internally coherent.
- [ ] Assert unavailable Chrome, Edge, and Safari controls cannot apply or mutate the container.
- [ ] Assert generation failure restores every saved identity preference.
- [ ] Add the probe to `run_daily_driver.py` and document it.
- [ ] Run `node --test tests/fingerprint/test_browser_profile_catalog.mjs tests/fingerprint/test_browser_picker_ui.mjs tests/engines/test_browser_picker_capabilities.mjs tests/fingerprint/test_persona_version.mjs`.
- [ ] Run `CLOAKFOX_BIN="$PWD/firefox-src/obj-aarch64-apple-darwin/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/probe_browser_profile_picker.py` against a fresh build.
- [ ] Run `git diff --check` and review the settings screen in light and dark modes at desktop and narrow widths.
