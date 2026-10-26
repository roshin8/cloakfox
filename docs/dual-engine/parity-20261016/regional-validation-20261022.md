# Regional validation source increment — 2026-10-22

Uncommitted source increment after a06a95168d. No installation, packaging, UI interaction or live build-source mutation.

## Changes

The store admits bounded language/script/region/variant tags and Unicode `u` extensions. It rejects duplicate variants/keys/attributes, malformed casing/structure, header injection, private-use and other singleton extensions. Native ICU remains the semantic authority. Extension fallbacks drop the entire extension before broadening the base tag, never producing incomplete `-u`/keyword fragments.

Timezone admission uses a pinned public-domain IANA tzdb 2026d-rearguard zone.tab regional-ID table, plus UTC, intersected with installed timezone data. This is an explicit regional admission policy, not a claim that every possible IANA name or ICU output spelling is supported. Backward aliases such as Asia/Calcutta and Europe/Kiev are rejected. Missing timezone data fails closed; existing invalid records are not silently migrated or replaced with host defaults.

A new regional-validation-patch-lock.json tail follows locale-timezone-patch-lock.json. Previous patches/locks remain unchanged. Native validation checks the complete canonical language tag and supported primary language, rejects private-use/non-u singleton extensions, and enforces the same timezone table before context creation. The client length bound is 128 bytes, matching the store/native boundary. Keyword negotiation remains ordinary ICU behavior; acceptance is not a promise every keyword has dedicated formatting support.

## Verification

Red regressions reproduced rejected variants/extensions and accepted timezone aliases before implementation. Configuration, patch replay/tamper, persona-store and schema2 policy tests passed (50 tests before adding the missing-tzdata regression; final count recorded in chat). Native/store timezone table equality is asserted. Earlier lock replay remains covered. Scoped independent static review found no remaining blocking finding; direct native bypass and page/worker runtime tests were added.

## Not yet verified / next work

The external Chromium build drive is disconnected. The new native patch has NOT been applied to the live CEF source, compiled, or exercised in Chromium. New runtime tests must run against a framework built with regional-validation-patch-lock.json, followed by full native suite, isolation, transport and coexistence. Do not claim runtime completion or update full policy-group capabilities. releaseEligible remains false.

The original Chromium parity plan remains active. Further native port implementation/build acceptance requires the external drive. Continue in headless/background mode only; no activation or typing in the user's windows. Shared policy/schema2 rejection tests were rerun without enabling unfinished native groups. Existing unrelated dirty UI/CI/canvas work was preserved.
