/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
(() => {
  const manager = ChromeUtils.importESModule('resource:///modules/CloakfoxProxyManager.sys.mjs');
  const root = document.getElementById('cfx-proxy-manager');
  const containers = document.getElementById('cfx-container-select');
  if (!root || !containers) return;
  const element = (tag,text) => {const node=document.createElement(tag);if(text)node.textContent=text;return node;};
  root.append(element('h3','Saved proxies'));
  root.append(element('p','Credentials stay in Firefox Password Manager. HTTP/HTTPS use Basic authentication; SOCKS5 uses username/password. Rejected credentials fail closed. Reload pages after changing routes.'));
  const row = element('div');row.className='form-row';root.append(row);
  function field(labelText,tag='input',type='text') {
    const label=element('label',labelText),control=element(tag);
    if(tag==='input')control.type=type;
    label.append(control);row.append(label);return control;
  }
  const saved=field('Saved proxy','select'),name=field('Name'),url=field('Proxy address');
  url.placeholder='socks5://proxy.example:1080';
  const username=field('Username'),password=field('Password','input','password');
  name.placeholder='For example, Work connection';
  username.placeholder='Optional username';
  username.autocomplete='off';password.autocomplete='new-password';
  const clear=field('Remove saved credentials','input','checkbox');
  const actions=element('div');actions.className='button-row';root.append(actions);
  function button(label,handler) {const b=element('button',label);b.type='button';b.addEventListener('click',handler);actions.append(b);return b;}
  const status=element('p');status.setAttribute('role','status');root.append(status);
  const checkLabel=element('label','Test endpoint (sends an HTTPS request through the selected container proxy)');
  const endpoint=element('input');endpoint.type='url';endpoint.placeholder='https://your-chosen-provider.example/';checkLabel.append(endpoint);root.append(checkLabel);
  const checkStatus=element('p');checkStatus.setAttribute('role','status');root.append(checkStatus);
  let busy=false;
  function refresh(preferred) {
    const selected=preferred ?? manager.getProxyReference(Number(containers.value)) ?? '';
    saved.replaceChildren();
    const empty=element('option','New proxy');empty.value='';saved.append(empty);
    for(const p of manager.listProxies()) {const option=element('option',p.name);option.value=p.id;saved.append(option);}
    saved.value=selected;loadEntry();showCheck();
  }
  function loadEntry() {
    const entry=manager.listProxies().find(p=>p.id===saved.value);
    name.value=entry?.name || '';url.value=entry?.url || '';
    username.value='';password.value='';clear.checked=false;
    password.placeholder=entry?.hasCredentials ? 'Saved; leave both fields blank to keep' : 'Optional password';
  }
  function showCheck() {
    const result=manager.getProxyCheck(Number(containers.value));
    checkStatus.textContent=result ? `${result.ok?'Connected':'Failed'} — ${result.message}. Last checked ${result.checkedAt}.` : 'Not checked for this route.';
  }
  async function act(operation) {
    if(busy)return;busy=true;
    for(const control of root.querySelectorAll('button,input,select'))control.disabled=true;
    try {await operation();} catch(error) {status.textContent=error.message;}
    finally {username.value='';password.value='';busy=false;for(const control of root.querySelectorAll('button,input,select'))control.disabled=false;}
  }
  button('Save proxy',()=>act(async()=>{
    const options={id:saved.value || undefined,name:name.value,url:url.value,clearCredentials:clear.checked};
    if(username.value || password.value)Object.assign(options,{username:username.value,password:password.value});
    const result=await manager.saveProxy(options);refresh(result.id);
    status.textContent='Saved. Credentials are excluded from identity exports.';
    document.dispatchEvent(new Event('cfx-network-changed'));
  }));
  button('Use for this container',()=>act(async()=>{
    manager.bindProxy(Number(containers.value),saved.value);showCheck();
    status.textContent='Required proxy route applied to this container. Reload open pages.';
    document.dispatchEvent(new Event('cfx-network-changed'));
  }));
  button('Delete proxy',()=>act(async()=>{
    await manager.removeProxy(saved.value);refresh('');
    status.textContent='Deleted. Containers using this proxy are now blocked.';
    document.dispatchEvent(new Event('cfx-network-changed'));
  }));
  button('Test container route',()=>act(async()=>{
    const ucid=Number(containers.value);checkStatus.textContent='Checking selected endpoint…';
    const result=await manager.testContainerProxy(ucid,endpoint.value);
    if(Number(containers.value)===ucid)checkStatus.textContent=`${result.ok?'Connected':'Failed'} — ${result.message}. Last checked ${result.checkedAt}.`;
  }));
  saved.addEventListener('change',loadEntry);
  containers.addEventListener('change',()=>{status.textContent='';refresh();});
  document.addEventListener('cfx-network-changed',showCheck);
  try {refresh();}catch(error){status.textContent=error.message;}
})();
