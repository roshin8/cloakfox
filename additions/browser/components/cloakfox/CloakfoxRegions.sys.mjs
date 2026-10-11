/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

const pref = ucid => {
  if (!Number.isSafeInteger(ucid) || ucid < 0) throw new Error('Invalid container ID');
  return `cloakfox.container.${ucid}.region`;
};

/** Manual only: no IP lookup or third-party requests. */
export function validateRegion(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Region must be an object');
  if (Object.keys(value).some(k => !['version','locale','languages','timezone','geolocation'].includes(k))) throw new Error('Unknown region field');
  if (value.version !== undefined && value.version !== 1) throw new Error('Unsupported region version');
  if (typeof value.locale !== 'string' || value.locale.length > 100 || !value.locale.trim()) throw new Error('Enter a BCP 47 locale');
  const locale = Intl.getCanonicalLocales(value.locale.trim())[0];
  if (!Array.isArray(value.languages) || !value.languages.length || value.languages.length > 10 || value.languages.some(x => typeof x !== 'string' || x.length > 100 || !x.trim())) throw new Error('Enter one to ten language tags');
  const languages = Intl.getCanonicalLocales(value.languages.map(x => x.trim()));
  if (typeof value.timezone !== 'string' || value.timezone.length > 100 || !value.timezone.trim()) throw new Error('Enter an IANA timezone');
  const timezone = new Intl.DateTimeFormat('en', {timeZone:value.timezone.trim()}).resolvedOptions().timeZone;
  let geolocation = null;
  if (value.geolocation != null) {
    if (typeof value.geolocation !== 'object' || Array.isArray(value.geolocation) || Object.keys(value.geolocation).some(k => !['latitude','longitude','accuracy'].includes(k))) throw new Error('Invalid geolocation fields');
    const {latitude, longitude, accuracy} = value.geolocation;
    if (![latitude, longitude, accuracy].every(Number.isFinite) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180 || accuracy < 1000 || accuracy > 20000000) throw new Error('Coordinates must be valid and accuracy at least 1,000 metres');
    geolocation = {latitude, longitude, accuracy};
  }
  return {version:1, locale, languages, timezone, geolocation};
}

/** null means use generated defaults; malformed saved data is ignored. */
export function getRegion(ucid) {
  const key = pref(ucid);
  try {
    const raw = Services.prefs.getStringPref(key, '');
    return raw ? validateRegion(JSON.parse(raw)) : null;
  } catch (_) { return null; }
}

export function setRegion(ucid, value) {
  const key = pref(ucid);
  const region = value == null ? null : validateRegion(value);
  if (region) {
    // Timezone is still consumed by the native timezone bridge/actor.
    Services.prefs.setStringPref(`cloakfox.container.${ucid}.timezone`, region.timezone);
    Services.prefs.setStringPref(key, JSON.stringify(region));
  } else {
    Services.prefs.clearUserPref(key);
    Services.prefs.clearUserPref(`cloakfox.container.${ucid}.timezone`);
  }
  if (Services.prefs.getStringPref(`cloakfox.container.${ucid}.math_seed`, '')) {
    const {refreshContainerConfig} = ChromeUtils.importESModule('resource:///modules/CloakfoxSeedSync.sys.mjs');
    refreshContainerConfig(ucid);
  }
  Services.prefs.savePrefFile(null);
  return region;
}

export function applyRegion(ucid, cfg) {
  const region = getRegion(ucid);
  const out = {...cfg};
  // Coarse location is opt-in. Generated personas must never imply consent.
  for (const key of ['geolocation:latitude','geolocation:longitude','geolocation:accuracy']) delete out[key];
  out['timezone'] = region?.timezone || Services.prefs.getStringPref(`cloakfox.container.${ucid}.timezone`, 'UTC');
  if (!region) {
    // Generated personas also need realm defaults; ICU is intentionally neutral.
    const existingLanguages = Array.isArray(out['navigator.languages'])
      ? out['navigator.languages'].join(',') : '';
    const header = out['headers.Accept-Language'] || existingLanguages ||
      out['locale:all'] || out['navigator.language'] || 'en-US,en;q=0.9';
    const languages = String(header).split(',').map(x => x.split(';')[0].trim()).filter(Boolean);
    out['locale:default'] = out['locale:default'] || out['navigator.language'] || languages[0] || 'en-US';
    out['locale:all'] = languages.join(',');
    out['navigator.languages'] = languages;
    out['navigator.language'] = languages[0] || 'en-US';
    return out;
  }
  const loc = new Intl.Locale(region.locale);
  out['locale:all'] = region.languages.join(',');
  out['navigator.language'] = region.languages[0];
  out['navigator.languages'] = [...region.languages];
  out['headers.Accept-Language'] = region.languages.map((x,i) => i ? `${x};q=${(1-i/10).toFixed(1)}` : x).join(',');
  out['locale:default'] = region.locale;
  out['locale:language'] = loc.language;
  out['locale:region'] = loc.region || '';
  out['locale:script'] = loc.script || '';
  if (region.geolocation) for (const [key,value] of Object.entries(region.geolocation)) out[`geolocation:${key}`] = value;
  return out;
}
