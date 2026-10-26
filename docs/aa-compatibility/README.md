# aa.com browser-identity comparison

Installed macOS Cloakfox, master protection verified enabled on every trial. Ordinary unauthenticated homepage navigation only; no flight booking, account sign-in, CAPTCHA interaction, cookie injection, or privacy opt-out. Disposable profiles imported the existing Cloakfox configuration, without personal site storage or login cookies.

The semantic setting under test is user-agent identity: navigator.userAgent, navigator.appVersion, and headers.User-Agent are changed together, with their effective DOM values and actual top-level HTTP request headers checked. Firefox mode naturally removes Chromium UA Client Hints. All other config keys remained unchanged within each comparison. The protected platform was Win32, so the tested Firefox identity was Windows Firefox 158; the original override advertised Linux Chrome 146.

Results:

- Same-session sequence: original, Firefox, original, Firefox all returned 403. These runs do not establish a useful setting distinction because the session carries previous site state.
- Fresh Firefox identity: homepage 200, redirect to /homePage.do, then 200; usable search form.
- Fresh original Chrome/Linux identity: initial 200 followed by 403 Access Denied.
- Second independent fresh Firefox identity: homepage 200, redirect to /homePage.do, then 200; usable search form.

Only the linked user-agent fields changed; no canvas, GPU, math, keyboard, focus, timer, storage, network isolation or permission protection was disabled. The user's actual settings were not changed. This isolates an identity-configuration compatibility difference in the tested clean sessions, rather than proving which undisclosed Akamai detector decided the result. Both browser family and UA OS text differ between the original and Firefox presets, so these trials do not distinguish engine-family mismatch from UA/platform mismatch or derived Client Hint checks. Two successful fresh trials do not guarantee future acceptance. The all-rejected reused-session result means a user-agent-only live switch is not proven sufficient for an already-rejected session.

Raw evidence is summarized in ua-comparison.json without cookies, fingerprint secrets, query tokens, or advertisement request logs. No automatic site-specific exception was added.
