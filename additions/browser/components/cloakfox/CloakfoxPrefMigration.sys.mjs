/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: one-shot roverfox.s.* → cloakfox.s.* pref migration.
 *
 * On profiles that were last used by a pre-cpp-first Cloakfox build,
 * any per-container fingerprint state the extension wrote lives under
 * prefs named roverfox.s.<key>. The new cpp-first code path reads
 * cloakfox.s.<key> first (checked in RoverfoxStorageManager::Get*;
 * see cpp-first-pref-reader.patch) so the cpp-first values win.
 *
 * If the user has *never* edited their cloakfox.s settings but has
 * existing roverfox.s values from the extension era, they'd suddenly
 * look unspoofed until they regen from about:cloakfox. The migration
 * script runs once at startup and mirrors all roverfox.s.* prefs
 * into cloakfox.s.* — preserving each container's existing seeds.
 *
 * Idempotent: sets cloakfox.migration.v1.done=true on completion; on
 * subsequent boots, does nothing.
 *
 * Imported from BrowserGlue at startup. See
 * patches/cpp-first-browser-glue.patch.
 */

const MIGRATION_DONE_PREF = "cloakfox.migration.v1.done";
const SRC_PREFIX = "roverfox.s.";
const DST_PREFIX = "cloakfox.s.";

export function runCloakfoxPrefMigration() {
  if (Services.prefs.getBoolPref(MIGRATION_DONE_PREF, false)) {
    return { migrated: 0, skipped: true };
  }

  let migrated = 0;
  try {
    const branch = Services.prefs.getBranch(SRC_PREFIX);
    const keys = branch.getChildList("");
    for (const key of keys) {
      const srcName = SRC_PREFIX + key;
      const dstName = DST_PREFIX + key;

      // Skip if the user (or cpp-first code) already set a value on
      // the destination side — don't overwrite.
      if (Services.prefs.prefHasUserValue(dstName)) {
        continue;
      }

      const type = Services.prefs.getPrefType(srcName);
      try {
        if (type === Services.prefs.PREF_STRING) {
          const value = Services.prefs.getCharPref(srcName, "");
          if (value) {
            Services.prefs.setCharPref(dstName, value);
            migrated++;
          }
        } else if (type === Services.prefs.PREF_INT) {
          const value = Services.prefs.getIntPref(srcName, 0);
          Services.prefs.setIntPref(dstName, value);
          migrated++;
        } else if (type === Services.prefs.PREF_BOOL) {
          const value = Services.prefs.getBoolPref(srcName, false);
          Services.prefs.setBoolPref(dstName, value);
          migrated++;
        }
      } catch (_e) { /* skip individual key on error */ }
    }
  } finally {
    // Mark done whether or not we migrated anything — prevents the
    // whole scan from re-running on every startup.
    Services.prefs.setBoolPref(MIGRATION_DONE_PREF, true);
  }

  return { migrated, skipped: false };
}
