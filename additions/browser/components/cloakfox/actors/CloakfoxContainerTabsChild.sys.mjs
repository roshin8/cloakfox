/* MPL-2.0. Checkbox selection on the existing MAC container tab list. */
export function initContainerTabSelection(actor) {
  const doc=actor.document,panel=doc.getElementById('container-info-panel'),table=doc.getElementById('container-info-table');
  if(!panel||!table||doc.getElementById('cfx-tab-selection'))return;
  let selecting=false,busy=false,cookieStoreId=null,identityName='';
  const selected=new Set();
  const node=(tag,text)=>{const el=doc.createElement(tag);if(text)el.textContent=text;return el;};
  const style=node('style');style.textContent=`
    #cfx-tab-selection {display:grid;gap:8px;margin:8px 16px;flex:none;}
    #cfx-tab-selection button {min-height:32px;padding:6px 10px;border:0;border-radius:4px;font:inherit;background:var(--button-bg-color-secondary);color:var(--text-color-primary);cursor:pointer;}
    #cfx-tab-selection button:hover {background:var(--button-bg-hover-color-secondary);}
    #cfx-tab-selection button:focus-visible {outline:2px solid var(--link-color);outline-offset:2px;}
    #cfx-tab-selection button:disabled {opacity:.5;cursor:default;}
    #cfx-tab-close {background:var(--button-bg-color-primary)!important;color:var(--button-text-color-primary)!important;}
    #cfx-tab-selection label {display:flex;align-items:center;gap:8px;}
    #cfx-tab-selection p {font-size:12px;line-height:1.4;margin:0;}
    #cfx-tab-selection .cfx-tab-controls {display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
    html[data-cfx-tab-selection],html[data-cfx-tab-selection] body {block-size:600px;min-block-size:600px;max-block-size:600px;}
    html[data-cfx-tab-selection] #container-info-panel {block-size:600px;max-block-size:600px;min-block-size:0;}
    html[data-cfx-tab-selection] #container-info-panel>.scrollable {min-block-size:0;}
    html[data-cfx-tab-selection] #container-info-table td {display:flex;align-items:center;gap:8px;width:100%;}
    html[data-cfx-tab-selection] #container-info-table .trash-button {display:none;}
    .cfx-tab-check {inline-size:16px;block-size:16px;margin:0;flex:none;pointer-events:none;}
  `;doc.head.append(style);
  const tools=node('section');tools.id='cfx-tab-selection';table.parentElement.before(tools);
  const row=node('div');row.className='cfx-tab-controls';tools.append(row);
  const toggle=node('button','Select tabs');toggle.type='button';toggle.id='cfx-tab-select';row.append(toggle);
  const allLabel=node('label'),all=node('input');all.type='checkbox';all.id='cfx-tab-all';allLabel.append(all,doc.createTextNode('Select all'));row.append(allLabel);
  const count=node('span');count.setAttribute('aria-live','polite');row.append(count);
  const close=node('button','Close selected tabs');close.type='button';close.id='cfx-tab-close';tools.append(close);
  const status=node('p');status.id='cfx-tab-status';status.setAttribute('role','status');tools.append(status);
  const rows=()=>[...table.querySelectorAll('tr')].map(row=>({row,id:Number(row.querySelector('.trash-button')?.id)})).filter(item=>Number.isInteger(item.id)&&item.id>0);
  const visible=()=>!panel.classList.contains('hide');
  const name=()=>doc.getElementById('container-info-title')?.textContent.trim()||'';
  function sync(){
    const entries=rows(),live=new Set(entries.map(item=>item.id));
    for(const id of selected)if(!live.has(id))selected.delete(id);
    toggle.textContent=selecting?'Done':'Select tabs';toggle.disabled=busy;
    allLabel.hidden=count.hidden=close.hidden=!selecting;
    all.checked=!!entries.length&&selected.size===entries.length;all.indeterminate=selected.size>0&&selected.size<entries.length;all.disabled=busy||!entries.length;
    count.textContent=`${selected.size} selected`;close.disabled=busy||!selected.size;
    for(const {row,id} of entries){
      let check=row.querySelector('.cfx-tab-check');
      if(selecting&&!check){check=node('input');check.type='checkbox';check.className='cfx-tab-check';check.tabIndex=-1;check.setAttribute('aria-hidden','true');row.querySelector('td').prepend(check);}
      if(check){check.hidden=!selecting;check.checked=selected.has(id);}
      if(selecting){row.setAttribute('role','checkbox');row.setAttribute('aria-checked',String(selected.has(id)));}
      else{row.removeAttribute('role');row.removeAttribute('aria-checked');}
    }
  }
  function setSelecting(value){selecting=value;selected.clear();identityName=name();doc.documentElement.toggleAttribute('data-cfx-tab-selection',value);status.textContent=value?'Only tabs in this window. The container, cookies and logins are kept.':'';sync();}
  toggle.addEventListener('click',()=>setSelecting(!selecting));
  all.addEventListener('change',()=>{selected.clear();if(all.checked)rows().forEach(item=>selected.add(item.id));sync();});
  function intercept(event){
    if(event.type==='click'||['Enter',' '].includes(event.key)){
      const identityRow=event.target.closest?.('#identities-list tr[data-cookie-store-id]');
      if(identityRow)cookieStoreId=identityRow.dataset.cookieStoreId;
    }
    const row=event.target.closest?.('#container-info-table tr');
    if(!selecting||!visible()||!row)return;
    if(event.type==='keydown'&&!['Enter',' '].includes(event.key))return;
    event.preventDefault();event.stopImmediatePropagation();if(busy)return;
    const id=Number(row.querySelector('.trash-button')?.id);if(!Number.isInteger(id)||id<=0)return;
    selected.has(id)?selected.delete(id):selected.add(id);sync();
  }
  doc.addEventListener('click',intercept,true);doc.addEventListener('keydown',intercept,true);
  close.addEventListener('click',async()=>{
    if(busy||!selected.size)return;
    busy=true;sync();status.textContent='Closing selected tabs…';
    try{
      const result=await actor.sendQuery('CloseSelectedTabs',{cookieStoreId,name:identityName,tabIds:[...selected]});
      if(result.closed===result.requested){rows().filter(item=>selected.has(item.id)).forEach(item=>item.row.remove());selected.clear();}
      status.textContent=`Closed ${result.closed} of ${result.requested} selected tabs. Cookies and logins were kept.${result.closed<result.requested?' A tab may be waiting for confirmation; reopen the list before trying again.':''}`;
    }catch(error){status.textContent=error.message;}finally{busy=false;sync();}
  });
  const panelObserver=new doc.defaultView.MutationObserver(()=>{if(!visible()&&selecting)setSelecting(false);});panelObserver.observe(panel,{attributes:true,attributeFilter:['class']});
  const listObserver=new doc.defaultView.MutationObserver(()=>{if(selecting&&identityName!==name())setSelecting(false);else sync();});listObserver.observe(table,{childList:true,subtree:true});
  actor.tabSelectionCleanup=()=>{panelObserver.disconnect();listObserver.disconnect();};sync();
}
