/* MPL-2.0. Config and runtime evidence are labeled separately. */
const {inspectConsistency,measureContainer,repairConsistency,undoConsistencyRepair}=ChromeUtils.importESModule('resource:///modules/CloakfoxInspector.sys.mjs');
const mount=document.getElementById('cfx-consistency-inspector');
function node(tag,text,id) {
 const element=document.createElement(tag);element.textContent=text;if(id)element.id=id;mount.append(element);return element;
}
node('h2','Fingerprint consistency inspector');
node('p','Checks an open website tab in this container, in a normal browsing window, including a short-lived worker. The site may block worker measurement. Findings do not certify anonymity.');
node('button','Check configuration and open tab','cfx-inspect-run');
node('button','Undo last repair','cfx-inspect-undo').disabled=true;
node('p','','cfx-inspect-status').setAttribute('role','status');
node('ul','','cfx-inspect-findings');
const selector=document.getElementById('cfx-container-select'),run=document.getElementById('cfx-inspect-run'),undoButton=document.getElementById('cfx-inspect-undo'),status=document.getElementById('cfx-inspect-status'),list=document.getElementById('cfx-inspect-findings');
let undo=null,generation=0;
async function check(){
 const ucid=Number(selector.value),seq=++generation;run.disabled=true;list.replaceChildren();status.textContent='Measuring…';
 try{
  const raw=Services.prefs.getStringPref(`cloakfox.s.cloak_cfg_${ucid}`,'{}'),cfg=JSON.parse(raw);
  const measured=await measureContainer(ucid);measured.expectedTimezone=Services.prefs.getStringPref(`cloakfox.container.${ucid}.timezone`,'');
  if(seq!==generation)return;
  status.textContent=measured.site?`Measured ${measured.site}. Only non-secret fingerprint fields are compared.`:'Configuration checked; no website tab available.';
  const issues=inspectConsistency(cfg,measured);
  for(const issue of issues){
   const row=document.createElement('li');row.textContent=`${issue.level} · ${issue.source}: ${issue.message} `;
   if(issue.repair){const button=document.createElement('button');button.textContent='Apply suggested repair';button.addEventListener('click',()=>{
    try{undo=repairConsistency(ucid,issue,raw);undoButton.disabled=false;check();}catch(error){status.textContent=error.message;}
   });row.append(button);}list.append(row);
  }
  if(!issues.some(i=>i.level==='contradiction'))status.textContent+=' No contradictions found in the checked fields.';
 }catch(error){status.textContent=error.message;}finally{if(seq===generation)run.disabled=false;}
}
run.addEventListener('click',check);
undoButton.addEventListener('click',()=>{try{undoConsistencyRepair(undo);undo=null;undoButton.disabled=true;check();}catch(error){status.textContent=error.message;}});
selector.addEventListener('change',()=>{generation++;run.disabled=false;undo=null;undoButton.disabled=true;status.textContent='';list.replaceChildren();});
