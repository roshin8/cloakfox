/* MPL-2.0. Privileged, selection-scoped container operations for the MAC popup. */
export function validateBulkSelection(ids, identities) {
  if (!Array.isArray(ids) || !ids.length || ids.length>500 || new Set(ids).size!==ids.length ||
      ids.some(id=>!Number.isInteger(id)||id<=0)) throw new Error('Select one or more existing containers.');
  return ids.map(id=>{
    const identity=identities.find(item=>item.id===id);
    if(!identity)throw new Error('A selected container no longer exists. Refresh the selection.');
    return identity;
  });
}
export function bulkProxyRows(rows, ids, proxy, isolationKey) {
  const result=rows.map(row=>({...row}));
  for(const id of ids){
    const cookieStoreId=`firefox-container-${id}`;
    const entry={cookieStoreId,proxy:proxy?{...proxy,connectionIsolationKey:isolationKey(id)}:null};
    const index=result.findIndex(row=>row.cookieStoreId===cookieStoreId);
    if(index<0)result.push(entry);else result[index]={...result[index],...entry};
  }
  return result;
}
function service(){return ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService;}
function identities(){return service().getPublicIdentities().map(item=>({id:item.userContextId,name:service().getUserContextLabel(item.userContextId)}));}
const editor=()=>ChromeUtils.importESModule('resource:///modules/CloakfoxContainerProxyEditor.sys.mjs');
const key=id=>`cloakfox-managed:mac-${id}-${Services.uuid.generateUUID()}`;
const usable=proxy=>proxy && !proxy.mozProxyEnabled && ['http','https','socks','socks4'].includes(proxy.type) && proxy.host && proxy.port;
async function rowsAndStorage(){
  const store=await editor().macProxyStorage();
  const data=await store.db.get('proxifiedContainersKey');
  return {...store,rows:data.proxifiedContainersKey||[]};
}
async function writeRows(store, rows){
  const changes=await store.db.set({proxifiedContainersKey:rows});
  if(changes)store.ExtensionStorageIDB.notifyListeners('@testpilot-containers',changes);
  ChromeUtils.importESModule('resource:///modules/CloakfoxIPConflicts.sys.mjs').clearIPCheckCache();
}
export async function listBulkContainers(){
  const store=await rowsAndStorage();
  return identities().map(item=>{
    const proxy=store.rows.find(row=>row.cookieStoreId===`firefox-container-${item.id}`)?.proxy;
    return {...item,proxy:!!usable(proxy),server:usable(proxy)?`${proxy.type}://${proxy.host}:${proxy.port}`:''};
  });
}
export async function applyBulkProxy(data){
  const targets=validateBulkSelection(data.ids,identities());
  const network=ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkPolicy.sys.mjs');
  const incompatible=targets.filter(item=>network.getContainerNetwork(item.id).mode!==0);
  if(incompatible.length)throw new Error(`These containers use a separate network policy: ${incompatible.map(item=>item.name).join(', ')}. Change that policy in Cloakfox settings first.`);
  const store=await rowsAndStorage();
  if(!store.extension.hasPermission('proxy'))throw new Error('Enable the extension’s proxy permission first.');
  let proxy=null;
  if(!data.remove){
    if(data.sourceId){
      validateBulkSelection([data.sourceId],identities());
      proxy=store.rows.find(row=>row.cookieStoreId===`firefox-container-${data.sourceId}`)?.proxy;
      if(!usable(proxy))throw new Error('The source container no longer has a compatible proxy.');
    }else{
      proxy=editor().buildMACProxy(data.server,data.username,data.password,key(0));
      if(!proxy)throw new Error('Enter a proxy server.');
    }
  }
  // All targets and input are validated before the single storage write.
  await writeRows(store,bulkProxyRows(store.rows,targets.map(item=>item.id),proxy,key));
  return {count:targets.length,removed:!!data.remove};
}
export function prepareBulkDelete(ids){return validateBulkSelection(ids,identities());}
export async function deleteBulkContainers(plan){
  const current=validateBulkSelection(plan.map(item=>item.id),identities());
  if(current.some((item,index)=>item.name!==plan[index].name))throw new Error('The selection changed. Review the container names again.');
  const {forgetContainerData}=ChromeUtils.importESModule('resource:///modules/CloakfoxIdentityActions.sys.mjs');
  const deleted=[],failed=[];
  for(const item of current){
    try{
      await forgetContainerData(item.id,{confirmed:true});
      if(!service().remove(item.id))throw new Error('Could not remove the container.');
      Services.prefs.deleteBranch(`cloakfox.container.${item.id}.`);
      Services.prefs.clearUserPref(`cloakfox.s.cloak_cfg_${item.id}`);
      deleted.push(item);
    }catch(error){failed.push({name:item.name,error:error.message});}
  }
  if(deleted.length){
    const store=await rowsAndStorage();
    const removed=new Set(deleted.map(item=>`firefox-container-${item.id}`));
    await writeRows(store,store.rows.filter(row=>!removed.has(row.cookieStoreId)));
  }
  return {deleted,failed};
}
