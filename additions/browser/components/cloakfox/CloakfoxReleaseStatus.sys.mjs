/* MPL-2.0 */
// No network request: inspect the same local classifier database Firefox uses.
export function assessLists({ enabled, key, tables, expected, lastSuccess, now = Date.now() }) {
  if (!enabled) return { state: 'disabled', message: 'Phishing and malware list checks are disabled.' };
  if (!key) return { state: 'missing-key', message: 'List checks are enabled, but the release owner must configure the Google provider key.' };
  const available = new Set(tables.split('\n').filter(line => /^[^;]+;[^:;\s]+/.test(line)).map(line => line.split(';')[0]));
  const missing = expected.filter(table => !available.has(table));
  if (!expected.length || missing.length) return { state: 'unavailable', message: 'Protection lists have not finished downloading. Inspect about:url-classifier for provider errors.', missing };
  if (!Number.isFinite(lastSuccess) || lastSuccess <= 0 || lastSuccess > now || now - lastSuccess > 48 * 3600000) {
    return { state: 'stale', message: 'Protection lists exist, but no successful provider update was recorded in the last 48 hours. Inspect about:url-classifier.' };
  }
  return { state: 'ready', message: 'Configured phishing and malware lists are present locally; the provider updated successfully within 48 hours.' };
}

export async function getSafeBrowsingReadiness() {
  const prefs = Services.prefs;
  const expected = [];
  for (const [enabled, tablePref] of [['phishing', 'phishTable'], ['malware', 'malwareTable']]) {
    if (prefs.getBoolPref(`browser.safebrowsing.${enabled}.enabled`, false)) {
      expected.push(...prefs.getStringPref(`urlclassifier.${tablePref}`, '').split(',').map(s => s.trim()).filter(s => /^goog(?:pub)?-/.test(s)));
    }
  }
  const enabled = prefs.getBoolPref('browser.safebrowsing.phishing.enabled', false) || prefs.getBoolPref('browser.safebrowsing.malware.enabled', false);
  // Inspect the substituted key directly; the diagnostic exclusion pref must not claim readiness.
  const keyText = Services.urlFormatter.formatURL('%GOOGLE_SAFEBROWSING_API_KEY%').trim();
  const key = /^[A-Za-z0-9_-]{20,200}$/.test(keyText) && !keyText.startsWith('no-');
  let tables = '';
  if (enabled && key) {
    try {
      tables = await new Promise((resolve, reject) => {
        const timer = Cc['@mozilla.org/timer;1'].createInstance(Ci.nsITimer);
        timer.initWithCallback(() => reject(new Error('Classifier timed out')), 5000, Ci.nsITimer.TYPE_ONE_SHOT);
        Cc['@mozilla.org/url-classifier/dbservice;1'].getService(Ci.nsIUrlClassifierDBService).getTables(value => { timer.cancel(); resolve(value); });
      });
    } catch {
      return { state: 'error', message: 'Local protection-list status is unavailable. Inspect about:url-classifier.' };
    }
  }
  const provider = prefs.getBoolPref('browser.safebrowsing.provider.google5.enabled', false) ? 'google5' : 'google4';
  const lastSuccess = Number(prefs.getStringPref(`browser.safebrowsing.provider.${provider}.lastupdatetime`, '0'));
  return assessLists({ enabled, key, tables, expected, lastSuccess });
}
