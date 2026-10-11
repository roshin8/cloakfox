(() => {
/* MPL-2.0. Native browser-wide resolver controls. */
const {getDNSPolicy,setDNSPolicy}=ChromeUtils.importESModule('resource:///modules/CloakfoxDNS.sys.mjs');
const host=document.getElementById('cfx-dns-settings');
function node(tag,text,id,parent=host){const e=document.createElement(tag);e.textContent=text;if(id)e.id=id;parent.append(e);return e;}
node('h2','DNS privacy');node('p','Browser-wide resolver settings. Required proxies resolve destination names through the proxy. This controls other browser DNS lookups. Encrypted-only mode blocks native DNS, including local-name exceptions; numeric addresses still work.');
const mode=node('select','','cfx-dns-mode',node('label','Resolver policy '));
for(const [value,label] of [['firefox','Firefox defaults'],['system','System DNS'],['fallback','Encrypted, allow system fallback'],['only','Encrypted only — no native DNS fallback']])node('option',label,null,mode).value=value;
const resolver=node('input','','cfx-dns-resolver',node('label','HTTPS DNS endpoint '));resolver.placeholder='https://resolver.example/dns-query';
const bootstrap=node('input','','cfx-dns-bootstrap',node('label','Resolver bootstrap IP '));bootstrap.placeholder='Numeric IPv4 or IPv6 address';
const save=node('button','Save DNS policy','cfx-dns-save'),status=node('p','','cfx-dns-status');status.setAttribute('role','status');
function fields(){const enabled=['only','fallback'].includes(mode.value);resolver.disabled=!enabled;bootstrap.disabled=!enabled;}
function load(){const p=getDNSPolicy();mode.value=p.mode;resolver.value=p.resolver;bootstrap.value=p.bootstrap;fields();}
mode.addEventListener('change',fields);save.addEventListener('click',()=>{try{setDNSPolicy({mode:mode.value,resolver:resolver.value,bootstrap:bootstrap.value});load();status.textContent='Saved. DNS caches cleared. Applies to new lookups; existing connections may continue. The resolver learns the DNS names it resolves.';}catch(error){status.textContent=error.message;}});load();

})();
