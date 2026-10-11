/* MPL-2.0 */
const { AppConstants } = ChromeUtils.importESModule('resource://gre/modules/AppConstants.sys.mjs');
document.getElementById('cfx-engine-version').textContent = `Firefox engine ${AppConstants.MOZ_APP_VERSION}`;
const updates = document.getElementById('cfx-update-readiness');
updates.textContent = AppConstants.MOZ_UPDATER
  ? 'An updater is compiled in. Release signing and update hosting must be configured before distributing this build.'
  : 'Automatic browser updates are unavailable in this development build. Install verified Cloakfox releases manually.';
const { getSafeBrowsingReadiness } = ChromeUtils.importESModule('resource:///modules/CloakfoxReleaseStatus.sys.mjs');
const protection = document.getElementById('cfx-provider-readiness');
protection.textContent = 'Checking local protection lists…';
getSafeBrowsingReadiness().then(result => { protection.textContent = result.message; }).catch(() => {
  protection.textContent = 'Protection-list status is unavailable. Inspect about:url-classifier.';
});
