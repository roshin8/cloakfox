> Maintained Gecko159 source comparison, refreshed 2026-10-27. The companion runs alongside Gecko; shared settings/tabs and full privacy parity remain pending.

# Chromium privacy port inventory

Baseline: Firefox 159.0 source port on `codex/firefox-159-port`. The [current source manifest](gecko159-inventory.json) records exact patch/module/UI hashes; the retained Gecko158 manifest is historical. Source replay and source tests do not attest native Chromium coverage or a completed Firefox runtime build.

The original binary SDK remains unpatched. The source-built companion has partial native canvas/worker/GPU privacy plus the v1 shared config foundation. `privacyPatched` stays false. Current config tests use actual native hooks, owned loopback fixtures and disposable profiles; they do not establish parity for the other groups.

Gecko158 additions missing from the old157 checklist include AudioWorklet privacy, CSS media exposure, request client hints, WebCodecs, coherent Chromium identities, backed WebGL capabilities/profiles, first-draw font fallback, canonical canvas backing/text and CPU/GPU producer provenance through the complete renderer. Chromium's narrower readback transforms do not implement that canonical renderer or those general capability policies.

## Native implementation groups

| Existing feature group | Chromium work needed | Prototype status |
|---|---|---|
| Container/site persona seeds, overrides, generation checkbox | Backend-independent config plus BrowserContext/StoragePartition ownership | V1 shared controller model/store, master/options/overrides, seed regeneration and clear-overrides supported. Native applyConfig/revision acknowledgement precedes navigation; seed reaches frames and all worker types. Context changes require companion restart. Shared Gecko adapter/UI and BrowserForge persona generation remain pending |
| Navigator, UA/client hints, platform/device capabilities | Native Blink navigator/worker hooks; coherent real engine version | Native hardwareConcurrency/deviceMemory and high-entropy UA-hint reduction implemented behind identityPrivacyVersion:1; source-framework/runtime verification passed on macOS (2026-10-16). Real OS/brand/version retained; cross-OS personas remain pending |
| Screen/window geometry, letterboxing, CSS, fonts | Blink layout/screen/CSS/font selection and browser display services | Native panel geometry (size and available rect) and a standard 24-bit SDR colour profile presented from the owner-provided persona presentation, so `window.screen`, the CSS `color`/`dynamic-range` queries and CSS device metrics agree per container instead of exposing the host panel (30-bit HDR here); the group has its own `display` option and a `displayPrivacyVersion` capability so an older framework rejects display fields instead of ignoring them; verified 2026-10-17. Colour gamut and layout-zoom/`deviceScaleFactor` deliberately keep the retained host display profile; letterboxing and font selection remain unported |
| Canvas/OffscreenCanvas, WebGL, WebGPU | Native readback and device information hooks, worker ownership | Partial native opaque RGBA8 Canvas2D/export (not Gecko158 canonical rendering/provenance) and WebGL direct/PBO readback; document/dedicated/shared/service-worker tests pass. GPU identifying metadata reduced; Metal RGBA8/BGRA8/sRGB WebGPU copy-time pixel noise plus optional all-READ-map denial. Other backends/formats and general capabilities remain uncovered |
| Audio, codecs, device labels and media permissions | Blink audio/media paths and browser permission/capture services | Permission requests denied; AudioWorklet/audio noise, WebCodecs and persona media masking not ported |
| Locale, timezone, geolocation | Blink/V8 Intl and permission-aware location services | Any canonical BCP 47 language list (1-4 distinct tags) and any canonical IANA zone the engine's own ICU can render are applied natively to frames and all worker types, with native preference restoration; a persona the engine cannot render is refused before any container context exists, instead of aborting a renderer or inheriting the host language/zone. Sampling still draws from a plausible regional preset table. Runtime verification passed on macOS (2026-10-16 bounded presets; 2026-10-17 widened values). Geolocation presentation remains unported |
| Performance clocks, entries, scheduling and Math | Blink timing/scheduling and V8 native math implementation | Not ported |
| Keyboard, gamepad, MIDI, feature detection | Blink device/input exposure and permission services | Not ported |
| WebRTC, IP discovery and DNS/proxy controls | Chromium WebRTC and NetworkContext policies, explicit consent and isolation | Not ported |
| Storage, network connections, TLS sessions, H2/H3 and WebSockets | Independent native profiles, NetworkContexts, cache/ticket/proxy tests | Website storage tested; authenticated network isolation pending |
| Clipboard, notifications, EME, focus/name, persistence flags | Native Blink/permission policies and browser settings | Existing option semantics not ported |
| Tracking/query stripping, bounce protection, site exceptions/presets | Browser/network policy integration | Not ported |
| Container/settings UI, appearance, bookmarks/passwords, security updates | Shared controller and engine capability mapping; engine-owned sensitive stores | Not integrated |

<!-- BEGIN GENERATED GECKO INVENTORY -->
## Active Gecko 159.0 source inventory

Canonical patch resolver: 171 active patches. These are rewrite/triage inputs, not a count of missing Chromium features. The source manifest records exact hashes and catches later source drift.

Canvas/GPU/config entries have partial Chromium equivalents described above. Gecko UI, branding, build and compatibility patches can be engine-specific; no patch is mechanically applied to Chromium.

- `patches/all-addons-private-mode.patch`
- `patches/anti-font-fingerprinting.patch`
- `patches/audio-context-spoofing.patch`
- `patches/audio-fingerprint-manager.patch`
- `patches/browser-init.patch`
- `patches/builtin-extension.patch`
- `patches/canvas-spoofing.patch`
- `patches/chromeutil.patch`
- `patches/clipboard-spoofing.patch`
- `patches/codecs-spoofing.patch`
- `patches/document-lastmodified-spoofing.patch`
- `patches/config.patch`
- `patches/cross-process-storage.patch`
- `patches/domrect-spoofing.patch`
- `patches/fingerprint-injection.patch`
- `patches/font-hijacker.patch`
- `patches/font-list-spoofing.patch`
- `patches/font-bundle-packaging.patch`
- `patches/system-font-spoofing.patch`
- `patches/force-default-pointer.patch`
- `patches/geolocation-spoofing.patch`
- `patches/http2-fingerprint-spoofing.patch`
- `patches/indexeddb-spoofing.patch`
- `patches/locale-spoofing.patch`
- `patches/macos-sandbox-crash-fix.patch`
- `patches/media-capabilities-spoofing.patch`
- `patches/media-features-spoofing.patch`
- `patches/media-device-spoofing.patch`
- `patches/mediasource-istypesupported-spoofing.patch`
- `patches/navigator-extra-spoofing.patch`
- `patches/cloakfox-webgpu-null-safety.patch`
- `patches/navigator-spoofing.patch`
- `patches/network-patches.patch`
- `patches/notification-spoofing.patch`
- `patches/permissions-spoofing.patch`
- `patches/range-domrect-spoofing.patch`
- `patches/screen-orientation-spoofing.patch`
- `patches/screen-spoofing.patch`
- `patches/shadow-root-bypass.patch`
- `patches/speech-voices-spoofing.patch`
- `patches/storage-estimate-spoofing.patch`
- `patches/svg-bbox-spoofing.patch`
- `patches/svg-geometry-spoofing.patch`
- `patches/svg-metrics-spoofing.patch`
- `patches/text-metrics-spoofing.patch`
- `patches/timing-jitter-spoofing.patch`
- `patches/timezone-spoofing.patch`
- `patches/vibration-spoofing.patch`
- `patches/visual-viewport-spoofing.patch`
- `patches/voice-spoofing.patch`
- `patches/webgl-spoofing.patch`
- `patches/webgl-readback-noise.patch`
- `patches/websocket-spoofing.patch`
- `patches/webrtc-ip-spoofing.patch`
- `patches/cloakfox-webrtc-network-policy.patch`
- `patches/window-name-spoofing.patch`
- `patches/cloakfox-enabled-staticpref.patch`
- `patches/cloak-config-webidl.patch`
- `patches/unified-maskconfig.patch`
- `patches/http3-fingerprint-spoofing.patch`
- `patches/http2-profile-webidl.patch`
- `patches/cpp-first-pref-reader.patch`
- `patches/cpp-first-pref-migration.patch`
- `patches/cpp-first-actors-registration.patch`
- `patches/cpp-first-about-cloakfox.patch`
- `patches/cpp-first-error-stack-depth.patch`
- `patches/cpp-first-worker-spoofers.patch`
- `patches/cloakfox-optional-assets-car.patch`
- `patches/worker-container-identity.patch`
- `patches/cloakfox-letterboxing.patch`
- `patches/cloakfox-container-forget.patch`
- `patches/cloakfox-scoped-data-clear.patch`
- `patches/cloakfox-strict-proxy-guard.patch`
- `patches/site-fingerprint-isolation.patch`
- `patches/cloakfox-upstream-hardening.patch`
- `patches/cloakfox-region-policy-proxy.patch`
- `patches/cloakfox-privacy-completion.patch`
- `patches/cloakfox-window-activity.patch`
- `patches/cloakfox-appearance.patch`
- `patches/cloakfox-clipboard-signals.patch`
- `patches/cloakfox-pointer-activity.patch`
- `patches/cloakfox-hover-activity.patch`
- `patches/cloakfox-native-worker-math.patch`
- `patches/cloakfox-exported-function-identity.patch`
- `patches/cloakfox-live-worker-math.patch`
- `patches/cloakfox-bundled-font-rendering.patch`
- `patches/cloakfox-user-agent-data.patch`
- `patches/cloakfox-math-data-correctness.patch`
- `patches/cloakfox-math-data-toggle.patch`
- `patches/cloakfox-hackerrank-media-recovery.patch`
- `patches/cloakfox-coderpad-media.patch`
- `patches/cloakfox-appearance-profile.patch`
- `patches/cloakfox-screen-presentation.patch`
- `patches/cloakfox-testdome-screen-management.patch`
- `patches/cloakfox-window-management-permission.patch`
- `patches/cloakfox-screen-orientation-events.patch`
- `patches/cloakfox-webgl-live-state-followup.patch`
- `patches/cloakfox-audio-analyser-copy-followup.patch`
- `patches/cloakfox-speech-error-followup.patch`
- `patches/cloakfox-stock-resource-followup.patch`
- `patches/cloakfox-windows-manifest-followup.patch`
- `patches/performance-timeline-timing.patch`
- `patches/cloakfox-media-device-privacy.patch`
- `patches/cloakfox-hdr-exposure-privacy.patch`
- `patches/cloakfox-network-profile.patch`
- `patches/cloakfox-network-conformance.patch`
- `patches/cloakfox-graphics-gap-fix.patch`
- `patches/cloakfox-fontface-native-loading.patch`
- `patches/cloakfox-font-whitelist-parent.patch`
- `patches/cloakfox-inherited-realm-privacy.patch`
- `patches/cloakfox-native-realm-presentation.patch`
- `patches/cloakfox-language-identity.patch`
- `patches/cloakfox-request-identity-and-mask-storage.patch`
- `patches/cloakfox-websocket-privacy.patch`
- `patches/cloakfox-websocket-headers.patch`
- `patches/cloakfox-proxy-resolver-errors.patch`
- `patches/cloakfox-turn-proxy-privacy.patch`
- `patches/cloakfox-privacy-enforcement.patch`
- `patches/cloakfox-screen-permission-effective-state.patch`
- `patches/cloakfox-hackerrank-actor-process-safety.patch`
- `patches/cloakfox-pointer-hover-retention.patch`
- `patches/cloakfox-firefox158-compat.patch`
- `patches/cloakfox-audioworklet-privacy.patch`
- `patches/cloakfox-css-media-privacy.patch`
- `patches/cloakfox-client-hints-headers.patch`
- `patches/cloakfox-webcodecs-privacy.patch`
- `patches/cloakfox-chromium-identity-coherence.patch`
- `patches/cloakfox-canvas-api-consistency.patch`
- `patches/cloakfox-webgl-capability-consistency.patch`
- `patches/cloakfox-webgl-backed-capacities.patch`
- `patches/canvas-render-privacy.patch`
- `patches/cloakfox-webgl-backend-profile.patch`
- `patches/canvas-canonical-backing.patch`
- `patches/cloakfox-font-fallback-first-draw.patch`
- `patches/canvas-canonical-text.patch`
- `patches/canvas-pixel-provenance.patch`
- `patches/canvas-gpu-provenance.patch`
- `patches/librewolf/bootstrap.patch`
- `patches/librewolf/custom-ubo-assets-bootstrap-location.patch`
- `patches/librewolf/dbus_name.patch`
- `patches/librewolf/devtools-bypass.patch`
- `patches/librewolf/disable-data-reporting-at-compile-time.patch`
- `patches/librewolf/mozilla_dirs.patch`
- `patches/librewolf/urlbarprovider-interventions.patch`
- `patches/canvas-complete-renderer.patch`
- `patches/cloakfox-native-engine-host.patch`
- `patches/cloakfox-camera-nicknames.patch`
- `patches/cloakfox-neutral-camera-labels.patch`
- `patches/cloakfox-capture-label-scope.patch`
- `patches/cloakfox-audio-website-labels.patch`
- `patches/cloakfox-camera-exposure.patch`
- `patches/cloakfox-microphone-exposure.patch`
- `patches/cloakfox-macos-stable-toolbar.patch`
- `patches/cloakfox-macos-colored-window-buttons.patch`
- `patches/cloakfox-macos-bundle-icon.patch`
- `patches/cloakfox-site-data-container-scope.patch`
- `patches/cloakfox-trust-panel-site-data-scope.patch`
- `patches/cloakfox-container-site-cache.patch`
- `patches/cloakfox-apple-linker-detection.patch`
- `patches/cloakfox-system-document-viewport.patch`
- `patches/cloakfox-coherent-gpu-catalog.patch`
- `patches/cloakfox-reference-gpu-profiles.patch`
- `patches/cloakfox-canonical-layout-geometry.patch`
- `patches/cloakfox-reference-backend-integrity.patch`
- `patches/cloakfox-touch-document-policy.patch`
- `patches/cloakfox-canonical-mac-texture-limits.patch`
- `patches/cloakfox-canonical-font-decoration.patch`
- `patches/cloakfox-observed-gpu-execution.patch`
- `patches/cloakfox-container-colors.patch`
- `patches/cloakfox-container-tab-accents.patch`
- `patches/cloakfox-container-label-spacing.patch`

## Optional/privacy preference inventory

Literal cloakfox.opt / cloakfox.webrtc names plus dynamically constructed userOpt names from maintained Gecko modules, defaults and HTML. These are Gecko names; matching semantics remain pending unless the group table says otherwise.

- `cloakfox.opt.canvas_render_privacy`
- `cloakfox.opt.clipboard_disabled`
- `cloakfox.opt.clipboard_masking`
- `cloakfox.opt.container_rendering_profiles`
- `cloakfox.opt.eme_disabled`
- `cloakfox.opt.focus_masking`
- `cloakfox.opt.gpu_backend_profiles`
- `cloakfox.opt.hdr_masking`
- `cloakfox.opt.math_constants_noise`
- `cloakfox.opt.math_data_noise`
- `cloakfox.opt.mediadevices_disabled`
- `cloakfox.opt.notification_permission_disabled`
- `cloakfox.opt.storage_persisted_disabled`
- `cloakfox.opt.timer_high_precision_jitter`
- `cloakfox.opt.timer_quantization_off`
- `cloakfox.opt.webgl_typed_readback_disabled`
- `cloakfox.opt.websocket_disabled`
- `cloakfox.opt.window_name_disabled`
- `cloakfox.webrtc.ip_lookup.enabled`
- `cloakfox.webrtc.protect_proxy`
- `cloakfox.webrtc.protect_unready`

## Settings surface inventory

All id/data-pref bindings from component HTML, including secondary settings panels. This is a UI audit checklist; the Chromium companion does not expose the Gecko settings UI. Dynamic panels/API fields still require manual review.

- `allow-website`
- `cfx-appearance-permissions`
- `cfx-appearance-restart`
- `cfx-appearance-reveal`
- `cfx-appearance-status`
- `cfx-browser-families`
- `cfx-browser-family-help`
- `cfx-camera-configuration`
- `cfx-camera-device-form`
- `cfx-camera-device-name`
- `cfx-camera-device-refresh`
- `cfx-camera-device-reset`
- `cfx-camera-device-save`
- `cfx-camera-device-status`
- `cfx-camera-exposure-controls`
- `cfx-camera-exposure-devices`
- `cfx-camera-exposure-form`
- `cfx-camera-exposure-heading`
- `cfx-camera-exposure-help`
- `cfx-camera-exposure-mode`
- `cfx-camera-exposure-refresh`
- `cfx-camera-exposure-save`
- `cfx-camera-exposure-status`
- `cfx-camera-website-custom`
- `cfx-camera-website-custom-form`
- `cfx-camera-website-custom-help`
- `cfx-camera-website-device`
- `cfx-camera-website-heading`
- `cfx-camera-website-help`
- `cfx-camera-website-label`
- `cfx-camera-website-save`
- `cfx-camera-website-status`
- `cfx-check-similarity`
- `cfx-chromium-presentation`
- `cfx-chromium-presentation-help`
- `cfx-chromium-presentation-status`
- `cfx-chromium-status`
- `cfx-clear`
- `cfx-clear-overrides`
- `cfx-colored-inactive-buttons`
- `cfx-consistency-inspector`
- `cfx-container-gpu-status`
- `cfx-container-rendering-settings`
- `cfx-container-rendering-status`
- `cfx-container-select`
- `cfx-dns-settings`
- `cfx-enabled`
- `cfx-engine-settings`
- `cfx-engine-title`
- `cfx-engine-version`
- `cfx-firefox-appearance`
- `cfx-font-custom`
- `cfx-font-effective`
- `cfx-font-generated`
- `cfx-font-reset`
- `cfx-font-save`
- `cfx-font-settings`
- `cfx-font-source`
- `cfx-font-status`
- `cfx-forget-data`
- `cfx-forget-status`
- `cfx-generate-help`
- `cfx-generate-new`
- `cfx-generation-clear-overrides`
- `cfx-headline-text`
- `cfx-help-clipboard-masking`
- `cfx-help-focus-masking`
- `cfx-help-math-data-noise`
- `cfx-identity-help`
- `cfx-identity-maintenance`
- `cfx-identity-status`
- `cfx-ip-lookup`
- `cfx-maintenance-title`
- `cfx-microphone-configuration`
- `cfx-microphone-device-form`
- `cfx-microphone-device-name`
- `cfx-microphone-device-refresh`
- `cfx-microphone-device-reset`
- `cfx-microphone-device-save`
- `cfx-microphone-device-status`
- `cfx-microphone-exposure-controls`
- `cfx-microphone-exposure-devices`
- `cfx-microphone-exposure-form`
- `cfx-microphone-exposure-heading`
- `cfx-microphone-exposure-help`
- `cfx-microphone-exposure-mode`
- `cfx-microphone-exposure-refresh`
- `cfx-microphone-exposure-save`
- `cfx-microphone-exposure-status`
- `cfx-microphone-website-custom`
- `cfx-microphone-website-custom-form`
- `cfx-microphone-website-custom-help`
- `cfx-microphone-website-device`
- `cfx-microphone-website-heading`
- `cfx-microphone-website-help`
- `cfx-microphone-website-label`
- `cfx-microphone-website-save`
- `cfx-microphone-website-status`
- `cfx-network-apply`
- `cfx-network-detected`
- `cfx-network-follow-identity`
- `cfx-network-mode`
- `cfx-network-profile-status`
- `cfx-observed-gpu-catalog`
- `cfx-override-count`
- `cfx-permission-settings`
- `cfx-persona-choice`
- `cfx-persona-filter`
- `cfx-persona-hardware`
- `cfx-persona-help`
- `cfx-persona-os-current`
- `cfx-persona-similarity`
- `cfx-persona-source`
- `cfx-persona-source-current`
- `cfx-persona-source-help`
- `cfx-persona-version`
- `cfx-privacy-settings`
- `cfx-profile-confidence`
- `cfx-profile-preview`
- `cfx-profile-preview-text`
- `cfx-profile-preview-traits`
- `cfx-profile-preview-ua`
- `cfx-profile-tools-title`
- `cfx-provider-readiness`
- `cfx-proxy-manager`
- `cfx-proxy-url`
- `cfx-regenerate`
- `cfx-region-settings`
- `cfx-release-status`
- `cfx-route-status`
- `cfx-screen-count`
- `cfx-screen-management`
- `cfx-screen-origins`
- `cfx-screen-origins-reset`
- `cfx-screen-origins-save`
- `cfx-screen-origins-status`
- `cfx-similarity-results`
- `cfx-similarity-summary`
- `cfx-speaker-configuration`
- `cfx-speaker-device-form`
- `cfx-speaker-device-name`
- `cfx-speaker-device-refresh`
- `cfx-speaker-device-reset`
- `cfx-speaker-device-save`
- `cfx-speaker-device-status`
- `cfx-speaker-website-custom`
- `cfx-speaker-website-custom-form`
- `cfx-speaker-website-custom-help`
- `cfx-speaker-website-device`
- `cfx-speaker-website-heading`
- `cfx-speaker-website-help`
- `cfx-speaker-website-label`
- `cfx-speaker-website-save`
- `cfx-speaker-website-status`
- `cfx-status-label`
- `cfx-template-settings`
- `cfx-tracking-settings`
- `cfx-tz-current`
- `cfx-tz-select`
- `cfx-update-readiness`
- `cfx-webrtc-mode`
- `cfx-workspace-settings`
- `cloakfox.appearance.colored_inactive_buttons`
- `cloakfox.appearance.firefox`
- `cloakfox.compat.screen_management`
- `cloakfox.experimental.canvas_pipeline`
- `cloakfox.opt.canvas_render_privacy`
- `cloakfox.opt.clipboard_disabled`
- `cloakfox.opt.clipboard_masking`
- `cloakfox.opt.container_rendering_profiles`
- `cloakfox.opt.eme_disabled`
- `cloakfox.opt.focus_masking`
- `cloakfox.opt.gpu_backend_profiles`
- `cloakfox.opt.hdr_masking`
- `cloakfox.opt.math_constants_noise`
- `cloakfox.opt.math_data_noise`
- `cloakfox.opt.mediadevices_disabled`
- `cloakfox.opt.notification_permission_disabled`
- `cloakfox.opt.storage_persisted_disabled`
- `cloakfox.opt.timer_high_precision_jitter`
- `cloakfox.opt.timer_quantization_off`
- `cloakfox.opt.webgl_typed_readback_disabled`
- `cloakfox.opt.websocket_disabled`
- `cloakfox.opt.window_name_disabled`
- `cloakfox.webrtc.protect_proxy`
- `cloakfox.webrtc.protect_unready`
- `comparison`
- `comparison-status`
- `conflicting-containers`
- `container`
- `current-container`
- `current-ip`
- `current-ipv4`
- `current-ipv6`
- `destination`
- `grp-audio`
- `grp-geo`
- `grp-graphics`
- `grp-hidden`
- `grp-locale`
- `grp-media`
- `grp-navigator`
- `grp-network`
- `grp-screen`
- `grp-seeds`
- `grp-timezone`
- `grp-voices`
- `guidance`
- `heading`
- `ip`
- `matching-profiles-heading`
- `once`
- `recheck`
- `sec-appearance`
- `sec-audio`
- `sec-display`
- `sec-geo`
- `sec-graphics`
- `sec-hardening`
- `sec-identity`
- `sec-locale`
- `sec-media`
- `sec-network-policy`
- `sec-screen-management`
- `sec-seeds`
- `settings`
- `warning-detail`
- `warning-status`
- `website`

## Privileged actor inventory

Gecko privileged actors are not installed in Chromium. Equivalent privacy behavior must use appropriate native Chromium hooks.

- `additions/browser/components/cloakfox/actors/CloakfoxCoderPadMediaChild.sys.mjs`
- `additions/browser/components/cloakfox/actors/CloakfoxContainerBulkChild.sys.mjs`
- `additions/browser/components/cloakfox/actors/CloakfoxContainerProxyEditorChild.sys.mjs`
- `additions/browser/components/cloakfox/actors/CloakfoxFeatureDetectChild.sys.mjs`
- `additions/browser/components/cloakfox/actors/CloakfoxGamepadChild.sys.mjs`
- `additions/browser/components/cloakfox/actors/CloakfoxHackerRankMediaChild.sys.mjs`
- `additions/browser/components/cloakfox/actors/CloakfoxIPProbeChild.sys.mjs`
- `additions/browser/components/cloakfox/actors/CloakfoxKeyboardChild.sys.mjs`
- `additions/browser/components/cloakfox/actors/CloakfoxMathChild.sys.mjs`
- `additions/browser/components/cloakfox/actors/CloakfoxMediaQueryChild.sys.mjs`
- `additions/browser/components/cloakfox/actors/CloakfoxMidiChild.sys.mjs`
- `additions/browser/components/cloakfox/actors/CloakfoxSpeechChild.sys.mjs`
- `additions/browser/components/cloakfox/actors/CloakfoxTabHistoryChild.sys.mjs`
- `additions/browser/components/cloakfox/actors/CloakfoxTimezoneChild.sys.mjs`
- `additions/browser/components/cloakfox/actors/CloakfoxTimingChild.sys.mjs`
- `additions/browser/components/cloakfox/actors/CloakfoxWebGPUChild.sys.mjs`
- `additions/browser/components/cloakfox/actors/CloakfoxWebRTCChild.sys.mjs`
<!-- END GENERATED GECKO INVENTORY -->

## Shared config capability boundary

`schemaVersion:1` names engine/container/private-session ownership, revision, master
switch and a 32-byte persona seed. The original v1 option names are `canvas` and
`blockWebGPUReadback`; optional presentation adds `navigator`, `language` and `timezone` and requires the new identity capability (verified on macOS 2026-10-16; regional values widened 2026-10-17); explicit overrides beat defaults. Master-off disables both
implemented transforms/policies. Fixed prototype permission denials remain separate.
Unknown fields/options and incompatible native capabilities are rejected, never
presented as working. Regenerating changes the graphics seed; it does not yet
sample a full navigator/device/font/audio persona.

The controller stores persistent records atomically with private permissions and
serializes revision updates. Private records are memory-only and retired automatically by the production controller on actual context/process closure, accounting for popups. Retired private seeds cannot be replayed in the same backend process. Snapshot seed and
settings are applied before creating any window; acknowledgements contain revision
and effective policy, never the secret. Same-snapshot reapplication is idempotent;
stale/changed live configs require restart rather than mixing worker/page state.
Existing legacy opens remain for regression tooling; once a context is versioned,
opening requires its acknowledged revision and cannot mix legacy privacy options.

## Verified bounded native identity increment

The native `identity-patch-lock.json` follows the graphics patches and provides
`identityPrivacyVersion:1`; the `locale-timezone-patch-lock.json` tail replaces the
bounded language/timezone preset list with the canonical one described above, so the
engine accepts any canonical value its own ICU data can render and refuses the ones
it cannot before a container context exists. The recovered framework and all five
identity runtime cases passed on macOS on 2026-10-16, including navigation/fetch
headers and worker/Intl behavior; the widening was verified on 2026-10-17 (all 35
sampling presets accepted, canonical languages/zones reach the page, HTTP headers
and workers, unrenderable values refused fail-closed). This supports only the
regional presentation documented in
[scope and verification](../../docs/dual-engine/chromium-identity-locale.md).
Cross-OS personas and the remaining groups above are still unported;
`privacyPatched` remains false.

A development-only windowless foundation now exercises CPU/IOSurface callbacks,
bounded owned frame copies, revision-bound resize/input and rejected native popup
escape. The separate native Mach boundary authenticates the launch child and
validates tab/configuration/viewport/replay ownership before copying surfaces.
These components are not connected to Gecko's viewport or production routing.
See [current acceptance and limits](../../docs/dual-engine/parity-20261016/README.md).
