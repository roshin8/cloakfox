/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
(() => {
  const section = document.getElementById('cfx-permission-settings');
  if (!section) return;
  const api = ChromeUtils.importESModule('resource:///modules/CloakfoxPermissions.sys.mjs');
  const selected = document.getElementById('cfx-container-select');
  const element = (tag, text, parent = section) => {
    const node = document.createElement(tag); node.textContent = text; parent.appendChild(node); return node;
  };
  element('h2', 'Site permission grants');
  element('p', 'Review stored camera, microphone, location and notification grants in the selected container. Temporary tab grants remain in the tab’s Firefox permission controls. Expiry only shortens existing consent; websites must still request permission. Revoking or expiring a grant prevents future use, but may not stop an already active stream or location watch. Stop it in the tab or close the tab.');
  const privateLabel = element('label', 'Browsing context ');
  const context = element('select', '', privateLabel);
  element('option', 'Normal browsing', context).value = '0';
  element('option', 'Private browsing', context).value = '1';
  const status = element('p', ''); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  const scopeLabel = element('p', '');
  const list = element('div', '');
  function button(label, parent, action) {
    const node = element('button', label, parent); node.type = 'button'; node.className = 'btn btn-ghost';
    node.addEventListener('click', () => {
      try { action(); } catch (error) { status.textContent = error.message; }
    }); return node;
  }
  function refresh() {
    list.replaceChildren();
    const isolation = api.permissionIsolation();
    scopeLabel.textContent = `${isolation.userContext ? 'Container-specific grants.' : 'Grants are shared across containers.'} ${isolation.privateBrowsing ? 'Normal and private grants are separate.' : 'Normal and private browsing share grants.'}`;
    const records = api.listPermissionGrants({ userContextId: isolation.userContext ? Number(selected.value) : 0,
      privateBrowsingId: isolation.privateBrowsing ? Number(context.value) : 0 });
    if (!records.length) element('p', 'No stored grants in this browsing context.', list);
    for (const record of records) {
      const row = element('div', '', list);
      const labels = { camera: 'Camera', microphone: 'Microphone', geo: 'Location', 'desktop-notification': 'Notifications' };
      element('strong', `${labels[record.type]} · ${record.origin}`, row);
      const expiry = record.expireType === Services.perms.EXPIRE_POLICY ? 'Managed by policy' :
        record.browserId ? 'This tab' : record.expireType === Services.perms.EXPIRE_SESSION ? 'This session' :
        record.expireType === Services.perms.EXPIRE_TIME ? 'Timed' : 'No expiry';
      element('p', `${expiry}${record.expireTime ? ' · ' + new Date(record.expireTime).toLocaleString() : ''}`, row);
      if (record.expireType === Services.perms.EXPIRE_POLICY) continue;
      button('Revoke', row, () => { api.revokePermissionGrant(record); refresh(); status.textContent = 'Grant revoked.'; });
      if (record.browserId || record.expireType === Services.perms.EXPIRE_SESSION_TAB) continue;
      button('Expire when session ends', row, () => {
        api.expirePermissionGrant(record, { mode: 'session' }); refresh(); status.textContent = 'Grant now ends with this session or its earlier deadline.';
      });
      const duration = element('select', '', row); duration.setAttribute('aria-label', 'Permission duration');
      for (const [text, minutes] of [['15 minutes', 15], ['1 hour', 60], ['1 day', 1440]]) element('option', text, duration).value = String(minutes);
      button('Set expiry', row, () => {
        api.expirePermissionGrant(record, { mode: 'time', expiresAt: Date.now() + Number(duration.value) * 60000 });
        refresh(); status.textContent = 'Grant expiry updated. Earlier deadlines and session boundaries are preserved.';
      });
    }
  }
  button('Refresh grants', section, refresh);
  selected.addEventListener('change', refresh); context.addEventListener('change', refresh);
  try { refresh(); } catch (error) { status.textContent = error.message; }
})();
