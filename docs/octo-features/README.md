# Region, fingerprint policies, templates and proxies

Implemented the five-item shortlist from the [Octo Browser audit](../octobrowser-feature-audit-2026-09-08.md) in `codex/firefox-155-compat`. Changes remain uncommitted and unmerged. The original `cpp-first-exploration` checkout was not modified.

## What is available

| Control in about:cloakfox | Behavior |
| --- | --- |
| Region | One validated manual record coordinates Accept-Language, document/dedicated-worker language arrays, default Intl locale, timezone/DST and optional coarse coordinates. Explicit Intl locales remain intact. Site permission is required for location. |
| Consistency inspector | Measures an open website in a normal window plus a short-lived worker. Separately labels configuration contradictions, measured differences, heuristic concerns and unavailable measurements. Header/screen repairs have stale-state checks and undo; they preserve seeds and site data. |
| Privacy policies | Standard retains existing protection; strict also blocks media-device enumeration and clipboard access; compatibility disables geometry noise. Expiring schemeful top-level site exceptions independently disable geometry/text metrics, canvas/WebGL readback or audio noise. Geometry retains its historical seed while using a separate policy gate. |
| Templates | Reuse region, policy, pinned persona, proxy reference and opening pages. Personal/work/temporary/proxy-required presets create fresh secrets and empty site storage. Strict settings-only import/export excludes cookies, passwords and seeds. Settings persist before opening pages; required routes without a bound proxy stay blocked. |
| Proxy manager | Named HTTP/HTTPS Basic and SOCKS5 routes keep credentials in Firefox LoginManager. Container/ref/revision isolation prevents credential or connection reuse between identities. Rejected authentication fails closed, without a retry prompt. Optional HTTPS diagnostics use the selected container route, disable redirects/cookies, and save a redacted reachability result. |

The old locale/coordinate rows now point to Region. A saved region disables the old standalone timezone picker; without a region, that picker updates the native configuration. All config writers apply the region and policy after low-level overrides. Settings changes do not regenerate identity secrets.

## Privacy bugs corrected during implementation

- Configured coordinates previously bypassed site permission. Synthetic positions now use a request-owned snapshot after normal site permission, without irrelevant OS device permission prompts. Global coordinate getters and the provider no longer substitute ambient-container values.
- HTTP language settings previously came from a process-global cache. Requests now use their owning container's record, including worker requests.
- Global ICU locale rewriting affected explicit locales and used unsafe temporary string storage. Default locale/timezone overrides now belong to document/worker realms.
- Firefox 155's Rust password storage normalizes origins. Named credentials use distinct path-free origins and are read back before a save succeeds.
- Inspector measurements exclude private windows and verify that the page did not navigate while measured. Repairs refuse to overwrite newer settings.

## Verification

[Machine-readable evidence](verification.json) records the final results:

- Native macOS build successful: [build-5.log](build-5.log).
- **144 automated tests passed**, including compiled production C++ seed/policy helpers: [node-final.log](node-final.log).
- **15 browser probes passed in their latest runs.** The evidence combines unchanged-feature regressions with the final targeted reruns, rather than hiding earlier failed attempts. Logs are linked in `verification.json`.
- **82/82 patches applied** to fresh Firefox 155.0.1 source. All **191 compared native files matched**, with no differences: [stack-final.log](stack-final.log), [source-verification.json](source-verification.json).
- Packaged JS sources match `additions/`. New UI controls and the old timezone/connection controls were exercised through real DOM handlers; headless smoke tests do not certify physical pointer hit testing.

Live probes cover page-owned and dedicated-worker region measurements, headers, DST, explicit locales, denied/granted coordinates and container switching; site/vector/container exception isolation and expiry; actual inspector window/worker readings and repair/undo; HTTP/SOCKS authentication and rejected credentials with no direct fallback; template freshness, empty storage, persistence before opening pages and restart stability. Existing defaults, persona migration, blocker, network/WebRTC policies, identity forgetting, shared permissions, site isolation, container workflows and upstream hardening also pass.

The new native delta is [`cloakfox-region-policy-proxy.patch`](../../patches/cloakfox-region-policy-proxy.patch), covering 20 native files. The native policy helper and new modules ship through `additions/`. Build failures and diagnostic runs are retained as debugging evidence; final results are distinguished in `verification.json`.

## Deliberate limits

- Region selection is manual; no third-party IP discovery runs automatically. IP/region agreement is a heuristic, not a guarantee. Diagnostics test reachability and do not infer exit IP or location.
- HTTP proxy authentication supports Basic only; other challenges fail closed. Proxy metadata/templates contain references, not credentials, and references require a matching proxy catalog in this profile.
- Reload pages/restart workers after region or policy changes to clear existing caches. Exception expiry is checked on extraction. Existing synthetic location watches retain their initial coordinates. Shared/service-worker region behavior is not covered by the dedicated-worker probe.
- Inspector checks a limited set of fields in an existing normal-window website. Page security policy can block worker measurement; network headers, TLS and exit location remain explicitly unmeasured there.
- The older encrypted identity-backup format does not yet contain region/policy/catalog fields. Template exports cover reusable settings, not full-profile state.
- Prior release limitations remain: production browser update signing/hosting and the Google Safe Browsing provider key are not configured. This work does not claim merge or release readiness on other operating systems.
