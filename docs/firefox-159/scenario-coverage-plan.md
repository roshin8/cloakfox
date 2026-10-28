# Firefox 159 privacy scenario coverage

Target: every current Firefox privacy feature and regression scenario, not native
line/branch coverage. Retain raw failures and hardware exclusions; do not call
mapped tests or test counts proof of every possible browser execution path.

Constraints: headless only; disposable profiles; preserve sandbox, blocklists,
production preferences, installed apps, Chromium inputs/build, and checkpoints.

- [x] Audit all nine deferred probes against current source and explicit binary.
- [x] Verify native WebGPU with supported `layers.gpu-process.allow-headless` in
  disposable test profiles, without force-enabling blocklisted hardware.
- [x] Rerun all four actual GPU corpora (compute, limits, owner and provenance).
- [x] Run both pinned library audit modes with WebGPU explicitly enabled.
- [x] Run configured synthetic region/permission and cross-container variance.
- [x] Run both cpp-first probes against explicit current binary (no DMG mount).
- [x] Run signature selection plus independent headless Chrome wire references.
- [x] Replace obsolete camera nickname UI test with actual synthetic picker test;
  verify original source remains in browser label, website labels exclude nickname,
  reset restores source, and profile restart preserves mapping.
- [x] Preserve machine-readable evidence and exact remaining scenario exclusions.
- [x] Review test changes and run targeted regression tests.

Two original scenarios cannot be verified fully under the headless-only contract:
real appearance relaunch uses NSWorkspace and can activate an app; real macOS
capture/permission chooser integration requires native UI. Headless substitutes
must be described as partial coverage, never counted as those end-to-end passes.

Known features already covered by existing probes include master-off, per-owner
and per-site identity, workers/realm startup, invalid ownership, native/resource
validation, media consent, synthetic media, cache/storage isolation, network
headers/transports/proxy routes, timing, fonts, canvas and geometry. This statement
is a feature map, not a claim that every combination of all settings is tested.
