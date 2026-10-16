# Chromium compiler cache comparison — hosted macOS

[Actual GitHub Actions run](https://github.com/roshin8/cloakfox/actions/runs/38972153962)
completed successfully at commit `43aede189510fe56f98744bd7ecf11f894445285`.
The comparison used standard `macos-26`, its installed ccache 4.14 and sccache
0.17.0, and the exact Clang 24 archive from the pinned Chromium source's DEPS.

Only the hosted results below inform the decision. Earlier local exploratory
results are excluded; the user explicitly requested hosted testing. The committed
benchmark now refuses execution outside GitHub-hosted macOS arm64.

## Result: retain ccache

Median warm wall time for each eight-translation-unit batch (seconds):

| Scenario | ccache | sccache |
| --- | ---: | ---: |
| C++20, ccache tested first | 0.102 | 0.159 |
| C++20, sccache tested first | 0.102 | 0.167 |
| C++23, ccache tested first | 0.081 | 0.152 |
| C++23, sccache tested first | 0.260 | 0.239 |

Both tools produced object and dependency bytes identical to the uncached
compiler, correctly invalidated a changed header, and recorded all 56 expected
warm hits in every scenario. There were no unsupported compiler requests,
non-cacheable requests or compilation failures for sccache. Cold results were
mixed: sccache won three cohorts by differing margins, and lost one. Those small
batches do not establish a reliable full cold-build improvement. Warm performance
did not show a consistent advantage for sccache, so the condition for switching
the production Chromium wrapper is not met. Chromium's ccache configuration,
checkpoint handling and verified SDK reuse remain unchanged.

This is a synthetic C/C++/Objective-C++ fixture with Chromium-style flags and the
pinned compiler, using local disk cache backends on an actual hosted runner. It
does not compile full Chromium translation units, use Chromium's complete custom
libc++/generated-header graph, or compare remote GitHub Actions cache backends.
Do not extrapolate these timings into a full-build speedup or a universal cache
ranking. Completed SDK reuse remains the way to skip an unchanged engine build.

The benchmark's separate concurrency group did not cancel, modify or dispatch a
duplicate of the active browser build. No production cache migration was made.

[Raw hosted reports and compiler provenance](compiler-cache-comparison-38972153962/)
are retained here as well as in the run artifact. The optional workflow reruns
only when its own benchmark files change or on explicit manual dispatch; it is
not part of routine browser CI.
