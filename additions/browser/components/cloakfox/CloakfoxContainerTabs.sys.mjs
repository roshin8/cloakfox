/* MPL-2.0. Close selected tabs without changing container identity or storage. */
export function validateSelectedTabs(ids, container, window, lookup) {
  if(!Array.isArray(ids)||!ids.length||ids.length>2000||new Set(ids).size!==ids.length||
     ids.some(id=>!Number.isInteger(id)||id<0))throw new Error('Select one or more open tabs.');
  return ids.map(id=>{
    const tab=lookup(id);
    if(!tab||tab.closing||tab.container!==container||tab.window!==window)
      throw new Error('The tab list changed. Reopen the container and select its tabs again.');
    return tab;
  });
}
export function closeSelectedContainerTabs(actor, data) {
  const {resolveContainer}=ChromeUtils.importESModule('resource:///modules/CloakfoxContainerProxyEditor.sys.mjs');
  const container=resolveContainer(data);
  const win=actor.browsingContext.top.embedderElement?.documentGlobal;
  if(!win?.gBrowser||win.closed)throw new Error('The browser window is no longer available.');
  const {ExtensionParent}=ChromeUtils.importESModule('resource://gre/modules/ExtensionParent.sys.mjs');
  const extension=ExtensionParent.GlobalManager.getExtension('@testpilot-containers');
  if(!extension||extension.hasShutdown)throw new Error('Multi-Account Containers is not running.');
  const chosen=validateSelectedTabs(data.tabIds,container.id,win,id=>{
    const native=extension.tabManager.get(id,null)?.nativeTab;
    return native?{native,closing:native.closing,container:Number(native.getAttribute('usercontextid')||0),window:native.documentGlobal}:null;
  });
  // Preserve beforeunload handling and normal SessionStore undo-close history.
  // This path never invokes identity deletion, browsingData, or cache clearing.
  win.gBrowser.removeTabs(chosen.map(item=>item.native),{animate:false,suppressWarnAboutClosingWindow:true});
  return {requested:chosen.length,closed:chosen.filter(item=>item.native.closing||!item.native.isConnected).length};
}
