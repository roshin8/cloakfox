/* MPL-2.0. Native privileged UI enhancement; no changes to the signed add-on. */
export class CloakfoxContainerProxyEditorChild extends JSWindowActorChild {
  handleEvent() {
    const doc=this.document;
    if (doc.nodePrincipal.addonId!=='@testpilot-containers' ||
        new URL(doc.documentURI).pathname!=='/popup.html' || doc.getElementById('cfx-mac-auth')) return;
    ChromeUtils.importESModule('resource:///actors/CloakfoxContainerBulkChild.sys.mjs').initBulkContainerUI(this);
    const panel=doc.getElementById('advanced-proxy-settings-panel');
    const form=panel?.querySelector('.advanced-proxy-panel-content');
    const apply=doc.getElementById('submit-advanced-proxy');
    const host=doc.getElementById('edit-advanced-proxy-input');
    if(!panel || !form || !apply || !host) return;
    const layout=doc.createElement('style');
    layout.textContent=`
      html[data-cfx-proxy-open], html[data-cfx-proxy-open] body {
        block-size:600px; min-block-size:600px; max-block-size:600px;
      }
      html[data-cfx-proxy-open] #advanced-proxy-settings-panel {
        block-size:600px; min-block-size:0; max-block-size:600px;
      }
      html[data-cfx-proxy-open] .advanced-proxy-panel-content {
        flex:1; min-block-size:0; overflow-y:auto; box-sizing:border-box;
        scrollbar-width:thin;
      }
      #cfx-mac-auth .primary-input {
        block-size:36px; min-block-size:36px; border-radius:4px;
        background-color:var(--input-bg-color); color:var(--text-color-primary);
        padding:8px; font:inherit;
      }
    `;
    layout.textContent+=`
      #edit-container-panel-choose-color .usercontext-icon::before {
        fill:var(--cfx-swatch-color,var(--identity-icon-color));
      }
    `;
    layout.textContent+=`
      html:has(#edit-container-panel:not(.hide)),html:has(#edit-container-panel:not(.hide)) body {block-size:600px;min-block-size:600px;max-block-size:600px;}
      #edit-container-panel {block-size:600px;min-block-size:0;max-block-size:600px;}
      #edit-container-panel > * {flex-shrink:0;}
      #edit-container-panel .edit-form {flex:0;padding-block:8px;}
      #edit-container-panel fieldset {padding-block-end:8px;}
      #edit-container-panel .radio-container {block-size:28px;}
      #edit-container-panel .moz-vpn-controller-content {padding-block:8px;}
      #edit-container-panel .collapsible-content > .flx-row.flx-space-between {padding-block-start:6px;}
      #edit-container-panel .moz-vpn-cta {margin-block-start:8px;}
      #edit-container-panel-choose-color label[for$="-gray"] { --cfx-swatch-color:#cc8540; }
      #edit-container-panel-choose-color label[for$="-yellow"] { --cfx-swatch-color:#f2b600; }
      #edit-container-panel-choose-color label[for$="-orange"] { --cfx-swatch-color:#f98422; }
      #edit-container-panel-choose-color label[for$="-red"] { --cfx-swatch-color:#f14c70; }
      #edit-container-panel-choose-color label[for$="-pink"] { --cfx-swatch-color:#e83ab5; }
      #edit-container-panel-choose-color label[for$="-purple"] { --cfx-swatch-color:#a650e8; }
      #edit-container-panel-choose-color label[for$="-violet"] { --cfx-swatch-color:#8055ee; }
      #edit-container-panel-choose-color label[for$="-blue"] { --cfx-swatch-color:#4385f5; }
      #edit-container-panel-choose-color label[for$="-cyan"] { --cfx-swatch-color:#00a8cb; }
      #edit-container-panel-choose-color label[for$="-green"] { --cfx-swatch-color:#00b983; }
      #edit-container-panel-choose-color label[for$="-navy"] { --cfx-swatch-color:#5279c4; }
      #edit-container-panel-choose-color label[for$="-teal"] { --cfx-swatch-color:#009e98; }
      #edit-container-panel-choose-color label[for$="-olive"] { --cfx-swatch-color:#94a922; }
      #edit-container-panel-choose-color label[for$="-burgundy"] { --cfx-swatch-color:#c83f73; }
      #edit-container-panel-choose-color label[for$="-brown"] { --cfx-swatch-color:#ba7c3f; }
      #edit-container-panel-choose-color label[for$="-slate"] { --cfx-swatch-color:#578fab; }
      #edit-container-panel-choose-color label[for$="-coral"] { --cfx-swatch-color:#f16f56; }
      #edit-container-panel-choose-color label[for$="-apricot"] { --cfx-swatch-color:#efa24a; }
      #edit-container-panel-choose-color label[for$="-mint"] { --cfx-swatch-color:#36b780; }
      #edit-container-panel-choose-color label[for$="-ice"] { --cfx-swatch-color:#48bbd6; }
      #edit-container-panel-choose-color label[for$="-lavender"] { --cfx-swatch-color:#9472d4; }
      #edit-container-panel-choose-color label[for$="-blush"] { --cfx-swatch-color:#db6ca8; }
      #edit-container-panel-choose-color label[for$="-sand"] { --cfx-swatch-color:#bca16a; }
      #edit-container-panel-choose-color label[for$="-charcoal"] { --cfx-swatch-color:#b75ba7; }
    `;
    doc.head.append(layout);
    const palette=doc.getElementById('edit-container-panel-choose-color');
    if(palette){
      const labelColors=()=>{
        for(const input of palette.querySelectorAll('input[type=radio]')){
          const label=({gray:'Copper',charcoal:'Berry'})[input.value] || input.value.charAt(0).toUpperCase()+input.value.slice(1);
          input.setAttribute('aria-label',label);
          input.parentElement.title=label;
        }
      };
      this.paletteObserver=new doc.defaultView.MutationObserver(labelColors);
      this.paletteObserver.observe(palette,{childList:true,subtree:true});labelColors();
    }

    let cookieStoreId=null, current=null, loading=false, saving=false, request=0;
    const group=doc.createElement('div');group.id='cfx-mac-auth';
    group.style.cssText='display:grid;gap:12px;margin:16px 0;text-align:start;';
    function field(labelText,id,type) {
      const label=doc.createElement('label');label.textContent=labelText;
      label.style.cssText='display:grid;gap:6px;font-size:14px;';
      const input=doc.createElement('input');input.id=id;input.type=type;input.className='primary-input';
      input.autocomplete='off';input.spellcheck=false;input.setAttribute('autocapitalize','none');
      input.style.cssText='box-sizing:border-box;width:100%;min-width:0;';
      label.append(input);group.append(label);return input;
    }
    const username=field('Username','cfx-mac-proxy-username','text');
    const password=field('Password','cfx-mac-proxy-password','password');
    const showLabel=doc.createElement('label');showLabel.style.cssText='display:flex;gap:8px;align-items:center;font-size:13px;';
    const show=doc.createElement('input');show.type='checkbox';show.id='cfx-mac-proxy-show-password';
    showLabel.append(show,doc.createTextNode('Show password'));group.append(showLabel);
    show.addEventListener('change',()=>{password.type=show.checked?'text':'password';});
    const help=doc.createElement('p');help.style.cssText='font-size:12px;line-height:1.45;margin:0;opacity:.85;';
    help.textContent='Saved for this container’s proxy. Leave both fields empty to remove authentication.';
    group.append(help);
    const status=doc.createElement('p');status.id='cfx-mac-proxy-auth-status';status.setAttribute('role','status');
    status.style.cssText='font-size:13px;line-height:1.4;margin:0;';group.append(status);
    form.insertBefore(group,apply);
    const name=()=>doc.getElementById('proxy-title-container-name')?.textContent.trim() ||
      doc.getElementById('edit-container-panel-name-input')?.value || '';
    const visible=()=>!panel.classList.contains('hide');
    const identify=()=>({cookieStoreId,name:name()});
    const enable=()=>{username.disabled=password.disabled=loading||saving;apply.disabled=loading||saving||!current;};
    const load=async()=>{
      if(!visible())return;
      doc.documentElement.setAttribute('data-cfx-proxy-open','');
      const serial=++request;loading=true;current=null;username.value=password.value='';show.checked=false;password.type='password';
      enable();status.textContent='Loading saved proxy authentication…';
      try {
        const result=await this.sendQuery('Read',identify());
        if(serial!==request || !visible())return;
        current=result;cookieStoreId=result.cookieStoreId;
        host.value=result.server;username.value=result.username;password.value=result.password;
        status.textContent=`Editing proxy authentication for ${result.name}.`;
      } catch(error){if(serial===request)status.textContent=error.message;}
      finally{if(serial===request){loading=false;enable();}}
    };
    const save=async()=>{
      if(loading||saving||!current||!visible())return;
      const serial=request;
      saving=true;enable();status.textContent='Saving proxy settings…';
      try {
        const result=await this.sendQuery('Save',{...identify(),server:host.value,username:username.value,password:password.value});
        if(serial!==request || !visible())return;
        host.value=result.server;form.classList.remove('invalid');
        status.textContent=`Saved for ${result.name}. ${result.authenticated?'Authentication preserved.':'No authentication.'}`;
      } catch(error){status.textContent=error.message;}
      finally{saving=false;enable();}
    };
    doc.addEventListener('click',event=>{
      const row=event.target.closest?.('[data-cookie-store-id]');
      if(row)cookieStoreId=row.getAttribute('data-cookie-store-id');
      if(!visible())return;
      if(event.target.closest?.('#submit-advanced-proxy')){
        event.preventDefault();event.stopImmediatePropagation();void save();
      } else if(event.target.closest?.('#clear-advanced-proxy-input')){
        event.preventDefault();event.stopImmediatePropagation();host.value='';host.focus();
      }
    },true);
    doc.addEventListener('keydown',event=>{
      const row=event.target.closest?.('[data-cookie-store-id]');
      if(row && ['Enter',' '].includes(event.key))cookieStoreId=row.getAttribute('data-cookie-store-id');
      if(visible() && event.key==='Enter' && [host,username,password].includes(event.target)){
        event.preventDefault();event.stopImmediatePropagation();void save();
      }
    },true);
    form.addEventListener('submit',event=>{event.preventDefault();event.stopImmediatePropagation();void save();},true);
    this.observer=new doc.defaultView.MutationObserver(()=>{
      if(visible())void load();else{doc.documentElement.removeAttribute('data-cfx-proxy-open');++request;current=null;username.value=password.value='';show.checked=false;password.type='password';}
    });
    this.observer.observe(panel,{attributes:true,attributeFilter:['class']});
    if(visible())void load();
  }
  didDestroy(){this.observer?.disconnect();this.paletteObserver?.disconnect();this.bulkCleanup?.();}
}
