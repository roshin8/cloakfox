/* MPL-2.0. Privileged settings UI; never runs in website scope. */
const {getPrivacyPolicy,setPrivacyPolicy}=ChromeUtils.importESModule('resource:///modules/CloakfoxPrivacyPolicy.sys.mjs');
const mount=document.getElementById('cfx-privacy-settings');
function node(tag,text,id,parent=mount) {
 const element=document.createElement(tag);element.textContent=text;if(id)element.id=`cfx-privacy-${id}`;parent.append(element);return element;
}
function select(label,id,options) {
 const parent=node('label',label+' '),element=node('select','',id,parent);
 for(const [value,text] of options)node('option',text,null,element).value=value;
 return element;
}
node('h2','Privacy policies');
node('p','Standard keeps the existing protections. Strict also disables media-device enumeration and clipboard access. Compatibility disables geometry noise; canvas and audio protection stay on.');
select('Preset','preset',[['standard','Standard'],['strict','Strict'],['compatibility','Compatibility']]);
node('button','Save preset','save');
node('h3','Temporary site exception');
node('p','Applies to the top-level site and its subdomains, including embedded frames and workers. Canvas includes WebGL pixel readback. Exceptions expose the selected signal’s original output.');
node('input','','site',node('label','Site ')).placeholder='https://example.com';
select('Signal','vector',[['geometry','Geometry and text metrics'],['canvas','Canvas and WebGL readback'],['audio','Audio noise']]);
select('Duration','duration',[['3600000','1 hour'],['86400000','1 day'],['604800000','7 days']]);
node('button','Add exception','add');node('button','Remove all exceptions','reset');
node('ul','','exceptions');node('p','','status').setAttribute('role','status');
const el=id=>document.getElementById(`cfx-privacy-${id}`), selector=document.getElementById('cfx-container-select');
const current=()=>Number(selector.value);
function load(){
 try {
 const policy=getPrivacyPolicy(current());el('preset').value=policy.preset;el('exceptions').replaceChildren();
 if (!policy.exceptions.length) { const empty=document.createElement('li');empty.className='empty-state';empty.textContent='No site exceptions. This container uses its selected protection preset on every site.';el('exceptions').append(empty); }
 for(const record of policy.exceptions){
  const row=document.createElement('li');row.textContent=`${record.site}: ${record.vectors.join(', ')} — ${record.expiresAt>Date.now()?'expires':'expired'} ${new Date(record.expiresAt).toLocaleString()} `;
  const button=document.createElement('button');button.textContent='Remove';button.addEventListener('click',()=>save(p=>({...p,exceptions:p.exceptions.filter(e=>e.site!==record.site)})));row.append(button);el('exceptions').append(row);
 }
 }catch(error){el('status').textContent=error.message;}
}
function save(edit){try{setPrivacyPolicy(current(),edit(getPrivacyPolicy(current())));load();el('status').textContent='Saved without changing identity seeds. Reload open pages and restart workers to apply changes and clear cached results. Expiry is checked on each extraction.';}catch(error){el('status').textContent=error.message;}}
el('save').addEventListener('click',()=>save(p=>({...p,preset:el('preset').value})));
el('add').addEventListener('click',()=>save(p=>{
 const site=el('site').value.trim(),vector=el('vector').value,existing=p.exceptions.find(e=>e.site===site);
 return {...p,exceptions:[...p.exceptions.filter(e=>e.site!==site),{site,vectors:[...new Set([...(existing?.vectors||[]),vector])],expiresAt:Date.now()+Number(el('duration').value)}]};
}));
el('reset').addEventListener('click',()=>save(p=>({...p,exceptions:[]})));
selector.addEventListener('change',load);load();
