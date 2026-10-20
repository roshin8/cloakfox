# Chromium cross-run cache implementation plan

> **For agentic workers:** Use superpowers:executing-plans task by task; request independent review before publishing.

**Goal:** Resume a completed segment checkpoint from a trusted repository-owned run without changing the active build, and retain cumulative compiler caches for future segments.

**Architecture:** A controller validates terminal producer runs and successful checkpoint-producing jobs. Continuations check out the original producer recipe at its immutable SHA, retaining strict checkpoint source/tool/SDK identity. Controller-run and compilation-source provenance remain separate. Future workflows have twelve bounded segments; the current four-segment run remains untouched. Completed SDK discovery remains gated by exact input keys, payload hashes, and successful engine completion.

**Tech stack:** GitHub Actions, Python, existing native tar/zstd handoffs, Git object identities, ccache.

- [ ] Add negative/positive tests for trusted SDK producers and cross-run producer selection.
- [ ] Implement terminal-run checkpoint discovery with bounded artifact evidence, source SHA and host-tool provenance validation; explicit requests fail closed.
- [ ] Add original-recipe checkout and cross-run artifact download to source segments, retaining source and controller provenance separately.
- [ ] Replace immutable shared ccache keys with unique segment snapshots and exact-input restore prefixes; record hit/miss statistics.
- [ ] Wire automatic exact-input partial reuse and explicit continuation through dispatcher/resolver; extend future segment chain to twelve.
- [ ] Run focused tests and actionlint on exact publication snapshot; independently review.
- [ ] Publish only owned files through an alternate index; do not dispatch while current run is active.
- [ ] Update hourly monitor with the validated continuation command and segment-4 checkpoint handling.
