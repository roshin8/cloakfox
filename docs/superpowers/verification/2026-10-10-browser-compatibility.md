# WebGPU crash repair verification — 2026-10-10

## Scope and change

Implemented the Cloudflare WebGPU null-safety plan on outer-repo baseline
`b6790033fa` (`cpp-first-exploration`), retaining the latest unrelated changes.
`upstream.sh` remains Firefox 146.0.1, beta.25. The separate TestDome/screen API
plan has not been implemented by this repair.

The ordered patch changes `GPU gpu` to `GPU? gpu` and renames the page and worker
getter declarations/definitions from `Gpu` to `GetGpu`. Both method bodies,
privacy settings, existing actors, secure-context restriction and `[SameObject]`
remain unchanged. The generated Navigator/WorkerNavigator bindings return null
before calling `GetOrCreateDOMReflector`.

## Reproduction and verification

- **Red:** the installed baseline, executable SHA-256
  `54ee08c14f7f59780d83dfe753f793cfe9f2e3d337b68308874874a9db0923ba`,
  passed master-off but failed the disabled blank-frame completion assertion.
  `/tmp/cloakfox-webgpu-before-fix/master-on-disabled-gecko.log:18` records a
  child exiting on signal 11. The captured stack reached DOM wrapping with a
  null WebGPU instance. No installed-app or user-profile changes were made.
- **Build:** `./mach build` succeeded after all five source changes. The initial
  WebIDL-only build failed because nullable getters require `GetGpu`; matching
  page/worker renames resolved it. Build log:
  `/tmp/cloakfox-webgpu-build-20261010.log`.
- **Green:** `probe_webgpu_null_safety.py` passed master-off, master-on-disabled
  and master-on-native-enabled on the bundled development app, signed staging
  app and final mounted DMG. Coverage includes page/blank/srcdoc/navigated
  frames, retained and fresh getters after same-frame navigation, native
  descriptor/receiver behavior, stable native GPU identity and dedicated
  workers. Completion, original-document sentinel and DOM liveness checks
  prevent a null WebDriver response from masking a crash. Final report:
  `/tmp/cloakfox-webgpu-final-probe/result.json`.
- **Existing regressions:** signed staging passed navigator coherence in all
  four containers and worker spoofing (17 worker plus 14 main signals).
  Logs: `/tmp/cloakfox-webgpu-signed-navigator.log` and
  `/tmp/cloakfox-webgpu-signed-workers.log`. `node --test
  tests/fingerprint/test_*.mjs` passed 43 tests; Python probe-scoring tests passed.
- **Reproducibility:** `bash scripts/test-patches.sh` applied all 92 patches to a
  separate extraction, with zero failures. The script cleaned its extraction;
  the current native checkout was never reset. Log:
  `/tmp/cloakfox-webgpu-patch-audit-20261010.log`.

Geckodriver 0.36.0 warned that 0.37.1 is recommended for this Firefox version;
the recorded final probe runs completed successfully.

## Packaging and rulings

The bare `dist/bin/cloakfox` launcher produced mismatched runtime identity and
failed initial GPU/navigator checks. Verification therefore uses the bundled
`dist/Cloakfox.app/Contents/MacOS/cloakfox` and final package executable, which
pass. The launcher discrepancy was not repaired as part of this change.

`./mach package` succeeded but its intermediate app had a stale resource
signature. A separate staging copy had Finder attributes cleared and was
ad-hoc signed; `codesign --verify --deep --strict` succeeds on staging and the
read-only final DMG payload. This is local signing, not notarization.

Final artifact: `cloakfox-146.0.1-beta.25-webgpu-crash-fix-20261010.dmg`.
Application BuildID: `20261010182521`.

| Payload | SHA-256 |
| --- | --- |
| Final DMG | `54db315905b93a5425ac461f5d458bac56a864e7211e807fecd0966d51e89925` |
| Mounted executable | `fbcfd5d22866fd9abe6831fe5c7ebe1fae6c02e51fa324ef0e34e124620629f5` |
| Mounted XUL | `e4966014abe3409aad03e42dc134dc5610cae7d035049d45056c9aa496797c1a` |

Mounted executable and XUL hashes exactly match signed staging. Old DMGs and
`/Applications/Cloakfox.app` were preserved.

## Live outcome

Read-only headful checks used the signed staging app, disposable profiles,
Firefox identity and privacy master enabled. Treet loaded its product listings
and remained alive for the bounded observation. The user-supplied Capital One
link displayed Cloudflare's normal **Verify you are human** checkbox instead of
the broken-frame face; its native log contains no signal-11/EXC_BAD_ACCESS crash.
Challenge completion was not tested: no CAPTCHA was clicked, no login was
performed and no assessment was started.

Screenshots and reports:
`/tmp/cloakfox-webgpu-live-20261010/fixed-treet.png`,
`/tmp/cloakfox-webgpu-live-20261010/fixed-treet-result.json`,
`/tmp/cloakfox-webgpu-live-20261010/fixed-cloudflare.png`, and
`/tmp/cloakfox-webgpu-live-20261010/fixed-cloudflare-result.json`.
These scratch artifacts are local evidence, not committed fixtures.

A separate read-only reviewer found no blocking or actionable correctness
issues in the native patch and regression coverage. Packaging and live results
were reviewed from the verification evidence rather than independently rerun.

## Follow-up: challenge restarts after a human click

The user subsequently reported that clicking the checkbox restarts verification.
Diagnostic runs of the same signed staging app reproduced a fresh challenge
without any content-process signal/EXC_BAD_ACCESS crash. The human performed
the checkbox interaction; the agent only collected browser observations.

The first capture showed an HTTP 200 challenge POST with Set-Cookie, saved
`cf_clearance` cookies, then HTTP 403 on the original link with a new Ray ID.
The second capture additionally confirmed that the subsequent original-link
GET sent `cf_clearance` and `cf_chl_rc_ni`. Its HTTP User-Agent was stable across
the challenge and reload and matched the page's navigator User-Agent. Cookie
values, challenge tokens and the private link are not included in this record.

This rules out the repaired WebGPU crash, a missing saved/sent clearance cookie,
and a changing HTTP User-Agent for these observed runs. It does not establish
why the site's challenge platform rejects/re-challenges the session. No new
browser patch or privacy exception has been justified or applied; successful
challenge passage remains unresolved. Selenium-driven diagnostics can themselves
influence a challenge decision and are not a clean daily-use-browser control.

Local reports: `/tmp/cloakfox-cloudflare-loop-20261010/result.json` and
`/tmp/cloakfox-cloudflare-loop-headers-20261010/result.json`. The latter contains
only cookie names/attributes and request metadata, not cookie values. Console
messages in scratch reports may contain private URLs; do not publish them raw.
