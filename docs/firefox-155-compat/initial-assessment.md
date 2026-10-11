# Firefox 155.0.1 compatibility assessment

Checked 2026-09-05 in branch `codex/firefox-155-compat`.

## Result

| Source version | Patches applied | Patches with failures | Rejected hunks | Skipped hunks |
| --- | ---: | ---: | ---: | ---: |
| 146.0.1 baseline | 75 / 75 | 0 | 0 | 0 |
| 155.0.1 target | 47 / 75 | 28 | 71 | 1 |

These are patch-application results, not build or runtime results. Application
uses the system patch tool's default context tolerance; “applied” does not
prove exact context matches or semantic compatibility. The audit continues
after failures, so some later rejects can cascade from earlier failures.
The 28 failing patches are not necessarily 28 independent upstream changes.

## Inputs and isolation

- Base commit: `274e503768` (full hash in `input-snapshot.json`).
- The six current uncommitted files were copied into this worktree, including
  `cloakfox-letterboxing.patch`; their SHA256 hashes are recorded in the snapshot.
- All 75 patch hashes are recorded in each version's `results.json`.
- Latest source: https://archive.mozilla.org/pub/firefox/releases/155.0.1/source/firefox-155.0.1.source.tar.xz
- Download verified against Mozilla's SHA512SUMS; relevant checksum retained.
- Target is fully extracted under `firefox-src/`, with additions copied and
  patches partially applied. The source has rejects and is NOT ready to build.
- Baseline used fresh files extracted from the existing 146.0.1 source archive.
  Only the patch targets and copy-additions prerequisites were extracted,
  sufficient for this application check; location is in `baseline-source.json`.
- Only this worktree's `upstream.sh` was changed to 155.0.1. No engine patches
  were ported, and no compile or runtime checks were attempted.

## Concurrent work

Final verification found later changes in the original checkout to `patches/cloakfox-letterboxing.patch`, `tests/fingerprint/README.md`, `tests/fingerprint/probe_letterboxing.py`. This assessment uses the start-of-run snapshot; those later edits were not copied into the experiment. No original working files were edited by this task.

## What the failures mean

The largest porting area is font shaping: `anti-font-fingerprinting.patch`
has 18 rejected hunks across six files. Rejected changes thread container IDs
through shaping functions and font word-cache keys. This needs careful
signature/call-site and cache-isolation review, beyond updating line numbers.

HTTP/3 has 12 rejected hunks: one vendored Rust checksum, six in Rust glue,
two in its C++ wrapper, and three in Http3Session. The profile parameter
must be reconciled across both sides of the C++/Rust interface, and vendored
checksums regenerated after changes. Actual network output needs validation.

Some failures look small: the HTTP/2 reject is an include insertion, while
audio and screen declarations reject around changed header context. Their
small textual scope is not evidence that the final build will pass.

SVG bounding boxes and Range rectangle hooks need review in the updated
implementations. The SVG patch rejects four of six hunks. Letterboxing has
two rejects: browser startup and `nsPresContext::UpdateTopInnerSizeForRFP`.
WebRTC has one reject in the stats sanitization callback, which must remain
covered to avoid exposing unspoofed candidate addresses.

`cpp-first-error-stack-depth.patch` targets the removed `js/src/jsexn.h`.
The constant now lives in `js/src/vm/ErrorObject.h`. The new source also
implements `Error.stackTraceLimit` in `ErrorObject.cpp`, so the patch's old
claim that Firefox ignores that property is obsolete. Review intended
semantics when porting it.

Most of the cpp-first configuration, actor registration, worker identity,
navigator, canvas and timezone patches apply. They still need compilation
and the live fingerprint probes after the full stack is ported.

## Failed patch inventory

| Patch | Rejected hunks | Skipped hunks |
| --- | ---: | ---: |
| `anti-font-fingerprinting.patch` | 18 | 0 |
| `audio-fingerprint-manager.patch` | 1 | 0 |
| `codecs-spoofing.patch` | 1 | 0 |
| `config.patch` | 1 | 0 |
| `cross-process-storage.patch` | 1 | 0 |
| `font-hijacker.patch` | 3 | 0 |
| `font-list-spoofing.patch` | 1 | 0 |
| `geolocation-spoofing.patch` | 1 | 0 |
| `http2-fingerprint-spoofing.patch` | 1 | 0 |
| `indexeddb-spoofing.patch` | 1 | 0 |
| `locale-spoofing.patch` | 2 | 0 |
| `network-patches.patch` | 1 | 0 |
| `permissions-spoofing.patch` | 1 | 0 |
| `range-domrect-spoofing.patch` | 2 | 0 |
| `screen-spoofing.patch` | 5 | 0 |
| `shadow-root-bypass.patch` | 1 | 0 |
| `storage-estimate-spoofing.patch` | 2 | 0 |
| `svg-bbox-spoofing.patch` | 4 | 0 |
| `text-metrics-spoofing.patch` | 1 | 0 |
| `webgl-spoofing.patch` | 2 | 0 |
| `webgl-readback-noise.patch` | 1 | 0 |
| `webrtc-ip-spoofing.patch` | 1 | 0 |
| `http3-fingerprint-spoofing.patch` | 12 | 0 |
| `cpp-first-error-stack-depth.patch` | 0 | 1 |
| `cloakfox-optional-assets-car.patch` | 1 | 0 |
| `cloakfox-letterboxing.patch` | 2 | 0 |
| `dbus_name.patch` | 3 | 0 |
| `mozilla_dirs.patch` | 1 | 0 |

## Reproduction and next steps

The experiment script uses the production `scripts/_mixin.py:list_patches`
ordering, copies additions, and runs `patch -p1 --batch --forward -i PATCH`
once per patch, saving its return code and complete output. Each version's
directory contains all 75 logs and a machine-readable `results.json`.

Run only on a FRESH disposable extraction, and use a new output directory
(the script refuses to overwrite an existing result directory):

```sh
python3 docs/firefox-155-compat/check_stack.py /path/to/fresh/source VERSION
```

Do not rerun on the partially patched source. For the port, create a fresh
source tree, fix/regenerate patches in dependency order, and repeat the full
application check. Prioritize fonts and HTTP/3 to expose the substantial
API work early. Then compile macOS and run Selenium/geckodriver fingerprint
probes, including container/domain determinism, workers, graphics,
letterboxing and H2/H3 output. Extend validation to Linux/Windows afterward.

The earlier rough estimate of 1–3 engineer-weeks for a validated macOS port
remains a planning allowance, not a measured forecast. This check establishes
the initial textual conflicts; compile failures and behavioral regressions
remain unmeasured.
