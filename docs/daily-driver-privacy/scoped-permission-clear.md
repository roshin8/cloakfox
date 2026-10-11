# Scoped permission clearing follow-up

Added native `deleteDataFromOriginAttributesPatternWithFlags(pattern, flags,
callback)` to nsIClearDataService.idl and ClearDataService.sys.mjs. The original
API delegates with CLEAR_ALL, preserving its behavior. Owning patch:
`patches/cloakfox-scoped-data-clear.patch`; source is already applied, reverse
apply check passes. Root must add patch to order and rebuild IDL consumers.

For UCID 0, IdentityActions' owner now excludes CLEAR_SITE_PERMISSIONS,
CLEAR_STORAGE_ACCESS, CLEAR_STORAGE_PERMISSIONS and CLEAR_SHUTDOWN_EXCEPTIONS.
Historical OA0 permission records cannot be attributed to a single container.
PermissionManager also always strips container attributes for cookie,
https-only-load-insecure and ipp-vpn permissions. Nonzero CLEAR_ALL matches only
provably scoped nonzero records and retains these shared records. This does not
change the permission-isolation preference or attempt a clear-and-restore race.

PermissionsCleaner and ShutdownExceptionsCleaner implement origin-attributes
clearing; StorageAccessCleaner and StoragePermissionsCleaner currently do not,
so the latter categories are skipped under this API's existing no-broadening
contract. PermissionManager no longer observes clear-origin-attributes-data
(see its test_permmanager_cleardata.js). That legacy notification still has
unflagged auth-cache, push, reports, storage and SessionStore observers, however.
The new method therefore emits it only when AUTH_CACHE, DOM_QUOTA,
DOM_PUSH_NOTIFICATIONS, REPORTS and HISTORY are all selected. ALL and
ALL-minus-permissions retain it; a narrower mask does not accidentally clear
unselected categories. Unsupported origin-attributes cleaners remain skipped;
this method does not promise unsupported fallback operations for narrow masks.
The IDL documents that restriction. The callback still reports only selected
cleaner completion/failure; legacy observer completion has the old semantics.

Settings confirmation now explicitly says shared site permissions are kept;
only provably isolated named-container permissions may be removed. Root owns
remaining HTML wording. Settings.js was mirrored to firefox-src.

Verification:
- `node --test tests/fingerprint/test_scoped_data_clear.mjs`: 4 passed; all four
  failed before the missing API was implemented. This evaluates the real native
  JS service, cleaner map and permission cleaner against a storage boundary,
  testing scoped dispatch, excluded permission state, zero flags and delegation.
  These tests skip when Firefox source is not fetched; they ran here.
- Native JS syntax, new Python probe syntax, and patch reverse apply check passed.
- New `tests/fingerprint/probe_shared_permissions.py` uses a disposable profile
  to test shared camera permissions with isolation disabled, always-shared cookie
  and HTTPS exceptions even with isolation enabled, and named microphone grants.
  It tests default/nonzero clear operations and unrelated named permissions.
  **Not run by this worker**; root must run sequentially after IDL rebuild.

No browser, build, real-profile changes or commits were performed by this worker.
