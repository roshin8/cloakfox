# SDD ledger — plan: docs/superpowers/plans/2026-09-07-daily-driver-privacy.md

Authorization: user approved the audit recommendations (“work on these”). Existing Firefox155 worktree retained. No commits or external publishing requested.

Ruling: Deliver independent subsystems incrementally under the accepted audit design; no additional approval ceremony for already-authorized reversible code work. Production signing/hosting cannot be represented as complete without a real configured trust root and owner-controlled distribution.

Preflight: tasks 1 and 2 have disjoint production files. Task 3/4/7 share settings UI and must coordinate serialized integration. Task 5 touches native patch/config readers and must be integrated after task1's migration contract. Task8 release workflow is independent until final build integration. All changes preserve RFP=false and containers=true.

## Implementation checkpoint

- Task 1: implementation and live verification pass. Engine-derived identity matches DOM/HTTP; legacy migration retains master seed and explicit overrides.
- Task 2: protective defaults and user choices pass startup/restart probe. Actual Google list-provider key is absent; UI reports that separately.
- Task 3: explicit data clearing implemented; independent review required strict SessionSaver/SessionFile error propagation, scoped pruning of every native restore fallback, awaited service-worker unregistration, and preservation of ambiguous/shared permission records. Focused regressions pass; final rebuilt live check pending.
- Task 4: optional IP lookup defaults off; opt-out aborts outstanding requests and prevents new fallback requests. Per-container routing, native RTC controls, typed fail-closed policy and numeric IPC epochs implemented. Real Necko bypass exposed advisory-filter limitations; final native callback guard now rejects missing required proxy. Final rebuild/runtime check pending.
- Task 5: initial live site probe passes reload/subdomain stability, distinct publishers, frames and workers. Independent review added main-thread-prepared atomic font snapshots and numeric invalidation epoch for Stylo/layout cache correctness; final rebuilt check pending.
- Task 6: official pinned signed uBlock Origin staged/packaged; live installation/signature and user disable/removal persistence pass. Geckodriver's own disabled-addon/update prefs are explicitly restored to verified production defaults only for this test.
- Task 7: exact-host native rules, temporary cleanup/recovery, encrypted settings export/import and native backup availability implemented. Review fixes for whole-window closure and concurrent-rule rollback underway; live workflow probe ready.
- Task 8: offline signed release metadata verification and release readiness UI implemented; 11 release tests pass. Production automatic updates remain disabled pending real signer/trust root and owner-controlled hosting. Safe Browsing provider configuration is also owner-dependent.
- Task 9: first complete native build passed and initial 78-patch stack applied cleanly. Final additions bring new native guard and flags API; a rebuild and fresh stack reconciliation are underway. Latest full Node run: 94 passed.

Ruling: Keep production updates disabled and report missing provider configuration in the settings UI — enabling test certificates or claiming working protection from preferences would be incorrect; deployment remains owner-dependent.
Ruling: Preserve ambiguous/shared site permissions when forgetting default-container data — historical permission records cannot be safely assigned to a container; these permissions remain until the user changes them separately.
Ruling: Offer encrypted identity-settings backup separately from native full-profile backup — it preserves named-container settings without pretending to include cookies/passwords/history; native backup availability is checked at runtime.
Ruling: Reject required-proxy requests when Firefox removes the proxy under its native bypass rules — local/bypass destinations can fail instead of connecting directly; ordinary inherited routing remains unchanged.


## Final verification

Tasks 1–7: complete; implementation, independent review fixes and disposable-profile verification passed. Task 8: release verification/support and status complete; production deployment/provider activation still requires owner configuration. Task 9: complete for macOS arm64; 80-patch fresh application, 183 patched files and 48 addition/settings mirrors match; 100 Node tests, Python regressions, 10 daily probes, 13 compatibility probes and 4 HTTP/3 preference tests pass. See README.md for detailed evidence and platform limits. No commit, merge, push, signing-key creation or production publishing was performed.
