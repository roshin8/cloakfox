(() => {
/* MPL-2.0. Narrow recovery controls for native navigation tracking protection. */
const T=ChromeUtils.importESModule('resource:///modules/CloakfoxTrackingProtection.sys.mjs');
const host=document.getElementById('cfx-tracking-settings'),container=document.getElementById('cfx-container-select');
function node(tag,text,id,parent=host){const e=document.createElement(tag);e.textContent=text;if(id)e.id=id;parent.append(e);return e;}
function checkbox(label,id){const e=node('input','',id,node('label',label+' '));e.type='checkbox';return e;}
node('h2','Tracking links and redirects');
node('p','Remove known tracking parameters during navigation and clear storage left by bounce trackers. Ordinary URL parameters are retained. These browser-wide protections use Firefox’s native implementation.');
const strip=checkbox('Clean tracking links','cfx-tracking-strip'),privateStrip=checkbox('Also clean private-window links','cfx-tracking-private');
const bounce=node('select','','cfx-tracking-bounce',node('label','Bounce trackers '));for(const [value,label] of [['1','Detect and clear tracking storage'],['3','Detect only'],['2','Standby'],['0','Disabled (restart required)']])node('option',label,null,bounce).value=value;
const save=node('button','Save tracking protection','cfx-tracking-save');
node('h3','Site recovery');node('p','A link-cleaning exception applies to that registrable domain and its subdomains across containers. A bounce exception lasts one day in the selected container and does not turn off other tracking protection.');
const input=node('input','','cfx-tracking-host',node('label','Site hostname '));input.placeholder='example.com';
const queryAdd=node('button','Keep this site’s URL parameters','cfx-tracking-query-add'),bounceAdd=node('button','Keep bounce storage for 1 day','cfx-tracking-bounce-add');
const list=node('ul','','cfx-tracking-exceptions'),status=node('p','','cfx-tracking-status');status.setAttribute('role','status');
function load(){try{const p=T.getTrackingProtection();strip.checked=p.strip;privateStrip.checked=p.stripPrivate;bounce.value=String(p.bounceMode);list.replaceChildren();
for(const domain of p.queryExceptions){const row=node('li',`Link cleanup exception: ${domain} `,null,list);node('button','Remove',null,row).addEventListener('click',()=>action(()=>T.setQueryException(domain,false)));}
for(const e of T.listBounceExceptions(Number(container.value))){const row=node('li',`Bounce storage: ${e.host}, until ${new Date(e.expiresAt).toLocaleString()} `,null,list);node('button','Remove',null,row).addEventListener('click',()=>action(()=>T.setBounceException(Number(container.value),e.host,0)));}
}catch(error){status.textContent=error.message;}}
function action(fn){try{fn();load();status.textContent='Saved. Reload affected pages to retry. Toggling fully disabled bounce protection requires a browser restart.';}catch(error){status.textContent=error.message;}}
save.addEventListener('click',()=>action(()=>T.setTrackingProtection({strip:strip.checked,stripPrivate:privateStrip.checked,bounceMode:Number(bounce.value)})));
queryAdd.addEventListener('click',()=>action(()=>T.setQueryException(input.value.trim(),true)));bounceAdd.addEventListener('click',()=>action(()=>T.setBounceException(Number(container.value),input.value.trim(),Date.now()+86400000)));container.addEventListener('change',load);load();

})();
