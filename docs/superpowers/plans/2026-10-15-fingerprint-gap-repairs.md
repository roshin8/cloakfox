# Installed Firefox 158 Fingerprint Gap Repairs

> **For agentic workers:** use the executing-plans and dispatching-parallel-agents workflows for independent repairs; one native build/replay/install coordinator owns integration.

**Goal:** Repair the five confirmed installed-browser audit gaps and repeat affected tests against the installed Cloakfox app.

**Architecture:** Keep native C++ enforcement, own-document/container/site policy and native permission/transport handling. Add reproducible native patches, remove contradictory actor overrides where native values are authoritative, and preserve functionality with conservative media capability policy. The audit JSON is the evidence/spec: `docs/fingerprint-audits/2026-10-15-installed-158.json`.

**Constraints:** Reuse the existing isolated `codex/firefox-158-port` worktree. Preserve uncommitted IP/history/settings fixes. No real camera/microphone grants, live assessments, profile deletion, main-world product scripts, blanket request-header injection or weakened certificate/proxy behavior. Native Gecko remains distinguishable from Chromium; UA coherence is not engine replacement. No commit/push unless requested.

**Review focus:** startup/worklet threads without JS callers; stale or cross-container policy; invalid/opt-out policy; numerical audio/silence stability and output bounds; native encoder unsupported configurations and real encoding; worker/header ownership, redirects, origins/privacy permissions and user/extension header precedence.

- [x] Reproduce and retain failing AudioWorklet/CSS/header/WebCodecs cases from the installed audit; add durable local regression probes.
- [x] Audio: protect the raw worklet readback boundary with owning-context/site noise without global mutable config/thread IPC; test stability, isolation, silence, numerical bounds and disabled mode.
- [x] CSS: own-document configuration for native media getters, Screen/CSS depth consistency, unified JS/stylesheet gamut preferences; test different containers, embedded documents, dynamic style evaluation and disabled mode.
- [x] Client Hints: coherent secure-context/native request UA hints from the actual channel identity; respect hint eligibility, trust/privacy and caller/header semantics. Cover default hints first and opt-in high entropy only where valid. Test actual HTTP echo and website reports.
- [x] WebCodecs: conservative native capability normalization, applied to support checks AND actual configure/encode paths, window and worker, with explicit compatibility behavior. Do not falsely claim unsupported hardware.
- [x] Review each independent change, integrate ordered patches, verify pristine replay and source parity, then build native 158.
- [x] Run affected local probes and Node/Python suites, package, verify and replace installed app preserving profiles, rerun local regressions and affected external fingerprint sites on `/Applications/Cloakfox.app`.
- [x] Final independent review and report: resolved findings, remaining native-engine limits and any incomplete site tests, with exact evidence.
