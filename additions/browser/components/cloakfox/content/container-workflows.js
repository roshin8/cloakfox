/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

(async () => {
  const api = ChromeUtils.importESModule('resource:///modules/CloakfoxContainerWorkflows.sys.mjs');
  const { ContextualIdentityService: cis } = ChromeUtils.importESModule(
    'moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
  const section = document.createElement('section');
  section.className = 'card';
  section.id = 'cfx-container-workflows';
  const element = (tag, text, parent = section) => {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    parent.appendChild(node);
    return node;
  };
  const button = (text, action, parent = section) => {
    const node = element('button', text, parent);
    node.type = 'button'; node.className = 'btn btn-ghost';
    node.addEventListener('click', async () => {
      node.disabled = true;
      status.textContent = '';
      try { await action(); } catch (error) { status.textContent = error.message; Cu.reportError(error); }
      finally { node.disabled = false; }
    });
    return node;
  };
  element('h2', 'Containers and backups');
  element('p', 'Site rules use exact hostnames, including subdomains. They apply to independent normal HTTP/HTTPS top-level navigation. Private windows, background requests and linked popup/opener or named-target groups can keep their existing container for compatibility.');
  const routingLabel = element('label', 'Route exact-host rules automatically ');
  const routing = element('input', '', routingLabel);
  routing.type = 'checkbox';
  const routingState = element('p');
  routingState.setAttribute('role', 'status');
  routing.addEventListener('change', () => {
    Services.prefs.setBoolPref('privacy.containers.switchDuringNavigation.enabled', routing.checked);
    Services.prefs.savePrefFile(null);
    loadRules();
  });
  const hostLabel = element('label', 'Exact hostname ');
  const host = element('input', '', hostLabel);
  host.type = 'text'; host.placeholder = 'accounts.example.com'; host.autocomplete = 'off';
  const containerLabel = element('label', ' Open in ');
  const container = element('select', '', containerLabel);
  function loadContainers() {
    container.replaceChildren();
    for (const identity of cis.getPublicIdentities()) {
      const option = element('option', identity.name || cis.getUserContextLabel(identity.userContextId), container);
      option.value = String(identity.userContextId);
    }
  }
  const ruleList = element('ul');
  function loadRules() {
    routing.checked = api.isSiteRoutingEnabled();
    routingState.textContent = routing.checked
      ? 'Automatic exact-host routing is enabled for independent navigations.'
      : 'Automatic routing is disabled. Saved rules are inactive; enable it before adding a rule.';
    loadContainers();
    ruleList.replaceChildren();
    for (const rule of api.getSiteRules()) {
      const item = element('li', `${rule.site} → ${cis.getUserContextLabel(rule.userContextId)} `, ruleList);
      button('Remove rule', () => { api.removeSiteRule(rule.site); loadRules(); status.textContent = 'Site rule removed.'; }, item);
    }
  }
  button('Save site rule', () => {
    api.setSiteRule(host.value, Number(container.value));
    loadRules(); status.textContent = 'Site rule saved. Independent matching navigations use that container; related popup/opener groups can keep their existing container.';
  });
  element('h3', 'Temporary containers');
  element('p', 'A temporary container is deleted after its last tab closes. Its remaining tabs and data are also cleared on the next browser startup. Bookmarks, shared history and saved passwords are not erased.');
  button('Open temporary container', async () => {
    if (!Services.prompt.confirm(window, 'Create a temporary container?',
      'Its tabs, cookies and site data will be removed after its last tab closes or on the next startup. Do not use it for work you need to keep. Create it?')) return;
    const win = Services.wm.getMostRecentWindow('navigator:browser');
    await api.createTemporaryContainer(win);
    loadRules(); status.textContent = 'Temporary container opened. Cleanup is automatic.';
  });
  const temporaryStatus = element('p');
  function loadTemporary() {
    const count = api.getTemporaryContainers().length;
    const error = Services.prefs.getStringPref('cloakfox.workflows.last_error', '');
    temporaryStatus.textContent = `${count} temporary container(s) tracked for cleanup.` + (error ? ' Last cleanup issue: ' + error : '');
  }
  button('Refresh cleanup status', loadTemporary);

  element('h3', 'Encrypted identity-settings backup');
  element('p', 'Exports persona seeds, source OS, OS mode, overrides, region, privacy policies, opening pages, proxy references and site rules. Proxy credentials are excluded; missing proxy bindings stay blocked after restore. It excludes temporary containers, cookies, site data, passwords, bookmarks and history. Host-mode identities adapt their appearance to the destination OS; saved seeds are preserved. This is not a full profile backup. Keep the password separately; it cannot be recovered.');
  const bindingStatus = element('p'); bindingStatus.setAttribute('role', 'status');
  function loadBindingStatus() {
    const manager = ChromeUtils.importESModule('resource:///modules/CloakfoxProxyManager.sys.mjs');
    const network = ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkPolicy.sys.mjs');
    const proxies = manager.listProxies();
    const pending = cis.getPublicIdentities().filter(identity => {
      const ref = manager.getProxyReference(identity.userContextId);
      return ref && (!proxies.some(proxy => proxy.id === ref) || network.getContainerNetwork(identity.userContextId).mode === 2);
    });
    bindingStatus.textContent = pending.length ? 'Proxy binding needed; networking remains blocked: ' +
      pending.map(identity => `${identity.name || cis.getUserContextLabel(identity.userContextId)} (container ${identity.userContextId})`).join(', ') +
      '. Select each container and bind a saved proxy in Proxy manager.' : '';
  }
  button('Refresh proxy binding status', loadBindingStatus);
  const appearanceStatus = element('p'); appearanceStatus.setAttribute('role', 'status');
  function loadAppearanceStatus() {
    const notes = cis.getPublicIdentities().map(identity => {
      const notice = Services.prefs.getStringPref(`cloakfox.container.${identity.userContextId}.restore_appearance_notice`, '');
      return notice ? `${identity.name || cis.getUserContextLabel(identity.userContextId)} (container ${identity.userContextId}): ${notice}` : '';
    }).filter(Boolean);
    appearanceStatus.textContent = notes.join(' ');
  }
  button('Refresh restored appearance status', loadAppearanceStatus);
  loadAppearanceStatus();
  const passwordLabel = element('label', 'Backup password (at least 12 characters) ');
  const password = element('input', '', passwordLabel);
  password.type = 'password'; password.autocomplete = 'new-password'; password.minLength = 12;
  const confirmLabel = element('label', 'Confirm password for export ');
  const confirm = element('input', '', confirmLabel);
  confirm.type = 'password'; confirm.autocomplete = 'new-password';
  async function chooseFile(save) {
    const picker = Cc['@mozilla.org/filepicker;1'].createInstance(Ci.nsIFilePicker);
    picker.init(window.browsingContext, save ? 'Export encrypted identity settings' : 'Import encrypted identity settings',
      save ? Ci.nsIFilePicker.modeSave : Ci.nsIFilePicker.modeOpen);
    picker.appendFilter('Encrypted Cloakfox identity settings', '*.cloakfox-identities');
    picker.defaultString = 'identity-settings.cloakfox-identities';
    picker.defaultExtension = 'cloakfox-identities';
    const result = await new Promise(resolve => picker.open(resolve));
    if (result !== Ci.nsIFilePicker.returnOK && result !== Ci.nsIFilePicker.returnReplace) return null;
    return picker.file.path;
  }
  button('Export encrypted settings', async () => {
    if (password.value !== confirm.value) throw new Error('The passwords do not match');
    const payload = api.captureIdentityBackup();
    let envelope;
    try { envelope = await api.encryptIdentityBackup(payload, password.value); }
    finally { password.value = ''; confirm.value = ''; }
    const path = await chooseFile(true);
    if (!path) return;
    await IOUtils.writeUTF8(path, JSON.stringify(envelope), { tmpPath: path + '.tmp' });
    await IOUtils.setPermissions(path, 0o600);
    status.textContent = 'Encrypted identity settings exported. Cookies and other profile data were not included.';
  });
  button('Import as new containers', async () => {
    const path = await chooseFile(false);
    if (!path) return;
    const info = await IOUtils.stat(path);
    if (info.size > 4 * 1024 * 1024) throw new Error('Identity backup is too large');
    let payload;
    try { payload = await api.decryptIdentityBackup(JSON.parse(await IOUtils.readUTF8(path)), password.value); }
    finally { password.value = ''; confirm.value = ''; }
    api.validateIdentityBackup(payload);
    const appearanceWarnings = api.backupAppearanceWarnings(payload, Services.appinfo.OS);
    const appearanceNotice = appearanceWarnings.length ? ` ${appearanceWarnings.length} host-mode container(s): ${appearanceWarnings[0].message}` : '';
    if (!Services.prompt.confirm(window, 'Import identity settings?',
      `Create ${payload.containers.length} new containers and ${payload.rules.length} exact-host rules? Existing containers and the default container are kept. Conflicting rules will prevent import. Cookies, logins and profile data are not restored.${appearanceNotice}`)) return;
    const imported = await api.restoreIdentityBackup(payload);
    loadRules(); loadBindingStatus(); loadAppearanceStatus();
    const adapted = imported.filter(item => item.appearanceWarning);
    status.textContent = 'Identity settings imported into new containers. Reload this settings page to select them in the persona controls.' +
      (imported.some(item => item.bindingRequired) ? ' Some restored containers are blocked until you bind a saved proxy in Proxy manager: ' + imported.filter(item => item.bindingRequired).map(item => item.userContextId).join(', ') + '.' : '') +
      (adapted.length ? ' Appearance notice: ' + adapted[0].appearanceWarning.message + ' Affected containers: ' + adapted.map(item => item.userContextId).join(', ') + '.' : '');
  });

  const native = api.nativeBackupAvailability();
  if (native.available) {
    element('p', 'For other profile data, use the separate native backup settings and review its data and encryption choices.');
    button('Open native profile backup settings', () => {
      const win = Services.wm.getMostRecentWindow('navigator:browser');
      win.gBrowser.selectedTab = win.gBrowser.addTrustedTab('about:preferences#sync');
    });
  } else element('p', 'Native profile backup: ' + native.reason);
  const status = element('p');
  status.id = 'cfx-workflows-status'; status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  document.querySelector('main').appendChild(section);
  loadRules(); loadTemporary(); loadBindingStatus();
})().catch(error => Cu.reportError(error));
