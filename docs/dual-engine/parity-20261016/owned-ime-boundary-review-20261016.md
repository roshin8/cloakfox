# Owned native input boundary review — development candidate

Independent reviewer: `/root/review_owned_ime_boundary`. Read-only source review of the owned input renderer APIs, private browser/frame RPC, privileged continuous reader, Cocoa metadata setter and AppKit adapter. This is a partial development increment, not final whole-port or installed-artifact approval.

- **P1: stale password/focus metadata.** Same focused text node can change to password without OnFocusedNodeChanged. Cocoa can pass the next key to a normal NSTextInputContext before a post-input query discovers the change. Pending frame-A replies also lacked a current-focused-frame check. Source flow confirmed; physical third-party IME exposure was not exercised.
- **P2: explicit IME replacement base.** Compiled independent harness reproduced replacement start20 being sent while local marked range stayed10 and selection14 instead of24.

Both findings have automated repair evidence. P2 has maintained AppKit RED/GREEN coverage. P1 uses a native TextInputManager type callback before the desktop virtual-keyboard early return, bounded private invalidation, current-frame/type epochs for metadata, and conservative AppKit context retirement while fresh metadata is pending. The maintained transition regression passes without requiring a focus change. A controlled renderer-busy cross-origin regression reproduces the older helper returning text metadata and verifies that the new helper withholds it after password focus changes. This does not assume that different origins use separate processes.

The full final candidate passed154 native engine tests (118.494s), CTest2/2, source/SDK/embedded-framework hashes, isolation, transport and installed-Gecko coexistence. Engine Node61/61 and Gecko Python141+13subtests passed. Browser acknowledgements preserve a renderer-validated operation result independently of metadata freshness; stale query acknowledgements remain rejected. Whole native host checks passed for metadata validation/invalidation, stale routes, large viewports, epoch retirement, startup cancellation, video15frames, tab retirement and helper death. An older helper without the type-invalidation capability is rejected before fixture requests.

Physical IME candidate placement/typing and password transitions with a real input method remain untested because the computer-use tool reports the Mac locked. Cold development-clone startup also remains unaccepted. This review and its repairs do not approve the complete engine port, ordinary-site switching or an installed dual-engine release.

No reviewer modifications, ordinary-site tests, permission changes, installed app changes or production release capability increases occurred.
