# Scope public-IP warnings to recorded website visits

A manual route measurement used to count as evidence for warnings on any website. The monitor also stored one owner per IP, so unrelated site visits could produce false warnings while later visits from a second container could be lost.

Warnings now require a recorded visit with the same exact normalized hostname and public IP, in another container. Paths, scheme and ports do not split a hostname; subdomains do. Settings-only route measurements remain visible as network diagnostics but cannot trigger a website warning. The existing website inclusion/exclusion rules and opt-in monitoring still apply. Visits made while monitoring is off are not collected retrospectively.

Visit history is keyed by container, hostname and IP, bounded to 500 records for 30 days and ten redacted URLs per record. Each record's age is updated independently. Existing unscoped records remain available for inspection/deletion but do not imply a hostname visit. History row actions target the selected record, including a separate selector for legacy records. Existing warning exceptions and native container/proxy routing remain in effect.

Verification:

- New tests first reproduced unrelated-host and unscoped-history false positives.
- Legacy row-action regression also failed before the selector correction.
- All 246 Node unit tests pass, including 11 IP monitor tests. Full binary-enabled Python suite: 39 passed, one conditional non-Chromium-UA skip.
- Stable packaged-app runs pass the IP monitor, IP settings and packaged-resource probes. The IP monitor probe verifies settings-only measurements do not warn, an unrelated hostname does not warn, and a recorded same-hostname/same-IP visit does warn, including notification, full warning, recheck, unknown route and continue flows using local TLS proxy fixtures.
- Independent review found a legacy row-action selector bug, fixed and retested; final review reports no remaining actionable findings.

The first loose-build settings run failed an immediate post-resize width assertion. The probe now waits up to five seconds for that same responsive-width invariant. An intervening loose-build launch failed to decode Marionette while build staging was being refreshed. After packaging finished, serial probes against the self-contained app passed; no production CSS change was needed.

The JS-only repair is built and packaged on the existing 158 native engine. `docs/firefox-158-port/site-ip-*` contains the build, package, test and install evidence. The earlier port report/checksums describe the pre-repair artifact; the repair's `site-ip-install.json` records the current DMG checksum. User profiles are preserved, and running browser processes are not restarted automatically.
