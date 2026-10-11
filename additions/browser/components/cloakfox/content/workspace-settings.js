/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
(() => {
  const section = document.getElementById('cfx-workspace-settings');
  if (!section) return;
  const api = ChromeUtils.importESModule('resource:///modules/CloakfoxWorkspaces.sys.mjs');
  const element = (tag, text, parent = section) => {
    const node = document.createElement(tag); node.textContent = text; parent.appendChild(node); return node;
  };
  element('h2', 'Separate-profile workspaces');
  element('p', 'Each workspace is a real Firefox profile with its own history, passwords, extensions, settings and website sign-ins. New workspaces start empty and open in another browser instance. Signing in to a website still happens on that website. Sync or imported data can intentionally reconnect profiles.');
  const label = element('label', 'New workspace name ');
  const name = element('input', '', label); name.maxLength = 80;
  const status = element('p', ''); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  const list = element('div', '');
  function button(text, parent, action) {
    const node = element('button', text, parent); node.type = 'button'; node.className = 'btn btn-ghost';
    node.addEventListener('click', async () => {
      node.disabled = true;
      try { await action(); } catch (error) { status.textContent = error.message; }
      finally { node.disabled = false; }
    }); return node;
  }
  function refresh() {
    list.replaceChildren();
    for (const item of api.listWorkspaces()) {
      const row = element('div', '', list);
      element('strong', item.name, row);
      element('p', item.current ? 'Current workspace' : item.available ? 'Ready to open' : 'In use or unavailable', row);
      if (item.available) button('Open workspace', row, () => {
        api.openWorkspace(item.id); status.textContent = `Requested a new browser instance for ${item.name}.`; refresh();
      });
    }
  }
  button('Create workspace', section, async () => {
    const item = await api.createWorkspace(name.value); name.value = ''; refresh();
    status.textContent = `${item.name} created with separate profile storage. Use Open workspace to launch it.`;
  });
  button('Refresh workspaces', section, refresh);
  const link = element('a', 'Open Firefox profile manager'); link.href = 'about:profiles'; link.target = '_blank';
  try { refresh(); } catch (error) { status.textContent = error.message; }
})();
