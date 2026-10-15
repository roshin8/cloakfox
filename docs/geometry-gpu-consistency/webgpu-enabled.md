# Installed WebGPU-enabled library verification

Tested `/Applications/Cloakfox.app/Contents/MacOS/cloakfox`, runtime BuildID `20261015160908`, on macOS arm64. No product rebuild or personal profile/settings change was needed. Disposable profiles explicitly enabled `dom.webgpu.enabled`, set each protected owning container's `navigator:webgpu:disabled=false`, and enabled the existing canonical rendering pipeline. Native controls ran with the master protection off.

## Results

- **464/464 checks**, eight cases × two libraries × three reloads = **48 library executions**. Pinned unmodified CreepJS and FingerprintJS fixtures retain the same checksums as the earlier report.
- CreepJS collected a nonempty WebGPU limit object and adapter result in every case and reload. Adapter and limits were stable across reloads. All 21 protected CreepJS samples returned empty vendor/architecture/description/device strings; those fields were also empty in the Firefox native control, so this observation alone does not establish Cloakfox masking efficacy.
- **103/103 separate GPU corpus checks passed** with WebGPU enabled, covering actual adapter/device creation, compute and mapping, render/upload validation, presentation, reload consistency and canonical unknown-input/readback guards. This includes both native controls and protected legacy/canonical modes.
- Protected CreepJS retains `unknown rotate dimensions` and WebGL `suspicious gpu` / `suspicious capabilities`. Chromium UA cases retain the previously documented Gecko engine mismatch. Enabling WebGPU did not introduce another identity warning in this run. These results do not imply undetectability or zero fingerprint entropy: WebGPU limits remain page-visible while the API is enabled.

FingerprintJS 5.3.0 does not independently probe WebGPU. Its full suite was rerun with the API enabled to catch interactions; the direct library WebGPU observation comes from CreepJS.

Evidence: [library summary](libraries-webgpu-enabled/summary.json), [complete results](libraries-webgpu-enabled/results.json), [per-sample adapter/limits and warnings](libraries-webgpu-enabled/observations.json), [GPU runtime checks](webgpu-enabled-native/probe_canvas_canonical_gpu/result.json).

Reproduce using the installed app and geckodriver with the existing fixture environment:

```sh
LIBRARY_WEBGPU_ENABLED=1 CLOAKFOX_TEST_CANVAS_PIPELINE=1 \
  REPORT_DIR=/tmp/cloakfox-libraries-webgpu \
  python tests/fingerprint/probe_fingerprint_libraries.py
CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox \
  CLOAKFOX_HEADFUL=1 REPORT_DIR=/tmp/cloakfox-webgpu-runtime \
  python tests/fingerprint/probe_canvas_canonical_gpu.py
```

Use the normal headed browser: Firefox headless mode can disable GPU processes. No blocklist overrides were added.
