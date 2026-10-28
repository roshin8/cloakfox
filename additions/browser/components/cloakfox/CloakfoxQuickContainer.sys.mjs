/* MPL-2.0. Permanent containers with an automatic name and balanced random color. */
function randomIndex(length) {
  const value=new Uint32Array(1),limit=0x100000000-(0x100000000%length);
  do {crypto.getRandomValues(value);} while(value[0]>=limit);
  return value[0]%length;
}
export function chooseQuickContainerOptions(identities,colors,pick=randomIndex) {
  if(!colors.length)throw new Error('No container colors are available.');
  const names=new Set(identities.map(item=>item.name.toLowerCase()));
  let number=1,name;
  do {name=`Container #${String(number++).padStart(2,'0')}`;} while(names.has(name.toLowerCase()));
  const counts=new Map(colors.map(color=>[color,0]));
  for(const item of identities)if(counts.has(item.color))counts.set(item.color,counts.get(item.color)+1);
  const minimum=Math.min(...counts.values()),choices=colors.filter(color=>counts.get(color)===minimum);
  return {name,color:choices[pick(choices.length)],icon:'circle'};
}
export function createQuickContainer(win) {
  if(!win?.gBrowser)throw new Error('Open a browser window first.');
  const cis=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService;
  const identities=cis.getPublicIdentities().map(item=>({...item,name:cis.getUserContextLabel(item.userContextId)}));
  const options=chooseQuickContainerOptions(identities,cis.containerColors);
  const identity=cis.create(options.name,options.icon,options.color);
  try {
    win.gBrowser.selectedTab=win.gBrowser.addTrustedTab('about:newtab',{userContextId:identity.userContextId});
    return identity;
  } catch(error) {
    cis.remove(identity.userContextId);
    throw error;
  }
}

let buttonRegistered=false;
export function initQuickContainerButton() {
  if(buttonRegistered)return;
  const {CustomizableUI}=ChromeUtils.importESModule('moz-src:///browser/components/customizableui/CustomizableUI.sys.mjs');
  const id='cloakfox-quick-container-button';
  const temporaryId='_c607c8df-14a7-4f28-894f-29e8722976af_-browser-action';
  const pref='cloakfox.quick_container.toolbar.v1';
  CustomizableUI.createWidget({
    id,
    localized:false,
    label:'New permanent container',
    tooltiptext:'New permanent container: automatic name, random color, new tab',
    onCreated(node) {
      node.setAttribute('label','New permanent container');
      node.setAttribute('tooltiptext','New permanent container: automatic name, random color, new tab');
      node.style.cssText='list-style-image:url("chrome://browser/content/cloakfox/quick-container.svg");-moz-context-properties:fill;fill:currentColor;';
    },
    onCommand(event) {createQuickContainer(event.target.documentGlobal);},
  });
  const migrate=()=>{
    const previous=CustomizableUI.getPlacementOfWidget(temporaryId);
    if(!Services.prefs.getBoolPref(pref,false) || previous?.area===CustomizableUI.AREA_TABSTRIP) {
      CustomizableUI.addWidgetToArea(id,CustomizableUI.AREA_TABSTRIP,
        previous?.area===CustomizableUI.AREA_TABSTRIP?previous.position:undefined);
      Services.prefs.setBoolPref(pref,true);
    }
    if(previous?.area===CustomizableUI.AREA_TABSTRIP)
      CustomizableUI.removeWidgetFromArea(temporaryId);
  };
  // BrowserGlue calls us before toolbar placements have been restored.
  Services.obs.addObserver({observe(){migrate();}},'browser-delayed-startup-finished');
  if(Services.wm.getMostRecentWindow('navigator:browser')?.gBrowserInit?.delayedStartupFinished)migrate();
  CustomizableUI.addListener({onWidgetAdded(widgetId){
    if(widgetId===temporaryId)Services.tm.dispatchToMainThread(migrate);
  }});
  buttonRegistered=true;
}
