# Full fpgen GPU catalog expansion

User-approved scope: expand validated profiles from the entire pinned fpgen model; preserve toggle behavior, per-container ownership, BrowserForge compatibility and existing privacy protections. Test on Firefox 159 headlessly and independently review. Do not change installed apps, personal profiles, Chromium inputs/builds, or existing checkpoints.

1. Import every browser/platform/GPU/WebGL1/WebGL2 conditional path from the verified archive, preserving observations and recording incomplete or inconsistent records separately. Keep the original Firefox corpus reproducible.
2. Replace the fixed observed shortlist with deterministic admission from the full corpus. Admit only complete coherent capability pairs executable by the canonical backend; preserve old codes and unsupported-record explanations. Do not fabricate measured values, weaken readback restrictions, enable timers/debug shaders, or fall back to host hardware.
3. Keep generated JS and native registries in agreement, explicit OS binding and exact owner/secret validation. Update settings documentation to describe actual dataset coverage and limits. Add reproducibility, rejection, matching, privacy and container-isolation tests.
4. Build a separate Firefox159 test app and run all added profiles through native pages/workers, resource operations, toggles and privacy boundaries, plus focused existing regressions. Preserve raw evidence.
5. Independent code review, resolve actionable findings, rerun affected checks and summarize verified counts/limits.

Task interfaces: importer owns new full corpus and its provenance; generator consumes it and emits immutable JS/C++ registries; existing native context admission remains mandatory; runtime tests exercise that same generated catalog. All tasks agree that source membership alone does not grant runtime admission.
