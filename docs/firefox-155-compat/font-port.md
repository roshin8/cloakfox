# Font patch port to Firefox 155.0.1

Ported `patches/anti-font-fingerprinting.patch`; no other patches or shared Firefox source were edited.

## Changes

- Retained Firefox 155 shaping APIs: no obsolete DrawTarget parameter, uint8_t word lengths, uint16_t app-unit scale, and current FNV initial hash. Updated declarations and all three ProcessShapedWordInternal call paths together.
- Carried userContextId into both WordCacheKey constructors and the shared ComputeHash helper, with full-ID equality checks. The ID hash multiplier preserves high container-ID bits; 8-bit/16-bit keys retain the same language-aware hash calculation.
- Preserved HarfBuzz seed perturbation, updated upstream includes/Unicode glue, current ellipsis creation, current drawing parameters, and the MathML Unicode-table representation.
- Text-run construction now inherits the font-group ID for shortcut and transformed runs. Single-space shaping receives that ID explicitly, and case transformations propagate it to child runs.
- Font groups read worker origin attributes on worker threads and document BrowsingContext attributes on the main thread. This avoids WorkerPrivate::GetDocument(), which asserts main-thread access.
- Made the optional FontVisibilityProvider document lookup return nullptr by default, preserving compatibility with Firefox 155's new document-free ListFontsVisibilityProvider. Existing document-backed providers retain overrides.
- Exposed a read-only nsFontMetrics pres-context accessor instead of moving the underlying field before its initializer order.

## Validation

- `python3 /tmp/cloakfox-port-patch.py generate anti-font-fingerprinting.patch` passed: patch applied with `--fuzz=0` to the exact before-155 snapshot and all resulting files matched the edited scratch files byte-for-byte.
- `python3 /tmp/test-cloakfox-font-cache.py` passed. This extracts the actual resulting WordCacheKey and HashPolicy::match C++ into a stub harness and compiles with `clang++ -std=c++17 -Wall -Wextra -Werror`. It checks 8/16-bit key equivalence, null/non-null language atoms, mismatching text, and IDs 0, 1, 257 and UINT32_MAX, including high-ID-bit hash differentiation.
- Reviewed full-source call sites for ProcessSingleSpaceShapedWord, ProcessShapedWordInternal, text-run constructors, and all FontVisibilityProvider implementations. No obsolete signature or unresolved merge markers remain in the port.

## Remaining integration checks

A full Gecko compile and runtime font probes are still required; this task did not build Firefox. The focused harness validates the cache structure and matching logic, not Gecko headers, linking, generated bindings, or rendering. Aggregate application must include the later unified-maskconfig patch, which replaces the font seed manager's inherited fallback with container-aware overlay lookup. Runtime checks should include canvas/OffscreenCanvas workers, case-transformed text, MathML, and multiple containers sharing fonts.
