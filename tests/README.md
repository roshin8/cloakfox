# Cloakfox Tests

Two live suites. Both run in CI (`.github/workflows/build.yml`).

## `fingerprint/` — the real suite

Selenium + geckodriver probes against a **built binary**, plus unit tests.

```bash
export CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox   # macOS
export CLOAKFOX_BIN=/path/to/cloakfox                               # Linux
python tests/fingerprint/run_all.py
```

- `probe_*.py` — one vector per file; `run_all.py` runs them all. These are the
  only guard against **silent** spoofing regressions, so a probe that cannot
  measure something must SKIP, never pass. See `probe_stealth` (WebGL
  no-context) and `probe_actors` (absent WebGPU) for the pattern.
- `test_*.mjs` — `node --test`, no browser needed.
- `test_*.py` — pytest. Some need `CLOAKFOX_BIN` and skip without it.

Anything seeding `cloakfox.s.cloak_cfg_*` must include `fonts` and
`fonts:spacing_seed`, or `CloakfoxSeedSync.needsCfgRebuild()` replaces the
injected config with a random persona before the probe reads anything. That
silently broke six probes — two failed outright, three kept passing while
testing nothing (two random personas differ, which satisfies a
"values changed" assertion).

## `build/` — build-script tests

Shell + pytest checks for `scripts/` behaviour (font renaming, Assets.car
clobbering, copy-additions idempotency). No browser required.

## Not Playwright

Playwright's Firefox driver speaks the Juggler protocol and needs a
Juggler-patched binary. Cloakfox does not ship one, so Playwright launches
time out on a handshake that never comes.

The inherited Playwright suites (`async/`, `async_imp/`, `assets/`,
`golden-firefox/`, `conftest.py`, `server.py`, and friends) were removed —
they came from the Camoufox import, never ran on this branch, and
`conftest.py` imported playwright at collection time, which killed pytest for
the live tests too. Recover from git history if Playwright support ever
returns.
