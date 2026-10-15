# Firefox 158 port code review

Independent reviewer checked the changed native integrations against preserved 157 input patches and intermediate native fixture, rather than treating the already dirty HEAD as the complete baseline.

## Findings and resolutions

P1: Initial patch regeneration omitted no-final-newline metadata, fusing source lines and later diff headers in several patches. Corrected formatting includes explicit metadata, standalone git diff headers and complete context. The reviewer independently compared all 333 patch targets in the normalized replay fixture with native source: zero missing files or byte drift. The subsequent fresh strict replay applied 128 patches without offsets or fuzz and matched 335 target/staging hashes.

P2: The new Firefox 158 feature probe initially required exact protected DOMRect widths, contradicting existing geometry noise. The corrected probe retains exact CSS grammar/computed-width assertions and exact disabled/stock geometry, while checking protected DOMRect widths within the native ±0.2px bound and offsetWidth within ±1px. It verifies the master state, seed 12345, a valid 32-byte secret and standard/strict policy without site exceptions. This fixes the test expectation without changing native protection. The isolated rerun passed.

## Reviewed integrations

- 158 UTF8 user-agent interfaces, UTF16 manager/UAData boundaries, caller and container ownership.
- 158 unified SVG text bounding boxes, TextContentBounds and document-scoped bbox/CTM noise.
- PermissionsPolicy class/path migration, modern header parsing, inherited denials and exact window-management empty-list denial when upstream header parsing is disabled.
- Native location consent and 158 network-geolocation missing-URL validation/logging.
- Patch formatting and source/replay coherence.
- Final ClientWebGLContext DOM namespace qualifications; the owner-method test adds matching namespace aliases without replacing the extracted production method or weakening owner assertions.
- Final test changes: PermissionsPolicy preference/header expectations, build staging fixture helpers and mandatory successful staging calls, persona UI failure diagnostics that rethrow, and Firefox 158 CSS/JPEG XL coverage.

## Final outcome and limits

No remaining actionable findings in the reviewed changes. Both P1 and P2 are resolved. Final strict replay records 128 successful patches and 335 matching hashes with zero offsets/fuzz/drift; the reviewer independently checked those hashes against the native files. The preserved 157 native-baseline parity report records 333 targets with zero drift. Native build 4 completed successfully.

Recorded verification reviewed: Node 242/242; Python 39 passed with 1 conditional non-Chromium-UA skip; runtime 110 initial passes plus 3 successful explicit reruns, covering 113 probes in total. Reruns addressed a missing local websockets dependency, the geometry expectation above, and a persona UI click failure that did not reproduce with failure diagnostics. These results are evidence from the saved runs, not independent reruns by this reviewer.

The extra desktop pointer check initially passed 142/145 and passed 145/145 on an isolated rerun. Investigation observed subsequent trusted exits; their cause remains unidentified. That intermittent observation is not established as fixed, and no product code was changed for it. Review was focused on port integrations and the specified test repairs, not an exhaustive audit of inherited 157 behavior. The reviewer did not launch browsers or builds. Package validation was still underway at this final review.

Post-review package validation (primary agent): the completed DMG-mounted app passed 12/12 representative probes. Version/build identity and Mach-O UUID parity were verified; no native source changes followed review. See `package-identity.json` and `packaged-results.json`.
