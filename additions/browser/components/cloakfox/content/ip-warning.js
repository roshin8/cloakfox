/* MPL-2.0 */
const monitor = ChromeUtils.importESModule('resource:///modules/CloakfoxIPConflicts.sys.mjs');
const token = new URL(location.href).searchParams.get('token');
const warning = monitor.getIPWarning(token);
const status = document.getElementById('warning-status');
const buttons = [...document.querySelectorAll('button')];
document.documentElement.dataset.theme = Services.prefs.getStringPref('cloakfox.ui.theme','light');
if (!warning) {
  document.getElementById('heading').textContent = 'This warning has expired';
  document.getElementById('guidance').hidden = true;
  document.getElementById('warning-detail').textContent = 'This warning has expired. Reopen the website to check again.';
  buttons.forEach(button => button.disabled = true);
} else {
  const {ContextualIdentityService} = ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
  const name = id => id === 0 ? 'Default' : ContextualIdentityService.getPublicIdentityFromId(id)?.name || `Container ${id}`;
  function renderComparison(ip, conflicts) {
    document.getElementById('heading').textContent = conflicts.length === 1 ? 'Two containers. One public IP.' : 'These containers share a public IP.';
    document.getElementById('warning-detail').textContent = `${name(warning.id)} matches an address already used by ${conflicts.map(name).join(', ')}.`;
    document.getElementById('current-container').textContent = name(warning.id);
    document.getElementById('current-ip').textContent = ip;
    const list = document.getElementById('conflicting-containers');
    list.replaceChildren();
    for (const id of conflicts) {
      const heading = document.createElement('h2');
      heading.textContent = name(id);
      const label = document.createElement('div');
      label.className = 'label';
      label.textContent = 'Previously observed';
      const address = document.createElement('div');
      address.className = 'address';
      address.textContent = ip;
      list.append(heading, label, address);
    }
    document.getElementById('comparison').hidden = false;
  }
  renderComparison(warning.ip, warning.conflicts);
  document.getElementById('website').textContent = new URL(warning.url).hostname;
  document.getElementById('destination').hidden = false;
  document.getElementById('settings').href = `about:cloakfox?ucid=${warning.id}#cfx-ip-conflict-panel`;
  for (const button of buttons) button.addEventListener('click',async()=>{
    buttons.forEach(b => b.disabled=true);
    button.setAttribute('aria-busy', 'true');
    status.textContent = button.id === 'recheck' ? 'Checking your public IP…' : 'Applying your choice…';
    try {
      const result=await monitor.resolveIPWarning(token,button.id);
      if (result.conflict) {
        const updated = monitor.getIPWarning(token);
        if (updated) renderComparison(updated.ip, updated.conflicts);
      }
      status.textContent=result.error ? `Unknown: ${result.error} Check your route and try again.` : result.conflict ? `Still shared: ${result.ip}. Change your route and recheck, or choose an exception.` : 'Returning to the website…';
    } catch(error) {status.textContent=error.message;}
    finally {button.removeAttribute('aria-busy');buttons.forEach(b => b.disabled=false);}
  });
}
