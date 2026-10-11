# Recent Firefox 146 → 157 feature audit

Audited 2026-10-11. The recent engine additions are represented in the 157
patch stack, and the main settings controls are present in the built app.
**Full parity is not established.** The initial audit found five differences;
the generation checkbox was restored afterward, leaving four follow-ups.
See [restoration verification](clear-overrides-verification.md).

Compared 146 HEAD `90903f2b24` with 157 HEAD `9371224db1`, covering changes
after common ancestor `274e503768`. All 63 changed production files were
inventoried. Two old patch files were superseded, rather than dropped without
replacement. The original 146 checkout and user profiles were not changed.

## Fresh checks

- Launched the built macOS arm64 app with a disposable headless profile;
  application version was `157.0.1-beta.25`.
- Visited all 11 settings categories and expanded their groups. All 51 fields
  from the 146 settings groups rendered somewhere in the current navigation.
  Region-managed fields link to the coordinated Region editor.
- All 13 optional-hardening checkboxes rendered under **Privacy & permissions →
  Optional hardening**, and their checked states matched stored preferences.
  This was a rendering/state audit, not an effectiveness test of every option.
- All four preset pickers rendered: browser/OS, display, GPU and language. The
  preset module is byte-identical to 146: 115 browser entries, 37 display entries,
  17 GPU entries and 27 language entries.
- OS and graphics-family selectors populated; changing the draft OS refreshed
  the graphics choices without applying a new identity.
- No duplicate DOM IDs or unresolved `aria-describedby` references were found.
- Read the development DMG without modifying it. All 83 Cloakfox modules,
  actors, settings resources and appearance assets checked were present and
  hash-identical to the current 157 source, including assets stored outside
  `browser/omni.ja`.

Detailed inventory, rendered controls, preference states, dropdown choices,
file presence and package hashes are in
[feature-parity-audit-2026-10-11.json](feature-parity-audit-2026-10-11.json).

## Differences requiring follow-up

1. **Resolved: clear overrides during generation.** Restored
   `cfx-generation-clear-overrides` after this audit. The built and packaged UI
   now support the one-step workflow; the separate Clear overrides action
   remains available.
2. **Some dropdown shortcuts are missing.** CPU values **1, 6, 64**, platform
   values **Linux armv8l, iPhone, iPad**, and audio channel count **1** are absent
   from 157's individual-field pickers. Custom editing remains available, and
   the four complete preset collections remain present.
3. **Screen-compatibility visibility is inconsistent.** With a Firefox identity,
   selecting the Chromium compatibility tab renders the screen panel while its
   status says to choose a desktop Chrome or Edge identity. The sidebar's
   `render()` overwrites the `hidden` value set by
   `updateChromiumCompatibility()`. The status paragraph also remains visible
   in unrelated categories. This is a UI finding; no change in native API
   eligibility or effectiveness was established.
4. **Generation failure handling differs.** The latest 146 handler samples and
   checks the requested OS/hardware before changing saved preferences. The 157
   handler writes mode/index/filter/seed preferences before sampling, and its
   catch block does not roll them back. This is a source-confirmed ordering
   difference; a sampling failure was not induced in this audit. Prior success
   probes do not cover preservation of the old identity after failure.
5. **Ten hardening descriptions were shortened.** Their toggles remain, with
   inline descriptions, but the expanded 146 help lists are absent. This is
   explanatory-text parity rather than a missing control. The Math-data,
   clipboard-signal and activity descriptions retain their detailed lists.

## Feature inventory

“Present” below means the source implementation is represented in the current
stack. “UI checked” means it rendered in this audit. Prior probe results are
separate evidence, not newly repeated acceptance tests.

| Recent feature or fix | 157 source | Settings UI / verification |
|---|---|---|
| Focus, page visibility and background scheduling option | Present: window-activity patch | Activity checkbox checked; dedicated effects not retested |
| Fullscreen state/event handling | Present: window-activity patch | Part of activity option; dedicated effects not retested |
| Pointer activity handling | Present: pointer-activity patch | Part of activity option; dedicated effects not retested |
| Hover activity handling | Present: hover-activity patch | Part of activity option; dedicated effects not retested |
| Clipboard signal option | Present: clipboard-signals patch | Checkbox checked; dedicated effects not retested |
| Content-only letterboxing and geometry integration | Present: letterboxing patch; enabled default | No dedicated Cloakfox checkbox in either recent UI; full geometry acceptance not repeated |
| Native worker Math wrappers | Present: native-worker-math patch | Engine feature; recorded worker/Math regression evidence |
| Live per-container Math updates and cache | Present: live-worker-math plus retained worker cache implementation | Existing identity/seed controls; recorded worker lifecycle evidence |
| Exported API names/descriptors | Present: exported-function-identity patch and actor changes | Automatic engine/actor fix, no dedicated control |
| Native logarithms/powers by default | Present: math-data-correctness patch; default opt-in false | Math-data checkbox checked |
| Optional logarithm/power noise | Present: math-data-toggle patch and actor handling | Checkbox checked; window/worker effectiveness not repeated |
| Animation Math caching | Present: Math actor and native cache changes | Automatic; no dedicated control |
| macOS Firefox appearance | Present: appearance module, patches and assets | Display & graphics → Application appearance checked; recorded appearance probe passed |
| Stable per-profile appearance app and profile-bound relaunch | Present: appearance-profile patch and module | Same appearance controls; recorded appearance/startup checks passed |
| Show active app in Finder | Present: appearance module | Button rendered on macOS; not clicked in this audit |
| Settings/extension appearance assets | Present; packaged hashes match | Settings appearance status rendered; recorded extension appearance probe passed |
| Native camera/microphone/screen capture permission reporting | Present: permissions patch | Native permission dialogs; recorded media-permission probe passed, actual capture delivery not established |
| HackerRank local-video failover recovery | Present: recovery actor/registration and config | Automatic site adapter, no dedicated checkbox; real site recovery not retested |
| Device-enumeration compatibility allowlist | Present in config | Automatic site setting; actual calls not retested |
| Website appearance preference persistence | Present: config and media-query actor | Standard Firefox preference; recorded daily-settings probe passed |
| Locale-tag handling | Present through retained 155/157 locale implementation | Region/language controls checked; recorded locale/region probes passed |
| Bundled glyph/rendering compatibility | Present: bundled-font-rendering patch | Automatic engine fix; full font/rendering matrix not repeated |
| Developer-console paste-protection default | Present: branding preference | Standard developer tools, no Cloakfox control |
| Native UA Client Hints | Present: user-agent-data patch | Existing identity fields/presets checked for presence only; effectiveness not tested |
| WebGPU null safety | Present: null-safety patch | Automatic repair; prior loose and packaged regression probes passed |
| Owner-based screen presentation | Present: screen-presentation patch | Screen section present; visibility inconsistency above; behavior not retested |
| Screen-details API and configurable topology | Present: screen-management patch and native files | Toggle, count, origins, save/reset controls present; native behavior not retested |
| Window-management permission/policy integration | Present: window-management-permission patch | Native integration; dedicated acceptance not repeated |
| Ancestor screen-orientation event handling | Present: screen-orientation-events patch | Automatic native behavior; dedicated acceptance not repeated |
| Restored browser/display/GPU/language preset pickers | Present; preset data identical | All four rendered; individual shortcut differences above |
| Fresh OS/hardware-constrained generation | Present: Bayesian network and persona modules | OS/hardware controls checked; recorded generation probe passed; failure staging differs |
| Existing field overrides and per-field resets | Present: override store and settings handler | All 51 fields rendered; coordinated Region editing retained |
| Generation status and clearing overrides | Present after follow-up | Status renamed to `cfx-identity-status`; separate Clear overrides retained; generation checkbox restored and verified |

The complete hardening set inspected was: Math-data noise, clipboard-signal
masking, activity masking, disabling `window.name`, WebSocket, clipboard API,
EME, media-device enumeration, notification-permission reporting and storage
persistence reporting, plus Math-constant noise, timer jitter and timer
quantization. Some of these predate the recent commits; none of their toggles
is missing.

## Superseded patches and limits

`cloakfox-worker-config-cache.patch` is archived because the retained 155/157
authoritative worker cache and live-update stack cover that responsibility.
`cloakfox-locale-tag-correctness.patch` is archived because the retained
155/157 locale design avoids modifying the process-wide browser locale.
Neither archived file should be re-enabled merely to match the old file list.

The existing port verification records all 102 active patches applying cleanly,
a successful native build, 19 selected live probes and six packaged probes.
Those records do not amount to a complete runtime test of every recent feature.
In particular, optional activity/clipboard effects, screen-management behavior,
real capture delivery and external site compatibility remain unverified on 157
by this audit. No Cloudflare challenge or assessment was exercised. This audit
changed documentation only; no product fix or rebuilt DMG was produced.
