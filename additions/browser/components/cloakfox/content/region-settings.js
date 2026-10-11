/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
(() => {
  const {getRegion,setRegion} = ChromeUtils.importESModule('resource:///modules/CloakfoxRegions.sys.mjs');
  const host = document.getElementById('cfx-region-settings');
  const select = document.getElementById('cfx-container-select');
  if (!host || !select) return;
  const heading = document.createElement('h3'); heading.textContent = 'Region'; host.append(heading);
  const detail = document.createElement('p'); detail.textContent = 'Manual settings make no network requests. Languages may differ from the formatting locale. Location is optional, approximate, and still requires site permission.'; host.append(detail);
  const fields = {};
  for (const [key,label,placeholder] of [
    ['locale','Formatting locale','en-US'], ['languages','Languages, preferred first','en-US, en'],
    ['timezone','IANA timezone','America/New_York'], ['latitude','Approximate latitude (optional)','40.7'],
    ['longitude','Approximate longitude (optional)','-74.0'], ['accuracy','Accuracy in metres (minimum 1,000)','10000']]) {
    const row = document.createElement('label'); row.textContent = label;
    const input = document.createElement('input'); input.type = 'text'; input.placeholder = placeholder; input.id = `cfx-region-${key}`;
    row.append(input); host.append(row); fields[key] = input;
  }
  const presetLabel = document.createElement('label'); presetLabel.textContent = 'Language and timezone preset';
  const preset = document.createElement('select'); preset.id = 'cfx-region-preset';
  const presets = [
    ['Choose a preset…', '', ''], ['English — United States (Eastern)', 'en-US', 'America/New_York'],
    ['English — United States (Pacific)', 'en-US', 'America/Los_Angeles'],
    ['English — United Kingdom', 'en-GB', 'Europe/London'], ['German — Germany', 'de-DE', 'Europe/Berlin'],
    ['French — France', 'fr-FR', 'Europe/Paris'], ['Spanish — Spain', 'es-ES', 'Europe/Madrid'],
    ['Portuguese — Brazil', 'pt-BR', 'America/Sao_Paulo'], ['Japanese — Japan', 'ja-JP', 'Asia/Tokyo'],
    ['English — Australia', 'en-AU', 'Australia/Sydney']
  ];
  presets.forEach(([label], i) => preset.add(new Option(label, String(i))));
  presetLabel.append(preset); host.insertBefore(presetLabel, fields.locale.parentElement);
  preset.addEventListener('change', () => {
    const [, locale, timezone] = presets[Number(preset.value)]; if (!locale) return;
    fields.locale.value = locale; fields.languages.value = `${locale}, ${locale.split('-')[0]}`;
    fields.timezone.value = timezone;
  });
  const zones = document.createElement('datalist'); zones.id = 'cfx-timezone-options';
  for (const zone of ['UTC', ...Intl.supportedValuesOf('timeZone')]) zones.append(new Option(zone, zone));
  host.append(zones); fields.timezone.setAttribute('list', zones.id);
  const status = document.createElement('p'); status.setAttribute('role','status');
  const save = document.createElement('button'); save.textContent = 'Save region'; save.type='button';
  const reset = document.createElement('button'); reset.textContent = 'Use generated defaults'; reset.type='button';
  host.append(save,reset,status);
  function load() {
    const region = getRegion(Number(select.value));
    fields.locale.value = region?.locale || 'en-US'; fields.languages.value = region?.languages.join(', ') || 'en-US, en';
    fields.timezone.value = region?.timezone || 'UTC';
    for (const key of ['latitude','longitude','accuracy']) fields[key].value = region?.geolocation?.[key] ?? '';
    status.textContent = region ? 'Manual region saved.' : 'Generated defaults. Approximate location is off.';
  }
  save.addEventListener('click', () => {
    try {
      const hasGeo = ['latitude','longitude','accuracy'].some(k => fields[k].value.trim());
      if (hasGeo && ['latitude','longitude','accuracy'].some(k => !fields[k].value.trim())) throw new Error('Provide latitude, longitude and accuracy, or leave all three blank');
      setRegion(Number(select.value), {locale:fields.locale.value,languages:fields.languages.value.split(','),timezone:fields.timezone.value,
        geolocation:hasGeo ? Object.fromEntries(['latitude','longitude','accuracy'].map(k => [k,Number(fields[k].value)])) : null});
      Services.prefs.savePrefFile(null); document.dispatchEvent(new Event('cfx-region-changed')); status.textContent = 'Saved. Reload pages and restart workers to apply the region. Existing location watches keep their initial value.';
    } catch(error) { status.textContent = error.message; }
  });
  reset.addEventListener('click', () => { try {setRegion(Number(select.value),null);Services.prefs.savePrefFile(null);document.dispatchEvent(new Event('cfx-region-changed'));load();} catch(error) {status.textContent=error.message;} });
  select.addEventListener('change',load); load();
})();
