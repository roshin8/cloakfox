/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
const { getContainerNetwork, setContainerNetwork } = ChromeUtils.importESModule(
  'resource:///modules/CloakfoxNetworkPolicy.sys.mjs');
const containerSelect = document.getElementById('cfx-container-select');
const mode = document.getElementById('cfx-network-mode');
const proxy = document.getElementById('cfx-proxy-url');
const rtc = document.getElementById('cfx-webrtc-mode');
const status = document.getElementById('cfx-route-status');
const lookup = document.getElementById('cfx-ip-lookup');
function updateFields() {
  proxy.disabled = mode.value !== '1';
  rtc.disabled = mode.value !== '0';
}
function loadNetwork() {
  const policy = getContainerNetwork(Number(containerSelect.value));
  mode.value = String([0,1,2].includes(policy.mode) ? policy.mode : 2);
  proxy.value = policy.proxyURL;
  rtc.value = String([0,1,2].includes(policy.webrtcMode) ? policy.webrtcMode : 2);
  lookup.checked = Services.prefs.getBoolPref('cloakfox.webrtc.ip_lookup.enabled', false);
  status.textContent = '';
  updateFields();
}
containerSelect.addEventListener('change', loadNetwork);
document.addEventListener('cfx-network-changed', loadNetwork);
mode.addEventListener('change', updateFields);
document.getElementById('cfx-network-apply').addEventListener('click', () => {
  try {
    setContainerNetwork(Number(containerSelect.value), {
      mode: Number(mode.value), proxyURL: proxy.value, webrtcMode: Number(rtc.value),
    });
    Services.prefs.savePrefFile(null);
    document.dispatchEvent(new Event('cfx-network-changed'));
    status.textContent = 'Saved manual route (saved proxy binding cleared). Applies to new page requests; existing WebRTC connections close. Reload open pages to use the new route. Existing downloads may continue.';
  } catch (error) {
    status.textContent = error.message;
  }
});
lookup.addEventListener('change', () => {
  Services.prefs.setBoolPref('cloakfox.webrtc.ip_lookup.enabled', lookup.checked);
  Services.prefs.savePrefFile(null);
});
loadNetwork();

// Recent route measurements and bounded, local IP ownership history.
{
  const ipMonitor = ChromeUtils.importESModule('resource:///modules/CloakfoxIPConflicts.sys.mjs');
  const panel=document.createElement('section');panel.id='cfx-ip-conflict-panel';panel.className='card';
  const heading=document.createElement('h2');heading.textContent='IP conflict management';panel.append(heading);
  const note=document.createElement('p');note.textContent='Checks ipify through each container’s route, with httpbin as fallback. Observations can differ by destination or address family. Warnings require a recorded visit to the same exact hostname in another container with the same IP. Manual route checks do not count as visits. Warnings appear after the initial connection. Private windows are excluded. Local history retains up to 500 container/hostname/IP records for 30 days and ten recent URLs per record, without query strings or fragments.';panel.append(note);
  function toggle(labelText,id){const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.id=id;label.append(input,document.createTextNode(labelText));panel.append(label);return input;}
  const automatic=toggle('Check automatically on website navigation','cfx-ip-auto');
  automatic.checked=Services.prefs.getBoolPref('cloakfox.ip_conflicts.enabled',false);
  automatic.addEventListener('change',()=>{Services.prefs.setBoolPref('cloakfox.ip_conflicts.enabled',automatic.checked);Services.prefs.savePrefFile(null);});
  const monitorStatus=document.createElement('p');monitorStatus.id='cfx-ip-monitor-status';monitorStatus.setAttribute('role','status');panel.append(monitorStatus);
  function showMonitorStatus(){monitorStatus.textContent=automatic.checked?'Automatic IP checking is ON. Reload a matching website in each container to compare their IPs.':'Automatic IP checking is OFF. Saved website rules do not run until you enable checking.';}
  automatic.addEventListener('change',showMonitorStatus);showMonitorStatus();
  const allowed=toggle('Allow shared IPs for the selected container','cfx-ip-allow');
  allowed.addEventListener('change',()=>{ipMonitor.allowSharedIP(Number(containerSelect.value),allowed.checked);Services.prefs.savePrefFile(null);});
  const check=document.createElement('button');check.type='button';check.id='cfx-ip-check';check.textContent='Check all containers now';panel.append(check);
  const results=document.createElement('p');results.id='cfx-ip-results';results.setAttribute('role','status');panel.append(results);
  document.querySelector('main').append(panel);
  const identities=()=>{
    const {ContextualIdentityService:service}=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
    return [{userContextId:0,name:'Default (no container)'},...service.getPublicIdentities().map(identity=>({
      userContextId:identity.userContextId,
      name:service.getUserContextLabel(identity.userContextId)||identity.name||`Container ${identity.userContextId}`,
    }))];
  };

  function selectField(labelText, choices) {
    const label=document.createElement('label');label.textContent=labelText;
    const select=document.createElement('select');for(const [value,text] of choices)select.append(new Option(text,value));label.append(select);panel.append(label);return select;
  }
  const checkRoute=selectField('IP lookup route',[
    ['background','Background route — native Cloakfox routing'],
    ['tab','Tab route — Multi-Account Containers / tab-based proxies'],
  ]);
  checkRoute.id='cfx-ip-check-route';checkRoute.value=ipMonitor.getIPCheckRoute();
  const routeHelp=document.createElement('p');
  routeHelp.textContent='Tab route uses temporary hidden background tabs in each container. Background route uses internal requests. Both measure the IP-check service; website-specific proxy rules may use another route. Switching clears cached checks; saved visit history is retained separately by lookup route.';
  panel.append(routeHelp);
  const routeStatus=document.createElement('p');routeStatus.id='cfx-ip-route-status';routeStatus.setAttribute('role','status');panel.append(routeStatus);
  checkRoute.addEventListener('change',()=>{
    ipMonitor.setIPCheckRoute(checkRoute.value);
    routeStatus.textContent='Route changed. Cached results cleared. Run a fresh check or visit a website with automatic checking enabled.';
    displayIPs();
  });
  const response=selectField('When a conflict is detected',[['warning','Show warning page'],['notification','Show notification only']]);
  response.value=Services.prefs.getStringPref('cloakfox.ip_conflicts.response','warning');
  response.onchange=()=>{Services.prefs.setStringPref('cloakfox.ip_conflicts.response',response.value);Services.prefs.savePrefFile(null);};
  const rulesTitle=document.createElement('h3');rulesTitle.textContent='Websites to check';panel.append(rulesTitle);
  const scope=selectField('Rule scope',[['global','Default for all containers'],['container','Selected container only']]);
  const ruleMode=selectField('Check on navigation',[['all','All websites except exclusions'],['selected','Only listed websites']]);
  const fields=document.createElement('div');fields.className='ip-manager-fields';panel.append(fields);
  function domainInput(text){const label=document.createElement('label');label.textContent=text;const input=document.createElement('textarea');input.placeholder='example.com';label.append(input);fields.append(label);return input;}
  const included=domainInput('Included hostnames — one per line'),excluded=domainInput('Excluded hostnames — one per line');
  const help=document.createElement('p');help.textContent='Hostnames include their subdomains. Exclusions win. Manual checks ignore this website filter.';panel.append(help);
  const ruleStatus=document.createElement('p');ruleStatus.setAttribute('role','status');panel.append(ruleStatus);
  function action(text,fn,parent=panel){const button=document.createElement('button');button.type='button';button.textContent=text;button.onclick=()=>{try{fn();}catch(error){ruleStatus.textContent=error.message;}};parent.append(button);return button;}
  const scopeId=()=>scope.value==='global'?null:Number(containerSelect.value);
  function loadRules(){const rules=ipMonitor.getIPRules(scopeId());ruleMode.value=rules.mode;included.value=rules.include.join('\n');excluded.value=rules.exclude.join('\n');ruleStatus.textContent='';explainRuleMode();}
  function saveRules(enable=false){
    const lines=input=>input.value.split(/\n/).map(v=>v.trim()).filter(Boolean);
    ipMonitor.setIPRules({mode:ruleMode.value,include:lines(included),exclude:lines(excluded)},scopeId());
    if(enable){automatic.checked=true;automatic.dispatchEvent(new Event('change'));}
    ruleStatus.textContent=automatic.checked?'Website rules saved. Automatic checking is on; reload the test sites.':'Website rules saved, but automatic checking is OFF. Use Save and enable checking to activate them.';
  }
  action('Save website rules',()=>saveRules());
  action('Save and enable checking',()=>saveRules(true));
  function explainRuleMode(){included.disabled=ruleMode.value==='all';help.textContent=ruleMode.value==='all'?'All websites are checked except exclusions. The included list is inactive in this mode. Manual checks ignore website filters.':'Only included hostnames and their subdomains are checked. Exclusions win. Manual checks ignore website filters.';}
  ruleMode.addEventListener('change',explainRuleMode);

  action('Use global rules for this container',()=>{ipMonitor.resetIPRules(Number(containerSelect.value));loadRules();ruleStatus.textContent='Selected container now uses global rules.';});
  scope.onchange=loadRules;containerSelect.addEventListener('change',loadRules);loadRules();
  const exceptionTitle=document.createElement('h3');exceptionTitle.textContent='Allowed IP addresses';panel.append(exceptionTitle);
  const exceptionLabel=document.createElement('label');exceptionLabel.textContent='IP address';const exceptionInput=document.createElement('input');exceptionInput.placeholder='192.0.2.1';exceptionLabel.append(exceptionInput);panel.append(exceptionLabel);
  action('Allow IP',()=>{ipMonitor.setIPException(exceptionInput.value,true);exceptionInput.value='';});
  const exceptionList=document.createElement('div');panel.append(exceptionList);
  const historyTitle=document.createElement('h3');historyTitle.textContent='Website IP visit history';panel.append(historyTitle);
  const historyHelp=document.createElement('p');historyHelp.className='ip-history-help';
  historyHelp.textContent='Saved observations, not a list of conflicts. Each record shows the public IP observed when a container visited a website. IPv4 and IPv6 are separate records. The same address may appear on several websites.';panel.append(historyHelp);
  action('Clear all IP records',()=>ipMonitor.clearIPHistory());
  const historyFilterLabel=document.createElement('label');historyFilterLabel.className='ip-history-filter';historyFilterLabel.textContent='Filter visit history';
  const historyFilter=document.createElement('input');historyFilter.type='search';historyFilter.placeholder='Website, container or IP address';historyFilterLabel.append(historyFilter);panel.append(historyFilterLabel);
  const historyCount=document.createElement('p');historyCount.className='ip-history-filter-status';historyCount.setAttribute('role','status');historyCount.setAttribute('aria-live','polite');panel.append(historyCount);
  const historyList=document.createElement('div');panel.append(historyList);
  const websiteOpenState=new Map();
  function filterHistory(){
    const query=historyFilter.value.trim().toLocaleLowerCase();
    let websites=0,records=0;
    for(const website of historyList.querySelectorAll('.ip-history-website')){
      let visible=0;
      for(const row of website.querySelectorAll('.ip-history-record')){
        row.hidden=!!query&&!row.dataset.search.includes(query);
        if(!row.hidden)visible++;
      }
      website.hidden=visible===0;
      website.querySelector('.ip-website-count').textContent=`${visible} record${visible===1?'':'s'}`;
      if(visible){websites++;records+=visible;}
      website.open=query?visible>0:!!websiteOpenState.get(website.dataset.hostname);
    }
    historyCount.textContent=query?`${records} matching records across ${websites} websites${records?'':'. Try a different filter.'}`:`${websites} websites · ${records} records. Expand a website to view its observations.`;
  }
  historyFilter.addEventListener('input',filterHistory);
  function displayHistory(){
    const all=identities(),names=new Map(all.map(item=>[item.userContextId,item.name]));
    exceptionList.replaceChildren();
    for(const ip of ipMonitor.ipExceptions()){const row=document.createElement('div');row.className='ip-record';row.append(document.createTextNode(ip+' '));action('Remove exception',()=>ipMonitor.setIPException(ip,false),row);exceptionList.append(row);}
    if(!exceptionList.children.length)exceptionList.textContent='No IP exceptions.';
    historyList.replaceChildren();
    const websiteGroups=new Map();
    for(const record of ipMonitor.ipHistory()){
      const hostname=record.hostname||'';
      let website=websiteGroups.get(hostname);
      if(!website){
        website=document.createElement('details');website.className='ip-history-website';website.dataset.hostname=hostname;
        const title=document.createElement('summary');
        const name=document.createElement('strong');name.textContent=hostname||'Legacy records — not used for warnings';
        const count=document.createElement('span');count.className='ip-website-count';title.append(name,count);website.append(title);
        website.open=!!websiteOpenState.get(hostname);
        website.addEventListener('toggle',()=>{if(!historyFilter.value.trim()&&website.isConnected)websiteOpenState.set(hostname,website.open);});
        websiteGroups.set(hostname,website);historyList.append(website);
      }
      const row=document.createElement('div');row.className='ip-record ip-history-record';
      const header=document.createElement('div');header.className='ip-history-record-header';
      const container=document.createElement('strong');container.className='ip-history-container';container.textContent=names.get(record.ucid)||'Deleted container';header.append(container);row.append(header);
      row.dataset.search=`${hostname} ${container.textContent} ${record.ip}`.toLocaleLowerCase();
      const address=document.createElement('p');address.className='ip-history-address';
      const family=document.createElement('span');family.textContent=record.ip.includes(':')?'IPv6':'IPv4';
      const ip=document.createElement('code');ip.textContent=record.ip;address.append(family,ip);row.append(address);
      const meta=document.createElement('p');meta.className='ip-history-meta';meta.textContent=`First seen ${new Date(record.firstAccessed).toLocaleString()} · Last seen ${new Date(record.lastAccessed).toLocaleString()} · ${record.accessCount} observations`;row.append(meta);
      const edit=document.createElement('div');edit.className='ip-record-actions';edit.hidden=true;
      const editButton=document.createElement('button');editButton.type='button';editButton.className='ip-history-edit';editButton.textContent='Edit';editButton.setAttribute('aria-label',`Edit ${container.textContent} ${family.textContent} record for ${hostname||'legacy history'}`);editButton.setAttribute('aria-expanded','false');
      editButton.onclick=()=>{edit.hidden=!edit.hidden;editButton.textContent=edit.hidden?'Edit':'Done';editButton.setAttribute('aria-expanded',String(!edit.hidden));};header.append(editButton);
      const editHelp=document.createElement('p');editHelp.textContent='Reassign changes which container owns this saved observation; it does not change the container’s IP or connection.';edit.append(editHelp);
      const ownerLabel=document.createElement('label');ownerLabel.textContent='Assign record to';
      const owner=document.createElement('select');owner.setAttribute('aria-label','Assign '+record.ip+' to container');for(const item of all)owner.append(new Option(item.name,item.userContextId));
      if(!names.has(record.ucid)) owner.append(new Option('Deleted container (current record)',String(record.ucid)));
      owner.value=String(record.ucid);ownerLabel.append(owner);edit.append(ownerLabel);
      const buttons=document.createElement('div');buttons.className='ip-history-actions';edit.append(buttons);
      action('Reassign record',()=>ipMonitor.reassignIP(record.ip,Number(owner.value),record.ucid,record.hostname??''),buttons);
      action('Delete record',()=>ipMonitor.clearIPHistory(record.ip,record.ucid,record.hostname??''),buttons);
      action('Allow this IP globally',()=>ipMonitor.setIPException(record.ip,true),buttons);
      const allowHelp=document.createElement('p');allowHelp.textContent='Allow this IP globally suppresses conflicts for this address across containers. Delete removes only this saved record.';edit.append(allowHelp);row.append(edit);
      const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Recent URLs';details.append(summary);
      for(const url of record.urls){const line=document.createElement('p');line.textContent=url;details.append(line);}row.append(details);website.append(row);
    }
    if(!historyList.children.length)historyList.textContent='No recorded website visits. History is collected on checked website visits.';
    filterHistory();
  }

  function displayIPs(){
    displayHistory();
    allowed.checked=Services.prefs.getBoolPref(`cloakfox.container.${Number(containerSelect.value)}.allow_shared_ip`,false);
    const names=new Map(identities().map(item=>[item.userContextId,item.name]));
    const rows=ipMonitor.ipConflictResults().filter(row=>names.has(row.ucid));
    results.replaceChildren();
    if (!rows.length) {results.textContent='No recent measurements. Check now or enable automatic checks.';return;}
    for(const row of rows){
      const line=document.createElement('span');line.style.display='block';line.style.overflowWrap='anywhere';
      const title=document.createElement('strong');title.textContent=names.get(row.ucid);line.append(title);
      const legacy=!('ipv4' in row)&&!('ipv6' in row);
      const legacyFamily=row.ip?.includes(':')?'ipv6':'ipv4';
      for(const [family,label] of [['ipv4','IPv4'],['ipv6','IPv6']]){
        const ip=legacy?(family===legacyFamily?row.ip:''):row[family];
        const error=row.errors?.[family]||(legacy&&family===legacyFamily?row.error:'');
        const conflicts=row.matches
          ? row.matches.filter(match=>match.family===family).flatMap(match=>match.conflicts)
          : legacy ? (family===legacyFamily?row.conflicts:[])
          : rows.filter(other=>other.ucid!==row.ucid && row.conflicts.includes(other.ucid) && ip && other[family]===ip).map(other=>other.ucid);
        const measurement=document.createElement('span');measurement.style.display='block';
        measurement.textContent=`${label}: ${ip||'Unknown'} — ${error|| (conflicts.length ? 'same measured address as '+[...new Set(conflicts)].map(id=>names.get(id)||`Container ${id}`).join(', ') : ip ? 'no match in recent route measurements' : 'no measurement available')}`;
        line.append(measurement);
      }
      results.append(line);
    }
  }
  check.addEventListener('click',async()=>{
    check.disabled=true;results.textContent='Checking container routes…';
    try {for(const identity of identities()) await ipMonitor.checkContainerIP(identity.userContextId,{force:true});displayIPs();}
    catch(error){results.textContent='Check failed: '+error.message;}
    finally{check.disabled=false;}
  });
  const observer={observe(){checkRoute.value=ipMonitor.getIPCheckRoute();displayIPs();}};Services.obs.addObserver(observer,'cloakfox-ip-conflicts-updated');
  window.addEventListener('unload',()=>Services.obs.removeObserver(observer,'cloakfox-ip-conflicts-updated'),{once:true});
  containerSelect.addEventListener('change',displayIPs);document.addEventListener('cfx-network-changed',displayIPs);displayIPs();
}
