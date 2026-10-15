# Chromium privacy port inventory

Baseline: Firefox 157 branch at 24c23d478e. This is a coverage inventory, not a claim that these protections exist in Chromium. The binary SDK prototype remains unpatched. The newer source-built companion has partial native canvas, worker and GPU protections, verified in `../../docs/dual-engine/cef-worker-gpu-privacy-20261015.json`; full parity remains pending. Fixed permission denial and native request-context isolation are separate measured behavior.

## Native implementation groups

| Existing feature group | Chromium work needed | Prototype status |
|---|---|---|
| Container/site persona seeds, overrides, generation checkbox | Backend-independent config plus BrowserContext/StoragePartition ownership | Partial canvas/WebGL secret ownership, including effective shared/SW storage-pool ownership; persona configuration/generation not ported |
| Navigator, UA/client hints, platform/device capabilities | Native Blink navigator/worker hooks; coherent real engine version | Native identity only; no persona masking |
| Screen/window geometry, letterboxing, CSS, fonts | Blink layout/screen/CSS/font selection and browser display services | Not ported |
| Canvas/OffscreenCanvas, WebGL, WebGPU | Native readback and device information hooks, worker ownership | Partial native opaque RGBA8 Canvas2D/export and WebGL direct/PBO readback; document/dedicated/shared/service-worker tests pass. GPU identifying metadata reduced; optional all-WebGPU-READ-map denial. Selective WebGPU pixel noise, other formats and general capabilities remain uncovered |
| Audio, codecs, device labels and media permissions | Blink audio/media paths and browser permission/capture services | Permission requests denied; noise/masking not ported |
| Locale, timezone, geolocation | Blink/V8 Intl and permission-aware location services | Location denied; persona presentation not ported |
| Performance clocks, entries, scheduling and Math | Blink timing/scheduling and V8 native math implementation | Not ported |
| Keyboard, gamepad, MIDI, feature detection | Blink device/input exposure and permission services | Not ported |
| WebRTC, IP discovery and DNS/proxy controls | Chromium WebRTC and NetworkContext policies, explicit consent and isolation | Not ported |
| Storage, network connections, TLS sessions, H2/H3 and WebSockets | Independent native profiles, NetworkContexts, cache/ticket/proxy tests | Website storage tested; authenticated network isolation pending |
| Clipboard, notifications, EME, focus/name, persistence flags | Native Blink/permission policies and browser settings | Existing option semantics not ported |
| Tracking/query stripping, bounce protection, site exceptions/presets | Browser/network policy integration | Not ported |
| Container/settings UI, appearance, bookmarks/passwords, security updates | Shared controller and engine capability mapping; engine-owned sensitive stores | Not integrated |

## Active Gecko patch inventory

All 112 active canonical patches require triage for engine specificity; none is mechanically applied to Chromium. Native privacy patches must be rewritten, while Gecko browser UI/branding/build patches may have no Chromium equivalent.

- `all-addons-private-mode.patch` — Chromium implementation not ported.
- `anti-font-fingerprinting.patch` — Chromium implementation not ported.
- `audio-context-spoofing.patch` — Chromium implementation not ported.
- `audio-fingerprint-manager.patch` — Chromium implementation not ported.
- `browser-init.patch` — Chromium implementation not ported.
- `builtin-extension.patch` — Chromium implementation not ported.
- `canvas-spoofing.patch` — Chromium implementation not ported.
- `chromeutil.patch` — Chromium implementation not ported.
- `clipboard-spoofing.patch` — Chromium implementation not ported.
- `codecs-spoofing.patch` — Chromium implementation not ported.
- `document-lastmodified-spoofing.patch` — Chromium implementation not ported.
- `config.patch` — Chromium implementation not ported.
- `cross-process-storage.patch` — Chromium implementation not ported.
- `domrect-spoofing.patch` — Chromium implementation not ported.
- `fingerprint-injection.patch` — Chromium implementation not ported.
- `font-hijacker.patch` — Chromium implementation not ported.
- `font-list-spoofing.patch` — Chromium implementation not ported.
- `font-bundle-packaging.patch` — Chromium implementation not ported.
- `system-font-spoofing.patch` — Chromium implementation not ported.
- `force-default-pointer.patch` — Chromium implementation not ported.
- `geolocation-spoofing.patch` — Chromium implementation not ported.
- `http2-fingerprint-spoofing.patch` — Chromium implementation not ported.
- `indexeddb-spoofing.patch` — Chromium implementation not ported.
- `locale-spoofing.patch` — Chromium implementation not ported.
- `macos-sandbox-crash-fix.patch` — Chromium implementation not ported.
- `media-capabilities-spoofing.patch` — Chromium implementation not ported.
- `media-features-spoofing.patch` — Chromium implementation not ported.
- `media-device-spoofing.patch` — Chromium implementation not ported.
- `mediasource-istypesupported-spoofing.patch` — Chromium implementation not ported.
- `navigator-extra-spoofing.patch` — Chromium implementation not ported.
- `cloakfox-webgpu-null-safety.patch` — Chromium implementation not ported.
- `navigator-spoofing.patch` — Chromium implementation not ported.
- `network-patches.patch` — Chromium implementation not ported.
- `notification-spoofing.patch` — Chromium implementation not ported.
- `permissions-spoofing.patch` — Chromium implementation not ported.
- `range-domrect-spoofing.patch` — Chromium implementation not ported.
- `screen-orientation-spoofing.patch` — Chromium implementation not ported.
- `screen-spoofing.patch` — Chromium implementation not ported.
- `shadow-root-bypass.patch` — Chromium implementation not ported.
- `speech-voices-spoofing.patch` — Chromium implementation not ported.
- `storage-estimate-spoofing.patch` — Chromium implementation not ported.
- `svg-bbox-spoofing.patch` — Chromium implementation not ported.
- `svg-geometry-spoofing.patch` — Chromium implementation not ported.
- `svg-metrics-spoofing.patch` — Chromium implementation not ported.
- `text-metrics-spoofing.patch` — Chromium implementation not ported.
- `timing-jitter-spoofing.patch` — Chromium implementation not ported.
- `timezone-spoofing.patch` — Chromium implementation not ported.
- `vibration-spoofing.patch` — Chromium implementation not ported.
- `visual-viewport-spoofing.patch` — Chromium implementation not ported.
- `voice-spoofing.patch` — Chromium implementation not ported.
- `webgl-spoofing.patch` — Chromium implementation not ported.
- `webgl-readback-noise.patch` — Chromium implementation not ported.
- `websocket-spoofing.patch` — Chromium implementation not ported.
- `webrtc-ip-spoofing.patch` — Chromium implementation not ported.
- `cloakfox-webrtc-network-policy.patch` — Chromium implementation not ported.
- `window-name-spoofing.patch` — Chromium implementation not ported.
- `cloakfox-enabled-staticpref.patch` — Chromium implementation not ported.
- `cloak-config-webidl.patch` — Chromium implementation not ported.
- `unified-maskconfig.patch` — Chromium implementation not ported.
- `http3-fingerprint-spoofing.patch` — Chromium implementation not ported.
- `http2-profile-webidl.patch` — Chromium implementation not ported.
- `cpp-first-pref-reader.patch` — Chromium implementation not ported.
- `cpp-first-pref-migration.patch` — Chromium implementation not ported.
- `cpp-first-actors-registration.patch` — Chromium implementation not ported.
- `cpp-first-about-cloakfox.patch` — Chromium implementation not ported.
- `cpp-first-error-stack-depth.patch` — Chromium implementation not ported.
- `cpp-first-worker-spoofers.patch` — Chromium implementation not ported.
- `cloakfox-optional-assets-car.patch` — Chromium implementation not ported.
- `worker-container-identity.patch` — Chromium implementation not ported.
- `cloakfox-letterboxing.patch` — Chromium implementation not ported.
- `cloakfox-container-forget.patch` — Chromium implementation not ported.
- `cloakfox-scoped-data-clear.patch` — Chromium implementation not ported.
- `cloakfox-strict-proxy-guard.patch` — Chromium implementation not ported.
- `site-fingerprint-isolation.patch` — Chromium implementation not ported.
- `cloakfox-upstream-hardening.patch` — Chromium implementation not ported.
- `cloakfox-region-policy-proxy.patch` — Chromium implementation not ported.
- `cloakfox-privacy-completion.patch` — Chromium implementation not ported.
- `cloakfox-window-activity.patch` — Chromium implementation not ported.
- `cloakfox-appearance.patch` — Chromium implementation not ported.
- `cloakfox-clipboard-signals.patch` — Chromium implementation not ported.
- `cloakfox-pointer-activity.patch` — Chromium implementation not ported.
- `cloakfox-hover-activity.patch` — Chromium implementation not ported.
- `cloakfox-native-worker-math.patch` — Chromium implementation not ported.
- `cloakfox-exported-function-identity.patch` — Chromium implementation not ported.
- `cloakfox-live-worker-math.patch` — Chromium implementation not ported.
- `cloakfox-bundled-font-rendering.patch` — Chromium implementation not ported.
- `cloakfox-user-agent-data.patch` — Chromium implementation not ported.
- `cloakfox-math-data-correctness.patch` — Chromium implementation not ported.
- `cloakfox-math-data-toggle.patch` — Chromium implementation not ported.
- `cloakfox-hackerrank-media-recovery.patch` — Chromium implementation not ported.
- `cloakfox-appearance-profile.patch` — Chromium implementation not ported.
- `cloakfox-screen-presentation.patch` — Chromium implementation not ported.
- `cloakfox-testdome-screen-management.patch` — Chromium implementation not ported.
- `cloakfox-window-management-permission.patch` — Chromium implementation not ported.
- `cloakfox-screen-orientation-events.patch` — Chromium implementation not ported.
- `cloakfox-webgl-live-state-followup.patch` — Chromium implementation not ported.
- `cloakfox-audio-analyser-copy-followup.patch` — Chromium implementation not ported.
- `cloakfox-speech-error-followup.patch` — Chromium implementation not ported.
- `cloakfox-stock-resource-followup.patch` — Chromium implementation not ported.
- `cloakfox-windows-manifest-followup.patch` — Chromium implementation not ported.
- `performance-timeline-timing.patch` — Chromium implementation not ported.
- `cloakfox-media-device-privacy.patch` — Chromium implementation not ported.
- `cloakfox-hdr-exposure-privacy.patch` — Chromium implementation not ported.
- `cloakfox-network-profile.patch` — Chromium implementation not ported.
- `cloakfox-network-conformance.patch` — Chromium implementation not ported.
- `librewolf/bootstrap.patch` — Chromium implementation not ported.
- `librewolf/custom-ubo-assets-bootstrap-location.patch` — Chromium implementation not ported.
- `librewolf/dbus_name.patch` — Chromium implementation not ported.
- `librewolf/devtools-bypass.patch` — Chromium implementation not ported.
- `librewolf/disable-data-reporting-at-compile-time.patch` — Chromium implementation not ported.
- `librewolf/mozilla_dirs.patch` — Chromium implementation not ported.
- `librewolf/urlbarprovider-interventions.patch` — Chromium implementation not ported.

## Optional/privacy preference inventory

Literal cloakfox.opt / cloakfox.webrtc preference names collected from the current module/UI/default sources, with UI-only HDR masking included. Dynamic names and config API fields also require manual audit before privacy parity is declared. These names are not Chromium preference names.

- `cloakfox.opt.clipboard_disabled` — Existing semantics not ported.
- `cloakfox.opt.clipboard_masking` — Existing semantics not ported.
- `cloakfox.opt.eme_disabled` — Existing semantics not ported.
- `cloakfox.opt.focus_masking` — Existing semantics not ported.
- `cloakfox.opt.hdr_masking` — Existing semantics not ported.
- `cloakfox.opt.math_constants_noise` — Existing semantics not ported.
- `cloakfox.opt.math_data_noise` — Existing semantics not ported.
- `cloakfox.opt.mediadevices_disabled` — Existing semantics not ported.
- `cloakfox.opt.notification_permission_disabled` — Existing semantics not ported.
- `cloakfox.opt.storage_persisted_disabled` — Existing semantics not ported.
- `cloakfox.opt.timer_high_precision_jitter` — Existing semantics not ported.
- `cloakfox.opt.timer_quantization_off` — Existing semantics not ported.
- `cloakfox.opt.websocket_disabled` — Existing semantics not ported.
- `cloakfox.opt.window_name_disabled` — Existing semantics not ported.
- `cloakfox.webrtc.ip_lookup.enabled` — Existing semantics not ported.

## Settings surface inventory

Current settings.html IDs/data-pref bindings, retained as an audit checklist for UI porting. The prototype exposes none of this existing Gecko settings surface. Separate settings modules and dynamic panels need manual audit in milestone 3.

- `cfx-appearance-permissions`
- `cfx-appearance-restart`
- `cfx-appearance-reveal`
- `cfx-appearance-status`
- `cfx-chromium-status`
- `cfx-clear`
- `cfx-clear-overrides`
- `cfx-consistency-inspector`
- `cfx-container-select`
- `cfx-dns-settings`
- `cfx-enabled`
- `cfx-engine-version`
- `cfx-firefox-appearance`
- `cfx-forget-data`
- `cfx-forget-status`
- `cfx-generate-help`
- `cfx-generate-new`
- `cfx-generation-clear-overrides`
- `cfx-headline-text`
- `cfx-help-clipboard-masking`
- `cfx-help-focus-masking`
- `cfx-help-math-data-noise`
- `cfx-identity-status`
- `cfx-ip-lookup`
- `cfx-network-apply`
- `cfx-network-detected`
- `cfx-network-follow-identity`
- `cfx-network-mode`
- `cfx-network-profile-status`
- `cfx-override-count`
- `cfx-permission-settings`
- `cfx-persona-choice`
- `cfx-persona-filter`
- `cfx-persona-hardware`
- `cfx-persona-help`
- `cfx-persona-os-current`
- `cfx-privacy-settings`
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
- `cfx-status-label`
- `cfx-template-settings`
- `cfx-tracking-settings`
- `cfx-tz-current`
- `cfx-tz-select`
- `cfx-update-readiness`
- `cfx-webrtc-mode`
- `cfx-workspace-settings`
- `cloakfox.appearance.firefox`
- `cloakfox.compat.screen_management`
- `cloakfox.opt.clipboard_disabled`
- `cloakfox.opt.clipboard_masking`
- `cloakfox.opt.eme_disabled`
- `cloakfox.opt.focus_masking`
- `cloakfox.opt.hdr_masking`
- `cloakfox.opt.math_constants_noise`
- `cloakfox.opt.math_data_noise`
- `cloakfox.opt.mediadevices_disabled`
- `cloakfox.opt.notification_permission_disabled`
- `cloakfox.opt.storage_persisted_disabled`
- `cloakfox.opt.timer_high_precision_jitter`
- `cloakfox.opt.timer_quantization_off`
- `cloakfox.opt.websocket_disabled`
- `cloakfox.opt.window_name_disabled`
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
