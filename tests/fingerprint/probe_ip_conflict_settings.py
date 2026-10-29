"""Exercise IP rule and exception controls in a disposable browser profile."""
import os
import tempfile
from pathlib import Path
from probe_daily_defaults import launch
from selenium.webdriver.support.ui import WebDriverWait

def main():
 with tempfile.TemporaryDirectory(prefix='cfx-ip-settings-') as t:
  root=Path(t);profile=root/'profile';profile.mkdir();d=launch(profile,root/'gecko.log')
  try:
   d.set_context('content');d.get('about:cloakfox#cfx-ip-conflict-panel')
   WebDriverWait(d,15).until(lambda d:d.execute_script("return !!document.querySelector('.ip-manager-fields')"))
   assert d.execute_script("return document.getElementById('cfx-ip-conflict-panel').closest('.settings-group') !== document.getElementById('sec-network-policy').closest('.settings-group')"), 'IP management must be an independent settings section'
   assert d.execute_script("return [...document.querySelectorAll('.settings-tabs button')].some(b=>b.textContent==='IP conflict management')")
   assert 'OFF' in d.find_element('id','cfx-ip-monitor-status').text
   assert d.execute_script("return document.querySelector('.ip-manager-fields textarea').disabled")
   def click(text):d.execute_script("[...document.querySelectorAll('#cfx-ip-conflict-panel button')].find(b=>b.textContent===arguments[0]).click()",text)
   d.execute_script("const p=document.getElementById('cfx-ip-conflict-panel');const fields=p.querySelectorAll('.ip-manager-fields textarea');fields[0].value='example.com';fields[1].value='accounts.example.com';[...p.querySelectorAll('select')].find(s=>s.querySelector('option[value=selected]')).value='selected';")
   d.execute_script("[...document.querySelectorAll('.settings-tabs button')].find(b=>b.textContent==='Container connections').click();")
   assert d.execute_script("return document.getElementById('cfx-ip-conflict-panel').hidden")
   d.execute_script("[...document.querySelectorAll('.settings-tabs button')].find(b=>b.textContent==='IP conflict management').click();")
   assert d.execute_script("return document.querySelector('.ip-manager-fields textarea').value")=='example.com'
   click('Save website rules')
   assert 'automatic checking is OFF' in d.find_element('id','cfx-ip-conflict-panel').text
   click('Save and enable checking')
   assert d.find_element('id','cfx-ip-auto').is_selected()
   assert 'ON' in d.find_element('id','cfx-ip-monitor-status').text
   d.refresh();WebDriverWait(d,10).until(lambda d:d.execute_script("return document.querySelector('.ip-manager-fields textarea')?.value==='example.com'"))
   assert d.execute_script("return document.querySelectorAll('.ip-manager-fields textarea')[1].value")=='accounts.example.com'
   d.execute_script("document.querySelector('#cfx-ip-conflict-panel input[placeholder=\"192.0.2.1\"]').value='192.0.2.1'")
   click('Allow IP');assert '192.0.2.1' in d.find_element('id','cfx-ip-conflict-panel').text
   click('Remove exception');assert 'No IP exceptions.' in d.find_element('id','cfx-ip-conflict-panel').text
   d.set_context('chrome');d.execute_script("ChromeUtils.importESModule('resource:///modules/CloakfoxIPConflicts.sys.mjs').recordIPAccess('192.0.2.9',0,'https://example.com/path?secret=x');")
   d.set_context('content')
   WebDriverWait(d,5).until(lambda d:d.execute_script("return document.querySelector('#cfx-ip-conflict-panel .ip-history-website')?.textContent.includes('192.0.2.9')"))
   d.execute_script("document.querySelector('#cfx-ip-conflict-panel .ip-history-website').open=true")
   WebDriverWait(d,5).until(lambda d:'192.0.2.9' in d.find_element('id','cfx-ip-conflict-panel').text)
   assert 'secret=x' not in d.execute_script("return document.getElementById('cfx-ip-conflict-panel').textContent")
   for width in [1280,848,600]:
    d.set_window_size(width,1000)
    WebDriverWait(d,5).until(lambda d:d.execute_script('return document.documentElement.scrollWidth <= innerWidth'),f'responsive width {width}')
   d.set_window_size(1280,1000)
   d.find_element('class name','ip-manager-fields').location_once_scrolled_into_view
   d.set_context('chrome');d.save_screenshot(str(Path(os.environ.get('REPORT_DIR', str(Path(__file__).resolve().parents[2]/'docs/ip-conflicts')))/'settings.png'));d.set_context('content')
   d.execute_script("const s=document.getElementById('cfx-layout');s.value='grouped';s.dispatchEvent(new Event('change'))")
   assert d.execute_script("return document.getElementById('cfx-ip-conflict-panel').closest('.settings-group').querySelector('summary').textContent==='IP conflict management'")
   click('Delete record');assert 'No recorded website visits.' in d.find_element('id','cfx-ip-conflict-panel').text
   print('PASS: website rules persist, exception add/remove, history display/delete, URL redaction, responsive settings')
  finally:d.quit()
if __name__=='__main__':main()
