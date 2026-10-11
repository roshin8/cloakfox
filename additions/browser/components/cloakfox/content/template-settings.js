/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
(() => {
  const section = document.getElementById('cfx-template-settings');
  if (!section) return;
  const api = ChromeUtils.importESModule('resource:///modules/CloakfoxTemplates.sys.mjs');
  const proxies = ChromeUtils.importESModule('resource:///modules/CloakfoxProxyManager.sys.mjs');
  const selectedContainer = document.getElementById('cfx-container-select');
  const element = (tag, text, parent = section) => {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    parent.appendChild(node); return node;
  };
  const field = (label, tag = 'input') => element(tag, '', element('label', label + ' '));
  element('h2', 'Reusable container templates');
  element('p', 'Save region, privacy policy, pinned persona, proxy reference and opening pages. Every new container gets fresh fingerprint secrets and empty site storage. Templates exclude cookies, passwords and proxy credentials.');
  const choose = field('Template', 'select');
  const name = field('New container or template name'); name.maxLength = 128;
  const opening = field('Opening pages, one HTTP or HTTPS URL per line', 'textarea'); opening.rows = 3;
  const proxy = field('Saved proxy', 'select');
  const required = field('Require a proxy (blocks networking until a proxy is bound)'); required.type = 'checkbox';
  const temporary = field('Temporary storage: delete when its last tab closes or at next startup'); temporary.type = 'checkbox';
  const mode = field('Persona OS', 'select');
  element('option', 'Match this computer only', mode).value = 'host';
  element('option', 'Windows, macOS and Linux', mode).value = 'legacy';
  for (const [value, label] of [['windows','Windows'],['macos','macOS'],['linux','Linux']]) element('option', label, mode).value = value;
  const persona = field('Pinned persona', 'select');
  function loadPersonas(index = -1) {
    persona.replaceChildren();
    element('option', 'Fresh generated persona', persona).value = '-1';
    const {listPersonas} = ChromeUtils.importESModule('resource:///modules/CloakfoxPersonas.sys.mjs');
    const items = listPersonas(Services.appinfo.OS, mode.value);
    for (const os of ['Windows', 'macOS', 'Linux']) {
      const matches = items.filter(item => item.label.startsWith(os));
      if (!matches.length) continue;
      const group = element('optgroup', '', persona); group.label = os;
      for (const item of matches) element('option', item.label.replace(`${os} · `, ''), group).value = String(item.index);
    }
    persona.value = String(index);
  }
  mode.addEventListener('change', () => loadPersonas());
  const summary = element('p');
  const status = element('p'); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  let items = [];
  const pages = () => opening.value.split(/\r?\n/).map(value => value.trim()).filter(Boolean);
  const current = () => {
    const item = items.find(record => record.id === choose.value);
    if (!item) throw new Error('Select a template');
    return { ...item.settings, name: name.value, startPages: pages(), proxyRef: proxy.value || null,
      proxyRequired: required.checked, temporary: temporary.checked, personaIndex: Number(persona.value), personaOSMode: mode.value };
  };
  function loadFields() {
    const item = items.find(record => record.id === choose.value);
    if (!item) return;
    const value = item.settings;
    name.value = value.name; opening.value = value.startPages.join('\n'); required.checked = value.proxyRequired;
    temporary.checked = value.temporary; mode.value = value.personaOSMode || "legacy"; loadPersonas(value.personaIndex);
    proxy.replaceChildren();
    const none = element('option', 'No saved proxy', proxy); none.value = '';
    const catalog = proxies.listProxies();
    for (const record of catalog) element('option', record.name, proxy).value = record.id;
    if (value.proxyRef && !catalog.some(record => record.id === value.proxyRef)) element('option', 'Missing saved proxy — select another', proxy).value = value.proxyRef;
    proxy.value = value.proxyRef || '';
    summary.textContent = `Privacy policy: ${value.policy.preset}. Region: ${value.region ? value.region.timezone + ' · ' + value.region.languages.join(', ') : 'Generated defaults'}.`;
  }
  function reload(selected) {
    items = [...api.templatePresets().map((settings, index) => ({ id: 'preset-' + index, settings, preset: true })), ...api.listTemplates()];
    choose.replaceChildren();
    for (const item of items) element('option', item.settings.name + (item.preset ? ' (preset)' : ''), choose).value = item.id;
    if (selected && items.some(item => item.id === selected)) choose.value = selected;
    loadFields();
  }
  const buttons = [];
  function button(text, action) {
    const node = element('button', text); node.type = 'button'; node.className = 'btn btn-ghost'; buttons.push(node);
    node.addEventListener('click', async () => {
      buttons.forEach(item => { item.disabled = true; }); status.textContent = '';
      try { await action(); } catch (error) { status.textContent = error.message; }
      finally { buttons.forEach(item => { item.disabled = false; }); }
    });
  }
  button('Save selected container as template', () => {
    const value = api.captureTemplate(Number(selectedContainer.value), name.value, pages());
    const saved = api.saveTemplate(value); reload(saved.id);
    status.textContent = 'Saved settings from the selected container. Fingerprint secrets and site data were excluded.';
  });
  button('Save template copy', () => { const saved = api.saveTemplate(current()); reload(saved.id); status.textContent = 'Template copy saved.'; });
  button('Create fresh container', async () => {
    const value = current();
    const id = await api.createFromTemplate(value, Services.wm.getMostRecentWindow('navigator:browser'));
    status.textContent = `Container ${id} created with fresh fingerprint secrets.${value.temporary ? ' Temporary cleanup is automatic.' : ''}${value.proxyRequired && !value.proxyRef ? ' Networking is blocked until a saved proxy is bound.' : ''} Reload this settings page to select it.`;
  });
  button('Delete saved template', () => {
    if (items.find(item => item.id === choose.value)?.preset) throw new Error('Built-in presets cannot be deleted');
    api.removeTemplate(choose.value); reload(); status.textContent = 'Template deleted. Existing containers are unchanged.';
  });
  async function chooseFile(save) {
    const picker = Cc['@mozilla.org/filepicker;1'].createInstance(Ci.nsIFilePicker);
    picker.init(window.browsingContext, save ? 'Export container templates' : 'Import container templates', save ? Ci.nsIFilePicker.modeSave : Ci.nsIFilePicker.modeOpen);
    picker.appendFilter('Cloakfox templates', '*.cloakfox-templates'); picker.defaultString = 'settings.cloakfox-templates';
    const result = await new Promise(resolve => picker.open(resolve));
    return [Ci.nsIFilePicker.returnOK, Ci.nsIFilePicker.returnReplace].includes(result) ? picker.file.path : null;
  }
  element('p', 'Template files contain opening URLs and settings in plain text. Proxy references work only when the corresponding saved proxy exists in this browser.');
  button('Export templates', async () => {
    const payload = api.exportTemplates();
    const path = await chooseFile(true); if (!path) return;
    await IOUtils.writeUTF8(path, JSON.stringify(payload, null, 2), { tmpPath: path + '.tmp' }); await IOUtils.setPermissions(path, 0o600);
    status.textContent = 'Settings-only templates exported.';
  });
  button('Import templates', async () => {
    const path = await chooseFile(false); if (!path) return;
    if ((await IOUtils.stat(path)).size > 1024 * 1024) throw new Error('Template file is too large');
    const added = api.importTemplates(JSON.parse(await IOUtils.readUTF8(path))); reload(added[0]?.id);
    status.textContent = `${added.length} templates imported with fresh catalog IDs. Create a container to generate a fresh fingerprint.`;
  });
  choose.addEventListener('change', loadFields);
  reload();
})();
