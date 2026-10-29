/* Configuration checks are advisory; they neither rewrite values nor establish
 * anonymity. Unknown hardware and missing optional fields are not contradictions. */
function osOf(value='') {
  if (/Windows|Win32/i.test(value)) return 'windows';
  if (/Macintosh|MacIntel|Mac OS/i.test(value)) return 'macos';
  if (/Linux|X11/i.test(value)) return 'linux';
  return null;
}
export function validatePersona(cfg={}) {
  cfg = cfg || {};
  const issues=[];
  const add=(code,message)=>issues.push({code,message});
  const ua=cfg['navigator.userAgent'];const os=osOf(ua);
  if (ua && cfg['headers.User-Agent'] && ua!==cfg['headers.User-Agent']) add('ua-header','The HTTP User-Agent header differs from navigator.userAgent.');
  const appVersion = cfg['navigator.appVersion'];
  const appOS = osOf(appVersion);
  if (os && appOS && os !== appOS) add('app-version','navigator.appVersion describes a different OS from the user agent.');
  // Firefox may use a reduced appVersion. Compare version tokens only when
  // both surfaces actually contain them; absence is not a contradiction.
  for (const browser of ['Chrome', 'Firefox', 'Edg', 'Version']) {
    const pattern = new RegExp(`${browser}/([\\d.]+)`);
    const uaToken = String(ua || '').match(pattern)?.[1];
    const appToken = String(appVersion || '').match(pattern)?.[1];
    if (uaToken && appToken && uaToken !== appToken) add('app-version',`${browser} versions differ between userAgent and appVersion.`);
  }
  for (const [key,code] of [['navigator.platform','platform-os'],['navigator.oscpu','oscpu-os']]) {
    const other=osOf(cfg[key]);if(os && other && other!==os)add(code,`${key} describes a different OS from the user agent.`);
  }
  if(os && os!=='macos' && /Apple (M\d|GPU)/i.test(cfg['webGl:renderer']||''))add('gpu-os','Apple graphics are paired with a non-macOS desktop identity.');
  for(const key of ['webGl:parameters','webGl2:parameters']) {
    const renderer=cfg[key]?.['7937'];
    if(renderer && cfg['webGl:renderer'] && renderer!==cfg['webGl:renderer'])add('gl-renderer',`${key} reports a different renderer from the GPU field.`);
  }
  for(const [axis,suffix] of [['Width','width'],['Height','height']]) {
    const size=cfg[`screen.${suffix}`],available=cfg[`screen.avail${axis}`];
    if(Number.isFinite(size)&&size<=0)add(`screen-${suffix}`,`Screen ${suffix} must be positive.`);
    if(Number.isFinite(available)&&(available<0 || (Number.isFinite(size)&&available>size)))add(`available-${suffix}`,`Available screen ${suffix} exceeds the screen or is negative.`);
    const inner=cfg[`window.inner${axis}`],outer=cfg[`window.outer${axis}`];
    if(Number.isFinite(inner)&&Number.isFinite(outer)&&(inner<0 || outer<inner))add(`viewport-${suffix}`,`Inner window ${suffix} exceeds outer window ${suffix} or is negative.`);
  }
  const dpr=cfg['window.devicePixelRatio'];
  if(dpr!==undefined&&(!Number.isFinite(dpr)||dpr<=0))add('dpr','Device pixel ratio must be a finite positive number.');
  const language=cfg['navigator.language'];
  if(language){
    try {
      const locale=new Intl.Locale(language);
      if(cfg['locale:language'] && locale.language!==cfg['locale:language'])add('locale-language','Locale language differs from navigator.language.');
      if(locale.region && cfg['locale:region'] && locale.region!==cfg['locale:region'])add('locale-region','Locale region differs from navigator.language.');
      const first=cfg['headers.Accept-Language']?.split(',')[0].split(';')[0].trim();
      if(first && first.toLowerCase()!==language.toLowerCase())add('language-header','The first Accept-Language choice differs from navigator.language.');
    }catch{add('language-tag','Navigator language is not a valid language tag.');}
  }
  return issues;
}
export function compareRealmSignals(page,realm) {
  return ['userAgent','platform','language','hardwareConcurrency'].filter(key=>key in page && key in realm && page[key]!==realm[key]).map(key=>({code:`realm-${key}`,message:`The worker and page disagree on ${key}.`}));
}
