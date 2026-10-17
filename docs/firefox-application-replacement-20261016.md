# Firefox application replacement investigation — October 16, 2026

## Evidence and limits

`/Applications/Firefox.app` was an ad-hoc-signed Cloakfox appearance bundle:
`org.mozilla.cloakfox.appearance.firefox`, executable `firefox`, version
158.0-beta.26, application.ini BuildID 20261015182945. The installed
`/Applications/Cloakfox.app` has the same version and application.ini BuildID.
The appearance bundle had neither `cloakfox-appearance.json` nor
`cloakfox-profile.ini`. Its source module, inspected directly inside its
browser/omni.ja, creates appearance copies in the profile's local cache, not
Applications, and writes both of those receipts.

The retained Codex and Cloakfox Claude command histories inspected did not
identify an operation placing this appearance app at `/Applications/Firefox.app`.
This establishes the wrong app's identity, but does not establish who copied it,
whether Finder was used, or exactly when Mozilla's original bundle was removed.
Do not describe the packaging fallback or a redirected cache as the proven
historical cause. No evidence establishes that toggling appearance alone wrote
to Applications.

The previous app is preserved in the user's Firefox-Restore-20261016 Downloads
folder. Genuine Mozilla Firefox 158.0 was restored from Mozilla's installer;
its org.mozilla.firefox identity, Mozilla signature and Apple notarization were
verified. The restoration did not change Firefox profile directories. macOS
denied access to those directories even after the reported Full Disk Access
change, so profile backup/content verification was not claimed.

## Confirmed hazards and safeguards

- The appearance cache formerly used the collision-prone filename Firefox.app.
  It now uses Firefox Personal.app; CFBundleName/DisplayName remain
  Firefox, and the engine/profile identity remains Cloakfox's.
- Appearance preparation now requires the actual Cloakfox source bundle ID and
  executable, refuses Applications paths regardless of case, refuses redirected
  cache ancestors, and refuses to replace an app without its matching ownership
  receipt. Only the standard OS-owned /var and /tmp aliases to /private are
  allowed; normal macOS temporary profiles traverse them.
- scripts/package-dmg.sh formerly accepted dist/Firefox.app when Cloakfox.app
  was missing. A real script regression demonstrated that this could publish
  an appearance bundle. The fallback is removed, and both packaging entry points
  validate the Cloakfox filename, ID, executable and absence of appearance/profile
  receipts. Repackaging validates again after arbitrary includes are copied.
- CLAUDE.md explicitly reserves Mozilla's install path and bundle identity.

These guards cover Cloakfox's managed appearance/packaging paths. They cannot
prevent someone with filesystem access from manually renaming an arbitrary app
to Firefox.app and replacing Mozilla's installation outside those paths.

## Verification

Regression cases failed before the guards and passed after: distinct appearance
filename, source identity, redirected cache, foreign target ownership,
case-insensitive Applications exclusion, forbidden DMG fallback, renamed
appearance bundle and profile-binding injection during repackaging. Final suites:
309 fingerprint Node tests and 66 CI helper tests passed. Independent review
found no remaining important issues after the case and repackaging fixes.

The real macOS `probe_appearance.py` passed against a staged copy of the installed
Cloakfox with the patched module: appearance round trip, cold launch, profile
preservation, extension metadata, branding and icons. This used disposable test
profiles; personal profiles were not edited. Only browser/omni.ja's appearance
module was changed, and the outer app signature was resealed without rewriting
nested canonical renderer libraries. The previous Cloakfox app is retained in
the Firefox-Restore-20261016 Downloads folder for rollback.
