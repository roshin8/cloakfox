/* MPL-2.0. Selection UI in the signed MAC popup; no website code. */
export function initBulkContainerUI(actor) {
  const doc=actor.document, panel=doc.getElementById('container-picker-panel');
  const list=doc.getElementById('picker-identities-list'), newContainer=doc.getElementById('new-container-div');
  if(!panel || !list || !newContainer || doc.getElementById('cfx-bulk-tools'))return;
  let selecting=false,busy=false,review=null,containers=[],anchor=null,anchorSelected=true;
  const selected=new Set();
  const node=(tag,text)=>{const el=doc.createElement(tag);if(text)el.textContent=text;return el;};
  const style=node('style');
  style.textContent=`
    #cfx-bulk-tools {margin:8px 16px;display:grid;gap:10px;flex:none;text-align:start;}
    #cfx-bulk-tools button {min-height:32px;border:0;border-radius:4px;padding:6px 10px;font:inherit;cursor:pointer;background:var(--button-bg-color-secondary);color:var(--text-color-primary);}
    #cfx-bulk-tools button:hover {background:var(--button-bg-hover-color-secondary);}
    #cfx-bulk-tools button:focus-visible {outline:2px solid var(--link-color);outline-offset:2px;}
    #cfx-bulk-tools button:disabled {opacity:.5;cursor:default;}
    #cfx-bulk-tools .cfx-primary {background:var(--button-bg-color-primary);color:var(--button-text-color-primary);}
    #cfx-bulk-tools .cfx-danger {color:var(--button-destructive-text-color);background:var(--button-destructive-bg-color);}
    .cfx-bulk-row {display:flex;gap:8px;align-items:center;flex-wrap:wrap;}
    .cfx-bulk-actions {display:grid;grid-template-columns:1fr 1fr;gap:8px;}
    #cfx-bulk-tools input:not([type=checkbox]),#cfx-bulk-tools select {box-sizing:border-box;width:100%;height:36px;min-height:36px;padding:8px;border:1px solid var(--input-border-color);border-radius:4px;background:var(--input-bg-color);color:var(--text-color-primary);font:inherit;}
    #cfx-bulk-tools label {display:grid;gap:5px;}
    #cfx-bulk-tools p {margin:0;font-size:12px;line-height:1.45;}
    #cfx-bulk-tools [data-fields] {display:grid;gap:10px;}
    #cfx-bulk-delete-names {max-height:120px;overflow:auto;white-space:pre-line;font-weight:600;}
    html[data-cfx-bulk-open],html[data-cfx-bulk-open] body {block-size:600px;min-block-size:600px;max-block-size:600px;}
    html[data-cfx-bulk-open] #container-picker-panel {block-size:600px;max-block-size:600px;min-block-size:0;}
    html[data-cfx-bulk-open] #container-picker-panel>.scrollable {min-block-size:80px;}
    html[data-cfx-bulk-open] #new-container-div {display:none;}
    html[data-cfx-bulk-open] #picker-identities-list tr td {display:flex;align-items:center;gap:8px;width:100%;}
    html[data-cfx-bulk-open] #picker-identities-list .move-button {display:none;}
    html[data-cfx-bulk-open] #picker-identities-list tr {user-select:none;}
    .cfx-bulk-check {inline-size:16px;block-size:16px;flex:none;margin:0;pointer-events:none;}
  `;
  doc.head.append(style);
  const tools=node('section');tools.id='cfx-bulk-tools';tools.hidden=true;
  panel.insertBefore(tools,newContainer);
  const controls=node('div');controls.className='cfx-bulk-row';tools.append(controls);
  const button=(text,parent,handler,id)=>{const b=node('button',text);b.type='button';if(id)b.id=id;b.addEventListener('click',handler);parent.append(b);return b;};
  const select=button('Select containers',controls,()=>setSelecting(!selecting),'cfx-bulk-select');
  const count=node('span');count.title='Shift-click containers to select a range.';count.setAttribute('aria-live','polite');controls.append(count);
  const all=button('Select all',controls,()=>{anchor=null;rows().forEach(row=>selected.add(row.dataset.cookieStoreId));sync();},'cfx-bulk-all');
  const clear=button('Clear',controls,()=>{anchor=null;selected.clear();sync();},'cfx-bulk-clear');
  const actions=node('div');actions.className='cfx-bulk-actions';tools.append(actions);
  const proxyForm=node('div');proxyForm.hidden=true;proxyForm.setAttribute('data-fields','');tools.append(proxyForm);
  const reviewForm=node('div');reviewForm.hidden=true;reviewForm.setAttribute('data-fields','');tools.append(reviewForm);
  const status=node('p');status.setAttribute('role','status');tools.append(status);
  const ids=()=>[...selected].map(value=>Number(value.replace('firefox-container-','')));
  const rows=()=>[...list.querySelectorAll('tr[data-cookie-store-id]')];
  const visible=()=>!panel.classList.contains('hide') && !!newContainer.querySelector('#new-container');
  async function run(task){
    if(busy)return;
    busy=true;sync();status.textContent='Working…';
    try{await task();}catch(error){status.textContent=error.message;}finally{busy=false;sync();}
  }
  button('Apply proxy…',actions,()=>void run(async()=>{
    containers=await actor.sendQuery('BulkList',{});
    source.replaceChildren(new doc.defaultView.Option('Choose a proxy…',''));
    for(const item of containers.filter(item=>item.proxy))source.add(new doc.defaultView.Option(`${item.name} · ${item.server}`,String(item.id)));
    source.add(new doc.defaultView.Option('Enter a new proxy','custom'));
    proxyForm.hidden=false;reviewForm.hidden=true;status.textContent='The same proxy will be assigned to every selected container.';
  }),'cfx-bulk-apply-open');
  button('Remove proxy',actions,()=>void run(async()=>{
    const result=await actor.sendQuery('BulkProxy',{ids:ids(),remove:true});
    status.textContent=`Removed proxy assignments from ${result.count} containers.`;
  }),'cfx-bulk-remove');
  const deleteOpen=button('Delete selected…',actions,()=>void run(async()=>{
    review=await actor.sendQuery('BulkDeleteReview',{ids:ids()});
    names.textContent=review.containers.map(item=>item.name).join('\n');
    reviewForm.hidden=false;proxyForm.hidden=true;status.textContent='Review the names before deleting.';
  }),'cfx-bulk-delete-open');deleteOpen.className='cfx-danger';
  const sourceLabel=node('label','Proxy to apply');const source=node('select');source.id='cfx-bulk-source';sourceLabel.append(source);proxyForm.append(sourceLabel);
  const custom=node('div');custom.setAttribute('data-fields','');custom.hidden=true;proxyForm.append(custom);
  function field(title,type,id){const label=node('label',title),input=node('input');input.type=type;input.id=id;input.autocomplete='off';label.append(input);custom.append(label);return input;}
  const server=field('Proxy server','text','cfx-bulk-server');server.placeholder='http://host:port';
  const username=field('Username (optional)','text','cfx-bulk-username');
  const password=field('Password','password','cfx-bulk-password');
  source.addEventListener('change',()=>{custom.hidden=source.value!=='custom';});
  const proxyButtons=node('div');proxyButtons.className='cfx-bulk-row';proxyForm.append(proxyButtons);
  const apply=button('Apply to selected',proxyButtons,()=>void run(async()=>{
    if(!source.value)throw new Error('Choose an existing proxy or enter a new proxy.');
    const data={ids:ids()};
    if(source.value==='custom')Object.assign(data,{server:server.value,username:username.value,password:password.value});
    else data.sourceId=Number(source.value);
    const result=await actor.sendQuery('BulkProxy',data);
    password.value='';proxyForm.hidden=true;status.textContent=`Proxy applied to ${result.count} containers. Reload their website tabs to use it.`;
  }),'cfx-bulk-apply');apply.className='cfx-primary';
  button('Cancel',proxyButtons,()=>{proxyForm.hidden=true;password.value='';});
  reviewForm.append(node('strong','Delete these containers?'));
  const names=node('p');names.id='cfx-bulk-delete-names';reviewForm.append(names);
  reviewForm.append(node('p','This permanently deletes these containers and their cookies and site data, and closes their tabs. This cannot be undone.'));
  const deleteButtons=node('div');deleteButtons.className='cfx-bulk-row';reviewForm.append(deleteButtons);
  const confirm=button('Delete permanently',deleteButtons,()=>void run(async()=>{
    if(!review)throw new Error('Review the selection again.');
    const result=await actor.sendQuery('BulkDeleteConfirm',{token:review.token});review=null;
    const removed=new Set(result.deleted.map(item=>`firefox-container-${item.id}`));
    rows().filter(row=>removed.has(row.dataset.cookieStoreId)).forEach(row=>row.remove());
    removed.forEach(id=>selected.delete(id));reviewForm.hidden=true;
    status.textContent=`Deleted ${result.deleted.length} containers.${result.failed.length?' Could not delete: '+result.failed.map(item=>`${item.name}: ${item.error}`).join('; '):''}`;
  }),'cfx-bulk-delete-confirm');confirm.className='cfx-danger';
  button('Cancel',deleteButtons,()=>{review=null;reviewForm.hidden=true;});
  function setSelecting(value){
    selecting=value;selected.clear();anchor=null;review=null;proxyForm.hidden=reviewForm.hidden=true;password.value='';status.textContent='';
    doc.documentElement.toggleAttribute('data-cfx-bulk-open',value);sync();
  }
  function sync(){
    tools.hidden=!visible();
    select.textContent=selecting?'Done':'Select containers';count.textContent=selecting?`${selected.size} selected`:'';
    all.hidden=clear.hidden=actions.hidden=!selecting;
    for(const b of tools.querySelectorAll('button'))b.disabled=busy;
    for(const b of actions.querySelectorAll('button'))b.disabled=busy||!selected.size;
    for(const row of rows()){
      let check=row.querySelector('.cfx-bulk-check');
      if(selecting && !check){check=node('input');check.type='checkbox';check.className='cfx-bulk-check';check.tabIndex=-1;check.setAttribute('aria-hidden','true');row.querySelector('td').prepend(check);}
      if(check){check.hidden=!selecting;check.checked=selected.has(row.dataset.cookieStoreId);}
      row.draggable=!selecting;
      if(selecting){row.setAttribute('role','checkbox');row.setAttribute('aria-checked',String(selected.has(row.dataset.cookieStoreId)));}
      else{row.removeAttribute('role');row.removeAttribute('aria-checked');}
    }
  }
  function toggle(event){
    const row=event.target.closest?.('#picker-identities-list tr[data-cookie-store-id]');
    if(!selecting||!row||!visible())return;
    if(event.type==='keydown'&&!['Enter',' '].includes(event.key))return;
    event.preventDefault();event.stopImmediatePropagation();if(busy)return;
    const id=row.dataset.cookieStoreId;
    const entries=rows(),start=entries.findIndex(item=>item.dataset.cookieStoreId===anchor),end=entries.indexOf(row);
    if(event.shiftKey && start>=0){
      for(const item of entries.slice(Math.min(start,end),Math.max(start,end)+1)){
        const value=item.dataset.cookieStoreId;
        anchorSelected?selected.add(value):selected.delete(value);
      }
    }else{
      selected.has(id)?selected.delete(id):selected.add(id);
      anchor=id;anchorSelected=selected.has(id);
    }
    review=null;reviewForm.hidden=true;sync();
  }
  doc.addEventListener('click',toggle,true);doc.addEventListener('keydown',toggle,true);
  const observePanel=new doc.defaultView.MutationObserver(()=>{if(!visible()&&selecting)setSelecting(false);else sync();});
  observePanel.observe(panel,{attributes:true,attributeFilter:['class']});
  const observeList=new doc.defaultView.MutationObserver(()=>sync());observeList.observe(list,{childList:true,subtree:true});
  // The New Container row identifies manage mode independently of localization.
  const observeMode=new doc.defaultView.MutationObserver(()=>sync());observeMode.observe(newContainer,{childList:true,subtree:true});
  actor.bulkCleanup=()=>{observePanel.disconnect();observeList.disconnect();observeMode.disconnect();};
  sync();
}
