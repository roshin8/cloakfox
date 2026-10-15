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
  const families = [['ipv4', 'IPv4'], ['ipv6', 'IPv6']];
  function renderComparison(current) {
    // Older pending warnings carry only one address. Never infer the other family.
    const legacy = !('ipv4' in current) && !('ipv6' in current);
    const legacyFamily = current.ip?.includes(':') ? 'ipv6' : 'ipv4';
    const matches = current.matches || (current.ip ? [{ip: current.ip, family: legacyFamily, conflicts: current.conflicts}] : []);
    const conflicts = current.conflicts || [];
    const hasMatch = matches.some(match => match.conflicts.length);
    const incomplete = Object.values(current.errors || {}).some(Boolean);
    const disclaimer = 'These lookups do not confirm the IP seen by this website; proxy rules and IPv4/IPv6 routing can differ.';
    document.getElementById('heading').textContent = hasMatch ? 'Public IP lookups match.' : incomplete ? 'IP check incomplete' : 'No current IP lookup match';
    document.getElementById('warning-detail').textContent = hasMatch
      ? `The public IP lookup for ${name(warning.id)} matches results recorded for ${conflicts.map(name).join(', ')} when visiting this hostname. ${disclaimer}`
      : `${incomplete ? 'An address family could not be checked. The previous recorded match has not been ruled out. Recheck before continuing.' : 'The current public IP lookups do not match another container’s recorded visits to this hostname.'} ${disclaimer}`;
    document.getElementById('comparison-status').textContent = hasMatch ? 'Matching lookup results: These sessions may be linked' : incomplete ? 'Check incomplete: The previous match has not been ruled out' : 'No current matching lookup results';
    document.getElementById('current-container').textContent = name(warning.id);
    for (const [family] of families) {
      const ip = legacy ? (family === legacyFamily ? current.ip : '') : current[family];
      const error = current.errors?.[family];
      document.getElementById(`current-${family}`).textContent = ip || (error ? `Unavailable — ${error}` : 'Unknown');
    }
    // Retain the legacy anchor for callers that inspect the primary matched IP.
    document.getElementById('current-ip').textContent = current.ip || '';
    const list = document.getElementById('conflicting-containers');
    list.replaceChildren();
    for (const id of conflicts) {
      const heading = document.createElement('h2');
      heading.textContent = name(id);
      list.append(heading);
      for (const [family, title] of families) {
        const label = document.createElement('div');
        label.className = 'label';
        label.textContent = `${title} recorded public IP lookup`;
        const address = document.createElement('div');
        address.className = 'address';
        address.textContent = matches.filter(match => match.family === family && match.conflicts.includes(id)).map(match => match.ip).join(', ') || 'No recorded match';
        list.append(label, address);
      }
    }
    document.getElementById('comparison').hidden = false;
  }
  renderComparison(warning);
  document.getElementById('website').textContent = new URL(warning.url).hostname;
  document.getElementById('destination').hidden = false;
  document.getElementById('settings').href = `about:cloakfox?ucid=${warning.id}#cfx-ip-conflict-panel`;
  for (const button of buttons) button.addEventListener('click',async()=>{
    buttons.forEach(b => b.disabled=true);
    button.setAttribute('aria-busy', 'true');
    status.textContent = button.id === 'recheck' ? 'Checking your public IP…' : 'Applying your choice…';
    try {
      const result=await monitor.resolveIPWarning(token,button.id);
      if (button.id === 'recheck') {
        const updated = monitor.getIPWarning(token);
        if (updated) renderComparison(updated);
      }
      status.textContent=result.error ? `Unknown: ${result.error} Check your route and try again.` : result.conflict ? 'Lookups still match: ' + (monitor.getIPWarning(token)?.matches?.map(match => match.ip).join(', ') || result.ip || 'recorded addresses') + '. Change your route and recheck, or choose an exception.' : 'Returning to the website…';
    } catch(error) {status.textContent=error.message;}
    finally {button.removeAttribute('aria-busy');buttons.forEach(b => b.disabled=false);}
  });
}
