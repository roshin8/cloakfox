"""Verify packaged uBO installation/signature and persistent user disable/removal.

Run sequentially with CLOAKFOX_BIN after build/package. Uses a disposable profile;
normal AMO/filter-list background updates may contact their configured endpoints.
This does not benchmark filter effectiveness or prove list-download availability.
"""
import json
from pathlib import Path
import tempfile

from probe_daily_defaults import launch

ADDON_ID = 'uBlock0@raymondhill.net'
READ = """
const done = arguments[arguments.length - 1];
const { AddonManager } = ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');
AddonManager.getAddonByID('uBlock0@raymondhill.net').then(addon => {
  const packageFile = Services.dirsvc.get('XREAppDist', Ci.nsIFile);
  packageFile.append('extensions');
  packageFile.append('uBlock0@raymondhill.net.xpi');
  done({
    packagedXPI: packageFile.exists() ? packageFile.path : null,
    addon: addon && {id: addon.id, version: addon.version, active: addon.isActive,
      userDisabled: addon.userDisabled, signed: [AddonManager.SIGNEDSTATE_SIGNED,
        AddonManager.SIGNEDSTATE_PRIVILEGED].includes(addon.signedState),
      canDisable: !!(addon.permissions & AddonManager.PERM_CAN_DISABLE),
      canRemove: !!(addon.permissions & AddonManager.PERM_CAN_UNINSTALL)},
    signatureRequired: Services.prefs.getBoolPref('xpinstall.signatures.required', false),
    updatesEnabled: Services.prefs.getBoolPref('extensions.update.enabled', false),
    autoUpdates: Services.prefs.getBoolPref('extensions.update.autoUpdateDefault', false),
    customAssetBootstrap: Services.prefs.getStringPref('librewolf.uBO.assetsBootstrapLocation', ''),
    trackingControlPresent: !!Services.wm.getMostRecentWindow('navigator:browser')
      .document.getElementById('tracking-protection-icon-container')
  });
}, error => done({error: String(error)}));
"""
CHANGE = """
const action = arguments[0], done = arguments[arguments.length - 1];
const { AddonManager } = ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');
AddonManager.getAddonByID('uBlock0@raymondhill.net').then(async addon => {
  if (action === 'disable') await addon.disable();
  else {
    await addon.uninstall();
    // Exercise distribution removal memory even when the app version changes.
    Services.prefs.setStringPref('extensions.lastAppVersion', '0');
  }
  Services.prefs.savePrefFile(null);
  done({ok: true});
}).catch(error => done({error: String(error)}));
"""


def main():
    with tempfile.TemporaryDirectory(prefix='cloakfox-blocker-') as directory:
        profile = Path(directory) / 'profile'
        profile.mkdir()
        for phase in ('fresh', 'disabled', 'removed'):
            driver = launch(profile, Path(directory) / f'{phase}.log', distro_addons=True)
            try:
                status = driver.execute_async_script(READ)
                assert 'error' not in status, status
                assert status['packagedXPI'], 'XPI missing from packaged distribution/extensions'
                if phase == 'fresh':
                    addon = status['addon']
                    assert addon and addon['active'] and addon['signed'], status
                    assert addon['canDisable'] and addon['canRemove'], status
                    assert status['signatureRequired'] and status['updatesEnabled'] and status['autoUpdates'], status
                    assert not status['customAssetBootstrap'], status
                    assert status['trackingControlPresent'], status
                    assert driver.execute_async_script(CHANGE, 'disable') == {'ok': True}
                elif phase == 'disabled':
                    assert status['addon']['userDisabled'] and not status['addon']['active'], status
                    assert driver.execute_async_script(CHANGE, 'remove') == {'ok': True}
                else:
                    assert status['addon'] is None, 'Removed blocker was silently reinstalled'
                print(json.dumps({phase: status}, indent=2))
            finally:
                driver.quit()
    print('PASS: packaged signed blocker, normal update defaults, disable/removal persist')


if __name__ == '__main__':
    main()
