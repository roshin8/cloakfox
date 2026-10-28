# Firefox 159 scenario coverage follow-up — 2026-10-28

161 of the 163 discovered regression probes now have passing results for the
explicit Firefox 159 candidate. There are no remaining GPU inconclusives. This
is coverage of the known probe inventory, not 100% of every privacy feature,
setting combination, possible browser execution path, or source line/branch.
Original acceptance receipts and earlier failures remain unchanged.

## Gaps closed

- Four WebGPU probes now run real compute, rendering/readback, resource-limit,
  provenance and container/site ownership checks. Firefox's supported
  `layers.gpu-process.allow-headless` is enabled only in disposable headless
  test profiles. No sandbox, hardware blocklist or production privacy setting
  was disabled. Both native and protected controls obtain actual adapters.
- Pinned CreepJS/FingerprintJS audits pass in both canvas modes with WebGPU
  explicitly enabled, including adapter/limit collection and stability.
- Region tests pass for headers, window/worker language/locale/DST, configured
  coordinates, site consent denial/allow and returning to the original owner.
  These do not exercise the real OS location provider.
- The cross-container variance probe passes. Its geolocation remains pending;
  its pass covers its actual strict canvas/audio/math and geometry assertions,
  not successful physical location acquisition.
- Both cpp-first probes pass with the explicit current binary. Their optional
  historical DMG path was not used; installer packaging is not covered here.
- Signature-selection checks pass for Firefox's native/Chrome network profiles
  and independent headless Chrome. Chrome's TLS/H2 and QUIC/H3 baseline also
  passes, but that reference alone is not proof of Cloakfox network parity.
- Replaced the obsolete OBS/settings-controls nickname probe with synthetic
  media. It checks the actual parent single-device label and menu, confirms
  browser nicknames do not alter website track/enumeration labels with master
  off, and reopens the picker after reset and profile restart. Protected website
  media-label scenarios remain covered by the original separate probes.

## Still unverified

1. `probe_appearance_restart.py`: actual appearance switch/relaunch through
   NSWorkspace can activate an application even when its browser is headless.
2. `probe_privacy_enforcement.py`: the actual display-capture negative path can
   reach native capture permission/chooser UI if the policy regresses. Existing
   individual permission, fake-media and routing probes do not replace this
   complete combined flow.

These two are not marked passed or waived. The user was asked whether to permit
those native UI checks; no permission is inferred from elapsed time. Successful
native permission/capture integration also requires an explicitly selected real
source, so a headless mock cannot establish complete end-to-end coverage.

## Evidence and preservation

`coverage-followup.json` reconciles all 163 discovered probes, records current
source hashes, library results and the exact two exclusions. Supporting results
and logs are in `coverage-followup-evidence/`. Large raw library reports remain
in the ignored reports directory with their SHA256 hashes recorded in the small
library summaries. The 26 targeted Gecko helper tests and three camera-nickname
unit tests pass. Independent review found no actionable bug in the test changes.

No native/product source, installed app, Chromium build process or shared build
input was changed. Earlier checkpoints remain valid Git objects. The older
checkout advanced independently through container UI commits; this work did not
alter or restore its files. No existing checkpoint or build artifact was deleted.
