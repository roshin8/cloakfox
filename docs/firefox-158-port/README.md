# Cloakfox Firefox 158 port

Start with [verification.md](verification.md) for results, reruns and coverage limits, and [code-review.md](code-review.md) for the independent review.

- Source/build reproducibility: `157-input-manifest.json`, `157-native-baseline-parity.json`, `final-replay.json`, `final-source-verification.json`, `build-environment.json`, `build-identity.json`.
- Final regression summaries: `runtime-results.json`, `desktop-results.json`, `packaged-results.json`.
- Unit evidence: `node-verified.log`, `pytest-verified.log`, `network-unit-baseline.log`, `blocker-unit-baseline.log`, `release-unit-final.log`.
- Package: `package-identity.json` and `package.log`.
- Independent native references: `network-adapter-native-tls-h2.json`, `network-adapter-native-quic-h3.json`, `stock-native-features.json`.

Detailed per-probe red/green artifacts and disposable fixtures are retained locally under `tests/fingerprint/reports/158-port/` (ignored by Git). Earlier failed build/test logs are intentionally retained; their names and resolutions are described in the verification report. `progress.md` is chronological and includes superseded intermediate states.
