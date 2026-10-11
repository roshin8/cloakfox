# Restore clear overrides during generation

2026-10-11, `codex/firefox-157-port`.

Restored **Clear existing field overrides when generating** in Persona &
identity → BrowserForge profile. It starts unchecked. Checked fresh generation
builds a configuration without manual field overrides, then clears only the
selected container's override preferences. Saved region and privacy policies
still apply. Applying a selected preview keeps overrides even with the checkbox
checked. The status confirms when overrides were cleared.

Verification:

- The new live probe initially failed because the checkbox was absent.
- `probe_generation_clear_overrides.py` passes against the loose built app and
  again against the read-only mounted DMG: unchecked retention, checked clearing,
  fresh effective values, other-container isolation, retained strict privacy
  policy, preview retention and unchecked default after reopening settings.
- All 218 Node tests pass; `git diff --check` passes.
- The resource build and macOS packaging completed successfully.
- All four changed packaged resources are byte-identical to source. Their
  hashes are in `clear-overrides-source-hashes.json`.

Updated development DMG: `cloakfox-157.0.1-beta.25.en-US.mac.dmg`.
SHA-256: `31048bd1238eea357ff95371380fe6dd87b50f3df646b9c8fe51b245567ecd6f`.
Artifact metadata and current source hashes were updated. No installed app or
existing user profile was changed. The broader generation-failure rollback
difference identified in the parity audit remains separate follow-up work.
