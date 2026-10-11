/* MPL-2.0. Read-only diagnostics plus explicit, reversible configuration repairs. */
export function inspectConsistency(config, measured={}) {
  const issues=[];
  const add=(code,message,source='configuration',level='contradiction',repair=null)=>issues.push({code,message,source,level,repair});
  const ua=config['navigator.userAgent'];
  if (ua && config['headers.User-Agent']!==ua) add('header-ua','HTTP and navigator user agents disagree.','configuration','contradiction',{'headers.User-Agent':ua});
  for(const axis of ['width','height']) {
    const size=config[`screen.${axis}`], key=`screen.avail${axis[0].toUpperCase()}${axis.slice(1)}`,available=config[key];
    if (Number.isFinite(size) && Number.isFinite(available) && available>size) add(`available-${axis}`,`Available screen ${axis} exceeds screen ${axis}.`,'configuration','contradiction',{[key]:size});
  }
  const platform=config['navigator.platform']||'';
  if ((/Windows/.test(ua||'')&&!/^Win/.test(platform)) || (/Macintosh/.test(ua||'')&&!/^Mac/.test(platform)) || (/Linux/.test(ua||'')&&!/Linux/.test(platform))) add('platform-family','User agent and platform appear to describe different operating systems.','configuration','heuristic');
  const fields={userAgent:'navigator.userAgent',platform:'navigator.platform',language:'navigator.language',hardwareConcurrency:'navigator.hardwareConcurrency'};
  for(const scope of ['window','worker']) {
    if (!measured[scope]) {add(`${scope}-unavailable`,measured[`${scope}Error`]||`No ${scope} measurement available.`,'measurement','unavailable');continue;}
    for(const [name,key] of Object.entries(fields)) {
      if (measured[scope][name]!==undefined && config[key]!==undefined && measured[scope][name]!==config[key]) add(`${scope}-${name}`,`${scope} ${name} differs from configured value. Reload the page after settings changes.`, 'measurement');
    }
    if(measured[scope].timezone && measured.expectedTimezone && measured[scope].timezone!==measured.expectedTimezone) add(`${scope}-timezone`,`${scope} timezone differs from the region setting.`,'measurement');
  }
  if (measured.window && measured.worker) for (const field of ['language','timezone','locale','hardwareConcurrency']) {
    if(measured.window[field]!==undefined && measured.worker[field]!==undefined && measured.window[field]!==measured.worker[field]) add(`window-worker-${field}`,`Window and worker ${field} disagree.`,'measurement');
  }
  add('network-unmeasured','HTTP headers, proxy exit location, TLS and IP-region agreement require an explicit network diagnostic; this check sends no requests.','measurement','unavailable');
  return issues;
}
export async function measureContainer(ucid) {
  if (!Number.isInteger(ucid)||ucid<0) throw new Error('Invalid container');
  // Inspect a real open website in this container, never the chrome settings page.
  const {PrivateBrowsingUtils}=ChromeUtils.importESModule('resource://gre/modules/PrivateBrowsingUtils.sys.mjs');
  for(const win of Services.wm.getEnumerator('navigator:browser')) {
    if(PrivateBrowsingUtils.isWindowPrivate(win))continue;
    for(const tab of [...win.gBrowser.tabs].reverse()) {
      const browser=tab.linkedBrowser;
      if(Number(tab.getAttribute('usercontextid')||0)!==ucid || !/^https?:$/.test(browser.currentURI.scheme+':')) continue;
      const global=browser.browsingContext.currentWindowGlobal;
      if(!global)continue;
      const result=await global.getActor('CloakfoxMath').sendQuery('Cloakfox:Inspect');
      if(browser.browsingContext.currentWindowGlobal!==global)throw new Error('Page navigated during measurement; run the check again.');
      return {...result,site:browser.currentURI.prePath};
    }
  }
  return {windowError:'Open a website in this container to measure its window.',workerError:'No website available for worker measurement.'};
}
export function repairConsistency(ucid, issue, expectedRaw) {
  const pref=`cloakfox.s.cloak_cfg_${ucid}`;
  const current=Services.prefs.getStringPref(pref,'');
  if(current!==expectedRaw)throw new Error('Settings changed; run the inspector again before repairing.');
  const cfg=JSON.parse(current);
  // Recompute the permitted repair; never accept arbitrary keys from the UI.
  const allowed=inspectConsistency(cfg).find(candidate=>candidate.code===issue.code)?.repair;
  if(!allowed)throw new Error('This finding has no automatic repair.');
  const {readOverrides,setOverride,clearOverride}=ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs');
  const oldOverrides=readOverrides(ucid), undo={ucid,before:current,overrides:{}};
  for(const [key,value] of Object.entries(allowed)) {
    undo.overrides[key]=Object.hasOwn(oldOverrides,key)?{present:true,value:oldOverrides[key]}:{present:false};
    setOverride(ucid,key,value);cfg[key]=value;
  }
  undo.after=JSON.stringify(cfg);Services.prefs.setStringPref(pref,undo.after);Services.prefs.savePrefFile(null);return undo;
}
export function undoConsistencyRepair(record) {
  const pref=`cloakfox.s.cloak_cfg_${record.ucid}`;
  if(Services.prefs.getStringPref(pref,'')!==record.after)throw new Error('Settings changed since repair; undo would overwrite newer changes.');
  const {readOverrides,setOverride,clearOverride}=ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs');
  const current=readOverrides(record.ucid), after=JSON.parse(record.after);
  for(const key of Object.keys(record.overrides))if(current[key]!==after[key])throw new Error('An override changed since repair; run the inspector again.');
  for(const [key,value] of Object.entries(record.overrides))value.present?setOverride(record.ucid,key,value.value):clearOverride(record.ucid,key);
  Services.prefs.setStringPref(pref,record.before);Services.prefs.savePrefFile(null);
}
