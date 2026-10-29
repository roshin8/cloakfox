# Exact-owner site-seed cache

Optimize repeated native geometry privacy calculations without changing outputs,
policy, thread ownership, or routing. Preserve existing GPU work and Chromium build.

- Cache parsed exact-owner overlay snapshots per thread, comparing current bytes on
  every access. Default owner zero remains exact; no ambient-container fallback.
- Bound retention to eight owners and 64 derivations per snapshot. Replace the
  whole immutable snapshot on any configuration change; retain in-flight references.
- Key derivations by the existing message (vector/base seed/canonical top-level site),
  within the exact owner and immutable config/secret. Keep HMAC and outputs unchanged.
- Re-evaluate live policy and time before any cached derivation. Do not cache errors.
- Prove hit suppression, changes, expiry, malformed inputs, eviction, worker isolation;
  run Firefox 159 local runtime probes and Amazon navigation/search with owner44's
  configuration in a disposable headless Container #02. Do not change the personal
  session or credentials. Compare old and rebuilt binaries with identical settings.
- Independent scoped code review, appropriate regression suites, bounded low-priority
  Firefox build. No Chromium changes, checkpoint deletion, commit or install implied.
