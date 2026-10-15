# IPv4 and IPv6 IP comparison — installed Mac verification

Installed `/Applications/Cloakfox.app`, Firefox158.0-beta.26, runtime BuildID **20261015182935**, application.ini BuildID20261015182945. Personal profiles were not edited. Restart the browser and select Recheck IP to replace older pending warning pages.

## Behavior

The previous universal lookup returned one address. On an IPv6 connection that was a colon-separated IPv6 literal, not a malformed IPv4 address. The monitor now requests IPv4 and IPv6 independently using [the provider's documented family-specific endpoints](https://www.ipify.org/). Both values have explicit family labels in warnings and settings. An unreachable family remains unavailable/unknown; no IPv6-to-IPv4 conversion or direct-route bypass is attempted.

Each lookup retains the exact container content principal, native proxy/route policy, anonymous/no-cookie request flags, cache bypass, bounded response/timeouts and disabled redirects. Automatic checking remains opt-in and excludes private windows. Two primary lookups run concurrently; fallbacks must return the requested family. Successful measurements retain the existing5minute cache; wholly failed checks use30seconds. There may now be up to four requests per full check including fallbacks, rather than the previous single-family request/fallback pair.

Either family can cause a warning only when its address is associated with a recorded visit to the same exact hostname in another container. The other container's column shows only the families with recorded matches; it never copies a current IPv4 address into an old IPv6-only visit. History remains bounded and URLs sanitized.

Rechecks retain previously conflicting-family requirements: a successful other-family lookup cannot turn an unavailable original family into a conflict-free result. The page shows IP check incomplete when no current match can be verified. Allow matching IPs refuses if no matching address is known; Continue once remains an explicit separate action. IP lookup results do not prove the address seen by an arbitrary destination under PAC/proxy/IP-family routing differences.

## Verification

- RED: previous installed app returned only ip=2001:db8::1 with no IPv4/IPv6 fields against the dual-family fixture; original failure retained in installed-red.log.
- Signed candidate and installed browser: local TLS proxy fixture passed with two actual containers, both-family display, hostname-scoped history, different IPv4/shared IPv6, no-match dual routes, blocked/partial family rechecks, IPv4-only and IPv6-only availability, validated fallback, notification/warning/continue and retained container.
- Actual Settings rows verify IPv6-only overlap is not falsely attributed to IPv4. Light1100px and dark420px warning layouts passed horizontal overflow checks and were visually inspected. Raw screenshots under candidate/ and installed/.
- Full Node suite:295passed. Python/native suite:118passed,14runtime-dependent cases skipped; explicit live fixture ran separately.
- Independent source review found one P2 family-label bug, fixed with failing regressions and re-reviewed. No remaining P1/P2 in the reviewed change. [Review](review.md).
- The app and updated DMG retain the prior canvas/WebGPU privacy fixes. Canonical renderer and resource-profile settings were not changed by this IP-only feature. Installation/signature/hash records are in install.json, acceptance.json and dmg.json.

All measurement results in the live test use reserved synthetic IP addresses and local proxy fixtures; no real public-IP lookup requests were sent by the probe. This does not verify arbitrary real-world proxy providers or destination-specific egress, and runtime testing is macOS arm64 only.
