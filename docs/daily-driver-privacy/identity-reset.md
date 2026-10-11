# Container forgetting — task 3

Implemented explicit **Forget container data…** in about:cloakfox, separate from
**Change appearance** and **Reset persona settings**. Both appearance-only
controls now explicitly say cookies, logins and site data are kept; the popup
links users to full settings for destructive forgetting. Container enumeration
now imports ContextualIdentityService instead of the nonexistent Services getter.

## Scope and safety

The privileged service validates a numeric uint32 container ID, requires explicit
confirmation, checks that a public container exists (zero means default), and
rejects concurrent operations for the same container. It preflights active
session restoration and closing-window flushes before destruction. UI confirmation
names the container and explains tabs, tab restore records, cookies, site storage,
permissions and local active website logins; shared history, saved passwords,
bookmarks, identity/name and connection settings are retained.

During the operation, matching content contexts have JavaScript disabled and are
stopped; newly attached matching contexts are similarly paused and matching HTTP
requests are cancelled. Observer failures prevent a success result. Target tabs
are closed with skipPermitUnload/skipSessionStore, and remote browser teardown is
awaited. about:cloakfox remains open for confirmation/status. Windows are kept
alive with a privileged settings tab to avoid generating new closing-window
snapshots. Native ClearDataService then owns worker/quota/storage shutdown and
origin-attributes deletion; the exact API is
`deleteDataFromOriginAttributesPattern({userContextId}, callback)` with no flags
argument. Its failure bitmask must be zero. New target tabs are closed once more
after clearing before restore records and appearance are finalized.

All target math, keyboard and timing seeds rotate only after successful native
clearing and restore cleanup. The generated config includes the full
`fingerprint:secret` required by task 5. Explicit persona overrides and network
connection settings remain. Failure messages distinguish possible partial
clearing from post-clear restore/appearance failure. They do not suggest an
already-closed tab or deleted cookie can be rolled back.

## Restore data

`patches/cloakfox-container-forget.patch` extends SessionStore with an explicit
preflight and scoped cleanup API. The native clear-origin-attributes observer
now handles explicitly specified UCID 0. Pruning covers live-window closed tabs
and closed groups, mixed closed windows, saved groups, LastSession and deferred
states, session cookies, selected indices and orphan group/split-view metadata.
Closed entries use native removeClosedTabData bookkeeping so late content updates
cannot resurrect forgotten closed tabs. Unrelated restore records are retained,
including a window's closed records if its last open tab was the target. The
public cleanup awaits SessionSaver.run; the native observer schedules saving.

Add the owning patch at the end of patches/order.txt (controller owns order).
No existing patch currently touches SessionStore.sys.mjs. The patch is generated
against the original Firefox 155.0.1 tarball and is already applied to firefox-src.
This is deletion from current browser restore state, **not forensic erasure of
old sessionstore backups, OS snapshots or copied profiles**. It does not revoke
remote server sessions or delete saved password-manager credentials. Native HTTP
auth cache also observes clear-origin-attributes-data with scoped matching in
nsHttpAuthCache; no global active-login purge was introduced.

## Files and integration

- New `additions/browser/components/cloakfox/CloakfoxIdentityActions.sys.mjs`.
- `content/settings.js`, `content/settings.html`, popup/popup.html wording/UI.
- `moz.build` module registration; also registered task 4 NetworkPolicy and task 5
  SiteSeed at their owners' request. `jar.mn` registers task 4 network-settings.js.
- New `tests/fingerprint/test_identity_actions.mjs` and
  `tests/fingerprint/probe_identity_forget.py`.
- Owning SessionStore patch noted above.

Owned additions were copied into firefox-src. Root subsequently owns
settings.html/network script integration; this worker will not overwrite it.

## Verification and remaining work

`node --test tests/fingerprint/test_identity_actions.mjs`: **10 passed**.
Production logic tests cover invalid IDs/confirmation, clear/close sequencing,
concurrent actions, failure without rotation, native removal bookkeeping,
default/mixed/legacy string-ID restore records, selection preservation,
saved/closed groups and nested last-session state. Five initial tests failed
against explicit unimplemented service stubs; an additional legacy-ID regression
failed before its fix.

`python3 -m py_compile tests/fingerprint/probe_identity_forget.py` and Node syntax
checks of settings.js, IdentityActions and patched SessionStore passed.

Live probe (not run by this worker):
`CLOAKFOX_BIN=<built-binary> python3 tests/fingerprint/probe_identity_forget.py`.
It uses one disposable Firefox profile and a loopback HTTP server, checking
named/default container cookies+localStorage, target tab closure, another
container's live data, seed rotation, retained identity/network policy, native
saved-group and LastSession pruning. It does not use real profiles or malicious
sites. Root must run sequentially after rebuilding. Browser confirmation/UI,
IndexedDB/service-worker shutdown, mixed closed-window reopening, concurrent tab
creation stress, crash/restart persistence and platform-specific behavior still
need live verification before claiming the entire workflow verified.
