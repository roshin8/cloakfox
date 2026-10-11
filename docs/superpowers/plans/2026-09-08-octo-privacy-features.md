# Octo-inspired daily browser features

Accepted scope: docs/octobrowser-feature-audit-2026-09-08.md, first five items.
Work only in codex/firefox-155-compat; preserve existing uncommitted port.

1. Region (independent agent): validated versioned manual region record; document/worker locale and request headers, timezone, coarse permission-gated location. Remove existing geolocation auto-permission shortcut. Unit tests and disposable-profile runtime probe.
2. Proxy manager (independent agent): named metadata catalog, LoginManager credentials, per-container references, isolated auth and fail-closed diagnostics. Test credentials never enter prefs/export and proxy failures never reach destination directly.
3. Templates (independent agent): strict settings-only records, fresh seeds, persona index, region/policy and proxy reference, validated start pages and temporary creation. Test independence and rollback.
4. Shared integration (root): apply region and policy after low-level overrides in all config writers; expose refreshContainerConfig. Package new modules and UI sections. Preserve seeds on every settings edit.
5. Privacy policy (root): standard/strict/compatibility presets, geometry/canvas/audio per schemeful top-level site exceptions with expiry and removal. Gate existing native derivation without changing its HMAC inputs; geometry gets a distinct policy gate while retaining its old canvas seed. Verify same seed before/after reset and separate container/site decisions.
6. Consistency inspector (root): compare configured fields and actual window/worker observations. Label contradictions, heuristic concerns, and unavailable measurements separately; targeted reversible config repair with stale-state checks, no identity/data reset.
7. Integration verification: Node suite, native build, targeted live probes including isolation/permission/407 behavior, existing daily-driver regressions, fresh full patch-stack application and exact source comparison. Document limitations and evidence. No merge or commit requested.

Shared interfaces: CloakfoxRegions applyRegion/getRegion/setRegion/validateRegion;
CloakfoxPrivacyPolicy applyPrivacyPolicy/getPrivacyPolicy/setPrivacyPolicy/validatePrivacyPolicy;
SeedSync refreshContainerConfig(id). UI modules mount their own dedicated cfx-* section.
Native owners snapshot each changed file before edits into /tmp/cloakfox-octo-before;
root emits one follow-up patch after integration and appends patch order.
