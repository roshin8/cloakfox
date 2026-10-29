# Preferred fpgen Personas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Generate fresh per-container personas from pinned fpgen data by default, retaining BrowserForge and privacy enforcement.

**Architecture:** A local privileged sampler uses a hash-pinned full Bayesian model and a strict supported-field adapter. Source selection routes through the existing native persona mapper and policy/admission code; new containers prefer fpgen while missing source on existing containers means BrowserForge.

**Tech Stack:** Python offline importer, privileged JavaScript modules, Node tests, Selenium/geckodriver Firefox159 headless probes.

**Spec:** `docs/superpowers/specs/2026-10-28-fpgen-personas.md`

## Global Constraints
- No Chromium source/build changes or process interruption; preserve checkpoint history.
- No production page injection or Python/network generation at runtime.
- Existing privacy/permission/native capability enforcement remains authoritative.
- Preserve existing identities; deterministic isolated container seeds; no silent source fallback.

## Review Focus
- Impossible hardware/OS combinations must fail without publishing partial state.
- Legacy profiles/backups must not migrate to a different identity silently.
- Dataset permissions, unique identifiers and unsupported capabilities must never become policy.
- Loaded model/shared caches must not retain or leak another container's sampled identity.
- Real packaged runtime imports and restart behavior must match tests.

### Task 1: Pinned model, deterministic sampler and adapter
**Files:** New `scripts/generate-fpgen-network.py`, `CloakfoxFPGen{Network,Sampler}.sys.mjs` under additions/browser/components/cloakfox, model provenance/license, Node/Python tests.
**Interface:** `sampleFPGenFingerprint(prng, {os,hardware,browser,version})` returns the explicitly allowlisted BrowserForge-shaped input consumed by `bfToCloakKeys`; throws on invalid or unsupported constraints. Preserve complete source model as packaged reference data; supported desktop fields may use a safe projection.
- [x] Write failing deterministic/filter/unsafe-field/model-integrity tests.
- [x] Implement offline bounded pinned import, sampler, supported-field mapping and attribution.
- [x] Run tests, document field coverage and incompatible observations, task review.

### Task 2: Source persistence and UI
**Files:** `CloakfoxPersonas.sys.mjs`, `CloakfoxSeedSync.sys.mjs`, `CloakfoxContainerWorkflows.sys.mjs`, `CloakfoxTemplates.sys.mjs`, settings HTML/JS, `moz.build`, tests.
**Interface:** `cloakfox.container.<id>.persona_source` enum `fpgen|browserforge`; missing existing source means BrowserForge. New container source fpgen. Fresh generation source selector defaults fpgen, applied identity source retained in pref. Explicit BF previews force browserforge.
- [x] Write tests for old identity preservation, new default, explicit source, per-owner persistence and backup validation.
- [x] Route generation and add UI source control/help; include source/filters in backup/template state; maintain rollback semantics.
- [x] Test both providers, invalid combinations, reset/import/restart; task review.

### Task 3: Firefox159 acceptance and review
**Files:** `tests/fingerprint/probe_fpgen_personas.py`, `docs/firefox-159/fpgen-personas/*`, generated Gecko inventory.
- [x] Clone the accepted Firefox159 test app without altering prior checkpoints; stage modules/data and validate registration.
- [x] Run unit regression tests and headless two-provider, multi-container, restart, window/worker/privacy-policy probes.
- [x] Run independent code review; fix findings and rerun covering tests.
- [x] Record exact binary/source hashes, results, supported-field limits and unchanged Chromium build input key.
