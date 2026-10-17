# Native editor increment review

This is a scoped review of the development host, not the final Chromium-port review or release approval.

Independent read-only reviewer `review_native_editor_increment` examined the native Command+A/menu action, the Chromium `selectAll` command, and the private input diagnostic counters. It reported no actionable findings. The command retains browser/config/surface ownership validation and a strict field allowlist, invokes the focused native frame, and does not read the clipboard or extract text. The counters expose only five numeric totals through the existing privileged development service.

A second, separately scoped review examined the newly reproduced first-click ASCII-key loss and its repair. The repair permits the existing native keyboard path only while metadata is invalidated, the previous validated state is noneditable/null-field, Secure Event Input is acquired, the owner remains active, and the key contains plain ASCII without Option/Command/Control. It does not pass the event to `NSTextInputContext`, permit unbound Unicode composition, or relax the field/document checks on IME commands. The reviewer reported no actionable security/privacy findings in that additional change.

The reviewer performed static review and did not independently run AppKit or native engine tests. The author runs and records runtime verification separately. Initial Option/Unicode before field-type confirmation, general IME candidate placement, AX, drag/drop, remaining full native policy groups, production switching and installed-app acceptance remain outside this increment.

Observed regressions before repairs:

- The old helper rejected the maintained native editor test with `Unsupported feasibility input kind`.
- The actual macOS Command+A attempt appended text rather than selecting the embedded editor.
- A subsequent native run recorded three intended prefix keys but only `a`, then `af`; the private counters showed one queued key discarded on a field transition. This identified the first-click null-field queue failure.
- New AppKit boundary tests failed before the diagnostic and uncomposed-key methods existed and passed after implementation.

The actual Cocoa and CEF fixtures are separate from the installed application. No installed app, DMG, release capability group, sandbox policy or permission grant was changed for this increment.
