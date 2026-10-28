/* MPL-2.0. Selection UI in the signed MAC popup; no website code. */
export function initBulkContainerUI(actor) {
  const doc=actor.document, panel=doc.getElementById('container-picker-panel');
  const list=doc.getElementById('picker-identities-list'), newContainer=doc.getElementById('new-container-div');
  if(!panel || !list || !newContainer || doc.getElementById('cfx-bulk-tools'))return;
  let selecting=false,busy=false,review=null,containers=[];
  const selected=new Set();
  const node=(tag,text)=>{const el=doc.createElement(tag);if(text)el.textContent=text;return el;};
  const style=node('style');
  style.textContent=`
    :is(#cfx-bulk-tools,#cfx-bulk-footer) {box-sizing:border-box;inline-size:calc(100% - 24px);margin:12px;padding:12px;display:grid;gap:12px;flex:none;text-align:start;border:1px solid color-mix(in srgb,var(--text-color-primary) 16%,transparent);border-radius:10px;background:color-mix(in srgb,var(--bgColor) 94%,var(--text-color-primary));max-block-size:360px;overflow:auto;}
    :is(#cfx-bulk-tools,#cfx-bulk-footer) button {min-height:34px;border:1px solid color-mix(in srgb,var(--text-color-primary) 12%,transparent);border-radius:6px;padding:7px 10px;font:inherit;cursor:pointer;background:var(--button-bg-color-secondary);color:var(--text-color-primary);}
    :is(#cfx-bulk-tools,#cfx-bulk-footer) button:hover {background:var(--button-bg-hover-color-secondary);}
    :is(#cfx-bulk-tools,#cfx-bulk-footer) button:focus-visible {outline:2px solid var(--link-color);outline-offset:2px;}
    :is(#cfx-bulk-tools,#cfx-bulk-footer) button:disabled {opacity:.5;cursor:default;}
    :is(#cfx-bulk-tools,#cfx-bulk-footer) .cfx-primary {background:var(--button-bg-color-primary);color:var(--button-text-color-primary);}
    :is(#cfx-bulk-tools,#cfx-bulk-footer) .cfx-danger {color:var(--button-destructive-text-color);background:var(--button-destructive-bg-color);}
    html:not([data-cfx-bulk-open]) :is(#cfx-bulk-tools,#cfx-bulk-footer) {padding:0;margin:8px 12px;gap:0;border:0;background:transparent;overflow:visible;}
    html:not([data-cfx-bulk-open]) #cfx-bulk-select {inline-size:100%;margin:0;padding:10px 12px;min-block-size:38px;text-align:start;border:1px solid color-mix(in srgb,var(--text-color-primary) 16%,transparent);background:transparent;border-radius:6px;}
    html:not([data-cfx-bulk-open]) #cfx-bulk-select:hover {background:var(--menu-bg-hover-color);}
    html:not([data-cfx-bulk-open]) #cfx-bulk-footer {inline-size:calc(100% - 24px);}
    #cfx-bulk-count {font-size:14px;font-weight:600;}
    :is(#cfx-bulk-tools,#cfx-bulk-footer)>.cfx-bulk-row {justify-content:space-between;flex-wrap:nowrap;}
    #cfx-bulk-select {margin-inline-start:auto;}
    #cfx-bulk-select,#cfx-bulk-all,#cfx-bulk-clear {background:transparent;border-color:transparent;min-height:28px;padding:4px 6px;}
    .cfx-bulk-selection {display:flex;gap:12px;align-items:center;border-block-end:1px solid color-mix(in srgb,var(--text-color-primary) 12%,transparent);padding-block-end:8px;}
    :is(#cfx-bulk-tools,#cfx-bulk-footer) #cfx-bulk-delete-open {grid-column:1/-1;background:transparent;color:light-dark(#a62136,#ffb3bf);border-color:color-mix(in srgb,currentColor 35%,transparent);margin-block-start:4px;}
    :is(#cfx-bulk-tools,#cfx-bulk-footer) p:empty {display:none;}
    html[data-cfx-bulk-open] #picker-identities-list tr {min-block-size:38px;box-sizing:border-box;}
    html[data-cfx-bulk-open] #picker-identities-list tr[aria-checked=true] {background:var(--menu-bg-hover-color);}
    .cfx-bulk-row {display:flex;gap:8px;align-items:center;flex-wrap:wrap;}
    .cfx-bulk-actions {display:grid;grid-template-columns:1fr 1fr;gap:8px;}
    :is(#cfx-bulk-tools,#cfx-bulk-footer) input:not([type=checkbox]),:is(#cfx-bulk-tools,#cfx-bulk-footer) select {box-sizing:border-box;width:100%;height:36px;min-height:36px;padding:8px;border:1px solid var(--input-border-color);border-radius:4px;background:var(--input-bg-color);color:var(--text-color-primary);font:inherit;}
    :is(#cfx-bulk-tools,#cfx-bulk-footer) label {display:grid;gap:5px;}
    :is(#cfx-bulk-tools,#cfx-bulk-footer) p {margin:0;font-size:12px;line-height:1.45;}
    :is(#cfx-bulk-tools,#cfx-bulk-footer) [data-fields] {display:grid;gap:10px;}
    :is(#cfx-bulk-tools,#cfx-bulk-footer) [data-delete-review] {gap:14px;}
    :is(#cfx-bulk-tools,#cfx-bulk-footer) [data-delete-review]>strong {font-size:15px;line-height:1.4;}
    #cfx-bulk-delete-names {max-height:120px;overflow:auto;white-space:pre-line;font-weight:500;line-height:1.8!important;padding:10px 12px;border:1px solid color-mix(in srgb,var(--text-color-primary) 15%,transparent);border-radius:6px;background:var(--bgColor);}
    :is(#cfx-bulk-tools,#cfx-bulk-footer) [data-delete-review]>.cfx-bulk-row {display:grid;grid-template-columns:1fr 1fr;gap:8px;}
    #cfx-bulk-delete-confirm {grid-column:2;grid-row:1;}
    :is(#cfx-bulk-tools,#cfx-bulk-footer) [data-delete-review]>.cfx-bulk-row>button:last-child {grid-column:1;grid-row:1;}
    html[data-cfx-bulk-review] :is(#cfx-bulk-tools,#cfx-bulk-footer) {max-block-size:420px;}

    html[data-cfx-bulk-open],html[data-cfx-bulk-open] body {block-size:600px;min-block-size:600px;max-block-size:600px;}
    html[data-cfx-bulk-open] #container-picker-panel {block-size:600px;max-block-size:600px;min-block-size:0;}
    html[data-cfx-bulk-open] #container-picker-panel>.scrollable {min-block-size:140px;}
    html[data-cfx-bulk-open] #new-container-div {display:none;}
    html[data-cfx-bulk-open] #picker-identities-list tr td {display:flex;align-items:center;gap:8px;width:100%;}
    html[data-cfx-bulk-open] #picker-identities-list .move-button {display:none;}
    .cfx-bulk-check {inline-size:16px;block-size:16px;flex:none;margin:0;pointer-events:none;}
    html[data-cfx-bulk-open] #cfx-bulk-tools {inline-size:100%;margin:0;padding:12px 16px;border:0;border-block-end:1px solid color-mix(in srgb,var(--text-color-primary) 15%,transparent);border-radius:0;background:transparent;gap:6px;overflow:visible;}
    html[data-cfx-bulk-open] .cfx-bulk-selection {border:0;padding:0;}
    html[data-cfx-bulk-open] #cfx-bulk-tools :is(#cfx-bulk-select,#cfx-bulk-all,#cfx-bulk-clear) {background:transparent;border-color:transparent;padding-inline:0;}
    #cfx-bulk-footer {inline-size:100%;margin:0;padding:12px 16px;border:0;border-block-start:1px solid color-mix(in srgb,var(--text-color-primary) 15%,transparent);border-radius:0;background:var(--bgColor);max-block-size:360px;}
    #cfx-bulk-footer #cfx-bulk-delete-open {border:0;border-block-start:1px solid color-mix(in srgb,var(--text-color-primary) 12%,transparent);border-radius:0;padding-block-start:12px;margin-block-start:4px;}
    html[data-cfx-bulk-open] #container-picker-panel>.scrollable {block-size:auto;flex:1;min-block-size:140px;}
  `;
  doc.head.append(style);
  const tools=node('section');tools.id='cfx-bulk-tools';tools.hidden=true;
  panel.insertBefore(tools,newContainer);
  const controls=node('div');controls.className='cfx-bulk-row';tools.append(controls);
  const button=(text,parent,handler,id)=>{const b=node('button',text);b.type='button';if(id)b.id=id;b.addEventListener('click',handler);parent.append(b);return b;};
  const select=button('Select containers',controls,()=>setSelecting(!selecting),'cfx-bulk-select');
  const count=node('span');count.id='cfx-bulk-count';count.setAttribute('aria-live','polite');controls.append(count);
  const all=button('Select all',controls,()=>{rows().forEach(row=>selected.add(row.dataset.cookieStoreId));sync();},'cfx-bulk-all');
  const clear=button('Clear',controls,()=>{selected.clear();sync();},'cfx-bulk-clear');
  controls.prepend(count);
  const selection=node('div');selection.className='cfx-bulk-selection';selection.append(all,clear);tools.append(selection);
  const footer=node('section');footer.id='cfx-bulk-footer';footer.hidden=true;panel.append(footer);
  const actions=node('div');actions.className='cfx-bulk-actions';footer.append(actions);
  const proxyForm=node('div');proxyForm.hidden=true;proxyForm.setAttribute('data-fields','');footer.append(proxyForm);
  const reviewForm=node('div');reviewForm.hidden=true;reviewForm.setAttribute('data-fields','');reviewForm.setAttribute('data-delete-review','');footer.append(reviewForm);
  const status=node('p');status.setAttribute('role','status');footer.append(status);
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
    reviewTitle.textContent=`Delete ${review.containers.length} ${review.containers.length===1?'container':'containers'}?`;
    confirm.textContent=`Delete ${review.containers.length} ${review.containers.length===1?'container':'containers'}`;
    reviewForm.hidden=false;proxyForm.hidden=true;status.textContent='';
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
  const reviewTitle=node('strong','Delete these containers?');reviewForm.append(reviewTitle);
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
  button('Cancel',deleteButtons,()=>{review=null;reviewForm.hidden=true;sync();});
  function setSelecting(value){
    selecting=value;selected.clear();review=null;proxyForm.hidden=reviewForm.hidden=true;password.value='';status.textContent='';
    doc.documentElement.toggleAttribute('data-cfx-bulk-open',value);sync();
  }
  function sync(){
    tools.hidden=!visible()||!selecting;
    footer.hidden=!visible();
    if(selecting && select.parentElement!==controls)controls.append(select);
    else if(!selecting && select.parentElement!==footer)footer.prepend(select);
    select.textContent=selecting?'Done':'Select containers';count.textContent=selecting?`${selected.size} selected`:'';
    const reviewing=!reviewForm.hidden;
    doc.documentElement.toggleAttribute('data-cfx-bulk-review',reviewing);
    select.hidden=reviewing;
    count.hidden=!selecting;
    selection.hidden=all.hidden=clear.hidden=actions.hidden=!selecting||reviewing;
    deleteOpen.textContent=selected.size?`Delete ${selected.size} ${selected.size===1?'container':'containers'}…`:'Delete selected…';
    for(const host of [tools,footer])for(const b of host.querySelectorAll('button'))b.disabled=busy;
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
    const id=row.dataset.cookieStoreId;selected.has(id)?selected.delete(id):selected.add(id);
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
