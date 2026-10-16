# Required upstream fingerprint library audits

Implement directly; user waived plan review. Preserve ongoing local native build, SDKs and pending identity changes.

- [x] Add strict probe outcome policy: exit2 fails by default; only an exact probe+platform allowance with reason and unexpired date can pass it. No default allowances. Preserve JSON verdicts, nonzero failures and failed setup behavior.
- [x] Reuse pinned CreepJS/FingerprintJS fixture verification, make Gecko audit portable across hosted macOS/Linux, and add Chromium audit with disposable native contexts, enabled/native controls, repeated collection, site/container separation and return stability. Keep upstream detector flags/raw results; Chromium audio masking is not implemented and must not be advertised as covered isolation.
- [x] Make fixture setup and library audit hard CI gates for both engines. Upload diagnostics on failure. Validate fixture integrity, actual negative/mutation cases and real browser runs on existing apps without duplicating the active native pipeline. Test workflow syntax, focused review, commit explicit files and push. Push these gates and the necessary CEF archive-patch prefix repair together; the previous hosted source job has failed before compilation. Preserve the independent local native build.

Runtime audit success means the asserted consistency/collection/isolation contracts passed; it does not certify undetectability or privacy parity. Timeouts, absent APIs required by the contract and missing samples fail. Exceptions are reviewable repository policy, never automatic fallbacks based on observed failure.

Review ledger: audio sentinels and seed-dependent native controls reproduced failing unit tests, fixed and green. Initial native shell last-window closure reproduced in real audit, fixed with blank owner window; final Chromium36executions/440checks pass. Gecko48/456 pass. Policy3/3, contract4/4, fixture-integrity5/5, CIhelpers8/8, actual pinned tarball patch replay and actionlint pass. Hosted end-to-end verification remains asynchronous and is tracked by the existing periodic watcher. No deferred review findings.
