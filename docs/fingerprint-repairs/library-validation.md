# Local upstream library validation

The installed `/Applications/Cloakfox.app` was tested headfully with unmodified CreepJS commit `10aa6724cd33a1015db1574211890518cd04f0cc` and FingerprintJS **5.3.0**. Bundle SHA-256 checksums, clean fixture Git state and npm lockfile integrity identify the exact tested code.

**48 library executions, 449 checks passed:** two libraries × eight cases × three page loads. Cases cover the default container, two containers with identical visible persona fields but distinct seed material, another top-level site, a Chrome identity on both sites, returning to the original site in a fresh tab, and a fresh protection-off browser control. The final tree also passes **247 JavaScript tests and 43 Python tests**, including five repository-safety and fixture-integrity tests.

The checks establish populated library outputs, reload stability of actual canvas images/audio and identity fields, cross-container/site canvas/audio separation, CSS/JS media-query agreement, window/worker OS and CPU consistency, Windows voice-family consistency, and differences from the native control. The fresh-tab return restores the original site's fingerprint. This does not test same-tab navigation, bfcache or restart behavior.

FingerprintJS 5.3 deliberately returns `skipped` for ordinary canvas images on modern Gecko, including the protection-off control. That is recorded explicitly. Its exported `getUnstableCanvasFingerprint(false)` API additionally collects real canvas images without modifying library code. CreepJS independently collects and compares all five actual canvas image fields.

## Detector findings retained

Passing isolation and stability tests **does not mean the browser is undetectable**. CreepJS still reports:

- Font measurement noise and unfamiliar rotated/ghost rectangle dimensions.
- Suspicious GPU capabilities/renderer values and pixel data; some runs explicitly detect modified canvas pixels.
- A SpiderMonkey/V8 engine mismatch with the Chrome identity, while identifying the engine as non-Chromium.
- An unavailable WebGPU `requestAdapter` path in this configuration.

CreepJS's aggregate canvas hash can vary because its randomized modification diagnostics vary. The actual PNG image fields and audio samples are checked separately and remain stable. The native control reports its real Mac platform and has none of the protected profile's CreepJS lie flags. These diagnostics remain visible in the raw results; the harness does not filter them out or redefine them as passes.

The reduced report, per-case warnings, exact bundle provenance and every assertion are in [library-validation.json](library-validation.json). Full library component objects remain locally in `tests/fingerprint/reports/library-audit-final/` and are excluded from Git.

## Reproduce

From the repository root:

```sh
python3 scripts/setup-fingerprint-libraries.py
CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox \
  REPORT_DIR=tests/fingerprint/reports/library-audit \
  /path/to/selenium-python tests/fingerprint/probe_fingerprint_libraries.py
```

Setup installs npm packages with lifecycle scripts disabled and fetches the pinned CreepJS checkout. It refuses to mutate a directory without its own matching Git repository, an unexpected origin, or a modified fixture. The library audit is an explicit opt-in test, excluded from the default local probe runner. It uses disposable profiles, grants no camera/microphone permissions and opens no assessment. Upstream CreepJS may attempt its ordinary STUN probe, subject to the browser's native protection.
