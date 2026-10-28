# Firefox 159 scenario coverage follow-up — 2026-10-28

163 of the 163 discovered regression probes now have passing results for the
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

## Native checks completed with user authorization

The user explicitly authorized the two remaining native UI checks. The unchanged
privacy-enforcement probe passed, including disabled screen capture/output
selection rejecting before chooser, location consent, container isolation,
WebRTC startup and opt-out behavior, and persistence.

The first appearance attempt failed before restart because Selenium clicked the
checkbox covered by its styled label. The test now clicks the actual visible
associated label and waits for checked state; no product code was changed.
The full headed test passed: both appearance directions, native process name and
bundle path, same disposable profile and tabs, extension metadata/toolbar/popup,
and fresh original-app launch honoring the saved choice. Nine appearance helper
unit tests also passed. The original failure is retained in native-final-evidence.

`scenario-acceptance-final.json` records all163 current probe source hashes and
resolves the earlier exclusions. A passed negative capture-policy test does not
certify a successful real screen-sharing session. Synthetic-device checks do not
certify physical camera/microphone hardware. Neither counts nor the probe list
prove every possible setting combination or guarantee absence of all privacy leaks.

## Evidence and preservation

`coverage-followup.json` reconciles the earlier163-probe inventory, records current
source hashes, library results and the earlier two exclusions. Supporting results
and logs are in `coverage-followup-evidence/`. Large raw library reports remain
in the ignored reports directory with their SHA256 hashes recorded in the small
library summaries. The 26 targeted Gecko helper tests and three camera-nickname
unit tests pass. Independent review found no actionable bug in the test changes.

No native/product source, installed app, Chromium build process or shared build
input was changed. Earlier checkpoints remain valid Git objects. The older
checkout advanced independently through container UI commits; this work did not
alter or restore its files. No existing checkpoint or build artifact was deleted.
