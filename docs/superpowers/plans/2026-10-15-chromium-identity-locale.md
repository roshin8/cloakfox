# Chromium navigator, hints and locale masking

Implement inline; the user explicitly waived plan review.

## Design and scope

Extend the portable snapshot with optional `persona.presentation`: bounded desktop
hardware, supported regional language lists and IANA timezone presets. Old v1
snapshots remain valid; presence requires a new native identity capability. Supply
three independent optional toggles (`navigator`, `language`, `timezone`), all gated
by the master switch. New personas generate deterministic presentation values;
regeneration re-samples them and explicit presentation overrides survive unless
clear-overrides is selected. Preserve actual OS family, Chromium brand/version,
UA/appVersion and native API brands; reduce high-entropy UA architecture/bitness/
model/OS-version details consistently in JS and request hints. No scripts/CDP in
production; native hooks only. Navigator hardwareConcurrency/deviceMemory must
agree in pages/workers and with Device-Memory request hints.

Apply immutable per-context prefs before browser creation. Propagate to every
renderer, including dedicated/shared/service-worker processes. Locale/timezone
initialize ICU/V8 before scripts and ignore host timezone changes while masked.
Native date arithmetic/explicit Intl options retain normal behavior, including
DST. Native values return with master/per-feature toggles off. Original framework,
SDKs, apps and Gecko sources are preserved. Shared Gecko settings UI remains pending.

## Tasks and verification

- [x] Write failing portable validation/generation and native runtime fixtures.
- [x] Implement capability-gated schema/controller/launcher controls and C++ adapter.
- [x] Add pinned native patch, prerequisite hashes and replay/negative tests.
- [ ] Build a fresh identity SDK/app from source, preserving previous SDKs.
- [ ] Run full engine suite, navigation/header/worker/Intl/DST/native-descriptor
  fixtures, legacy SDK rejection, concurrent158 and owned TCP/QUIC checks.
- [ ] Update coverage/evidence, independent review, commit and push.

Supported regional presets keep validation explicit and JS/header/Intl values
coherent. They are not a complete BCP47/IANA database. Full cross-OS personas,
touch/display/font/audio masking and UI integration remain separate work.

Execution: portable/launcher regressions5/5, store7/7, pinned source replay
and12 implementation-unit compiler smoke checks passed. Baseline runtime tests
failed the old framework capability as expected. Independent review corrected
profile-vs-Local-State lookup for navigation hints and a disable toggle pinning
generated values. Further fixtures cover navigation after Accept-CH, worker
headers, individual toggles and native restoration. Full framework build and
runtime checks remain pending in the single identity pipeline. Existing apps,
SDKs, logs and compiled objects are preserved. The periodic thread monitor
watch-chromium-identity-build is active. No runtime success is claimed.
