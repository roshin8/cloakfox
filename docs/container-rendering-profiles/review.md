# Independent native enforcement review

Reviewer: persona_enforcement_review, read-only review of privileged policy, settings transactions and native WebGL/WebGPU paths.

Two P2 findings were fixed and re-reviewed:

- GPU profile identity incorrectly depended on the canvas exception gate. It now uses a separate HMAC domain with the owning container secret and schemeful site. Readback policy remains separately enforced.
- Resetting a GPU preset could partly delete overrides before validation rejected the operation. Complete preset updates now validate before any field is written; the actual module regression test reproduces the former failure.

Unused OffscreenCanvas transfers now require matching container ID and both site-owner key halves before creating a profile context. Native WebGL restrictions feed real resource/shader validators, and WebGPU requiredLimits uses the clamped adapter.

Re-review: no remaining concrete P1/P2 found in the reviewed changes. Reviewer ran five Node profile tests and the native profile unittest; runtime installation was verified separately by the implementing agent. This does not establish physical driver parity or zero fingerprint warnings.
