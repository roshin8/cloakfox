# Cloakfox — pending work

Living tracker of what's outstanding after the test-suite pass that landed on
`unified-maskconfig` 2026-04-19. Ordered by priority. Keep this file under
revision control so we don't lose context between sessions.

## 2026-10-10 — pre-push verification

Rechecked the installed signed application against the current module, actor,
settings and configuration sources; all bytes match. Fresh native incremental
build passes. All 43 Node tests pass, and all seven new ordered native patches
reverse/apply without fuzz and restore the exact source bytes. Both installed
app signatures verify strictly, and the appearance-recovery DMG checksum is
valid. Disposable-profile runtime results are recorded under
`/tmp/cloakfox-prepush-20261010/`; these checks do not modify the active call.
All 12 runtime probes pass: native profile selection, website appearance,
settings overrides, locale tags, bundled-font fixture/reference widths,
UA Client Hints, permission reporting, optional data-math noise, media failover,
workers, signed appearance reuse/cold launch and the real restart round trip.
The separate page/frame/worker identifier audit passes 259/259 checks. The font
fixture's headless checks do not replace the earlier native compositor visual
verification. Remote live camera/video delivery is not asserted by these probes.

## 2026-10-10 — persistent macOS appearance app and profile binding

Screen-share follow-up: macOS Settings showed the exact stable Firefox app
enabled, but a full restart still reported native ScreenCapture DENIED (2).
Filtered TCC logs confirm `Failed to match existing code requirement` for
`org.mozilla.cloakfox.appearance.firefox`/`kTCCServiceScreenCapture`: stored
requirement hash `256fcb1995831b8d03106a81e9473fb007540060`, running app hash
`21f0988ab9333690182b4a8f3fa78453f8a7836b`. Adding an app with the same bundle ID
while its old entry exists did not replace that stored requirement. Removed
the stale row through System Settings and re-added the exact stable bundle.
After the macOS relaunch, native ScreenCapture is AUTHORIZED (3), with Default
User retained. A normal HackerRank Share again opens Firefox's site permission
prompt and, after Allow, the native chooser. After the user's screen selection,
Firefox reports **You are sharing your entire screen** and HackerRank's stopped
sharing/failure overlay is gone. Remote viewer frames were not independently
inspected. No signature or browser settings were changed.

Implemented a stable per-profile `cloakfox-appearance/Firefox.app` path. An
unchanged source reuses the signed copy without rebuilding/resigning. Verified
signed resource seals plus executable/plist digests detect packaged updates;
full content digests cover unsealed/loose development builds. Replacement is
staged and signed before moving the old copy aside, with rollback on a failed
install. The running copy is never overwritten. Legacy schema-1 copies remain
readable so launching the updated original installation can migrate them.

The signed copy carries `Contents/Resources/cloakfox-profile.ini`. The ordered
`cloakfox-appearance-profile.patch` reads this during macOS profile selection,
including the early XRE-provider path before the XPCOM directory service exists.
It preserves explicit environment/command-line/profile-manager selection and
background/reset behavior. An invalid owning profile opens the manager instead
of creating a blank profile. The restart environment branch also avoids
claiming/creating a new dedicated profile for an appearance copy. Settings now
provides **Show app in Finder** for locating the actual bundle in OS permissions.

Verification: native incremental build and packaging pass; all four actual-module
cache tests pass (reuse, content updates, failed signing/replacement rollback,
damaged copy and running-copy protection). Seven isolated native startup cases
pass. The signed packaged appearance probe passes including plain cold launch
without `--profile` or `XRE_PROFILE_*`, branding/source preservation and signed
reuse. The packaged real-button restart probe passes both directions, restores
profile/tabs, and honors the saved choice from the original installation.

The initial plain-launch regression revealed the pre-XPCOM lookup bug and
created three blank test profiles. These alone were removed from the active
registry and archived under
`profile-backups/appearance-regression-20261010T221435Z`. The final probe leaves
only Default User registered. A standalone xpcshell networking-sandbox shutdown
failure also occurs with an empty script; the filesystem-only probe disables its
socket process, as a bare xpcshell executable has no macOS app path.

Installed the strictly verified signed build at `/Applications/Cloakfox.app`;
previous installation preserved under
`app-backups/appearance-recovery-20261010/Cloakfox.app`. Signed installer:
`cloakfox-146.0.1-beta.25-appearance-recovery-20261010.dmg`. Live migration verifies
the stable copy uses Default User, exactly one profile remains registered, the
seven original tabs and the extra New Tab window return, and the bundled
extension is running. A real direct reopen through the native app launcher
verifies the same Default User root, one registered profile and window tab counts
of 7 and 1. Signature digest and mtime remain unchanged and strict/deep codesign
verification passes. The settings button was clicked and Finder selects the
stable `Firefox.app` at
`~/Library/Caches/cloakfox/Profiles/v6fs6ydf.Default User/cloakfox-appearance/Firefox.app`.
The initial native Screen Recording state was DENIED (2); the permission reset
and successful screen-share retry at the start of this section supersede that
initial result. Remote camera/viewer verification remains a separate check.

## 2026-10-10 — scoped HackerRank camera failover compatibility

Fresh-launch follow-up: launching the updated source app generated the signed
Firefox appearance copy `a704eb1f-40ea-4edf-b949-fa1fba07a23f` for Default User.
The initial restart retained the correct profile and restored all seven tabs.
Directly reopening the copy later selected a new `gx673uci.default-default-6`
profile: Gecko keys installation defaults by executable directory, and the
new copy's installation entry was not associated with its originating profile.
The live routing entries in profiles.ini and installs.ini were backed up under
`profile-routing-backups/20261010-before-appearance-recovery`, then the exact
`483E54E88499AD8` entry was changed back to Default User with all appearance
processes stopped. Directly reopening the original copy now verifies the correct
profile and restored interview tabs. That manual repair covered only the old
copy; the permanent implementation and regression results above now supersede it.

At the user's request, removed all seven other Cloakfox profiles from the active
profile registry and directories, preserving Default User. Their data, five
existing local-cache directories and the original registry files are archived
under `profile-backups/unused-profiles-20261010T215716Z` in Cloakfox's Application
Support directory. All existing installation defaults now reference Default
User; the sole profile section is Profile0. Direct restart verifies the native
profile service sees exactly one profile, the active root is Default User and
all seven original tabs reopen. Regular Mozilla Firefox profiles were untouched.

The current original copy's native Screen Recording state is DENIED (2).
The fresh share attempt reports SDK error 6200, `user deny screen share`.
Awaiting the user's macOS permission setup before testing capture, fresh-call
recovery and remote camera delivery. Do not attribute this permission rejection
to the earlier Zoom transport disconnect, or claim the fresh-launch media test
has passed yet.

The startup trace reproduced an SDK participant-ID change during failover,
after the application saved its initial local ID. An ID-only live correction
restored active camera capture and a normal video player while sharing stayed
connected; no readiness flag, transport or permission changes were required.

Added `CloakfoxHackerRankMediaChild`, restricted to top-level HTTPS
`www.hackerrank.com/pair/*`. It discovers the initialized application store
and AV getter without fixed bundle IDs/export names, refreshes only a stale
connected local ID from the SDK, and increments the application's render
epoch. It never starts capture or changes SDK/browser APIs. Default on;
`cloakfox.compat.hackerrank_media=false` opts out on the next load. Unsupported
application versions are left alone. This adapter depends on application
capabilities and may need maintenance after site changes. It does not explain
or fix the initial Zoom transport disconnect.

Verification: red/green regression; all 39 Node tests pass. Real Gecko tests
pass origin exclusion, two failovers on each of two fresh loads, zero capture
starts, unchanged readiness and opt-out. Native build/package succeed. Bundled
actor bytes match the tested source and bundled registration has the exact
origin scope. The live reload test reconnects at 4,693 ms with mismatched IDs;
the adapter reconciles the ID at 5,517 ms without manual state writes. After
normal screen selection and the normal Join video call button, live state is
connected, sharing true, capture active, camera video on, IDs matching, one
video player, no attachment failure and no Video unavailable text. Remote
peer receipt is awaiting user confirmation.

Signed `/Applications/Cloakfox.app` updated and passes strict/deep codesign
verification. Previous app preserved at
`/Users/zeus/Library/Application Support/cloakfox/app-backups/media-recovery-20261010/Cloakfox.app`.
The running cached Firefox appearance copy remains untouched; its working
call uses a process-local registration of the exact tested compatibility
actor. Launch the updated `/Applications/Cloakfox.app` after quitting the old
copy to use bundled recovery across restarts; the saved appearance is honored
by generating a fresh copy from the updated source. The old cached copy alone
does not contain the bundled fix. New macOS app copies may need their normal
camera/screen permissions again; no permission was reset in this follow-up.

Installer: `cloakfox-146.0.1-beta.25-media-recovery-20261010.dmg`.
Reports: `/tmp/cloakfox-media-recovery-{red,unit,gecko,packaged,build,package,sign,dmg-create,dmg-verify}-20261010.log`.
Startup tracing was unregistered, its resource substitution removed and its
two profile modules deleted. Temporary page console globals are removed and
Developer Tools is closed. The live compatibility resource remains at
`chrome/HackerRankMediaRecovery-20261010/CloakfoxHackerRankMediaChild.sys.mjs`
in the active profile so this browser process can keep using the fix without
changing its signature or stopping the call. After quitting this process, the
temporary resource directory can be removed; the installed app supplies the
bundled actor. No commit/push performed for this follow-up.

## 2026-10-10 — editor sync: Math noise corrupts Firebase trees

Follow-up: added **Randomize logarithms and powers**, backed by
`cloakfox.opt.math_data_noise` (default false). Pages and workers choose this
policy when their realm is created; reload affected pages after changing it.
Off preserves native log/log2/log10/log1p/pow, while other function noise still
uses the container seed and master switch. On restores deterministic noise to
the five functions and can reproduce Firebase data loss. Worker installation
reads an atomic StaticPref; the page actor has no extra per-call pref reads.
`cloakfox-math-data-toggle.patch` follows the correctness patch, with a verified
reverse/forward round trip. Settings' timer wording now describes fractional
jitter accurately instead of claiming it hides the underlying quantization.

Verification: two new actor tests fail before implementation and pass after;
all 33 Node tests pass. Native build succeeds. Default worker probe passes
31 signals, page/frame/worker audit passes 259/259, and both built and packaged
apps pass default/off/on/master-off plus real Settings UI on/off tests.
Packaged Zoom SDK local fake-camera preview passes at 1280x720 for both Firefox
and Chrome identities; this does not establish reconnect or remote delivery.
Installer `cloakfox-146.0.1-beta.25-math-toggle-20261010.dmg` has a valid hdiutil
checksum. Reports: `/tmp/cloakfox-math-toggle-{build,unit,workers,realms,ui,packaged,zoom-preview,package,dmg-verify}-20261010.*`.
The active app/call and temporary recovery override have not been changed.

Live HackerRank investigation reproduced `Invalid operation` in Firepad's
Firebase adapter. Its connection reports true, but SDK snapshots of revisions
A2–A7 have only `t`. A separate authenticated REST read of the same records
returns `a`, `o`, `t` for A2–A6, while A7 itself has only `t` on the server.
No shared history was modified or deleted by the investigation.

The failing live seed is 761685640. Page Math.log(4)/Math.log(2) is
1.999999999999675; Firebase's Base12Num constructor truncates this to 1
instead of 2, dropping nodes from three-field records. The installed worker
reproduces levels=1 and Math.pow(2,-52)=-4.77993705469089e-13 instead of the
native 2.220446049250313e-16. This is a verified browser math bug, independent
of editor event reporting. The Firepad adapter then skips incomplete edits.

Fix: leave logarithms and powers native in the page actor and worker method
list (`cloakfox-math-data-correctness.patch`). Regression tests failed before
the edit and pass afterward; all 31 Node unit tests pass. The updated worker
probe fails on the installed app in six intended checks. The corrected build
succeeds; page/worker checks pass (29 signals) on both the build and packaged
app, and the broader page/frame/worker probe passes 259/259 checks. The probe
preserves sample names as an array because WebDriver sorts object keys.
Live recovery is
verified: saved `math:trig_seed=0` as a field override in container 0, updated
its generated cloak_cfg, then reloaded with the user's approval. Math reports
levels [2,3] and the native power; SDK revisions A2–A6 retain `a`, `o`, `t`.
The editor recovers the interviewer's Python document and the user confirms
edits sync in both directions. A7 remains incomplete on the server and is
skipped; no shared history was changed. Keep the temporary override until the
corrected app is installed. No active app was replaced. The local build directory was
missing from firefox-src; restored that directory from its inner Git HEAD
without overwriting the other source changes, then completed the build.

Verified installer: `cloakfox-146.0.1-beta.25-math-fix-20261010.dmg`;
`mach package` succeeds and `hdiutil verify` reports a valid checksum. The
previous root installer is preserved. The installed application still uses
the temporary override; installing this artifact and restoring normal math
function noise afterward remain user-session follow-up work.

## 2026-10-09 — camera/microphone permission reporting fixed

2026-10-10 live session recovery: repeated the user's requested permission reset
through macOS Settings. Show in Finder verified the Firefox entry was the exact
3cb73c96 appearance copy; removed and re-added that same copy, authenticated by
the user, and reopened it. Native ScreenCapture state is authorized (3), with
appearance=true. A fresh normal Grant Access still stalled.

User-supplied errors add two concrete findings: the screen-media WebSocket can
fail, followed by SDK IMPROPER_MEETING_STATE/closed (5002); a late capture callback
also throws because desktopSharingValue is null after the SDK resets. Host DNS
and TLS succeeded over IPv4 and IPv6; that does not establish WebSocket/media
delivery. Native WebSocket logging was stopped, and a temporary parent HTTP
observer was removed. A proposed appVersion comparison did not isolate that
setting: generated config was refreshed by the persona bridge on reload, and
the page still reported Chrome appVersion. No persistent override was added.

Recovery used the page AV service's existing retireShareOperations() to clear
the stranded request, followed by a trusted-click startShareScreen() on the
current connected SDK, with real browser/OS capture permissions. The first retry
returned INSUFFICIENT_PRIVILEGES/only host can grab screen share (6204). After
the user stopped the other test share, the retry opened the normal permission
prompt and native picker. The user selected sharing; startShareScreen resolved,
and the actual lobby reports Screen share access granted. SDK capture is live
and unmuted, desktop=true, metadata loaded, 1667x1070. Cached encode stats were
fps=0/bitrate=0 at the first sample; remote delivery is awaiting user confirmation.
This is live-session recovery, not a shipped browser fix for the SDK race.

Second sample remains connected/live with one Zoom participant; cached stats
still show zero fps/bitrate. There is no remote test receiver joined yet. Removed
the temporary retry button and its click handler, kept the SDK's active preview
element so capture continues, and closed Developer Tools. Final normal lobby
still reports Screen share access granted. The diagnostic page variables will
disappear on its next navigation/reload; no SDK method wrappers were installed
for this recovery.

2026-10-10 Zoom follow-up: on a clean reload with only a forwarding native
getDisplayMedia observer and connection-change listener, Grant Access produces
Connected -> Reconnecting (reason: failover) -> Connected. There is no capture
API call; the AV service retains activeShareOperation.kind=start even though
the current SDK sharing encode/decode statuses are success. A separate trusted
click invoking the current SDK's startShareScreen with its existing share canvas
then reaches Firefox's real screen permission prompt. Cancelled with Not now:
native NotAllowedError and SDK user-deny error 6200; no content shared. This
supports a request stranded during SDK failover, rather than persistent native
capture denial. The cause of the failover and a durable fix remain unresolved.

An earlier diagnostic wrapped the SDK mediaAgent proxy method and induced
recursion. Discard those instrumented results; the clean comparison above does
not modify SDK methods. Reload removed all forwarding hooks/listeners and the
temporary test button, verified trace=undefined/button=false; Developer Tools
closed and the original lobby again offers Grant Access. No browser source fix
or build was made for the Zoom hang.

2026-10-10 recurrence: the running Firefox-appearance copy uses the original
v6fs6ydf.Default User profile, whereas yesterday's changes were saved in
yyh04u5k.default-default-4. The original profile lacked both the HackerRank
enumeration allowlist entry and devtools.selfxss.count. Restored these values
in the active profile and saved them through Services.prefs. After reloading
the real lobby, preview metadata reports 640x480, readyState=4, paused=false,
live/unmuted video. A disposable loopback probe also confirms that the scoped
legacy entry exposes device IDs on initial load and after reload; without the
entry, IDs remain empty in both cases. No capture requested by this probe.

Screen-sharing recurrence is independent: nsIOSPermissionRequest initially
reported PERMISSION_STATE_DENIED (2) for the current appearance copy. Adding
the exact copy over the existing enabled Firefox entry did not fix it. After
removing the stale appearance entry, readding the exact copy and restarting,
the native state is PERMISSION_STATE_AUTHORIZED (3). The real lobby reaches
the screen permission request. The user selected content, but the lobby still
reported Connecting. A separate trusted-click getDisplayMedia diagnostic then
resolved with a live, unmuted video track (396x32, 30 fps); it immediately stopped
the stream and sent no frames. That size suggests the small sharing indicator
was selected, rather than the intended TextEdit window. Native capture works;
HackerRank/Zoom end-to-end sharing remains unresolved.

A forwarding getDisplayMedia diagnostic installed before a fresh Grant Access
click stayed at waiting while Zoom repeatedly connected/reconnected. No screen
stream was active in webrtcUI (camera=1, microphone=1, screen=0, window=0).
Native WebSocket logging showed HTTP 101 handshakes; earlier connection errors
alone do not establish a persistent transport failure. Logging is stopped and
the forwarding diagnostic, local test button, and console were removed/closed.

Directly opening the appearance copy selected a fresh profile because the app
path has a different dedicated-install association. Restored the newly created
association in profiles.ini and installs.ini to v6fs6ydf.Default User; backups
are in /tmp/cloakfox-profile-association-backup-20261010. The original seven
tabs returned. This is a runtime repair; source appearance-profile handling
and stable permission identity still need a durable design. Finder is open
at the exact current copy. The existing DMG predates the source defaults added
yesterday. Do not assume every profile has those defaults installed.

`permissions:spoof` defaults on and previously forced every native
`PermissionStatus` to `prompt`. HackerRank's camera/microphone permission
monitor treats `prompt` as revoked, discarding a real grant. The native patch
now preserves Firefox's real Camera/Microphone state conversion and change
events. Other permission privacy behavior is unchanged; capture authorization
and OS permission checks are untouched.

The old packaged browser reproduced a camera grant returning `prompt`.
`probe_media_permissions.py` passes 13 checks in the rebuilt development app
and 17 checks in the final packaged app (including the added removal-event and
Always Ask cases). It uses a disposable local-origin permission manager and
never requests a stream or records devices. Native build, patch reverse/reapply
audit, reviewer check and DMG validation succeed. The running updated app
(BuildID 20261009174323) now shows Camera connected and Microphone connected
in the live HackerRank lobby. Camera frames and interview completion have not
been tested.

Screen sharing initially failed because macOS TCC rejected the replacement
appearance app's ad-hoc code requirement despite its Settings switch being on.
After the user completed authentication, the stale entry was removed and the
exact running copy re-added. TCC now returns authValue=2 for ScreenCapture;
the same copy was restarted. A local real `getDisplayMedia` call opens Firefox's
native screen chooser and cancelling returns `NotAllowedError`. No screen stream
or camera frames were captured by that diagnostic.

After restarting the authorized appearance copy and retrying, HackerRank
reaches Firefox's real screen permission prompt and macOS's native window/screen
picker. The user confirms screen sharing now works. The focused native log also
shows Zoom sockets exchanging binary data; earlier reconnect warnings were not
a proven remaining transport defect. A disposable-profile WebSocket echo probe
passes in both page and worker contexts. Some diagnostic coordinate clicks missed
controls because the native screenshot has Retina scaling/padding; keyboard/AX
and corrected input located the real pending permission prompt.

Temporary WebSocket logging is stopped, its about:logging tab is closed, and the
original interview tab is restored. No interview was joined by the agent. The
isolated TextEdit test window is left open to avoid interrupting an active share.
Actual camera frames and remote receipt by an interviewer remain unverified.
Reports: `tests/fingerprint/reports/media-permissions-2026-10-09/`.

### Camera follow-up: lobby preview restored

2026-10-10 deeper source follow-up: the full loaded PairShell/provider factory
28878 refreshes `localZoomUserId` after `zmClient.join` resolves. The earlier
service-only inspection missed this delegated update; absence of that setter
in `rejoinAfterLocalVideoAttachmentFailure` is not a demonstrated bug. The
provider's `Connected` reconnect handler only logs/records telemetry, without
an ID refresh there. The authorized reload reproduced an ID change after the
initial join update (see the startup sequence below). Public provider source
saved at `/tmp/cloakfox-reconnect-provider-20261010.js`. No website-specific
state injection or permanent camera reconnect patch was shipped. This proves
the stale application ID across failover, but does not establish why the first
media connection failed or whether an ID-only repair restores the camera.

Authorized reload startup sequence, 2026-10-10:
- 303 ms: observer attached; cached and SDK local IDs agree.
- 1,757 ms: SDK reports Connected; IDs still agree.
- 2,721–2,722 ms: SDK video decode/encode initialization succeeds.
- 2,882 ms: SDK reports Reconnecting; local IDs now disagree.
- 4,624 ms: SDK reports Connected again; IDs still disagree.
- 6,047/6,297 ms: video decode/encode initialization succeeds again; IDs
  remain different through the end of the 30-second trace.
The current loaded application's `isVideoDecodeReady` flag remains false, but
the full public module export shows that flag is only declared/set in the
store, with no video component consumers. It should not be treated as a causal
readiness gate for this page version. The normal video component uses capture
state, participant video state, connection status and the render epoch.
Reload stopped sharing and the page's normal Share again control opened the
browser chooser. Awaiting the user's intended screen selection before the
camera attachment check. IPv4 and IPv6 TLS/HTTP root requests to the earlier
Zoom media server both returned HTTP 404; this establishes current endpoint
reachability only, not successful authenticated media transport.

Startup tracing ran during the user-authorized reload. Temporary
`MediaStartupTrace` WindowActors are
registered only in the current browser process for the top-level
`https://www.hackerrank.com/pair/*` document. They record bounded metadata
(connection events, codec statuses, capture/share state and ID-match booleans)
without modifying media, permissions, UI state or editor content. No actual
participant IDs, camera frames, session tokens or URLs are collected.
The local fixture verifies early actor attachment, reconnect event capture,
ID-mismatch detection and exclusion of an unrelated private event field.
Report: `/tmp/cloakfox-reconnect-trace-20261010/smoke.log`.

Active profile root is `/Users/zeus/Library/Application Support/cloakfox/Profiles/v6fs6ydf.Default User`
(appearance app remains under the separate Library/Caches path). Trace modules
are in that profile's `chrome/MediaStartupTrace-20261010` directory, accessible
through Firefox's existing sandbox policy; loading modules directly from /tmp
failed in content processes. No sandbox settings or app signatures were changed.
Parent records are available via
`ChromeUtils.importESModule('resource://mediastartuptrace/MediaStartupTraceParent.sys.mjs').records`.
After the test, unregister `MediaStartupTrace`, remove the `mediastartuptrace`
resource substitution, and remove only the two diagnostic module files and
their empty diagnostic directory. Browser restart also clears registration.
Consoles are closed; the native sharing chooser is awaiting selection. The
diagnostic registration is still present and must be removed after verification.

2026-10-10 live interview recovery: initial state has device IDs available,
camera selected, SDK capture active, and both codec initialization statuses
`success`; HackerRank's `isVideoDecodeReady` is false. Reconciled that readiness
flag, but attachment still failed. Camera-only stop/start succeeds without
fixing the UI. A one-call observer on the AV service's ordinary `attachVideo`
method confirms the UI targets the saved local Zoom ID instead of the current
SDK local ID, receiving `INVALID_PARAMETERS`, code 6001, `user is not send
video`. Direct attachment to the current SDK local ID succeeds. The observer
restores the original method in `finally`; it does not wrap the SDK proxy.

Resynchronized `localZoomUserId` from `getLocalParticipantId()`, kept readiness
consistent with actual successful decoder initialization, cleared the prior
attachment-failure latch and advanced the normal render epoch. The normal
player attaches, `Video unavailable` disappears, and SDK encode counters show
640x360 at 17 fps, bitrate 23111, RTT 55, with no attachment failure. Remote
visibility is awaiting user confirmation. The ID mismatch was measured after
the site's attachment recovery ran; this does not prove it caused the initial
symptom. This is a session UI recovery, not a shipped browser patch. Earlier
failover logs and the initial readiness mismatch still need a clean reproduction
to establish a durable fix. Temporary statistics subscriptions are restored to
their original off state, the one-call observer is removed, and Developer Tools
is closed. The recovered camera player remains attached.
No camera images were collected. A diagnostic cleanup call initially used the
wrong wrapper argument (participant ID instead of an attachment object); it was
corrected before the successful camera-only restart.

The user reports that the camera light turns on and the other participant also
sees Video unavailable. The active interview showed camera enabled. Its
about:webrtc diagnostics showed successful ICE candidates and traffic; empty
RTP sections do not establish a transport failure because this Zoom SDK also
uses data channels. No specific permission, codec, or transport error was found.

Disposable local-origin probes pass fake-camera capture, video playback,
VideoFrame construction, and H.264 encoding with Firefox and Chrome UA settings.
The exact signed appearance app also captures 30 live camera frames and emits
30 H.264 chunks (10,488 bytes), with no encoder error. Only frame metadata and
aggregate pixel statistics were returned, not camera images. Those tests do not
establish usable image content or delivery through HackerRank/Zoom.

Both UA settings select the same tested Zoom capability flags; only its browser
classification changes. A live comparison with Firefox identity was proposed,
but not performed. The interview ended before camera-device selection or live
comparison could be tested. Root cause remains unresolved. Next: use a fresh
authorized test call, verify selected camera, then compare native Firefox and
Chrome identities while checking capture/encoder errors and remote receipt.
No additional browser patch or UA change was made for this symptom.

In a fresh lobby, the camera toggle reports on/Turn off camera while the preview
still says Camera off. Turning the camera off and on reproduces the mismatch.
The cached Zoom SDK's `createLocalVideoTrack().start(HTMLVideoElement)` succeeds
at 1280x720 with a fake camera under both Firefox and Chrome identities in
isolated local pages. This tests the SDK's direct HTML video preview path, not
HackerRank's state management or custom video-player rendering.

Diagnostic blocker: console evaluation throws NS_ERROR_UNEXPECTED reading
`devtools.selfxss.count`; Cloakfox's branding preference file lacks the stock
Firefox value of 0. Content debugging also reports target/actor errors; whether
restoring that preference resolves those errors is untested. A diagnostic
about:config tab is at its caution warning awaiting the user's click. No preference
has been changed, and no camera fix or browser-identity comparison was made.

Resolved later in the same session: Firefox reports saved Always Ask camera/mic
permissions as granted, while initially returning anonymous devices with empty
IDs. HackerRank filters these out and requires a selected ID before starting
preview capture. The local enumeration probe reproduced this sequence; IDs
became available after a successful native capture request.

Refreshing the lobby's existing devicechange handler selected the real camera
and microphone. The preview reported 640x480, readyState=4, paused=false, and a
live, enabled, unmuted video track. The user confirmed it works. The current
profile's native media.devices.enumerate.legacy.allowlist now includes the exact
www.hackerrank.com host, preserving Firefox's Slack/Riverside entries. This
exposes IDs earlier on that host while retaining capture permission checks.
The missing devtools.selfxss.count default was also restored to 0, preserving
normal console paste protection; console evaluation then worked.

Both defaults are recorded in source for the next build. No DMG was rebuilt
for these defaults. Reload persistence and remote video delivery were not
independently verified; the working lobby was left open. Diagnostic consoles
and the temporary about:config tab are closed.

## 2026-10-09 — animation Math hot path optimized

The actual HackerRank onboarding page animated its title slowly and delayed
the rest of the page. Native sampling caught a saturated content main thread;
a fresh-profile Gecko profile placed **13,855/15,948** samples in
`currentTrigSeed`, which deserialized the entire `cloakfox-seeds` SharedMap
value for each Math operation. The page's background animation makes tens of
thousands of trig calls per frame. Its standalone typewriter completes in
about 1.1 seconds, and the initial network response was about 283 ms.

The Math actor now shares one process snapshot, invalidates it on the native
SharedMap change event, and caches the master switch via a pref observer.
Numeric inputs use the actor realm's equivalent engine intrinsic to avoid a
second realm crossing; coercible inputs retain page-realm behavior. Sin/cos/tan
keep the page path when the global fdlibm policy is false, preserving private/FPP
realm policy on Windows. That policy guard updates live. Module observers retain
no actor/window. Captured function references, containers and seed removal remain
live, and existing result/descriptor/error semantics are preserved.

The new actor tests reproduced **2,003 snapshot reads** for a 2,000-operation
burst; the fixed actor reads once. A separate RED test exposed per-operation
pref reads, and another caught the fdlibm guard omission. Final Node **29/29**
and packaged Math/identifier/frame/worker regression **259/259** pass. One dev
regression attempt overlapped resource staging during a build and failed loading
`browser-webrtc.js`; the stable packaged rerun passes. Final native build,
packaging, actor-source audit and DMG verification succeed.

The packaged desktop page exposes its welcome button in **3.57 s** and its form
in **3.97 s**. Thirty subsequent animation callbacks have a **44 ms median**
and **74 ms maximum** gap. The background animation still carries overhead;
this is not a claim of Chrome frame-rate parity or interview compatibility.
No form details were entered, terms accepted or interview started. Existing
user-profile confirmation requires installation of the updated DMG.

Root installer: BuildID **20261009171117**, SHA256
`638cba7ebbf7da5c2d5b52192392e158c647f879abd67e9c438df2646e933bef`.
Reports: `tests/fingerprint/reports/onboarding-loading-2026-10-09/`.

## 2026-10-09 — settings edits reverting to persona fixed

Reproduced in the installed app: editing a UA saved a Chrome override pref,
but the active config and settings display reverted to Firefox. The settings
builder omitted the override layer that SeedSync applies at startup. It now
applies overrides last when rebuilding, including on persona regeneration
and reset actions. Also replaced the nonexistent
`Services.contextualIdentityService` getter with the explicit service import,
restoring actual containers in the settings dropdown.

`probe_settings_overrides.py` passes **22/22** checks in the development and
packaged apps: string/numeric edits, container selection/isolation, regeneration,
reload/restart persistence, website navigator/HTTP UA and Client Hints, and
single/all reset actions. Node **24/24**, scoring self-test, native build,
packaging and DMG validation pass. The installer at the repository root includes
these fixes; the installed Applications app has not been replaced automatically.
Reports: `tests/fingerprint/reports/settings-overrides-2026-10-09/`.

## 2026-10-09 — native UA Client Hints compatibility

`cloakfox-user-agent-data.patch` adds native `navigator.userAgentData` for
Chrome/Chromium/Edge user-agent overrides with the master enabled. Availability
is decided before page scripts run; Firefox personas/master-off leave the API
and interface absent. The navigator property honors secure-context gating,
while the interface's insecure-context exposure matches Chromium. Brands,
versions, mobile/platform and requested high-entropy hints derive from each
navigator's own UA; unknown/reduced OS/device details are withheld. Getters
return fresh native objects/frozen arrays; JSON and Promise conversion use
native bindings. Pages, frames and all worker types share their own container's
identity, without actors or page injection.

Local and packaged-app regression: **67/67** checks each, including a reproduced reduced-Android
metadata failure before correction. Native build, existing navigator coherence
(all four containers), worker/container coherence, Node **24/24** and scoring
checks pass. The actual HackerRank onboarding URL renders “Welcome to your
interview” with a Chrome UA and no unsupported-browser dialog; no interview
was joined and no proctoring permissions were accepted. Source audit confirms
all 11 patched files apply and match the compiled source. Native packaging and
DMG checksum validation pass; the new DMG is at the repository root. Reports are in
`tests/fingerprint/reports/user-agent-data-2026-10-09/`.

This implements the JavaScript Client Hints API, not HTTP `Accept-CH`
negotiation or Chromium-only window-management/WebRTC functionality. Interview
and proctoring compatibility remain unverified. Reload pages after identity or
master changes; no separate toggle is required.

## 2026-10-09 — malformed desktop text fixed

Reproduced the user’s wrong characters and missing letters in `about:cloakfox`
on the native desktop, with the master off. The bundled Menlo/Helvetica
substitutes reuse host PostScript names; the compositor resolved a different
font and interpreted the shaping font’s glyph IDs against it. For example,
the bundled middle dot’s glyph ID is the host Helvetica `č` glyph.

`cloakfox-bundled-font-rendering.patch` sends actual font tables over renderer
IPC for fonts from the bundled `/fonts/` directory. Native system-font
descriptors retain their existing path. Bundled family names and spacing
behavior are unchanged. The patch applies to pristine Firefox source, and
native build/package/DMG verification pass.

The packaged desktop app was visually checked against exact-file webfont
references (Helvetica, Menlo, Arial, Times New Roman), in ordinary content and
`about:cloakfox` with the master off. The original headline and Settings’
`files` labels (master on) also render correctly. The fixture’s automated
text/readiness/width checks pass with the master off/on in all four cases; native captures were inspected separately
because WebDriver screenshots bypassed the failure. Existing per-seed font
metric tests and font-name regression pass. Reports are in
`tests/fingerprint/reports/bundled-font-rendering-2026-10-09/`.

## 2026-10-09 — Settings initialization locale bottleneck fixed

User narrowed the intermittent `about:preferences` lag to trackpad scrolling
just after opening or refreshing Settings; settled Settings and ordinary pages
scroll normally. Earlier steady-state wheel/native-pan diagnostics passed.
Sampling the actual running browser during initialization found roughly 89%
of main-thread samples in locale component overrides repeatedly parsing the
Cloakfox config. Those getters also returned pointers into destroyed strings
and corrupted explicitly requested locale tags.

`cloakfox-locale-tag-correctness.patch` restores components of parsed locale
tags instead of applying persona defaults to every tag. Native default-locale
selection retains its override, with owned thread-local storage cleared when
the override is removed or disabled. The focused test reproduced six corrupted
explicit tags before the fix; 100 maximize operations dropped from 328 ms to
below the timer's 1 ms resolution after it.

Development and packaged locale probes pass **17/17** each. The packaged
Settings override regression passes **22/22**, Node checks **24/24**, and scoring,
native rebuild, packaging and DMG verification succeed. Desktop native macOS pan
checks on first load and refresh advance all eight gestures from 80 to 640 px;
largest sampled animation-frame gaps are 32 ms and 17 ms respectively. Fresh
profiles did not reproduce the user's full transient freeze before the fix, so
confirmation in the user's existing profile after installation is outstanding.
JS runtime default-locale refresh is outside this change; its cached behavior
is recorded rather than claimed fixed.

The root DMG is BuildID **20261009163611**, SHA256
`ae90e3c178de337270ab4bc8d8945f5c2ed7bdbd668d15e67ef7837da3c192f0`.
It has not been installed automatically. Current evidence is under
`tests/fingerprint/reports/preferences-startup-2026-10-09/`; earlier scrolling
diagnostics remain under `tests/fingerprint/reports/preferences-scroll-2026-10-09/`.

## 2026-10-09 — Website appearance honors Dark and Automatic

Removed the forced-light persona value, native `PreferredColorScheme` override,
and `matchMedia` color-scheme pin. Firefox's Website appearance selection now
controls both CSS and JavaScript in existing pages and frames. AutoConfig uses
`defaultPref(..., 2)` so fresh profiles default to Automatic and saved selections
survive restart. Old persona overlays containing the light pin are ignored for
color scheme; regeneration is unnecessary.

The rebuilt packaged app passes **52/52** appearance checks across containers 0
and 2 with the master switch on/off: Dark, Light, Automatic with the actual
built-in light/dark/system themes, live CSS/JS and change events, same-/cross-origin
frames, and saved settings after restart. System appearance is simulated only
inside disposable test profiles. Node **24/24** and the speech/media regression
also pass. Native rebuild and packaging succeeded using the earlier clean build
tree. Reports are under `tests/fingerprint/reports/website-appearance-2026-10-09/`.

## 2026-10-09 — full clean macOS build verified

Extracted the full pristine Firefox archive into an isolated source tree,
staged frozen additions/settings, and applied all **84 patches** successfully.
The native ARM64 release build used a new object directory with compiler caches
and Cargo incremental compilation disabled; no old build objects were reused.
`mach build` and `mach package` both exited **0**, and `hdiutil verify` confirms
the new DMG checksum is valid. The verified DMG is at the repository root.
Existing source/build directories and uncommitted work were preserved.

**Verification on the clean packaged app:** Math/identifier **259/259**,
OS-native desktop pointer and headless Gecko widget/APZ **145/145 each**,
fullscreen **13/13**, legacy workers **14 worker + 11 main signals**, headless
focus/visibility/scheduling/live switches, clipboard, container canvas/audio/UA
isolation, appearance, Math constants **4/4**, Node **23/23**, and scoring
self-tests passed. The first desktop probe timed out during WebDriver startup;
the isolated retry passed all assertions. The temporary-directory Python
selection issue was corrected by selecting the existing Python 3.12 environment.

Logs, manifests and the test report are retained under
`tests/fingerprint/reports/clean-build-2026-10-09/`. This closes the full clean
compilation follow-up; unrelated pending behavior and deferred work remain.

## 2026-10-08 — Math settings now update existing pages and workers

Removed the Math method requirement to reload pages or recreate workers after
seed changes or enabling the master switch. Native pass-through wrappers are
installed in web workers even when the master starts disabled; privileged
chrome workers retain their native Math methods. Calls honor the live atomic
master switch and their explicit container's typed seed cache. Parent preference
updates now carry the scoped `cloakfox.s.cloak_cfg_*` overlays to content
processes, including remote service workers; all other preference sanitization
continues through its existing path. The main thread parses changed overlays,
and workers perform no JSON parsing or IPC inside Math calls.

The page Math actor likewise installs gated wrappers before page scripts and
reads the live shared-data overlay, parsing only when its text changes. This
preserves page/worker state and function references captured before enabling
or regeneration. Missing/invalid/zero seeds pass through native results.
Changes propagate asynchronously through the existing process messaging.

**Verification:** the new tests first reproduced unchanged results on
initially-disabled live realms and stale seeds after regeneration. The rebuilt
packaged app passes **259/259** runtime checks: exact bits for all 23 methods;
initially-disabled and already-masked live realms; captured Math references;
retained realm tokens/counters/function identities; frame and worker types;
container isolation; seed zero, removal and invalid data; native API identities,
exception behavior and new-realm refresh. Legacy worker (**14 worker + 11 main
signals**), container canvas/audio/UA isolation, headless focus/scheduling/live
switches, **23/23** Node unit tests and the scoring self-test passed. The new
84th patch applies after the pristine 83-patch stack; all five patched native
files match the sources compiled. Native/resource builds and packaging passed.
This live behavior covers Math methods; other persona vectors retain their own
update behavior.

## 2026-10-08 — service-worker Math configuration gap closed

Remote service-worker configuration reached the main-thread IPC read but was
not cached on the cpp-first priority path. Worker-thread reads consequently
missed it. `cloakfox-worker-config-cache.patch` now stores that exact container
key under the cache mutex, serves off-thread reads from the cache, and refreshes
or removes entries during main-thread reads.

The page Math actor also used seed bytes 28–31 while the worker overlay used
16–19. It now honors the authoritative `math:trig_seed` overlay (including
explicit overrides), with the same derived seed as the fallback. Its existing
wrappers honor the master switch at call time, matching native worker wrappers.

**Verification:** the strengthened local identifier probe reproduced the gap
before the change, then passed **153/153** on the rebuilt packaged app. It checks
exact bits across all 23 Math methods in pages, same-/cross-origin frames,
dedicated/shared/service workers; distinct containers; overrides; live
master disable/re-enable on already-masked realms; and new realms after seed
changes, including zero. Legacy worker (**14 worker + 11 main signals**),
container isolation (canvas/audio/UA), headless focus/visibility/scheduling/live
switches, and **23/23** Node tests passed.

All **83 patches** applied successfully in build order to a temporary tree made
from the pristine Firefox archive's **180 target files**, with the normal
additions/settings staging. This validates patch application; it is not a full
clean compilation. The incremental native/resource build and packaging passed.
The initialization-seed limitation recorded at this stage was removed by the
live Math settings work above.

## 2026-10-08 — Firefox appearance covers the extension UI

Fixed the remaining extension branding in the private macOS Firefox appearance
copy. It now changes the extension name/description, toolbar tooltip,
extensions-panel labels, popup heading/title/mark and icon assets. The original
installation retains the Cloakfox UI, restored when appearance is switched off.
The built-in system add-on is hidden from `about:addons`; earlier claims that
its entry there was visible were incorrect.

The private copy changes only this built-in's resource root to
`resource://builtin-addons/firefox-panel/`, allowing Gecko to reload cached
metadata on the same profile without changing its ID, version, permissions,
extension origin or privileged bridge. Both loose development resources and
packaged `omni.ja` entries use that root. Author/homepage metadata is omitted
from the cosmetic copy; no Mozilla authorship is asserted.

**Verification:** the expanded appearance test first reproduced stale Cloakfox
labels in Firefox mode. It now passes on development and packaged apps, including
source preservation, unchanged bridge/permissions, stable extension origin,
Firefox icon payloads, rendered popup/working bridge, master-switch independence
and restoration. The actual **headful restart button** test passes in both
directions with profile/tab preservation; relaunching the original app honors
the saved appearance and shows the updated extension UI. **23/23** Node tests
pass. Rebuilt resources and packaged a new DMG. This fixes these visible labels;
it does not make the custom browser or popup indistinguishable from Firefox.

## 2026-10-08 — retained CSS hover and page-visible identifier audit

Implemented retained native `:hover` state under the existing opt-in
`cloakfox.opt.focus_masking` setting. Trusted departures preserve the hovered
chain and styles; returning to another element reconciles the old chain,
including nested cross-origin frames. Normal movement, shadow-DOM menus,
pointer capture and script-dispatched events continue to work. Turning the
option or master switch off clears retained hover on open pages. The changes
are tracked in `patches/cloakfox-hover-activity.patch`.

Replaced evaluated worker Math wrappers with native C++ functions, removing
the reproduced `CloakfoxWorker.js` exception filename and leaving
`Function.prototype.toString` native. Actor exports now opt into native names
and non-constructor behavior; unrelated privileged exports keep their existing
defaults. Timer wrappers delegate non-number delays to the native implementation
so caller-owned conversion errors keep their native type and stack. See
`patches/cloakfox-native-worker-math.patch` and
`patches/cloakfox-exported-function-identity.patch`.

**Verification:** rebuilt and packaged. The OS-native desktop and headless
trusted Gecko widget/APZ hover probes each passed **145/145**, including
disabled/master-disabled controls, frame cleanup, shadow menus, live switches
and capture. Input must reach the intended element before departure checks
count. The native path uses two moves at the same position to settle macOS/APZ
ancestor routing into nested frames; button presses/releases are sent once.
The page MAIN-world identifier audit passed **92/92** across containers 0 and 2,
frames and worker types.
Focus, fullscreen (**13/13**), clipboard, legacy worker (**14 worker + 11 main
signals**) regressions passed, as did **23/23** Node tests. All three new
patches round-trip against the generated sources. The disk-image checksum is
valid. These checks do not establish browser-wide indistinguishability from
stock Firefox.

**Follow-up:** the service-worker Math gap and missing pristine patch-application
check were resolved by the later service-worker configuration work above.

## 2026-09-07 — SAB timing privacy: PENDING, protection off

User decision: defer SharedArrayBuffer timing mitigation. Keep SAB, Atomics,
and shared WebAssembly available; do not enable worker jitter or serialization
by default. The experimental `codex/timing-signal-coverage` branch already has
`cloakfox.sab_worker_timing_masking=false`; Firefox's
`dom.workers.serialized-sab-access` default is also false. PerformanceObserver
timing coverage is separate and is not being disabled.

- **Evidence so far:** native SAB measurements were similar across actual
  containers, but reliable cross-container tracking has not been demonstrated.
  The installed test build did not apply the requested distinct personas, and
  the experiment used only one physical device.
- **Cost:** serialization suppressed the tested clock but increased completion
  time by 15.3% in an exploratory two-worker benchmark, above the agreed 5%
  budget. This is not a 15.3% slowdown estimate for ordinary browsing.
- **Revisit when:** a runnable current build passes distinct-persona checks;
  then test cross-container/session matching with other devices as negative
  controls, and measure false matches, compatibility, and performance before
  deciding whether any mitigation is worthwhile. Do not mark the signal safe
  or the privacy gap closed merely because work is deferred.

Detailed measurements are currently in the timing worktree under
`docs/superpowers/specs/2026-09-05-sab-privacy-measurements.md` and
`docs/superpowers/specs/2026-09-05-sab-linkability-baseline.md`.

## 2026-08-01 — font subsystem: #3 was dead, #4 wired (per-container fonts)

Investigated the per-container font vectors under systematic debugging. Two
distinct issues found and fixed; both verified against the built binary.

**#3 font-metric noise was DEAD (key mismatch).** `CloakfoxSeedSync.buildCloakCfg`
emitted the spacing seed as `"font:spacing_seed"` (singular) but C++
`FontSpacingSeedManager` reads `"fonts:spacing_seed"` (plural) — no C++ reader
for the singular key, so `GetSeed()` always returned 0 and `gfxHarfBuzzShaper`
added zero letter-spacing. Canvas/audio worked because their keys match. Fixed
by aligning the JS key (`fb8b083470`, JS-only, no rebuild). Verified: enabled
now shifts Arial width ~6–12px/persona (was ≤0.2px), deterministic per profile.
Note: an earlier `probe_font_metric_noise.py` (sans-serif) was a **false
positive** — with the whitelist active, CSS generics resolve nondeterministically
across launches, so it passed even while the seed was dead. Rewritten to measure
Arial and assert enabled≠disabled by >1px; proven to fail on the buggy key.

**#4 per-container font sets — wired (`d5796a4530`).** `FontListManager` filters
enumeration per userContextId at resolution time (AutoFontListContext wraps
gfxTextRun) but was dormant: it read the in-memory `sFontLists` map, only ever
populated by the dead `window.setFontList()` extension path. So every container
inherited the default (ucid 0) persona's fonts. Root cause confirmed via an
instrumented gfx build: the process-global `font.system.whitelist` is
parent-authoritative (content-process per-container `SetCString` is overridden),
so it can only carry ucid-0's set. Fix: point `HasFontList`/`IsFontAllowed` at
the live per-container source `CloakConfigOverlay_Get(ctx)["fonts"]` (lazily
cached), and drop the `ctx != 0` guard so the default container narrows too.
Scope = **narrowing-only**: each container shows its persona's subset of
host-present fonts; the cross-container linkage is gone. New regression:
`probe_container_fonts.py` (deterministic — injected overlays, ctx 1 hides what
ctx 0 shows despite one shared process whitelist).

**Residual / deliberately out of scope:**
- **Full cross-OS font independence** needs bundled font files — a host can only
  expose fonts it actually has (a Mac can't show `Segoe UI`), so a Windows
  persona on a Mac still can't present Windows-only fonts. `bundle/fonts/` does
  not exist here. Large project (+ font licensing); the "union whitelist" half of
  full independence was intentionally NOT built for this reason.
- **`"font:seed"` dead key.** `buildCloakCfg` emits `font:seed` (singular) with
  no C++ reader (`fonts:seed` or otherwise) — likely reserved/dormant. Harmless;
  worth confirming intent.
- **From-scratch patch validation.** `font-list-spoofing.patch` hunks were
  header/body validated and dry-run applied cleanly from pristine, but a full
  `make setup-minimal && make dir` (0-rejects) run is recommended before release.

## 2026-07-27 — cloakfox.enabled=false didn't disable C++ spoofing

**Bug.** `cloakfox.cfg` documents `cloakfox.enabled=false` as "disable all
spoofing globally (e.g. for debugging)", but it only gated the ~10 JS actors.
`initCloakfoxSeedSync` generates `cloak_cfg` unconditionally and the C++ getters
never checked the flag, so navigator/canvas/audio/webgl/screen/fonts kept
spoofing. Repro (verified): with `enabled=false` on a real Mac, navigator
reported `platform=Linux x86_64` / a persona UA instead of the real MacIntel.

**Fix (landed, built + verified).** Gate `CloakConfigOverlay_Get` — the single
choke point every per-container MaskConfig getter flows through — on
`cloakfox.enabled`; return an empty overlay when false so the browser presents
its real identity even with a persisted `cloak_cfg`. Guarded on
`NS_IsMainThread()` (Preferences::GetBool is main-thread only; DOM spoofing all
reads here on the main thread). Verified: `enabled=false` → real MacIntel/oscpu/
UA/core-count; `enabled=true` → still spoofs.

**Follow-ups — DONE 2026-07-27 (StaticPrefs mirror).** Added `cloakfox.enabled`
as a `RelaxedAtomicBool` StaticPref (`cloakfox-enabled-staticpref.patch`:
StaticPrefList.yaml entry + the `cloakfox` group in `modules/libpref/moz.build`)
so it can be read thread-safely off the main thread. Switched
`CloakConfigOverlay_Get` to `StaticPrefs::cloakfox_enabled()` (drops the
`NS_IsMainThread()` guard → now also gates **worker** reads), and gated
`Http2Session::SendHello` + `Http3Session::Init` on it (socket-thread safe) so
**H2/H3** fall back to the stock Firefox fingerprint when disabled. Verified
end-to-end: with `enabled=false`, `tls.peet.ws` reports the stock Firefox H2
akamai hash `6ea73faa…` (vs `a345a694…` chrome when enabled). `cloakfox.enabled`
is now a true global kill-switch. Built (export + dom/base + netwerk, XUL
relink) and runtime-verified. **Full from-scratch patch-stack validation
PASSED (2026-07-27):** a fresh `firefox-146.0.1` extract + `copy-additions` +
`make dir` applied all 63 ordered patches + the librewolf patches with **0
reject files** and set `_READY` — the entire stack (incl. the 4 new/modified
patches) applies cleanly from pristine.

## 2026-07-27 — font list was never spoofed (persona mapper dropped it)

**Root cause.** `bfToCloakKeys` in `CloakfoxPersonas.sys.mjs` mapped navigator/
screen/WebGL/audio/locale/geo but **never set `keys["fonts"]`** — the
BrowserForge-sampled `fonts` field was silently dropped. The C++ font-hijacker
treats `cloak_cfg "fonts"` as an allowlist that only activates when non-empty
(`mFontFamilyWhitelistActive = !mEnabledFontsList.IsEmpty()`; `IsFontAllowed`
returns true when empty). So the allowlist was **inactive** and the browser
exposed the **real host system fonts**, unspoofed and identical across every
container — a per-container isolation hole. CreepJS's "Like Windows 11" on a
Mac was reading the host's real MS-Office fonts.

**Fix (landed).** Added a curated per-OS `CANONICAL_FONTS` table (Windows/
macOS/Linux, `base` + seed-varied `optional`) and `bfToCloakKeys` now sets
`keys["fonts"]` from the persona's detected OS. We deliberately do NOT reuse
BrowserForge's `fonts` field — its values are cross-OS-contaminated (a Mac UA
can sample a Windows set), which is the incoherence being fixed. Verified: with
the persona active, host-distinctive fonts (Helvetica Neue, Menlo, Zapfino on
the Mac) are BLOCKED and the whitelist matches the persona OS.

**Known limitations:**
1. ~~**First-launch gap.**~~ FIXED 2026-07-27. `font-hijacker.patch` now sets a
   conservative cross-platform web-safe allowlist in the gfxPlatformFontList
   ctor when `GetStringList("fonts")` is empty AND `cloakfox.enabled` (default
   true) — the same in-ctor `Preferences::SetCString` path that already worked
   on launch 2, so it takes effect on launch 1 (unlike a plain
   `font.system.whitelist` pref default, which gfx reads before profile prefs
   load). Verified: fresh-profile launch 1 now BLOCKS host Mac fonts
   (Helvetica Neue/Menlo/Zapfino); `enabled=false` correctly skips the fallback.
   Built + relinked (compile 15s, XUL relink 22s).
2. **Cross-OS ceiling.** An allowlist can only REMOVE fonts, not add ones the
   host lacks. A Windows persona on a Mac host shows only the common web-safe
   intersection, not the full Windows set. It no longer self-contradicts (no
   Mac-only fonts under a Win UA), but shows fewer fonts than a real Windows
   box. True cross-OS font faking needs font-metric bundling — large, separate.
3. **Global, not per-container.** The system-font allowlist is process-wide
   (set once at gfx init from ctx-0's persona), so non-default containers get
   ctx-0's font set for system-font enumeration regardless of their own persona
   OS. `IsFontAllowed` is per-context but only gates @font-face load status.

## 2026-07-27 — actor descriptor-leak fixes + architecture reconciliation

**Architecture reality check (this file was badly stale below).** The
`cpp-first-exploration` branch's JS-spoofer surface is **10 chrome-principal
JSWindowActor pairs** in `additions/browser/components/cloakfox/actors/`
(Math, Keyboard, Timing, Gamepad, Midi, FeatureDetect, TabHistory, Timezone,
WebGPU, WebRTC) — the "must-stay-JS" vectors with no C++ coverage. It is NOT
the "~55 `inject/spoofers/*.ts` files" the older P1 sections below describe;
that MAIN-world extension architecture was removed in the pivot. Consequences:
- **"P1 — JS spoofer audit (~55 files)" and "P1 — Phase 3 JS→ISOLATED
  migration" below are SUPERSEDED.** The actors already run chrome-principal
  via `Cu.exportFunction` (the stealth goal of that migration) and there are
  only 10 of them.
- **"Cold-start Sec-CH-UA race" and the `header-spoofer.ts` items are MOOT.**
  No `webRequest`/header-spoofer code exists on this branch, and Firefox-only
  builds don't send `Sec-CH-UA` at all.
- **"WebIDL setters don't persist prefs → need Experiment API" is DONE.**
  `additions/browser/extensions/cloakfox-shield/experiment-apis/cloakfox.js`
  is the parent-process bridge (`setEnabled`/`regeneratePersona` write prefs +
  H2/H3 profiles from parent scope).
- **The self-destruct skip-coordination double-run is MOOT.** canvas/webgl/
  audio/screen are C++-only now — no JS fallback spoofer to double-run.

**Fixed: 6 own-enumerable descriptor leaks in the actors.** The actors
installed spoofs via plain instance assignment (`navigator.getGamepads = …`,
`spoofedMath[fn] = …`, `performance.now` via `defineAs`), creating **own
enumerable** properties where native keeps them inherited/non-enumerable. Net
tell: `Object.keys(navigator)` returned `["getGamepads","gpu","javaEnabled",
"requestMIDIAccess"]` and `Object.keys(Math)` returned all 23 method names —
stock Firefox returns `[]` for both. Fix: define on the PROTOTYPE with the
measured native flags (all `enumerable:true` on the WebIDL prototype; Math
methods `enumerable:false`). Files: `CloakfoxMathChild`, `CloakfoxGamepadChild`,
`CloakfoxMidiChild`, `CloakfoxFeatureDetectChild` (javaEnabled), `CloakfoxWebGPUChild`,
`CloakfoxTimingChild` (performance.now). Verified against the built binary:
`Object.keys(navigator)=[]`, `Object.keys(Math)=0`, all props `inherited`,
functionality intact (getGamepads→4 nulls, gpu→undefined, Math.sin still noised,
now still monotonic). NOT leaks (confirmed vs native baseline, left alone):
`window.setTimeout/setInterval` (native own+enumerable on the global) and
`History.prototype.length` (matches native accessor flags).

**Known low-severity gap (deferred):** `CloakfoxKeyboardChild` defines an own
`timeStamp` on fast-typed keyboard events (native inherits it from
`Event.prototype`). Exploiting it needs `hasOwnProperty('timeStamp')` inside a
handler on sub-min-delay keys — exotic; a stealthy fix needs a global
`Event.prototype` getter patch. Not worth it yet.

**Tooling:** `tests/fingerprint/probe_js_spoofers.py` hung (async awaits
blocked its result element); fixed with timeout-bounded awaits + a `finally`
append + a Python poll, and dropped the false-positive Math.PI/E heuristics
(bit-exact constants are correct by design). **Dev-build note:** the local
build is NON-packaged — actor modules are loose files at
`obj-*/dist/bin/browser/actors/` and `…/Cloakfox.app/Contents/Resources/browser/actors/`.
Copy edited `*.sys.mjs` there to test JS-only changes with **no rebuild**.

## 2026-07-27 — auto-coordinated per-container H2/H3 profiles (C1–C4 landed; E2E reveals a runtime gap)

Implemented the feature designed in
`docs/superpowers/specs/2026-07-26-h2h3-per-container-profile-design.md`,
committed as C1–C4 (`516f30a958`, `84e4f31f8c`, `8092f412a2`, `9bc5365d14`):

- **C1** `deriveHttpProfile(ua)` + **C2** write `cloakfox.container.<ucid>.h{2,3}_profile`
  on every `cloak_cfg` write (JS, verified).
- **C3** `Http2Session::SendHello` reads the per-container `h2_profile` (ucid
  from `ConnectionInfo()->GetOriginAttributes()`) + pushes it to the HPACK
  compressor. Compiles.
- **C4** threads `fingerprint_profile:u32` through the neqo FFI, resolved
  per-container in `Http3Session` (fallback global StaticPref). Full build
  succeeds (Rust included) → all four compile-verified.

**Per-container H2: initially broke at runtime, now FIXED (see below).**
`tests/fingerprint/probe_h2_per_container.py` sets container 1→firefox,
container 2→chrome and compares `tls.peet.ws` akamai H2 hashes. It first
failed (both = global firefox `6ea73faa…`); after the fix it PASSES
(container 2 = chrome `a345a694…`).

**ROOT-CAUSED + FIXED (2026-07-27). Per-container H2 now works E2E.**

Two things were going on:

1. **Real C3 bug:** C3 read the ucid from `ConnectionInfo()` in `SendHello`,
   but `ConnectionInfo()` delegates to `mConnection`, which is NOT attached
   yet — `CreateSession(socketTransport,…)` calls `SendHello()` immediately.
   So `ConnectionInfo()` returned null, the per-container branch was skipped,
   and every connection fell back to the global pref. **Fix:** resolve from
   `mSocketTransport->GetOriginAttributes()` (valid at `SendHello`).
2. **A testing artifact that masked the fix for hours:** `mach build binaries`
   relinks `obj/dist/bin/XUL` but does NOT re-package `dist/Cloakfox.app/
   Contents/MacOS/XUL`. The E2E ran the `.app` binary, so it kept executing
   the STALE `ConnectionInfo` build while the fixed code sat in `dist/bin/XUL`.
   Every "still broken" result + empty diagnostic was the stale binary. A full
   `make build` re-packages correctly; for incremental verification, `cp
   dist/bin/XUL dist/Cloakfox.app/Contents/MacOS/XUL` after `mach build
   binaries`.

Confirmed via `MOZ_LOG` on the correctly-deployed binary:
`CFXDIAG SendHello ucid=1 perctr='firefox'`, `ucid=2 perctr='chrome'` — and
`probe_h2_per_container.py` now PASSES (container 1 = `6ea73faa…`,
container 2 = `a345a694…`). Note H2 runs on the **parent process's socket
thread** (not a socket process); prefs are available there. The socket
transport carries the container's origin attributes
(`tls.peet.ws:443^userContextId=1/2`).

**C4/H3 VERIFIED (2026-07-27).** `Http3Session::Init` resolves per-container
correctly — MOZ_LOG confirms `ucid=1 -> h3Profile=0`, `ucid=2 -> h3Profile=1`
(from `cloakfox.container.<ucid>.h3_profile`), `ucid=0 -> global default`.
`mConnInfo` is valid in `Init` (unlike C3's null `ConnectionInfo()` at
`SendHello`), so H3 never had the timing bug. The resolved profile reaches
neqo via the compile-verified FFI; H3 SETTINGS emission is covered by neqo's
Rust unit tests. Note: no external service reports an H3 fingerprint
(tls.peet.ws only reports http2/tls/tcpip, and wouldn't upgrade to H3), so
there's no committed H3 E2E — the resolve was confirmed via MOZ_LOG instead.

**From-scratch validation DONE (2026-07-27).** Clean
`make setup-minimal && make dir && make build` from the committed patches:
`make dir` applied all patches (0 rej), `make build` packaged a working
`.app`. Against that fresh `.app`: `probe_h2_per_container.py` PASSES
(container 1 firefox `6ea73faa`, container 2 chrome `a345a694`),
`probe_container_isolation.py` PASSES (canvas/audio/UA per-container). The
whole C1–C4 feature is verified end-to-end from a clean build.

**Dev-workflow note:** `mach build binaries` relinks `obj/dist/bin/XUL` but
does NOT re-package `dist/<App>.app`; use `make relink` (added) after C++/Rust
edits so the packaged `.app` gets the fresh library.

## 2026-07-27 — WebRTC leak check

`tests/fingerprint/probe_webrtc_leak.py` (new): gathers ICE candidates and
checks for the machine's real local IP. Result: **PASS — no local-IP leak.**
Host candidates are mDNS-obfuscated (`*.local`); the real local IP
(`172.20.20.20`) never appears. The public IP shows via STUN srflx (by
design — the site already sees it over HTTP; `cloakfox.cfg` documents this
as the accepted position, with `setWebRTCIPv4` available for per-container
overrides). The dangerous vector (local/internal IP behind NAT) is closed.

## 2026-07-26 — first real-site anti-bot battery + fixes

Ran `antibot_battery.py` against the built app (firefox/chrome/safari HTTP
profiles) — the first real-site validation of this branch.

**Fixed:**
- **Persona navigator incoherence.** `CloakfoxPersonas.sys.mjs` took
  `navigator.platform`/`oscpu`/`appVersion` straight from BrowserForge's
  independently-sampled fields, which paired e.g. `platform "Linux armv81"`
  (ARM) with an x86_64 UA/oscpu — a self-contradiction any detector flags.
  Now derived coherently from the UA's OS (canonical frozen Firefox values)
  and `appVersion` = UA minus `Mozilla/`. Re-run confirms coherent
  platform/oscpu/appVersion on all three profiles.
- **`antibot_battery.py` extractors.** `areyouheadless` used a bare `#res`
  lookup that returned `<no element>`; now waits + falls back through
  selectors and body text, and surfaces upstream HTTP errors.

**Observations (not bugs / out of scope):**
- `bot.sannysoft.com`: clean — `webdriver: false`, all PHANTOM/HEADCHR/CHR
  automation checks pass on every profile.
- CreepJS: `chromium: false`, but ~33% headless signals. Needs a
  non-headless run to get a true read — see the follow-up below.

**Non-headless follow-up (2026-07-26, `--no-headless`):**
- CreepJS "like headless" **6% → 0%** (firefox/chrome) — that signal was a
  headless artifact, now cleared.
- Window/screen **dimension coherence resolved** in a real window (viewport
  fits within screen), confirming the earlier `inner > outer` incoherence
  was headless-only (`browser-init`'s `resizeTo` needs a real chrome
  window). The P2 dim-coherence item below is therefore a headless-only
  test artifact, not a real-window bug.
- Persona platform/oscpu coherence holds non-headless too.
- CreepJS "**33% headless**" persists even non-headless (constant hash
  `a427e0b8`). **Attributed 2026-07-26:** the harness now extracts CreepJS's
  per-signal headless breakdown, which reads
  `webDriverIsOn: true / hasHeadlessUA: false / hasHeadlessWorkerUA: false`.
  So the entire headless rating is `webDriverIsOn` — CreepJS detecting the
  WebDriver/Marionette connection the battery drives the browser with, NOT a
  browser fingerprint tell. `navigator.webdriver` is already spoofed false
  (sannysoft agrees) and both UA-based headless checks are false. A real
  (non-automated) user isn't driven by Marionette, so they wouldn't trigger
  it. Hiding Marionette from detection is an automation-stealth feature,
  out of scope for a daily-driver privacy browser — not tracked as a bug.
  Also fixed a latent race here: the CreepJS wait broke on
  "FP ID: Computing…" and could snapshot before compute finished; it now
  waits for the headless breakdown / a real FP-ID hash.
- `arh.antoinevastel.com/bots/areyouheadless` was serving `502 Bad Gateway`
  during the run — external site down, nothing to fix here.
- HTTP transport profile (chrome/safari) is orthogonal to the sampled
  navigator persona, so a "chrome" profile still presents a Firefox UA.
  By design; coordinating the two is a possible future feature, not a bug.

## 2026-07-18 — full-branch code review fix pass

A high-effort review of the whole `cpp-first-exploration` branch landed 15
fixes across 5 commits (`1f92a0cd5b`..`76b9357385`). Highlights + what's
still open below.

**Fixed + validated with a full build:**

- **Per-container C++ isolation (was release-blocking).** `MaskConfig`
  getters dropped the container id and always read `cloak_cfg_0`, so every
  non-default container reused container 0's fingerprint. `GetString`/
  `GetUintImpl`/`GetUint32` now take an optional `userContextId` and the six
  per-container managers pass their id. Verified end-to-end by the new
  `tests/fingerprint/probe_container_isolation.py`: containers 0 and 1 with
  different `cloak_cfg_<ucid>` overlays now produce different canvas + audio
  fingerprints (they were identical before the fix). Build compiles, links,
  runs.
- Actor `exportFunction` global leaks, `Math` brand, keyboard
  `removeEventListener`, timing monotonicity, gamepad array; WebRTC beacon
  gating + IP-race; ToolbarPin idempotency; SeedSync double-observer;
  PrefMigration one-shot; extension float-override corruption + status pill;
  build order.txt + dead generator + cfg comment. See the commit messages.

**Still open (need a build-verified pass — NOT done in the review):**

- ~~**P0 — cross-container contamination of persona-blob values.**~~ FIXED
  2026-07-21. `GetContextOverlay` now auto-resolves the current window's
  container (via `CloakConfigOverlay_CurrentUserContextId()` →
  `xpc::CurrentWindowOrNull`, main-thread-guarded, 0 in workers) whenever
  no explicit ucid is given, so the context-blind getters (navigator,
  timezone, fonts) read their own `cloak_cfg_<ucid>`. The `SetCloakConfig`
  ctx-0 mirror is removed. Validated end-to-end: `probe_container_isolation.py`
  now opens two NON-default containers (1 and 2) and asserts canvas, audio,
  AND `navigator.userAgent` all differ — the context-blind UA path exercises
  the auto-resolve. Built clean, test passes.
- ~~**P1 — `MergeUint`/`MergeString` non-atomic read-modify-write.**~~
  NOT A LIVE BUG (verified 2026-07-26). `CloakConfigOverlay_MergeUint/
  MergeString` (and `SetCloakConfig`) are only reachable via the
  self-destructing per-vector WebIDL setters (`window.setCanvasSeed`, …),
  and a tree-wide grep finds **no JS caller** for any of them — the old
  inject/core-bridge that called them was deleted in the cpp-first pivot.
  At runtime `cloak_cfg` is written *exclusively* as the pref
  `cloakfox.s.cloak_cfg_<ucid>` (experiment-API `cloakfox.js` + `content/
  settings.js`) and read by the C++ pref-reader, so the RMW race cannot
  occur. The merge/setter C++ is now vestigial — optional low-priority
  cleanup (removing it edits applied patches + needs a rebuild, for dead
  code that's harmless), not a bug.
- ~~**P1 — HTTP/2-3 profile setters write prefs from a content process.**~~
  NOT A LIVE BUG (verified 2026-07-26). The broken content-process setter
  *calls* were already removed; `setHttp2Profile`/`setHttp3Profile` remain
  in WebIDL but have no callers. The profile is set at startup via
  `defaultPref("network.http.http{2,3}.fingerprint_profile", …)` in
  `cloakfox.cfg` (parent process — correct). What's missing is only a
  *runtime, per-container* toggle, which is a FEATURE (would add a
  `setHttpProfile` method to the Experiment API + UI), not a bugfix.
  Deferred as a feature, not tracked as a defect.

**Build/infra gaps surfaced during validation:**

- **P0 for non-Xcode machines — missing `browser/branding/cloakfox/Assets.car`.**
  `browser/app/Makefile.in` copies a prebuilt macOS asset catalog, but the
  cloakfox branding ships only the uncompiled `Assets.xcassets`, so
  `make build` fails at the packaging `tools` step with
  `cp: .../Assets.car: No such file or directory`. Generating it needs Apple's
  `actool`, which requires **full Xcode** (Command Line Tools alone is not
  enough). Fix: on a machine with Xcode, run
  `actool additions/browser/branding/cloakfox/Assets.xcassets --compile <out> --platform macosx --minimum-deployment-target 10.15 --app-icon AppIcon --output-partial-info-plist <plist>`
  and commit the resulting `Assets.car` into
  `additions/browser/branding/cloakfox/` (matches how upstream `official`/
  `nightly` branding ship a prebuilt `Assets.car`). The 2026-07-18 validation
  build used the `official` `Assets.car` as an uncommitted placeholder.

- **P2 — window inner/outer/screen dimension incoherence under headless.**
  `probe_per_container.py` reports `dim_coherent: false` (e.g.
  `innerWidth 1440 > outerWidth 1150`). Root cause: inner/outer nesting is
  established by `browser-init.patch` via `window.resizeTo` + chrome CSS
  injection on the chrome window, which does not engage in `--headless`
  (no real chrome window / no resize). Appears to be a headless-only test
  artifact rather than a real-window bug; confirm by running the probe
  non-headless before spending effort. If real in a windowed browser, the
  fix is to also spoof `window.innerWidth/Height` to nest under the spoofed
  outer/screen. Not caused by the review fixes (they touch seed reads, not
  dimension values).

## P0 — blocks release / blocks real-site validation

### ~~Self-destructing WebIDL setters defeat C++/JS skip-coordination~~ — FIXED in commits `4bb9a03edb` + `20c5864f21`

`20c5864f21` adds the privilege gate: `cloakfoxIsConfigured` is now
`[Func='nsGlobalWindowInner::IsCloakfoxShieldCaller']` and only the
cloakfox-shield extension's ISOLATED-world content script can see it.
Page MAIN scripts get an undefined property — they can't probe whether
Cloakfox is installed via this method.

ISOLATED reads it at document_start, caches results in
sessionStorage['__cloakfox_configured']. MAIN's core-bridge.ts reads
sessionStorage instead. Manifest content_scripts order swapped so
ISOLATED runs before MAIN.



**Resolution (option 1 from below):** Added a non-self-destructing
WebIDL query method `window.cloakfoxIsConfigured(name)` that returns
true if a per-userContext spoofer manager has been configured already.

In `core-bridge.ts`, every callCore for a Func-gated setter is now
wrapped in `callOrAlreadyConfigured(setter, name, ...args)` which:
1. Tries the setter (works on nav 1).
2. Falls back to `cloakfoxIsConfigured(name)` (works on nav 2+).

If either returns true, the signal goes into `handled` and the JS
spoofer correctly skips. Covers all 12 self-destructing setters:
canvas, audio, navigator UA/platform/oscpu/HWC, screen, fontList,
fontSpacing, webglVendor, webglRenderer, speechVoices.

Backward-compat: on builds without the new WebIDL, the helper returns
false and behavior degrades to today's "always run JS fallback".

CI build pending (run `24699715160`). Re-probe against the resulting
DMG to verify `jsWebglRan: false` on second navigation.

---

### Original report (kept for historical context):

**Root cause discovered while debugging the WebGL Chrome-UA mismatch.**

How it's supposed to work: `core-bridge.ts` calls C++ WebIDL setters
(`setCanvasSeed`, `setNavigatorUserAgent`, `setWebGLVendor`,
`setWebGLRenderer`, `setScreen`, `setHardwareConcurrency`,
`setFontList`, `setSpeechVoices`, etc.). If the call succeeds, it
adds the corresponding signal name (e.g. `'graphics.webgl'`) to a
`handled` Set. The JS spoofer registry then skips any spoofer whose
name is in that set — leaving the C++ value as the only source.

What actually happens after the FIRST navigation:
1. WebIDL setter is called → C++ stores value in
   RoverfoxStorageManager keyed by userContextId.
2. C++ deletes the WebIDL property from the JS window AND sets a
   "disabled" flag in storage (e.g. `webgl_vendor_disabled_<id>`).
3. The disabled flag is checked at WebIDL binding time by `Func`
   attribute (e.g. `IsVendorFunctionEnabledForWebIDL`). On every
   subsequent window construction in the same userContext, the
   property is **never bound** at all — `typeof setWebGLVendor`
   returns `'undefined'` from the start, not "called and
   self-destructed".
4. `core-bridge.ts:callCore` returns `false` for
   `setWebGLVendor` because the function isn't there.
5. `handled.add('graphics.webgl')` doesn't fire.
6. JS WebGL spoofer runs as fallback and overrides
   `WebGLRenderingContext.prototype.getParameter` with its own
   values — which used to be Firefox-style.

The C++ stored values still persist in RoverfoxStorageManager, but
the JS spoofer's getParameter override wins (it ran later, on the
prototype). The C++ patch reads its stored values inside the
GetParameter implementation (`webgl-spoofing.patch:2328`), but that
implementation is bypassed by the JS prototype override.

This is why all WebIDL-handled signals (canvas, screen, navigator UA,
fonts, speech, timezone, etc.) end up "double-spoofed" — first by
C++ on nav 1, then by JS on every subsequent nav. The JS values win
at the prototype level. If the JS values diverge from the C++ values
(or are not browser-coherent), you get fingerprint mismatches like
the WebGL Chrome-UA bug.

**Diagnostic verified live:** sentinels added to `webgl.ts` and
`spoofers/index.ts` showed:
- nav 1: `coreHandled` contains 31 entries including `graphics.webgl`,
  `jsWebglRan` is false (skip works).
- nav 2: `coreHandled` contains only 12 entries (the non-WebIDL ones
  like `permissions.query`, `storage.estimate` that don't self-disable).
  `jsWebglRan` is true. WebIDL setters all show typeof `undefined`
  because they were never bound.

**Workaround already applied (commit `d487e550c6`):** make the JS
spoofer's GPU lists match what C++ would have emitted for each UA
family, so coherent values either way.

**Architectural fix paths (pick one):**

1. **Add a non-self-destructing query method.** New WebIDL like
   `__cloakfoxWebGLConfigured()` returns `true` if the disabled flag
   is set for this userContext. core-bridge.ts checks it BEFORE
   trying the setter; adds to `handled` based on either path. This
   is the cleanest — C++ remains the source of truth, JS skips
   correctly on nav 2+.
2. **Persist the handled set in sessionStorage.** core-bridge.ts
   reads sessionStorage on entry to remember "I configured WebGL
   on a prior nav this tab"; uses that to populate `handled` even
   when the setter is missing. Per-tab cache; per-container cache
   needs cross-tab coordination (background script).
3. **Don't self-destruct WebIDL after first call.** Re-bind on
   every nav; have the C++ setter no-op (already-set guard) on
   subsequent calls. Loses the security property of "page can't
   keep probing the setter" but the page can't observe much from
   a no-op anyway.

Option 1 is most invasive but architecturally cleanest. Option 3 is
smallest patch. Option 2 is workable but messy.

**Files touched (any option):** `additions/browser/extensions/cloakfox-shield/src/inject/core-bridge.ts`,
plus either C++ patches (option 1 or 3) or extension storage logic
(option 2).

### WebGL emits Firefox-style strings under a Chrome UA (verified broken)

**Symptom:** With the assigned UA = `Chrome/123 Mac OS X`, the WebGL
debug-renderer extension returns:
- `UNMASKED_VENDOR_WEBGL = "Apple Inc."`
- `UNMASKED_RENDERER_WEBGL = "Apple M1"` (rotates across runs within
  Apple family — M1, M1 Pro, M2, M2 Pro, M3, M4)

But real Chrome on Mac uses ANGLE and returns:
- `UNMASKED_VENDOR_WEBGL = "Google Inc. (Apple)"`
- `UNMASKED_RENDERER_WEBGL = "ANGLE (Apple, ANGLE Metal Renderer: Apple
  M1 Pro, Unspecified Version)"`

The values we emit are FIREFOX-style. With a Chrome UA they're a direct
mismatch any anti-bot would notice — Chrome ≠ ANGLE-renderer-string is
a known fingerprint divergence. Same issue would apply for Chrome/Windows
or Chrome/Linux profiles emitting Firefox-style Mesa/etc strings.

**Diagnosis:** All four WebIDL setters self-destructed in the probe
(`setWebGLVendor: undefined`, `setWebGLRenderer: undefined`,
`setCanvasSeed: undefined`, `setNavigatorUserAgent: undefined`). C++
WAS called. `core-bridge.ts:399` `pickPlatformGPU()` correctly returns
ANGLE-style strings for Mac platform (`"Google Inc. (Apple)"` /
`"ANGLE (Apple, ANGLE Metal Renderer: Apple M1, ...)"`). But what
WebGL queries return is the JS spoofer's `MAC_GPUS` list values
(`webgl.ts:` `"Apple Inc." / "Apple M1"`). Two scenarios:

1. C++ stored the spoofed value but the parameter-resolver patch reads
   from a different source / doesn't override `UNMASKED_*_WEBGL`.
2. C++ ran successfully but the JS spoofer ran AFTER and overrode it
   (the skip()/handled set didn't gate JS WebGL away).

**Fix path:**
- Verify which scenario via console.log injection in webgl.ts
  `initWebGLSpoofer` — if it runs at all, scenario #2.
- If scenario #2: fix the skip-gating in spoofers/index.ts so JS WebGL
  doesn't run when C++ took ownership.
- If scenario #1: fix the C++ webgl-spoofing.patch storage read at
  parameter-resolution time.
- Either way: align the JS MAC_GPUS list with the C++ ANGLE-style
  strings so even when JS wins it emits Chrome-coherent values.

**Files touched:** `additions/browser/extensions/cloakfox-shield/src/inject/core-bridge.ts`,
`additions/browser/extensions/cloakfox-shield/src/inject/spoofers/graphics/webgl.ts`,
`additions/browser/extensions/cloakfox-shield/src/inject/spoofers/index.ts`,
possibly `patches/webgl-spoofing.patch`.



### WebIDL setters don't actually persist prefs — RESOLVED 2026-07-27

> **RESOLVED:** The Experiment API now exists
> (`extensions/cloakfox-shield/experiment-apis/cloakfox.js`) and writes prefs +
> H2/H3 profiles from parent-process scope (`setEnabled`, `regeneratePersona`).
> The historical analysis below stands but the fix has landed.


**Status:** broken setter calls removed from `content/index.ts`;
`cloakfox.cfg` `defaultPref` remains the working path. The underlying
bug (below) is still real — the popup/options toggle won't take effect
until the Experiment API lands. Tracked here; no user-facing regression
because the calls weren't doing anything anyway.


**Symptom:** `window.setHttp2Profile("chrome")` self-destructs (proving the
method ran) but the `network.http.http2.fingerprint_profile` pref stays at
its default. Same for `setHttp3Profile`. The extension's
`content/index.ts` calls both setters from `globalSettings.http2Profile`
— it's a no-op today.

**Cause:** The C++ handler calls `Preferences::SetCString` /
`Preferences::SetUint` from content-process scope. In e10s Firefox the
parent owns the prefs DB; content-side writes don't IPC up to the parent
automatically, so they don't persist or propagate to the other content
processes that establish H2/H3 connections.

**Working path today:** `about:config` or profile `prefs.js` (set at
browser start via `opts.set_preference` in tests) — these write through
the parent. CLI-style pref override works. UI toggle does not.

**Fix path:** Expose a WebExtensions Experiment API in the
`cloakfox-shield` system addon that the background script calls. The
background runs with privileged-extension scope and can write through
`Services.prefs.setCharPref` (goes through parent). Scope: new
`experiment_apis` manifest entry + `schema.json` + `api.js` + plumbing
so the popup/options pages call `browser.cloakfoxPrefs.setProfile(...)`
instead of the (broken) WebIDL setter.

**Files touched:** `additions/browser/extensions/cloakfox-shield/manifest.json`,
new `additions/browser/extensions/cloakfox-shield/src/experiment_apis/`,
`additions/browser/extensions/cloakfox-shield/src/content/index.ts` (remove
the broken setHttp2Profile/setHttp3Profile calls), `settings/cloakfox.cfg`
(unchanged — defaultPref is still correct).

### Cold-start Sec-CH-UA race

> **MOOT (2026-07-27):** No `webRequest`/header-spoofer exists on this branch
> and Firefox-only builds don't send `Sec-CH-UA` at all. Nothing to race.
> Kept for history.

**Symptom:** First navigation in a session doesn't emit `Sec-CH-UA`,
`Sec-CH-UA-Mobile`, `Sec-CH-UA-Platform` headers. Second navigation
onward, they fire correctly. Verified live.

**Cause:** The `webRequest` header-spoofer in `background/header-spoofer.ts`
reads `browser.storage.local[activeProfile:${tabId}]` to get the brands.
That entry is populated only after the inject script runs, post-messages
to content script, which forwards to background. On the FIRST navigation
the storage key doesn't exist yet when `onBeforeSendHeaders` fires.

**Fix path:** Have `background/index.ts` pre-assign a profile to the
default container at startup (synchronously) and write it to
`activeProfile:<tabId>` for any newly-opened tab before the first request
fires. Or: move the brands source to `settings.profile.brands` on the
container settings, so the header-spoofer doesn't depend on the activeTab
round-trip for request 0.

**Files touched:** `additions/browser/extensions/cloakfox-shield/src/background/index.ts`,
`additions/browser/extensions/cloakfox-shield/src/background/header-spoofer.ts`,
`additions/browser/extensions/cloakfox-shield/src/types/settings.ts`.

### Real-site validation with a post-all-fixes DMG

Once CI `24637464609` (or its successor) goes green on both Linux + macOS:

- Run `python tests/fingerprint/antibot_battery.py` against the new DMG,
  review the markdown + screenshots.
- Manual check that the extension popup UI actually works end-to-end —
  pick a container, toggle protection level, verify the per-container
  fingerprint changes on a refresh at `browserleaks.com`. This was never
  tested before the `jar.mn` fix because the extension wasn't loading.
- Hit 2-3 real anti-bot sites (Cloudflare challenge page, Akamai-protected
  site, PerimeterX) with `chrome` profile active, confirm they don't
  immediately challenge.

## P1 — Phase 3 JS→ISOLATED migration

> **SUPERSEDED (2026-07-27):** Done differently. The spoofers are now 10
> chrome-principal JSWindowActor pairs using `Cu.exportFunction` — already out
> of page MAIN world — not the `inject/spoofers/*.ts` files this section lists.
> Kept for history; do not action.

**Why:** After the stealth pass, Cloakfox's *presence* is undetectable
from page MAIN. What's still detectable is the JS spoofer machinery —
when `initCanvasSpoofer` / `initNavigatorSpoofer` / … run in MAIN,
their `Object.defineProperty` getters leak via descriptor inspection,
`Function.prototype.toString`, and stack traces.

**Pattern:** move each JS spoofer to
`additions/browser/extensions/cloakfox-shield/src/content/spoofers/`
and use Firefox's `exportFunction(valueFn, pageWin, { defineAs: ... })`
to plant a native-looking getter on the page's prototype. The exported
function has `.toString() = "function <name>() { [native code] }"`,
carries no extension-file references, and is invisible to the usual
inspection class.

Scaffold landed 2026-04-21: `content/spoofers/README.md` +
`example-native-getter.ts` + commented template in place. The rest
below.

**Priority ordering** — start with spoofers that have NO C++ coverage,
since those currently have no choice but to run in MAIN:

1. `inject/spoofers/math/math.ts` — Math constants + trig noise.
2. `inject/spoofers/keyboard/cadence.ts` — no C++ backing.
3. `inject/spoofers/network/webrtc.ts` — SDP/ICE munging.
4. `inject/spoofers/graphics/domrect.ts` — DOMRect jitter.
5. `inject/spoofers/graphics/text-metrics.ts` — canvas text metrics.
6. `inject/spoofers/timing/performance.ts` — performance.now() jitter.
7. `inject/spoofers/storage/storage-estimate.ts` — navigator.storage.
8. `inject/spoofers/permissions/permissions.ts` — Permissions API.
9. `inject/spoofers/audio/audio-latency.ts` — AudioContext latency.
10. `inject/spoofers/hardware/touch.ts` — ontouchstart et al.

**Second tier** — signals with C++ coverage (JS is fallback only):

11. `inject/spoofers/navigator/user-agent.ts`
12. `inject/spoofers/graphics/canvas.ts`
13. `inject/spoofers/graphics/webgl.ts` + `webgl-shaders.ts`
14. `inject/spoofers/hardware/screen.ts` + `screen-frame.ts` +
    `screen-orientation.ts`
15. `inject/spoofers/fonts/font-enum.ts` + `css-fonts.ts`
16. `inject/spoofers/audio/audio-context.ts` + `offline-audio.ts`
17. `inject/spoofers/speech/synthesis.ts`

**Third tier** — visual/UX-adjacent:

18. `inject/spoofers/timezone/intl.ts`
19. `inject/spoofers/css/media-queries.ts`
20. `inject/spoofers/navigator/clipboard.ts`, `vibration.ts`,
    `window-name.ts`, `tab-history.ts`, `media-capabilities.ts`,
    `font-preferences.ts`
21. `inject/spoofers/hardware/battery.ts`, `media-devices.ts`,
    `architecture.ts`, `visual-viewport.ts`
22. `inject/spoofers/timing/event-loop.ts`
23. `inject/spoofers/iframe/*`, `rendering/*`, `devices/*`,
    `errors/*`, `codecs/*`, `crypto/*`, `intl/*`

**How to migrate one:**

1. Create `content/spoofers/<signal>.ts` using the
   `installNativeGetter` helper.
2. Import in `content/index.ts`, call before the bridge-attribute write.
3. `handled.add('<signal-name>')` so MAIN's registry skips the old
   path — same mechanism C++ spoofers already use.
4. Run `tests/fingerprint/probe_js_spoofers.py` to confirm the signal
   is still spoofed; run `tests/fingerprint/probe_stealth.py` to
   confirm `.toString()` reads as native code.
5. Once green, delete the MAIN-world implementation.

Keep changes surgical — one spoofer per commit so bisecting stays useful.

## P1 — JS spoofer audit (~55 files, only ~5 live-verified)

> **SUPERSEDED (2026-07-27):** The ~55 `inject/spoofers/*.ts` files no longer
> exist on this branch — the JS surface is 10 actor pairs (see the top entry).
> The audit that matters now is descriptor/stealth fidelity of those 10 actors
> (`probe_js_spoofers.py` + the descriptor probes described up top); the first
> pass found + fixed 6 own-enumerable leaks. Kept for history.

Live testing of Math.PI surfaced four stacked bugs (double-XOR seed,
noise-below-ULP, Proxy invariant violation, copy-before-override silent
failure). The double-XOR fix unblocks ALL spoofers' PRNG streams — so
per-domain seeding should work across the board now. But there's no
guarantee the rest don't have their own specific bugs (e.g. the
Math-style non-configurable property issue, or wrong override targets).

**Quick-audit tool:** `tests/fingerprint/probe_js_spoofers.py` dumps ~40
signals via a single Cloakfox launch and compares against "unspoofed
defaults on my machine" heuristics. Run it first to triage what's
broken before writing per-spoofer tests.

### Verified working via live probe

- `navigator.userAgent` — spoofed to Chrome 125 Windows post-warmup
- `navigator.hardwareConcurrency` — spoofed (16 vs real 12)
- `Math.sin(x)` — ±1e-12 noise on result
- `Math.PI / Math.E / ...` — per-domain noise at 1e-13 (post-fix)
- `Sec-CH-UA / Sec-CH-UA-Mobile / Sec-CH-UA-Platform` — emitted on
  warm navigations for Chromium profiles
- H2 SETTINGS / WINDOW_UPDATE / HPACK — all three profiles distinct

### Not yet live-verified (presumed working via C++ or untouched code)

Most of these have C++ patches that do the heavy lifting; the JS
spoofer is a fallback or complement. Low risk, but worth a probe run.

- `canvas.toDataURL` noise (C++ canvas-spoofing patch)
- WebGL `getParameter(VENDOR/RENDERER)` (C++ webgl-spoofing + JS)
- WebGL shader precision / extension list (JS: webgl.ts, webgl-shaders.ts)
- `OffscreenCanvas` (JS: offscreen.ts)
- `WebGPU` adapter info (JS: webgpu.ts, C++: nothing currently)
- `AudioContext` getChannelData noise (C++: audio-context-spoofing)
- `OfflineAudioContext` (JS: offline-audio.ts)
- `HTMLMediaElement` latency (JS: audio-latency.ts)
- `MediaSource.isTypeSupported` (C++: mediasource-istypesupported + JS)
- `RTCRtpSender.getCapabilities` (JS: codecs.ts)
- `screen.width / height / availWidth / availHeight` (C++: screen-spoofing)
- `window.outerWidth / outerHeight / screenFrame` (JS: screen-frame.ts)
- `screen.orientation.type` (C++: screen-orientation-spoofing + JS)
- `navigator.getBattery()` (JS: battery.ts; C++ disables entirely via pref)
- `navigator.mediaDevices.enumerateDevices()` (C++: media-device + JS)
- `navigator.maxTouchPoints` (JS: touch.ts)
- `navigator.architecture / bitness` via UA-CH (JS: architecture.ts)
- `window.visualViewport.*` (C++: visual-viewport-spoofing + JS)
- `navigator.clipboard.*` (C++: clipboard-spoofing + JS)
- `navigator.vibrate()` (C++: vibration-spoofing + JS)
- `document.fonts.check()` / FontFaceSet (C++: font-list + JS: font-enum)
- CSS font-family fallback enumeration (JS: css-fonts.ts)
- `navigator.fontConfig` (JS: font-preferences.ts)
- `window.name` persistence (C++: window-name-spoofing + JS)
- `navigator.mediaCapabilities.decodingInfo()` (C++: + JS)
- CSS media queries: prefers-color-scheme, prefers-reduced-motion,
  color-gamut, resolution (C++: media-features-spoofing)
- `speechSynthesis.getVoices()` (C++: speech-voices-spoofing + JS)
- `navigator.permissions.query()` (C++: permissions-spoofing + JS)
- `navigator.storage.estimate()` (C++: storage-estimate-spoofing + JS)
- `indexedDB.databases()` (C++: indexeddb-spoofing + JS)
- `window.Notification.permission` (C++: notification-spoofing + JS)
- `navigator.getGamepads()` (JS: gamepad.ts)
- `navigator.requestMIDIAccess()` (JS: midi.ts)
- `window.crypto.getRandomValues` (JS: webcrypto.ts)
- `window.Notification.requestPermission` (C++ + JS)
- `performance.now()` timer resolution (C++: timing-jitter-spoofing + JS)
- `setTimeout / setInterval` jitter (JS: event-loop.ts)
- Worker fingerprint propagation (JS: worker-fingerprint.ts)
- Service worker UA override (JS: worker-fingerprint.ts)
- `Error().stack` normalization (JS: stack-trace.ts)
- Emoji rendering quirks (JS: emoji.ts)
- MathML bbox (JS: mathml.ts)
- SVG bbox / CTM / getTotalLength (C++ handles; JS: svg.ts)
- Iframe re-patching on dynamic append (JS: iframe-patcher.ts)
- `Intl.DateTimeFormat().resolvedOptions().timeZone` (C++: locale-spoofing + JS: intl-apis.ts)
- Feature-detection (`document.implementation.hasFeature`, CSS.supports) (JS: feature-detection.ts)
- `Geolocation.getCurrentPosition` (C++: geolocation-spoofing + JS)
- `WebSocket` constructor (C++: websocket-spoofing + JS)
- `tab.sessionStorage` history (JS: tab-history.ts)
- Private-mode detection (JS: private-mode.ts)
- Architecture-detection via Math.fround tricks (JS: architecture.ts)
- Keyboard cadence / typing rhythm (JS: cadence.ts — no test, separately P1)

### Known likely-broken (same class as the Math bugs)

No evidence yet — identification needed via probe run. Categories of
bugs to look for:

1. **Non-configurable property replacement.** Math.PI/E are non-writable
   non-configurable; I had to swap Math entirely via Proxy (which also
   broke — see history) and ultimately via a plain object copy. Similar
   bugs may exist in:
   - `navigator.userAgent` override — browsers lock this with specific
     descriptor rules; verify assignment sticks in page world not just
     selenium sandbox.
   - `screen.width / height` — check descriptor.
   - `navigator.hardwareConcurrency` — check.
   - Any `Object.defineProperty(X.prototype, 'someNativeGetter', ...)`
     in the spoofers — if the original getter is non-configurable, the
     override fails silently.

2. **Double-XOR-style seed cancellation.** Now fixed for the fallback
   path (inject/index.ts `generateSeed` no longer includes domain). But
   verify no other spoofer does its own XOR-with-domain on top of the
   pagePRNG — that would re-introduce cancellation.

3. **Selenium sandbox / page world mismatch.** When writing tests, `Math`
   is one case. `navigator` might be another — check via inline `<script>`
   DOM injection pattern (same trick used in test_math_constants.py).

### Action items

- [ ] Run `probe_js_spoofers.py` against the next green DMG, save the
      output as the baseline
- [ ] For each signal marked UNSPOOFED in probe output, triage: is the
      spoofer disabled by default? Is it genuinely broken?
- [ ] Write a per-spoofer test for each broken one, following
      `test_math_constants.py` pattern

## P1 — test coverage gaps

### Cross-container uniqueness (not just cross-domain)

`test_math_constants.py::test_math_pi_differs_across_domains` covers
per-domain seeding. It does NOT cover per-container: that requires the
inject script to receive a real container-scoped seed from the background,
which in turn requires the tab to be routed through a specific container
via the Multi-Account Containers API.

**Fix path:** Either add a test-mode pref (e.g.
`cloakfox.test.force_container_seed`) that injects a specific seed via the
inject path for testing, OR use privileged Marionette to create a
container and open a URL in it, then read Math.PI.

### CreepJS trust score extraction

`antibot_battery.py` captures CreepJS screenshots fine, but emits
`trust: ?` — the selectors `.unblurred-trust-score, .trust-score` don't
match CreepJS's shadow-DOM-rendered output.

**Fix path:** Use `document.querySelectorAll` inside a `<script>` tag
appended to the page so it runs in page world (same pattern as
`test_math_constants.py`), and walk the shadow roots with
`element.shadowRoot.querySelector` to reach the score elements.

### `areyouheadless` timeouts

`antibot_battery.py` hits a 60s navigation timeout on
`arh.antoinevastel.com/bots/areyouheadless` during smoke runs. May be
site flakiness; may be the site blocking selenium-driven Firefox.

**Fix path:** Bump timeout to 90s AND/OR detect the headless-test verdict
via the `verdict_extractor` rather than waiting for full page load AND/OR
drop the site from the default battery if it's consistently flaky.

### Keyboard cadence spoofing

No integration test exists for `inject/spoofers/keyboard/cadence.ts`. The
spoofer adds jitter to `KeyboardEvent.timeStamp`. Worth a test that
synthesizes keyboard events via Marionette and asserts the timestamps
diverge from the monotonic clock.

### WebRTC SDP fingerprint

C++ patches cover WebRTC IP leak (mDNS suppression) but not SDP-level
fingerprint (media line order, fingerprint algorithm list). Worth
profiling what real Chrome/Firefox/Safari emit and spoofing it. Not yet
attempted.

## P2 — housekeeping

### `CLAUDE.md` refresh

The top-level `CLAUDE.md` still describes the pre-test architecture. It
doesn't mention:
- The `tests/fingerprint/` harness + selenium+geckodriver choice
- The 7 gotchas documented in `tests/fingerprint/README.md`
- The `defaultPref()` contract for cloakfox.cfg
- The `jar.mn` dest-path rule

Should be a short pointer block — the detailed docs live in
`tests/fingerprint/README.md`.

### Memory refresh

Session memory didn't capture the 7 bugs as anti-regression markers.
Worth writing to:
- `feedback_testing.md` — "Cloakfox extension tests need selenium+geckodriver,
  NOT Playwright (no Juggler patch)"
- `feedback_build.md` — "AutoConfig cloakfox.cfg must use defaultPref() for
  toggleable prefs; pref() clobbers on every startup"
- `architecture.md` — "Content-process WebIDL setters can't persist
  Preferences — use Experiment API from background"

### Stale Playwright commit

`8de1f2c1aa — Fingerprint test harness: Playwright + mitmproxy` is
superseded by `1d6bbec843` which rewrote to Selenium. The Playwright
test file was replaced but the commit message still mentions Playwright.
Harmless but confusing when grepping history.

## Out of scope (not pending — deliberately deferred)

- **TLS JA3/JA4 spoofing.** Requires NSS patches. Weeks of work, separate
  project scope.
- **HTTP/3 wire-level SETTINGS frame observation.** Would need
  mitmproxy-quic or wireshark integration in the test harness. The pref
  plumbing is verified; the SETTINGS emission is covered by the Rust
  unit tests in neqo-http3 that shipped with the patch.
- **HTTP/3 profile UI toggle per-container.** Same underlying problem as
  the P0 WebIDL-setter-doesn't-persist issue — the extension toggle
  needs the Experiment API path to actually work.

## How to update this file

- Move items to the completed section (or delete) as they land.
- Keep each bullet self-contained: symptom, cause, fix path, files
  touched. Future-you won't have the context you have today.
- If an item spawns subtasks, nest them in place rather than creating
  a separate file.
