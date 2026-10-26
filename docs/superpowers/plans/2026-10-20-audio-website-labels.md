# Audio website labels

Implement in the existing Firefox 158 worktree. Add microphone and speaker per-device names and default/numbered/custom fallback controls in Audio & media, matching camera validation, persistence and global scope. Keep capture permissions, device IDs and screen sharing unchanged.

1. Add native/UI runtime regression probe; observe failure before implementation.
2. Add a chrome-only physical audio inventory API; extend the native anonymization path with independently scoped microphone/speaker preference maps and fallback labels. Preserve camera and display capture paths.
3. Reuse the camera settings controller for three kinds and add parallel microphone/speaker sections.
4. Run native probes, label scope regression and UI save/reset/reload validation. Review patch consistency and privacy boundaries.
5. Build and update only the necessary installed native library/settings resources, sign and verify; restart with user timing approval and show controls.

Validation: native Firefox 158 build passed; audio probe failed before implementation (missing chrome inventory API), then passed against clone and installed app. It checks custom fallbacks, microphone/speaker raw-ID overrides, stable public IDs, ChromeOnly exposure, UI visibility/save/reset/validation/reload, and required preference defaults. Shared controller unit suite: 8/8. Camera runtime probe passes after moving the old cross-compartment expando placeholder fixture to direct controller tests. Native capture-label scope regression passes.

Runtime finding: default string preferences must ship with the app, or Firefox sanitizes dynamic strings before content-process delivery. All six new defaults were appended to the installed config. Installed app signed and verified; backups in /Applications/.cloakfox-audio-labels-20261020. Restart timing requested to avoid interrupting an active assessment recording/call.
