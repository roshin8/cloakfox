# Container workflows — task 7

Implemented `CloakfoxContainerWorkflows.sys.mjs` and dynamically appended
`content/container-workflows.js` UI. Both are mirrored into firefox-src. Root
owns moz.build/jar.mn/settings.html and startup integration: register the module,
package and defer-load the script, and call initCloakfoxContainerWorkflows once
at delayed startup. The UI needs no fixed markup.

Site rules reuse Firefox 155's native ContextualIdentityService associations and
DocumentLoadListener container selection before channel creation. Input is
canonicalized to an exact lowercase IDN hostname, checked with Firefox eTLD,
and rejects URLs, paths, wildcards, IP addresses and public suffixes. Rules target
named containers. Removing a rule restores Firefox's baseline-container behavior;
there is no forced-default rule because native zero means no association. Rules
do not claim to cover private windows, subframe/background requests or entire
registrable domains. The UI exposes add/remove and explains exact-host scope.

Temporary creation explicitly confirms automatic deletion after last-tab close
and on next startup, then persists the native identity and recovery marker before
opening a tab. Cleanup calls the reviewed IdentityActions service, retains its
marker until data clearing and container removal succeed, and retries errors
with capped backoff. Startup recovery closes remaining temporary tabs and clears
them after session restore is ready. Missing/orphan identity markers receive
scoped cleanup before removal. Normal identity/name records are not targeted.
This is not private-history mode: shared history/passwords/bookmarks remain, as
stated in the UI. Native identity persistence uses a small version-specific
adapter that disarms the DeferredTask and awaits the real save, because the
DeferredTask logs rather than propagates disk-write failures.

Identity-settings backup is encrypted before any file write, using WebCrypto
AES-256-GCM, a fresh 96-bit IV and 128-bit salt, and PBKDF2-HMAC-SHA256 with
600,000 iterations. The file has an authenticated format/version context and
fixed KDF parameters; malformed/oversized envelopes and wrong passwords fail.
The password is never stored. Export/import use native file pickers; exported
files are chmod 0600. Export includes default/named-container persona seeds,
overrides, timezone/persona settings, connection policies and native exact-host
rules, and excludes temporary containers. It explicitly excludes cookies, site
data, passwords, bookmarks, history and full-profile data.

Import validates an allowlist of keys/types, seed lengths, IDs, host rules,
connection settings, timezone, icon/color and limits. It creates fresh named
containers, including a fresh named copy for backed-up default settings. It
remaps rule IDs and never overwrites existing identities or host rules. Conflicts
are checked before creation and again before rule writes; concurrent imports are
rejected. Failed imports remove only newly created containers/rules; rollback
failure is reported honestly. Network settings are blocked during population,
then the imported route is applied before rules can use the container.

The UI separately offers native profile-backup settings only if actual
BackupService archive/restore availability reports enabled in this build. It
makes no unconditional macOS/support/encryption guarantee for that service.
Its settings UI owns full-profile backup behavior; this workflow does not turn
on an automatic backup or create an unencrypted profile archive.

Verification: `node --test tests/fingerprint/test_container_workflows.mjs`:
**8 passed** (six initial tests failed against unimplemented stubs). Tests cover
host parsing, encrypted roundtrip/non-determinism/tampering/wrong-password/KDF
limits, untrusted schema rejection, remapping, conflicts and rollback, temporary
clear sequencing/failure retention and startup recovery. Node syntax checks of
module/UI passed. Live native rules, file-picker export/import, last-tab cleanup,
startup recovery and macOS backup UI availability remain controller verification
work; no browser/build was run by this worker for this task.

## Review follow-up

All four findings in workflows-review.md were addressed. Whole-window teardown
now schedules tracked temporary cleanup even without TabClose; the ordinary
hasTabs check preserves temporary tabs in other surviving windows. Failed-import
rollback tracks host→new-ID ownership and removes an association only if it still
points at that imported ID. Rollback now awaits persistence after removal; native
success writes identities before prefs, and a failed cleanup save explicitly warns
that containers/rules may remain or return after restart. Imports are **not crash
atomic**: an interruption before final save can leave partial new identities.
No full transaction journal or atomic cross-file claim was added.

Native opener/openee/named-target groups with multiple top-level contexts may
retain their existing container for compatibility. Both site-rule help and save
feedback now disclose that exception, in addition to private/background limits.

Focused workflow tests now **12 pass**; added regressions failed before fixes for
whole-window teardown, rule reassignment during save, awaited rollback persistence
and honest rollback-save failure. The new disposable
`probe_container_workflows.py` exercises actual native routing with a loopback
server and local domain mappings, checking the server sees only target cookies
for independent exact-host navigation, negative hosts keep default, and a related
popup intentionally keeps default. It also checks encrypted file roundtrip,
new-ID seed retention and existing-rule conflicts, last-tab and whole-window
cleanup, persisted startup recovery markers, and reports native backup service
availability. The restart case injects a pending marker after clean shutdown to
simulate interrupted cleanup deterministically; it is not an OS-crash test.
The probe compiles but was not run by this worker; root owns sequential live runs.

## Native feature gate correction

The first controller live routing run exposed Firefox's upstream default-false
`privacy.containers.switchDuringNavigation.enabled`. Added a Cloakfox
`defaultPref(..., true)` so explicit native host rules actually run; profiles
without rules are unaffected and explicit user opt-out survives restart. The
workflow UI now exposes an automatic-routing checkbox and reports saved rules
inactive when disabled. `setSiteRule` rejects adding a rule while the native
feature is disabled rather than falsely reporting active routing. Config, module
and UI are mirrored. The fresh-default/opt-out and disabled-write regressions
failed before the fix; **18 combined daily-default/workflow tests pass**. No
browser/build run was performed by this worker for this correction; controller
must rerun the native probe against the updated build.
