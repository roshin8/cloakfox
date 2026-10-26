"""Verify site-data clearing isolation using only a disposable profile/local site."""
import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<!doctype html><title>Site data isolation test</title>')
    def log_message(self, *_):
        pass

def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/'
    with tempfile.TemporaryDirectory(prefix='cloakfox-site-data-') as profile:
        Path(profile, 'user.js').write_text('user_pref("browser.profiles.enabled", false);\nuser_pref("privacy.userContext.enabled", true);\n')
        options = Options()
        options.binary_location = '/Applications/Cloakfox.app/Contents/MacOS/cloakfox'
        for arg in ['-headless', '-no-remote', '-profile', profile, '-purgecaches']:
            options.add_argument(arg)
        driver = webdriver.Firefox(options=options, service=Service(service_args=['--allow-system-access'], log_output=str(Path(profile, 'gecko.log'))))
        try:
            tabs = {}
            for container in [0, 1, 2]:
                driver.set_context('chrome')
                driver.execute_script('''gBrowser.selectedTab = gBrowser.addTab(arguments[0], {
                    userContextId: arguments[1], triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()
                });''', url, container)
                driver.set_context('content')
                handle = driver.window_handles[-1]
                driver.switch_to.window(handle)
                WebDriverWait(driver, 15).until(lambda _: driver.execute_script('return document.readyState') == 'complete' and driver.current_url == url)
                driver.execute_script('document.cookie="scope=value; path=/"; localStorage.setItem("scope", "value"); sessionStorage.setItem("scope", "value");')
                tabs[container] = handle
            def clear(pattern, full=False):
                driver.set_context('chrome')
                result = driver.execute_async_script('''const [pattern, full, done] = arguments;
                    Services.clearData.deleteDataFromSite('127.0.0.1', pattern, true,
                    full ? Ci.nsIClearDataService.CLEAR_COOKIES_AND_SITE_DATA | Ci.nsIClearDataService.CLEAR_ALL_CACHES :
                    Ci.nsIClearDataService.CLEAR_COOKIES | Ci.nsIClearDataService.CLEAR_DOM_STORAGES, done);''', pattern, full)
                assert result == 0, result
                driver.set_context('content')
            def read(container):
                driver.switch_to.window(tabs[container])
                driver.refresh()
                return driver.execute_script('return [document.cookie, localStorage.getItem("scope"), sessionStorage.getItem("scope")];')
            def trust_panel(scope=None):
                driver.set_context('chrome')
                driver.execute_async_script("""const done = arguments[arguments.length-1];
                    gTrustPanelHandler.showPopup({reason:'shieldButtonClicked'}).then(() => done(true), e => done(String(e)));""")
                WebDriverWait(driver, 10).until(lambda _: driver.execute_script("return document.getElementById('trustpanel-popup').state === 'open'"))
                driver.execute_script("document.getElementById('trustpanel-clear-cookies-button').doCommand();")
                WebDriverWait(driver, 10).until(lambda _: driver.execute_script("return document.getElementById('trustpanel-clear-cookie-current').label.startsWith('This container:') && document.getElementById('trustpanel-clear-cookie-scope').getBoundingClientRect().height > 0"))
                assert driver.execute_script("return document.getElementById('trustpanel-clear-cookie-scope').value") == 'container'
                assert 'This container:' in driver.execute_script("return document.getElementById('trustpanel-clear-cookie-current').label")
                if scope is None:
                    driver.save_screenshot('/tmp/cloakfox-site-data-scope-panel.png')
                    driver.execute_script("document.getElementById('trustpanel-clear-cookie-cancel').click();")
                else:
                    driver.execute_script("document.getElementById('trustpanel-clear-cookie-scope').value = arguments[0]; document.getElementById('trustpanel-clear-cookie-clear').click();", scope)
                WebDriverWait(driver, 10).until(lambda _: driver.execute_script("return document.getElementById('trustpanel-popup').state === 'closed'"))
                driver.set_context('content')
            trust_panel()
            assert read(2) == ['scope=value', 'value', 'value'], 'Trust Panel Cancel must preserve data'
            # Exercise the real native choice dialog, then cancel it.
            driver.set_context('chrome')
            driver.execute_script("""window.setTimeout(() => {
                const popup = { addEventListener(_event, callback) { this.callback = callback; } };
                const hide = PanelMultiView.hidePopup;
                PanelMultiView.hidePopup = () => popup.callback();
                try {
                    gIdentityHandler.clearSiteData.call({
                        _uriHasHost: true, _uri: { host: '127.0.0.1' }, _identityPopup: popup
                    }, { stopPropagation() {} });
                } finally { PanelMultiView.hidePopup = hide; }
            }, 0);""")
            dialog = WebDriverWait(driver, 10).until(EC.alert_is_present())
            assert 'This container (' in dialog.text
            assert 'All containers' in dialog.text
            dialog.dismiss()
            driver.set_context('content')
            assert read(2) == ['scope=value', 'value', 'value'], 'Cancel must preserve data'
            driver.switch_to.window(tabs[1])
            trust_panel('container')
            assert read(1) == ['', None, None]
            assert read(0) == ['scope=value', 'value', 'value']
            assert read(2) == ['scope=value', 'value', 'value']
            clear({'userContextId': 0, 'privateBrowsingId': 0})
            assert read(0) == ['', None, None]
            assert read(2) == ['scope=value', 'value', 'value']
            driver.switch_to.window(tabs[2])
            trust_panel('all')
            assert read(2) == ['', None, None]
            print(json.dumps({'passed': True, 'checks': ['current container isolated', 'default container isolated', 'all containers cleared']}))
        finally:
            driver.quit()
            server.shutdown()

if __name__ == '__main__':
    main()
