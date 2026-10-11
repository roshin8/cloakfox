# Fresh final review — 2026-10-11

Read-only gpt-6-astra review of changes after 0030d79a81, including native applied
context and the new canonical patches/fixtures. No Critical finding.

Four Important findings were accepted:

1. Reversed label/key tuples prevented media Settings controls from saving.
   Corrected; live control probe failed before correction and passed afterward.
2. Container timing re-read values changed after an option toggle. Added cached
   first-render/start values; compiled actual getter regression RED→GREEN.
3. Public entry lists sorted raw resource times against explicit author mark
   times, producing descending visible timestamps. Restore StartTime sorting;
   local mixed-coordinate mark regression demonstrated the failure.
4. Per-read mode changes mixed lazy timing fields and could move now backwards.
   Capture presentation mode in the immutable per-global key. Existing globals
   retain a consistent clock; reload/restart applies new option/master choices.
   Delayed getter runtime regression demonstrated the previous mixed mode.

Both Minor findings addressed: the wire report now names pseudo-header order
explicitly, and config/UI documentation describes native timing and reloads.
No deferred minor code findings.

Reviewer verified exact-owner default-container resolution, mutex-protected
worker config/atomic pref reads, permission-filtered real media backing and
native ID anonymization, compositor-independent HDR masking, and actual wire
observations with certificate checks. Final green evidence is recorded in
privacy-followup-verification.md rather than inferred from the review.

Declined behaviors retained as limits: physical capture/HDR playback (fake/local
fixtures), Windows/Linux runtime (macOS host), public challenge/assessment
behavior (outside scope), baseline-only code (separate prior audit), and the
final DMG (review ran before packaging; executor must verify the artifact).
