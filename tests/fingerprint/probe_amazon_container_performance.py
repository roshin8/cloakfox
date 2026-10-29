"""Read-only Amazon browsing with a disposable copy of one container's settings.

CLOAKFOX_BIN, CLOAKFOX_SOURCE_PROFILE and REPORT_DIR are required. Copies only
container definitions and selected privacy settings; never cookies, logins or
session files. Opens homepage, searches, and follows one product. No purchases.
"""
import hashlib
import json
import os
import re
import shutil
import statistics
import tempfile
import time
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from probe_daily_defaults import launch
from probe_container_workflows import chrome, open_site


def read_prefs(path):
    result={}
    for line in path.read_text().splitlines():
        match=re.fullmatch(r'user_pref\(("(?:[^"\\]|\\.)*"), (.*)\);',line)
        if match:result[json.loads(match[1])]=json.loads(match[2])
    return result


def main():
    source=Path(os.environ['CLOAKFOX_SOURCE_PROFILE']);out=Path(os.environ['REPORT_DIR']);out.mkdir(parents=True,exist_ok=True)
    owner=int(os.environ.get('CLOAKFOX_TEST_OWNER','44'))
    source_prefs=read_prefs(source/'prefs.js');key=f'cloakfox.s.cloak_cfg_{owner}'
    cfg=json.loads(source_prefs[key]);prefs={k:v for k,v in source_prefs.items() if k.startswith(('cloakfox.opt.','cloakfox.experimental.','cloakfox.compat.'))}
    prefs.update({k:v for k,v in source_prefs.items() if k.startswith(f'cloakfox.container.{owner}.') or k==key})
    prefs.update({'cloakfox.enabled':True,'browser.sessionstore.resume_from_crash':False,'browser.startup.page':0})
    identities=json.loads((source/'containers.json').read_text())
    identity=next(x for x in identities['identities'] if x['userContextId']==owner)
    report={'binary':os.environ['CLOAKFOX_BIN'],'container':{'id':owner,'name':identity.get('name')},'scope':'Disposable headless profile using source container configuration; no personal cookies/session or profile mutations','steps':[]}
    source_hash=hashlib.sha256((source/'prefs.js').read_bytes()).hexdigest()
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-amazon-cache-') as temp:
            profile=Path(temp);shutil.copy2(source/'containers.json',profile/'containers.json')
            (profile/'user.js').write_text(''.join(f'user_pref({json.dumps(k)},{json.dumps(v)});\n' for k,v in prefs.items()))
            d=launch(profile,out/'gecko.log',purge_caches=True)
            try:
                d.set_page_load_timeout(60);d.set_script_timeout(30)
                report['buildID']=chrome(d,'return Services.appinfo.appBuildID;')
                open_site(d,'about:blank#amazon-cache-probe',owner)
                actual=chrome(d,"return Services.wm.getMostRecentWindow('navigator:browser').gBrowser.selectedBrowser.browsingContext.originAttributes.userContextId;");assert actual==owner
                chrome(d,"Services.prefs.setStringPref(arguments[0],arguments[1]);",key,json.dumps(cfg,separators=(',',':')))
                d.set_context('content')
                def snapshot(label,start):
                    row={'step':label,'elapsedMs':round((time.perf_counter()-start)*1000,2)}
                    row.update(d.execute_script("return {url:location.origin+location.pathname,title:document.title,readyState:document.readyState,search:!!document.getElementById('twotabsearchtextbox'),results:document.querySelectorAll('[data-component-type=s-search-result]').length,product:!!document.getElementById('productTitle'),blocked:/robot check|captcha|access denied/i.test(document.title)};"))
                    current=chrome(d,"const w=Services.wm.getMostRecentWindow('navigator:browser');return {owner:w.gBrowser.selectedBrowser.browsingContext.originAttributes.userContextId,enabled:Services.prefs.getBoolPref('cloakfox.enabled'),cfg:Services.prefs.getStringPref(arguments[0]),focus:Services.prefs.getBoolPref('cloakfox.opt.focus_masking',false)};",key)
                    effective=json.loads(current['cfg'])
                    changed=[k for k in set(effective)|set(cfg) if effective.get(k)!=cfg.get(k)]
                    effective_prefs=chrome(d,"const result={};for(const k of arguments[0]){const type=Services.prefs.getPrefType(k);result[k]=type===128?Services.prefs.getBoolPref(k):type===64?Services.prefs.getIntPref(k):Services.prefs.getStringPref(k);}return result;",[k for k in prefs if k.startswith('cloakfox.') and k!=key])
                    state_key=f'cloakfox.container.{owner}.network_state'
                    # Config writes advance connection generation; preserve the
                    # selected profile bit and prohibit generation rollback.
                    row['networkGenerationValid']=(effective_prefs[state_key]>=prefs[state_key] and (effective_prefs[state_key]&1)==(prefs[state_key]&1))
                    row['changedPrivacyPrefs']=[k for k,v in effective_prefs.items() if v!=prefs[k] and k!=state_key]
                    row.update(ownerMatches=current['owner']==owner,protectionEnabled=current['enabled'],focusMasking=current['focus'],configMatches=set(changed)<= {'timing:session_key_hi','timing:session_key_lo'},sessionSpecificChanges=changed)
                    assert row['ownerMatches'] and row['protectionEnabled'] and row['configMatches'] and not row['changedPrivacyPrefs'] and row['networkGenerationValid'],row
                    d.set_context('content');report['steps'].append(row);print(json.dumps(row),flush=True)
                    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
                start=time.perf_counter();d.get('https://www.amazon.com/')
                snapshot('homepage-loaded',start)
                report['initialPageText']=d.execute_script("return document.body.innerText.slice(0,600);")
                controls=WebDriverWait(d,30).until(lambda x:x.find_elements(By.ID,'twotabsearchtextbox') or x.find_elements(By.XPATH,"//button[normalize-space(.)='Continue shopping'] | //input[@type='submit' and @value='Continue shopping']"))
                if controls[0].get_attribute('id')!='twotabsearchtextbox':
                    report['continueShoppingPrompt']=True
                    controls[0].click()
                search=WebDriverWait(d,30).until(lambda x:x.find_element(By.ID,'twotabsearchtextbox'))
                snapshot('homepage',start)
                start=time.perf_counter();search.send_keys('usb c cable');search.send_keys(Keys.ENTER)
                WebDriverWait(d,45).until(lambda x:x.find_elements(By.CSS_SELECTOR,'[data-component-type=s-search-result]'))
                snapshot('search',start)
                product=d.execute_script("return [...document.querySelectorAll('[data-component-type=s-search-result] a[href]')].map(a=>a.href).find(h=>new URL(h).hostname.endsWith('amazon.com')&&new URL(h).pathname.includes('/dp/')); ")
                assert product,'No product link found'
                start=time.perf_counter();d.get(product)
                WebDriverWait(d,30).until(lambda x:x.find_elements(By.ID,'productTitle'))
                snapshot('product',start)
                # Same synthetic workload on the real page; wall clock avoids masked clocks.
                values=[];widths=[]
                for _ in range(5):
                    start=time.perf_counter();result=d.execute_script("const e=document.createElement('div');e.style.cssText='position:absolute;left:0;top:0;width:123px;height:45px;visibility:hidden';document.body.append(e);let sum=0;for(let i=0;i<2000;i++)sum+=e.getBoundingClientRect().width;const width=e.getBoundingClientRect().width;e.remove();return {sum,width};")
                    values.append(round((time.perf_counter()-start)*1000,2));widths.append(result)
                assert all(x['width']==widths[0]['width'] and x['width']!=123 and x['sum']==x['width']*2000 for x in widths), 'Geometry protection/stability regressed'
                report['geometry']={'iterations':2000,'wallMs':values,'medianMs':statistics.median(values),'values':widths}
                report['status']='PASS'
            except Exception:
                try:
                    d.set_context('content')
                    report['failurePage']=d.execute_script("return {title:document.title,url:location.origin+location.pathname,text:document.body.innerText.slice(0,1000)};")
                except Exception:pass
                raise
            finally:d.quit()
    except Exception as error:
        report['status']='FAIL';report['error']=type(error).__name__+': '+str(error)[:1000]
        raise
    finally:
        report['sourcePrefsUnchangedAtEnd']=hashlib.sha256((source/'prefs.js').read_bytes()).hexdigest()==source_hash
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'geometry':report['geometry']},indent=2))

if __name__=='__main__':main()
