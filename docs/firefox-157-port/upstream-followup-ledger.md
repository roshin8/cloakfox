# Upstream follow-up ledger

Preflight: isolated branch codex/firefox-157-port, prior clear-overrides changes preserved. Current upstream patch contents verified unchanged. Full native rebuild is incremental; 22 GiB available.
Task 1: started; behavioral regressions precede native edits.
Task 1: native build and source checks pass; live WebGL, audio, owner/container and speech controls now pass. Initial failing regressions recorded in runtime-red/source-red; intermediate renderer and color-mask failures were fixed with the covering probes retained.
Task 2: resource runtime/startup and manifest checks pass. Rust pc-to-unknown normalization was already present; regression confirms exact vendor and Windows ABI choices remain valid.
Task 3: 107 patches replay from 224 pristine targets with no offset/fuzz/native-source drift. Node 218/218 and Python source suite 17 pass; 16 opt-in network/math tests skipped without a binary environment (not claimed as verified). Preserved generation UI regression passes. Packaging and final review pending.
