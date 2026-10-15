# Experimental Chromium Command Line Tools build mode

Scope: user-authorized attempt to build with installed Apple Command Line Tools,
without Apple sign-in, Xcode download, system preference changes or fabricated
Xcode installations. Existing Gecko and CEF runtime behavior stay unchanged.

1. Pin the upstream Chromium 154.0.8037.98 mac_sdk.gni input by SHA256. Add an
   opt-in, non-official, system-toolchain-only branch that uses a CLT SDK helper.
   Keep the default Xcode/hermetic branches unchanged.
2. Write tests first: patch application and unchanged-input rejection; actual CLT
   discovery without xcodebuild; required paths/version metadata; missing tools.
   Use actual pkgutil/xcrun results, not an invented Xcode version. Record that
   legacy GN xcode_version variables represent CLT compatibility in this mode.
3. Apply the patch to a small pinned-source test checkout. Exercise the adapted
   SDK discovery, compile/run Cocoa+Metal with its discovered paths, and exercise
   the GN branch if a public standalone GN binary is available. Missing resource
   compilers and full CEF framework builds remain separate gates.
4. Run engine regression tests, document measured limits, review, commit and push
   the existing prototype branch. Do not claim full Chromium/CEF build success
   from SDK discovery, a minimal GN fixture or a native smoke test.
