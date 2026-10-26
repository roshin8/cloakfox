# Keyboard lifecycle review

Independent reviewer: review_keyboard_lifecycle. Reviewed the actor and local runtime regression probe. No outstanding findings after test correction.

Borrowed EventTarget methods dispatch into the recipient realm before accessing source-frame wrappers. The realm registry has weak keys, and each recipient retains its existing site/container seed and timestamp map. Native exportFunction argument checks still reject cross-origin receivers; no allowCrossOriginArguments exemption was added. Missing-hook recipients use their native Xray event methods. Native same-realm descriptor behavior is unchanged.

Review initially raised a possible WindowProxy key collision. This was withdrawn after checking JS_WrapObject precedes ToWindowProxyIfWindow, which only converts actual globals, and running retained-document navigation coverage. Chrome-side wrappers preserve distinct inner-global keys in this path.

A real probe weakness was corrected: cadence is now measured on a fresh standalone EventTarget with no preceding listener that could normalize the same events. Candidate, packaged and installed probes pass. These tests cover synthetic keyboard events; they do not establish that an airline's server will accept a particular session.
