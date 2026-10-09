#!/usr/bin/env python3
"""Native clipboard-event privacy, using a disposable headless profile.

The headless clipboard is process-local; this probe leaves the desktop
clipboard alone. Set CLOAKFOX_BIN and optionally GECKODRIVER.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait

PREF = "cloakfox.opt.clipboard_masking"
PAYLOAD = "clipboard α\nsecond line"

HTML = b'''<!doctype html><meta charset="utf-8">
<textarea id="plain"></textarea><input id="single">
<div id="rich" contenteditable="true"></div>
<textarea id="custom"></textarea>
<script>
window.log=[];
window.model='';
for (const type of ['copy','cut','paste','beforeinput','input','keydown','keypress','keyup']) {
  document.addEventListener(type,event=>{
    const row={type,target:event.target.id,trusted:event.isTrusted};
    if (event instanceof InputEvent) {
      row.inputType=event.inputType; row.data=event.data;
      row.transfer=event.dataTransfer ? [...event.dataTransfer.types] : null;
    }
    if (event instanceof KeyboardEvent) {
      row.key=event.key;row.ctrl=event.ctrlKey;row.meta=event.metaKey;
    }
    log.push(row);
  },true);
}
for (const type of ['copy','cut','paste']) {
  document.addEventListener(type,()=>log.push({type,phase:'bubble'}));
  document.querySelector('#plain')['on'+type]=()=>log.push({type,phase:'inline'});
}
document.querySelector('#custom').addEventListener('paste',event=>{
  model=event.clipboardData.getData('text/plain');
  event.preventDefault();
  event.target.value='handled:'+model;
});
window.reset=id=>{
  const el=document.getElementById(id);
  if (el.isContentEditable) el.textContent=''; else el.value='';
  el.focus();
  if (el.isContentEditable) {
    const range=document.createRange();range.selectNodeContents(el);range.collapse(false);
    getSelection().removeAllRanges();getSelection().addRange(range);
  }
  log.length=0;
};
window.value=id=>{
  const el=document.getElementById(id);
  return el.isContentEditable ? el.textContent : el.value;
};
</script>'''


class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        body = HTML
        if self.path == "/frames":
            body += (f'<iframe src="/same"></iframe><iframe src="http://localhost:{self.server.server_port}/cross"></iframe>').encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def chrome(driver, script, *args):
    driver.set_context("chrome")
    try:
        return driver.execute_script(script, *args)
    finally:
        driver.set_context("content")


def trusted_keypress(driver):
    # Test-only privileged dispatch reaches printable keypress independently
    # of native commands consuming keydown. Product code uses no page scripts.
    frame_script = """
      const target=content.document.getElementById('plain');
      content.wrappedJSObject.log.length=0;
      const event=new content.KeyboardEvent('keypress',{
        bubbles:true,key:'v',keyCode:0,charCode:118,
        metaKey:USE_META,ctrlKey:USE_CTRL
      });
      content.windowUtils.dispatchDOMEventViaPresShellForTesting(target,event);
      sendAsyncMessage('CloakfoxClipboardProbe',
        JSON.parse(JSON.stringify(content.wrappedJSObject.log)));
    """.replace('USE_META','true' if os.uname().sysname == 'Darwin' else 'false').replace(
        'USE_CTRL','false' if os.uname().sysname == 'Darwin' else 'true')
    driver.set_context('chrome')
    try:
        return driver.execute_async_script("""
          const mm=gBrowser.selectedBrowser.messageManager;
          const done=arguments[arguments.length-1];
          function listener(message) {
            mm.removeMessageListener('CloakfoxClipboardProbe',listener);
            done(message.data);
          }
          mm.addMessageListener('CloakfoxClipboardProbe',listener);
          mm.loadFrameScript('data:application/javascript,'+encodeURIComponent(arguments[0]),false);
        """,frame_script)
    finally:
        driver.set_context('content')


def main():
    binary = os.environ["CLOAKFOX_BIN"]
    gecko = os.environ.get("GECKODRIVER") or shutil.which("geckodriver")
    assert gecko, "Install geckodriver or set GECKODRIVER"
    server = ThreadingHTTPServer(("127.0.0.1", 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory(prefix="cloakfox-clipboard-probe-") as temp:
        opts = Options()
        opts.binary_location = binary
        opts.add_argument("-headless")
        driver = webdriver.Firefox(options=opts, service=Service(
            executable_path=gecko, service_args=["--allow-system-access"],
            log_output=os.path.join(temp, "geckodriver.log")))
        failures = []

        def check(ok, description, data=None):
            if not ok:
                failures.append(description)
                print(f"FAIL — {description}: {json.dumps(data,ensure_ascii=False)}", flush=True)

        def pref(enabled, master=True):
            chrome(driver, """
              Services.prefs.setBoolPref(arguments[0],arguments[1]);
              Services.prefs.setBoolPref('cloakfox.enabled',arguments[2]);
            """, PREF, enabled, master)

        def action(command):
            # Use native key bindings instead of chrome's asynchronous cached
            # command state, which can remain disabled for empty HTML editors.
            letter = {'cmd_paste':'v','cmd_copy':'c','cmd_cut':'x',
                      'cmd_selectAll':'a','cmd_undo':'z','cmd_redo':'z'}[command]
            accel = Keys.COMMAND if os.uname().sysname == 'Darwin' else Keys.CONTROL
            keys = [accel]
            if command == 'cmd_redo':
                keys.append(Keys.SHIFT)
            driver.switch_to.active_element.send_keys(*keys,letter,Keys.NULL)

        def clipboard(text):
            chrome(driver, "Cc['@mozilla.org/widget/clipboardhelper;1'].getService(Ci.nsIClipboardHelper).copyString(arguments[0]);", text)

        def read_clipboard():
            return chrome(driver, """
              const transfer=Cc['@mozilla.org/widget/transferable;1'].createInstance(Ci.nsITransferable);
              transfer.init(null);transfer.addDataFlavor('text/plain');
              Cc['@mozilla.org/widget/clipboard;1'].getService(Ci.nsIClipboard)
                .getData(transfer,Ci.nsIClipboard.kGlobalClipboard);
              const data={};transfer.getTransferData('text/plain',data);
              return data.value.QueryInterface(Ci.nsISupportsString).data;
            """)

        def reset(target):
            driver.execute_script("reset(arguments[0]);", target)

        def events():
            return driver.execute_script("return log;")

        def paste(target="plain", text=PAYLOAD):
            reset(target)
            clipboard(text)
            action("cmd_paste")
            try:
                WebDriverWait(driver, 5).until(lambda d: d.execute_script("return value(arguments[0]);", target) != "")
            except TimeoutException:
                state = driver.execute_script("return {value:value(arguments[0]),events:log,active:document.activeElement.id,selection:String(getSelection())};",target)
                raise AssertionError(f"Native paste did not insert into {target}: {json.dumps(state)}")
            return events()

        try:
            check(chrome(driver, "return Services.appinfo.name") == "Cloakfox", "Cloakfox launched")
            check(not chrome(driver, "return Services.prefs.getBoolPref(arguments[0],false)", PREF), "mask is opt-in")
            driver.get(f"http://127.0.0.1:{server.server_port}/")
            baseline = paste()
            check(any(e['type'] == 'paste' for e in baseline), "baseline exposes native paste", baseline)
            check(any(e.get('inputType') == 'insertFromPaste' for e in baseline), "baseline exposes paste metadata", baseline)
            baseline_rich = paste('rich','rich baseline')
            check(any(e.get('transfer') == ['text/plain'] for e in baseline_rich), "contenteditable baseline exposes transfer metadata", baseline_rich)
            keypress_baseline = trusted_keypress(driver)
            check(any(e['type'] == 'keypress' and e['trusted'] for e in keypress_baseline), "trusted printable keypress baseline", keypress_baseline)
            pref(True)
            keypress_masked = trusted_keypress(driver)
            check(not any(e['type'] == 'keypress' for e in keypress_masked), "zero-keyCode clipboard keypress masked", keypress_masked)
            masked = paste()
            check(driver.execute_script("return value('plain')") == PAYLOAD, "native paste still inserts text")
            check(not any(e['type'] in ('copy','cut','paste') for e in masked), "clipboard events hidden in capture, target and bubble listeners", masked)
            check(all(e.get('inputType') == 'insertText' for e in masked if e['type'] in ('beforeinput','input')), "paste-specific input metadata masked", masked)
            check(any(e['type'] == 'input' and e['trusted'] for e in masked), "trusted ordinary input remains observable", masked)
            action('cmd_undo')
            WebDriverWait(driver,5).until(lambda d: d.execute_script("return value('plain')") == '')
            action('cmd_redo')
            WebDriverWait(driver,5).until(lambda d: d.execute_script("return value('plain')") == PAYLOAD)
            paste('single','single line')
            check(driver.execute_script("return value('single')") == 'single line', "single-line native paste preserved")

            for command in ('cmd_copy','cmd_cut'):
                paste()
                action('cmd_selectAll')
                driver.execute_script('log.length=0;')
                action(command)
                if command == 'cmd_cut':
                    WebDriverWait(driver,5).until(lambda d: d.execute_script("return value('plain')") == '')
                check(read_clipboard() == PAYLOAD, f"{command} still writes selected text")
                rows = events()
                check(not any(e['type'] in ('copy','cut','paste') for e in rows), f"{command} notifications hidden", rows)
                if command == 'cmd_cut':
                    check(any(e.get('inputType') == 'deleteContentBackward' for e in rows), "cut input metadata masked", rows)
                    check(not any(e.get('inputType') == 'deleteByCut' for e in rows), "no cut-specific metadata", rows)

            rich = paste('rich','rich \u03b1')
            check(driver.execute_script("return value('rich')") == 'rich \u03b1', "contenteditable paste inserts text")
            check(not any(e['type'] == 'paste' for e in rich), "contenteditable paste notification hidden", rich)
            check(all(e.get('transfer') is None for e in rich if e['type'] in ('beforeinput','input')), "contenteditable transfer metadata hidden", rich)
            check(all(e.get('inputType') == 'insertText' for e in rich if e['type'] in ('beforeinput','input')), "contenteditable paste type masked", rich)

            accel = Keys.COMMAND if os.uname().sysname == 'Darwin' else Keys.CONTROL
            for letter, command in (('v','paste'),('c','copy'),('x','cut')):
                paste()
                action('cmd_selectAll')
                clipboard('shortcut paste')
                driver.execute_script('log.length=0;')
                driver.find_element(By.ID,'plain').send_keys(accel,letter,Keys.NULL)
                rows = events()
                check(not any(e['type'] in ('copy','cut','paste') for e in rows), f"{command} shortcut clipboard notification hidden", rows)
                check(not any(e.get('key','').lower() == letter and (e.get('ctrl') or e.get('meta')) for e in rows), f"{command} shortcut key events hidden", rows)
                if letter == 'v':
                    check(driver.execute_script("return value('plain')") == 'shortcut paste', "native paste shortcut still works", rows)
            reset('plain')
            driver.find_element(By.ID,'plain').send_keys('typing')
            check(driver.execute_script("return value('plain')") == 'typing', "normal typing preserved")
            check(any(e.get('key') == 't' for e in events()), "ordinary keystrokes remain native", events())

            synthetic = driver.execute_script("""
              log.length=0;
              const el=document.getElementById('plain');
              el.dispatchEvent(new ClipboardEvent('paste',{bubbles:true}));
              const event=new InputEvent('input',{bubbles:true,inputType:'insertFromPaste',data:'synthetic'});
              el.dispatchEvent(event);
              return {rows:log,type:event.inputType,data:event.data,trusted:event.isTrusted};
            """)
            check(synthetic['type'] == 'insertFromPaste' and not synthetic['trusted'], "script-created input events retain their supplied metadata", synthetic)
            check(any(e['type'] == 'paste' for e in synthetic['rows']), "script-created clipboard notifications remain native", synthetic)

            for enabled, master in ((False,True),(True,False),(True,True)):
                pref(enabled,master)
                rows = paste()
                visible = any(e['type'] == 'paste' for e in rows)
                check(visible == (not enabled or not master), f"live option/master gating {enabled}/{master}", rows)
            pref(True)
            driver.get(f"http://127.0.0.1:{server.server_port}/frames")
            for index in (0,1):
                driver.switch_to.frame(index)
                rows = paste()
                check(not any(e['type'] == 'paste' for e in rows), f"frame {index} clipboard notifications hidden", rows)
                check(all(e.get('inputType') == 'insertText' for e in rows if e['type'] in ('beforeinput','input')), f"frame {index} paste metadata masked", rows)
                driver.switch_to.default_content()

            # A paste-event-driven custom editor cannot update its own model
            # when its clipboard handler is hidden. This is an explicit tradeoff.
            pref(False)
            paste('custom','custom text')
            check(driver.execute_script('return window.model') == 'custom text', "custom editor baseline receives paste")
            pref(True)
            driver.execute_script("window.model='';")
            rows = paste('custom','private text')
            check(driver.execute_script('return window.model') == '', "strict mode suppresses custom clipboard handlers", rows)

            original = driver.current_window_handle
            chrome(driver,"""
              gBrowser.selectedTab=gBrowser.addTab(arguments[0],{
                userContextId:1,
                triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()
              });
            """,f"http://127.0.0.1:{server.server_port}/container")
            driver.switch_to.window(next(h for h in driver.window_handles if h != original))
            WebDriverWait(driver,5).until(lambda d: d.find_element(By.ID,'plain'))
            container_rows = paste()
            check(chrome(driver,"return gBrowser.selectedBrowser.getAttribute('usercontextid');") == '1', "container fixture is isolated")
            check(not any(e['type'] == 'paste' for e in container_rows), "clipboard masking applies in containers", container_rows)
            driver.close()
            driver.switch_to.window(original)

            chrome_rows = chrome(driver, """
              const field=gURLBar.inputField, rows=[];
              function observe(event) {
                rows.push({type:event.type,inputType:event.inputType ?? null});
              }
              field.addEventListener('paste',observe);
              field.addEventListener('input',observe);
              try {
                gURLBar.focus();field.value='';
                Cc['@mozilla.org/widget/clipboardhelper;1']
                  .getService(Ci.nsIClipboardHelper).copyString('chrome clipboard');
                goDoCommand('cmd_paste');
                return {rows,value:field.value};
              } finally {
                field.removeEventListener('paste',observe);
                field.removeEventListener('input',observe);
              }
            """)
            check(chrome_rows['value'] == 'chrome clipboard', "browser chrome paste preserved", chrome_rows)
            check(any(e['type'] == 'paste' for e in chrome_rows['rows']), "browser chrome retains clipboard event", chrome_rows)
            check(any(e['inputType'] == 'insertFromPaste' for e in chrome_rows['rows']), "system caller retains paste metadata", chrome_rows)

            driver.get('about:cloakfox')
            toggle = WebDriverWait(driver,5).until(lambda d: d.find_element(By.CSS_SELECTOR,f'input[data-pref="{PREF}"]'))
            check(toggle.is_selected(), "settings exposes native option")
            driver.execute_script('arguments[0].click();',toggle)
            check(not chrome(driver,"return Services.prefs.getBoolPref(arguments[0]);",PREF), "settings disables native option")
            assert not failures, '\n'.join(failures)
        finally:
            driver.quit()
            server.shutdown()
    print("PASS — clipboard events, shortcuts/keypress, input metadata, native editing/undo, chrome, frames, containers and live switches")


if __name__ == "__main__":
    main()
