/* MPL-2.0. Read-only diagnostics plus explicit, reversible configuration repairs. */
export function inspectConsistency(config, measured={}) {
  config = config || {};
  const issues=[];
  const add=(code,message,source='configuration',level='contradiction',repair=null)=>issues.push({code,message,source,level,repair});
  const ua=config['navigator.userAgent'];
  if (ua && config['headers.User-Agent'] && config['headers.User-Agent']!==ua) add('header-ua','HTTP and navigator user agents disagree.','configuration','contradiction',{'headers.User-Agent':ua});
  for(const axis of ['width','height']) {
    const size=config[`screen.${axis}`], key=`screen.avail${axis[0].toUpperCase()}${axis.slice(1)}`,available=config[key];
    if (Number.isFinite(size) && Number.isFinite(available) && available>size) add(`available-${axis}`,`Available screen ${axis} exceeds screen ${axis}.`,'configuration','contradiction',{[key]:size});
  }
  const platform=config['navigator.platform']||'';
  if (platform && ((/Windows/.test(ua||'')&&!/^Win/.test(platform)) || (/Macintosh/.test(ua||'')&&!/^Mac/.test(platform)) || (/Linux/.test(ua||'')&&!/Linux/.test(platform)))) add('platform-family','User agent and platform appear to describe different operating systems.','configuration','heuristic');
  const osOf = value => /Windows|Win32/i.test(value || '') ? 'windows'
    : /Macintosh|MacIntel|Mac OS/i.test(value || '') ? 'macos'
    : /Linux|X11/i.test(value || '') ? 'linux' : null;
  const os = osOf(ua), appVersion = config['navigator.appVersion'];
  if (os && osOf(appVersion) && os !== osOf(appVersion)) add('app-version','appVersion and user agent describe different operating systems.');
  for (const browser of ['Chrome','Firefox','Edg','Version']) {
    const pattern = new RegExp(`${browser}/([\\d.]+)`);
    const a = String(ua || '').match(pattern)?.[1], b = String(appVersion || '').match(pattern)?.[1];
    if (a && b && a !== b) add('app-version',`${browser} versions differ between userAgent and appVersion.`);
  }
  if (os && osOf(config['navigator.oscpu']) && os !== osOf(config['navigator.oscpu'])) add('oscpu-os','oscpu and user agent describe different operating systems.');
  if (os && os !== 'macos' && /Apple (M\d|GPU)/i.test(config['webGl:renderer'] || '')) add('gpu-os','Apple graphics are paired with a non-macOS identity.','configuration','heuristic');
  for (const key of ['webGl:parameters','webGl2:parameters']) {
    const renderer = config[key]?.['7937'];
    if (renderer && config['webGl:renderer'] && renderer !== config['webGl:renderer']) add('gl-renderer',`${key} renderer differs from the GPU field.`);
  }
  for (const axis of ['Width','Height']) {
    const suffix = axis.toLowerCase(), size = config[`screen.${suffix}`], available = config[`screen.avail${axis}`];
    if (Number.isFinite(size) && size <= 0) add(`screen-${suffix}`,`Screen ${suffix} must be positive.`);
    if (Number.isFinite(available) && available < 0) add(`available-${suffix}`,`Available screen ${suffix} must not be negative.`);
    const inner = config[`window.inner${axis}`], outer = config[`window.outer${axis}`];
    if (Number.isFinite(inner) && (inner < 0 || (Number.isFinite(outer) && inner > outer))) add(`viewport-${suffix}`,`Inner window ${suffix} is negative or exceeds outer ${suffix}.`);
  }
  const dpr = config['window.devicePixelRatio'];
  if (dpr !== undefined && (!Number.isFinite(dpr) || dpr <= 0)) add('dpr','Device pixel ratio must be finite and positive.');
  const language = config['navigator.language'];
  if (language) {
    let locale;
    try { locale = new Intl.Locale(language); }
    catch { add('language-tag','Navigator language is not a valid language tag.'); }
    if (locale) {
      const configuredLanguage = config['locale:language'];
      if (configuredLanguage) {
        try { if (new Intl.Locale(configuredLanguage).language !== locale.language) add('locale-language','Locale language differs from navigator.language.'); }
        catch { add('locale-language','Configured locale language is invalid.'); }
      }
      if (locale.region && config['locale:region'] && locale.region !== String(config['locale:region']).toUpperCase()) add('locale-region','Locale region differs from navigator.language.');
      const first = config['headers.Accept-Language']?.split(',')[0].split(';')[0].trim();
      if (first) {
        try { if (new Intl.Locale(first).toString() !== locale.toString()) add('language-header','Primary Accept-Language differs from navigator.language.'); }
        catch { add('language-header','Primary Accept-Language is invalid.'); }
      }
    }
  }
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

// Compare configuration findings only: no measurements, repairs or preference writes.
export function confirmConsistencyChange(previous, candidate, confirm) {
  const findings = config => inspectConsistency(config).filter(issue => issue.source === 'configuration');
  const known = new Set(findings(previous).map(issue => issue.code + ':' + issue.message));
  const fresh = findings(candidate).filter(issue => !known.has(issue.code + ':' + issue.message));
  return !fresh.length || confirm('This change introduces persona conflicts:\n\n' +
    fresh.map(issue => '• ' + issue.message).join('\n') +
    '\n\nSave anyway? Cancel keeps your current settings.');
}
