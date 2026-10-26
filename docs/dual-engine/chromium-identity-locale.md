# Chromium navigator/client hints and regional presentation

**Status: native identity increment built and runtime-verified on macOS on 2026-10-16,
with the regional presentation widened to canonical languages/timezones and
re-verified on 2026-10-17.**
The external build volume is mounted and the completed framework was recovered;
no duplicate full-source rebuild was needed. The candidate remains separate from
`/Applications/Cloakfox.app`. This verifies the bounded scope below, not full
Chromium privacy parity or same-window engine switching.

## Native scope

The v1 shared snapshot optionally contains `persona.presentation`:

```json
{
  "hardwareConcurrency": 4,
  "deviceMemory": 4,
  "languages": ["fr-FR", "fr"],
  "timezone": "Europe/Paris"
}
```

New personas derive a regional preset and hardware values deterministically from
their seed. Supported CPU counts are 4/8/16 and memory 4/8. `languages` is any list
of 1-4 distinct canonical BCP 47 tags (`lang[-Script][-REGION]`: lowercase 2-3 letter
language, Titlecase script, uppercase 2-letter or 3-digit region) and `timezone` is
any canonical IANA zone (`Area/Location[/Location]`, or `UTC`) present in the
platform tzdata; legacy and bare aliases (`US/Eastern`, `Etc/*`, `CET`, `GMT`,
`Japan`) are rejected as non-canonical. There is no prefix-chain rule: each tag
stands alone, and `locale` is always the first tag.

Authority is split deliberately. The store owns structure, canonicity, count and
distinctness, but it ships no CLDR or ICU data, so it cannot decide what a given
engine can actually render. Each engine is the authority for existence and
applicability, and refuses a persona it cannot present — cleanly, and before any
container context or renderer exists — rather than aborting a renderer or inheriting
the host language or zone.

Sampling keeps a curated table of 35 plausible regional presets, each a language list
with its fallback chain plus its zone, so generated personas look like real machines
rather than random tag/zone pairs. Explicit presentation selections survive generation
unless clear-overrides is selected; toggling a feature does not pin generated values.
An explicit CLI language/timezone selection records a full presentation preset.

Legacy v1 records without presentation remain valid and unchanged on normal load.
Explicit regeneration upgrades them to the new generated presentation. Presence
of presentation requires `identityPrivacyVersion:1`; older SDKs fail closed.
Three independent boolean options—`navigator`, `language`, `timezone`—default on
for presented personas and remain gated by the master switch. Context changes
still require a new companion session. This is not yet in the Gecko settings UI.

Native hooks preserve the actual Chromium brand/version, UA/appVersion, OS family
and native API descriptors. Navigator hardwareConcurrency/deviceMemory are
container-owned. High-entropy architecture, bitness, model and platform-version
hints become empty strings, with wow64 false; low-entropy brands/platform and
actual full versions remain native. The same reduction is applied to browser
navigation hints and renderer/worker metadata. Device-memory navigation/fetch
hints use the same configured value as navigator. Other device/display/audio/
font/graphics signals are outside this increment.

The CEF per-profile presentation preference is applied before creating a browser
and propagated as internal renderer switches, covering worker renderer startup.
Browser client-hint lookup uses a separate profile preference pointer; its
existing global Local State preferences retain their original semantics.
Language prefs/settings supply HTTP Accept-Language, native navigator getters
supply canonical primary/fallback languages, and ICU/V8 defaults initialize before
scripts. Existing native timezone override ownership handles Date/Intl/DST and
suppresses host timezone changes. Explicit Intl locale/timezone options and UTC
arithmetic remain native. Disabling language or the master switch restores the
saved native profile languages on the next companion session.

## Verification already performed

- New presentation/model/launcher regression tests 5/5; existing store tests 7/7.
- Native runtime fixture failed on the old framework's absent identity capability,
  confirming the new behavior is not already provided by the prior app.
- Twelve affected C++ implementation units compile with the real generated flags,
  using normal headers in place of relocated stale PCM modules for this smoke
  check. This is not the full framework build or runtime verification.
- Pinned patch replay, inherited hashes, idempotence and changed-input rejection pass.
- Companion client compiles against the previous SDK and capability-gates the new
  presentation. That old framework cannot provide the new native behavior.
- Independent source review identified navigation hints reading Local State rather
  than profile prefs, and a disable flag accidentally pinning the full preset.
  Both source issues are corrected. Subsequent-navigation assertions and launcher
  regression coverage were added. The recovered framework now passes native HTTP navigation/fetch and worker/header runtime assertions.

## Original source build and recovery

Source relocation invalidates much of the native cache: the pre-change dry run
reported 58,406 steps. No source-path/hash tricks or cache deletion are used.
The runner is `engines/chromium/build_identity.py`; a filesystem lock prevents
another identity pipeline from running against the same output directory.
It preserves compiled objects, original SDKs and the installed app. Stages:
source hashes → framework → fresh SDK/package hashes → patched and unpatched
clients → complete engine tests → C++ test → sandbox/isolation → owned TCP/QUIC
certificate checks → concurrent Gecko158 with versioned configs.

The original interrupted pipeline records and logs are preserved in:

- `/Volumes/CloakfoxChromiumBuild/source-build/identity-build-status.json`
- `/Volumes/CloakfoxChromiumBuild/source-build/logs/identity-framework.log`
- `/Volumes/CloakfoxChromiumBuild/source-build/logs/identity-pipeline.log`

Failures keep their logs and objects. Do not launch duplicate Ninja/build/test
pipelines. After a successful framework build, inspect actual native headers,
page/frame/dedicated/shared/service-worker readouts, Intl/DST behavior, individual
toggles and restored native values. Only then update this record/inventory,
install the candidate locally (preserving the previous app), and commit/push the
completed work. Authenticated H2/H3 isolation and full privacy parity remain open.

Prebuild unit discovery ran26 available tests and skipped11 binary runtime
classes. It does not verify the new native runtime. Source patch replay and12
implementation-unit compiler checks passed. [Prebuild evidence](identity-locale-20261015/prebuild-result.json).
The thread monitor `watch-chromium-identity-build` checks this single pipeline
periodically and resumes diagnosis/finalization when it finishes or fails.

## Recovery verification, 2026-10-16

The original status file still reports its interrupted `engine-tests` stage; its
PID is no longer running. Do not interpret that stale file as a live build or a
successful completed pipeline. A separate recovery report records fresh checks.

- Framework SHA-256: `d1c7b99c9c512f12ec87fff78f52072989c9f76780745fbeeac66ee689807298`.
- Pinned native source and inherited privacy hashes pass `apply_identity_patch.py --check`.
- All five native identity tests passed, covering first script, frames, workers,
  HTTP hints/languages, Intl/DST, separate containers/toggles and native restoration.
- Full suite initially passed96/97; the sole failure was stale inventory after the
  independent Gecko keyboard fix. Inventory was regenerated; the subsequent
  suite including the windowless foundation passed103/103. Later additions have
  their exact result in the [foundation record](parity-20261016/README.md).
- C++ container paths, real renderer sandbox enforcement, owned storage isolation,
  TCP/QUIC certificate refusal and versioned Gecko158/Chromium coexistence passed.

The prototype still rejects media permissions and exposes only its implemented
native groups. Cross-OS/full BrowserForge presentation, native canonical rendering,
complete device/media/network policy, authenticated H2/H3 isolation and production
host/controller integration remain open. No parity release or installed-engine
switching claim follows from these results.

## Regional widening verification, 2026-10-17

The bounded language/timezone preset list is gone. The engine now accepts any
canonical language list and any canonical zone its own ICU data can render, and the
acceptance test it applies is the same one Blink applies in the renderer:
`base::i18n::GetLanguageTagFromString` plus membership in
`base::i18n::GetSupportedIcuLocales` for every tag, and
`icu::TimeZone::createTimeZone(...) != icu::TimeZone::getUnknown()` for the zone.

Where that check lives matters. The companion client is a pure CEF embedder: it links
no Chromium internals and no ICU, so it keeps structural checks only (1-4 distinct
non-empty tags, bounded lengths) and never guesses at applicability. The framework
applies the ICU test at the choke point the client actually uses —
`CefBrowserContext::ParseInitialPrivacySnapshot`, reached through
`CefRequestContextImpl::CreateContext` while the initial-snapshot capability is
present. A refusal there means no container context exists, so no renderer is ever
started with a language or zone ICU cannot adopt. CEF's context-creation API returns
no error detail, so the host sees one generic container-context failure: the refusal
is clean and fail-closed, but it does not name the offending value. That is a known
limit of the current CEF surface, not a silent fallback; a validated-presentation
error channel would be a separate increment.

An earlier draft put the same test in `pref_helper.cc` (the `SetPreference` path).
That path is not taken for the presentation while the initial-snapshot capability is
present, so the hook was reverted rather than left as unexercised validation inside a
security-sensitive patch.

Because `ParseInitialPrivacySnapshot` is introduced by the initial-snapshot patch and
is also touched by later patches on the same file, the widening ships as a new tail
patch: `patches/native-locale-timezone-privacy.patch` with
`locale-timezone-patch-lock.json`, applied after the display lock. Appending keeps
every already-verified patch and lock byte-identical, so their evidence still applies.

Evidence (locale build, `locale-built-sdk`, framework
`f03b85fdad197673fdf8ee055269dfdf5a730c139b418e7f52834ad2271eb33d`):

- All 35 sampling presets are accepted by the engine
  (`test_every_sampling_preset_is_accepted_by_the_engine`), so sampling can never
  emit a container that cannot start.
- Arbitrary canonical values reach the page: ko-KR/Asia/Seoul,
  pt-BR/America/Sao_Paulo, a three-part `zh-Hant-TW` tag on Asia/Taipei and
  sv-SE/Europe/Stockholm (a zone that observes DST) report matching
  `navigator.language`/`languages`, exact `Intl` locale, zone, DST offsets,
  Accept-Language and worker identity.
- Unrenderable values are refused fail-closed (`xx-XX`, `Mars/Olympus`) and the same
  container still accepts a renderable persona afterwards; a duplicate or malformed
  list is named precisely by the embedded client, which needs no ICU.
- Patch replay: the new lock replays to its exact before/after hashes and rejects
  tampering (`test_locale_timezone_extension_replays_and_rejects_tampering`); the
  earlier identity/display locks still normalize and replay through it.
- ctest 2/2; sandbox/isolation, owned TCP/QUIC certificate and versioned
  Gecko158/Chromium coexistence probes pass (exit 0).
- Full engine suite: 170 tests, 169 passed. The sole failure is the pre-existing
  stale `test_privacy_inventory` (concurrent settings-UI work in `additions/` adds
  `cfx-engine-*` bindings), unrelated to this change. An earlier run under full
  build/test parallelism also hit a load-induced timing flake in the owned-IME state
  probe; it passes alone and did not recur in the final serial run.

`identityPrivacyVersion` stays 2 and the ready report is otherwise unchanged;
`releaseEligible` remains false. Cross-OS personas (claiming Windows/Linux on this
macOS host) still need a UA/platform policy decision and remain unported.
