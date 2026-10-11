# Remaining privacy controls implementation plan

User approved the full shortlist: updates/rebases, tracking links/bounces, DNS,
profile workspaces, network leak coverage, permission expiry, workers/live policy,
font realism, complete settings backups, and Safe Browsing integration.

Architecture: reuse Firefox native enforcement and services, expose privileged
about:cloakfox controls, preserve the cpp-first identity model. Existing identities
and user data remain stable. New native changes form a follow-up to the 82-patch
stack; snapshot originals under /tmp/cloakfox-next-before before editing.

## Independent deliverables and ownership

- Release agent: scripts/release_config.py + release_security.py, release status
  module/UI and tests. Native authenticated update configuration requires actual
  owner HTTPS hosting/MAR certificates; provider integration requires a real key.
  Fail closed when absent. Test signatures, rollback, configuration rejection,
  security-feed age and classifier DB/provider status using local fixtures.
- Permissions/workspaces agent: CloakfoxPermissions and CloakfoxWorkspaces modules,
  standalone UI files and tests/probes. Native permission principals/expiry and
  Firefox profile service/launcher. Never manufacture grants, copy credentials,
  or delete existing profiles.
- Worker/font agent: cache update propagation and shared/service worker probes;
  font license/hash audit, complete host-compatible BrowserForge sampling helper.
  CloakfoxHostPersona.sampleHostFingerprint(prng,sampler,os) returns a complete
  tuple; no string-only fake OS conversion. Existing identities remain legacy
  until explicit appearance change, new identities opt into host coherence.
- Root: tracking/DNS settings, expanded network tests, backup schema, integration.

## Root deliverables

1. CloakfoxTrackingProtection.sys.mjs + tracking-settings.js. Enable Firefox query
   stripping with maintained remote list plus conservative bundled tracking names,
   browser-wide registrable-domain exceptions, and real bounce purging (mode1).
   Preserve login/payment parameters. Test actual navigation cleanup and native
   bounce purge/interaction protection using loopback sites.
2. CloakfoxDNS.sys.mjs + dns-settings.js. Explicit system/encrypted-with-fallback/
   encrypted-only choices, HTTPS resolver and numeric bootstrap validation, cache
   clearing and no implicit resolver purchase/contact. Encrypted-only native guard
   prevents NativeLookup even when Firefox exclusions would normally fall back.
   Browser-wide policy; proxy destinations remain proxy-resolved. Test local DoH,
   refused resolver, DNS mode interactions and unchanged proxy routing.
3. Backup v2: include validated region/privacy policy, start pages, persona mode,
   and proxy references without credentials. Read v1. Missing proxy references
   restore blocked instead of downgrading to an unauthenticated/direct route.
   Encrypted envelope remains authenticated and backwards compatible. Test
   roundtrip, bad schemas, missing refs and exact seed retention.
4. Network probes: IPv4/IPv6, proxy failure/reconnect, speculative requests and
   advertised HTTP3/QUIC where the local fixture provides a meaningful control.
   Explicitly report surfaces a fixture cannot prove; no fake passing tests.
5. Shared settings packaging, startup hooks and host-mode generation. Existing
   config is retained; UI describes reload requirements until live behavior is
   proven. Font bundle claims match actual substitute fonts/licenses.

## Verification and completion

Each deliverable gets production-function tests before integration, disposable
profile probes and bounded read-only review. Root exclusively runs Firefox builds
and browser probes. Run Node suite, required Python/C++ checks, macOS native build,
new probes and affected regressions. Apply full final stack to fresh Firefox
155.0.1 source and compare native files. Record final evidence and external
activation prerequisites separately; no merge, commit, deployment or invented
production key is implied. Leave original checkout unchanged.
