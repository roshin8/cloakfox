#!/usr/bin/env python3
"""macOS appearance round trip, using one disposable profile and app copies."""
from __future__ import annotations

import os
import json
import plistlib
import shutil
import tempfile
import zipfile
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait


PREF = "cloakfox.appearance.firefox"
MODULE = "resource:///modules/CloakfoxAppearance.sys.mjs"
ADDON_ID = "cloakfox-shield@cloakfox"


def addon_payload(app, folder="cloakfox-shield"):
    resources = app / "Contents/Resources/browser"
    prefix = f"chrome/browser/builtin-addons/{folder}/"
    archive = resources / "omni.ja"
    if archive.exists():
        with zipfile.ZipFile(archive) as reader:
            return {name[len(prefix):]: reader.read(name) for name in reader.namelist()
                    if name.startswith(prefix) and not name.endswith("/")}
    root = resources / prefix
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def extension_branding(driver, expected):
    """Check loaded extension metadata and the UI people can see, not source text."""
    driver.set_context("chrome")
    try:
        state = driver.execute_async_script("""
          const [id,done]=arguments;
          const {AddonManager}=ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');
          const {ExtensionParent}=ChromeUtils.importESModule('resource://gre/modules/ExtensionParent.sys.mjs');
          AddonManager.getAddonByID(id).then(async addon=>{
            const deadline=Date.now()+10000;
            let extension;
            while(!(extension=ExtensionParent.GlobalManager.getExtension(id))&&Date.now()<deadline)
              await new Promise(resolve=>setTimeout(resolve,100));
            if(!addon||!extension){done({error:'Bundled extension is not running'});return;}
            const wid=id.toLowerCase().replace(/[^a-z0-9_-]/g,'_')+'-browser-action';
            const widget=document.getElementById(wid);
            const labels=widget?Array.from(widget.querySelectorAll('*')).concat(widget)
              .flatMap(n=>['label','tooltiptext','aria-label'].map(k=>n.getAttribute(k)).filter(Boolean)):[];
            done({id:addon.id,name:addon.name,description:addon.description,hidden:addon.hidden,
              title:extension.manifest.browser_action.default_title,labels,
              popup:extension.baseURI.resolve('popup/popup.html')});
          }).catch(e=>done({error:e.message}));
        """, ADDON_ID)
    finally:
        driver.set_context("content")
    assert "error" not in state, state
    assert state["id"] == ADDON_ID, state
    assert state["name"] == expected, f"Extension metadata keeps old branding: {state}"
    assert state["title"] == expected and expected in state["labels"], state
    if expected == "Firefox":
        assert not any("cloakfox" in value.lower() for value in state["labels"]), state
        assert "cloakfox" not in state["description"].lower(), state
    driver.get(state["popup"])
    assert driver.title == expected
    assert driver.find_element(By.CSS_SELECTOR, ".brand-name").text == expected
    WebDriverWait(driver, 10).until(lambda d: d.find_element(By.ID, "cfx-status").text in ("active", "off"))
    assert "bridge unavailable" not in driver.find_element(By.ID, "cfx-persona-preview").text.lower()
    assert driver.find_element(By.ID, "cfx-open-settings").is_enabled()
    if expected == "Firefox":
        mark = driver.find_element(By.CSS_SELECTOR, "img.brand-mark")
        assert driver.execute_script("return arguments[0].complete && arguments[0].naturalWidth>0", mark)
    # Firefox's built-in system add-ons are hidden from about:addons. Their
    # loaded metadata still supplies labels in the toolbar/extensions panel.
    assert state["hidden"], state
    print(f"PASS — {expected} extension metadata, toolbar tooltip and popup (system add-on hidden from about:addons)", flush=True)
    return state


def chrome(driver, script, *args):
    driver.set_context("chrome")
    try:
        return driver.execute_script(script, *args)
    finally:
        driver.set_context("content")


def prepare(driver, enabled):
    driver.set_context("chrome")
    try:
        result = driver.execute_async_script("""
          const done = arguments[arguments.length - 1];
          ChromeUtils.importESModule(arguments[0]).prepareAppearance(arguments[1])
            .then(done, e => done({error:e.message}));
        """, MODULE, enabled)
        assert "error" not in result, result
        return result
    finally:
        driver.set_context("content")


def main():
    assert os.uname().sysname == "Darwin", "This probe exercises macOS bundles"
    binary = Path(os.environ["CLOAKFOX_BIN"]).absolute()
    source_app = binary.parents[2]
    source_plist = source_app / "Contents/Info.plist"
    source_bytes = source_plist.read_bytes()
    source_addon = addon_payload(source_app)
    assert source_addon, "Source extension payload missing"
    gecko = os.environ.get("GECKODRIVER") or shutil.which("geckodriver")
    assert gecko, "Set GECKODRIVER or install geckodriver"

    with tempfile.TemporaryDirectory(prefix="cloakfox-appearance-probe-") as temp:
        profile = Path(temp) / "profile with spaces"
        profile.mkdir()

        def launch(executable):
            opts = Options()
            opts.binary_location = str(executable)
            opts.add_argument("-headless")
            opts.add_argument("-profile")
            opts.add_argument(str(profile))
            driver = webdriver.Firefox(options=opts, service=Service(
                executable_path=gecko, service_args=["--allow-system-access"],
                log_output=str(Path(temp) / "geckodriver.log")))
            driver.set_script_timeout(180)
            return driver

        driver = launch(binary)
        try:
            driver.get("about:cloakfox")
            toggles = driver.find_elements(By.CSS_SELECTOR, f'input[data-pref="{PREF}"]')
            assert len(toggles) == 1, "Firefox appearance setting is missing"
            assert not toggles[0].is_selected(), "Appearance should default off"
            assert chrome(driver, "return Services.strings.createBundle('chrome://branding/locale/brand.properties').GetStringFromName('brandShortName')") == "Cloakfox"
            original_extension = extension_branding(driver, "Cloakfox")
            driver.get("about:cloakfox")
            toggles = driver.find_elements(By.CSS_SELECTOR, f'input[data-pref="{PREF}"]')
            chrome(driver, "Services.prefs.setStringPref('cloakfox.appearance.probe','profile preserved');")
            driver.execute_script("arguments[0].click()", toggles[0])
            assert chrome(driver, "return Services.prefs.getBoolPref(arguments[0])", PREF)
            target = prepare(driver, True)
            refreshed = prepare(driver, True)
            assert refreshed["app"] != target["app"], "A new switch must use the current source payload"
            target = refreshed
            assert source_plist.read_bytes() == source_bytes, "Source bundle changed"
            driver.set_context("chrome")
            cancelled = driver.execute_async_script("""
              const done = arguments[arguments.length - 1];
              const block = subject => {subject.QueryInterface(Ci.nsISupportsPRBool).data = true};
              Services.obs.addObserver(block, 'quit-application-requested');
              ChromeUtils.importESModule(arguments[0]).restartAppearance().then(result => {
                Services.obs.removeObserver(block, 'quit-application-requested');
                done({cancelled:result.cancelled,env:Services.env.get('CLOAKFOX_RESTART_BUNDLE')});
              }, e => {Services.obs.removeObserver(block, 'quit-application-requested');done({error:e.message})});
            """, MODULE)
            driver.set_context("content")
            assert cancelled == {"cancelled": True, "env": ""}, cancelled
        finally:
            driver.quit()

        firefox_app = Path(target["app"])
        assert firefox_app.name == "Firefox.app"
        info = plistlib.loads((firefox_app / "Contents/Info.plist").read_bytes())
        assert info["CFBundleName"] == info["CFBundleDisplayName"] == "Firefox", info
        assert info["CFBundleExecutable"] == "firefox", info
        assert "CFBundleIconName" not in info, "Original asset catalog overrides the Firefox icon"
        assert info["CFBundleIdentifier"] != plistlib.loads(source_bytes)["CFBundleIdentifier"]
        assert (firefox_app / "Contents/Resources/firefox.icns").read_bytes() == (source_app / "Contents/Resources/browser/appearance/firefox.icns").read_bytes()
        firefox_addon = addon_payload(firefox_app, "firefox-panel")
        assert not addon_payload(firefox_app), "Appearance copy keeps original extension root"
        assert firefox_addon.keys() == source_addon.keys(), "Extension files lost during rebranding"
        original_manifest = json.loads(source_addon["manifest.json"])
        firefox_manifest = json.loads(firefox_addon["manifest.json"])
        for key in ["version", "browser_specific_settings", "permissions", "experiment_apis", "background",
                    "content_scripts", "web_accessible_resources"]:
            assert firefox_manifest.get(key) == original_manifest.get(key), f"Extension behavior changed: {key}"
        for name in ["background.js", "experiment-apis/cloakfox.js", "experiment-apis/cloakfox.json"]:
            assert firefox_addon[name] == source_addon[name], f"Privileged extension bridge changed: {name}"
        for size in [48, 128]:
            assert firefox_addon[f"icons/icon-{size}.png"] == (source_app / f"Contents/Resources/browser/appearance/icon{size}.png").read_bytes()
        assert addon_payload(source_app) == source_addon, "Source extension was modified"
        driver = launch(target["executable"])
        try:
            assert chrome(driver, "return Services.dirsvc.get('ProfD',Ci.nsIFile).path") == str(profile)
            assert chrome(driver, "return Services.prefs.getStringPref('cloakfox.appearance.probe')") == "profile preserved"
            assert chrome(driver, "return Services.strings.createBundle('chrome://branding/locale/brand.properties').GetStringFromName('brandShortName')") == "Firefox"
            assert extension_branding(driver, "Firefox")["popup"] == original_extension["popup"], "Extension origin changed"
            messages = chrome(driver, """
              return new Localization(['branding/brand.ftl','browser/menubar.ftl']).formatMessages([{id:'menu-about'}]);
            """)
            assert any(a["value"] == "About Firefox" for a in messages[0]["attributes"]), messages
            driver.get("about:cloakfox")
            assert driver.title == "Firefox", driver.title
            assert driver.find_element(By.CSS_SELECTOR, ".brand-name").text == "Firefox"
            assert driver.find_element(By.ID, "cfx-appearance-status").text.startswith("Active: Firefox")
            toggle = driver.find_element(By.CSS_SELECTOR, f'input[data-pref="{PREF}"]')
            assert toggle.is_selected()
            chrome(driver, "Services.prefs.setBoolPref('cloakfox.enabled',false);")
            assert chrome(driver, "return Services.strings.createBundle('chrome://branding/locale/brand.properties').GetStringFromName('brandShortName')") == "Firefox", "Appearance is independent of privacy master switch"
            extension_branding(driver, "Firefox")
            driver.get("about:cloakfox")
            toggle = driver.find_element(By.CSS_SELECTOR, f'input[data-pref="{PREF}"]')
            driver.execute_script("arguments[0].click()", toggle)
            restored = prepare(driver, False)
            for _ in range(20):
                assert prepare(driver, False) == restored, "Fast plist helpers must not fail when already exited"
            assert Path(restored["app"]) == source_app, restored
            assert source_plist.read_bytes() == source_bytes
            assert addon_payload(source_app) == source_addon, "Source extension changed on restoration"
        finally:
            driver.quit()

        driver = launch(restored["executable"])
        try:
            driver.get("about:cloakfox")
            assert driver.title == "Cloakfox"
            assert driver.find_element(By.ID, "cfx-appearance-status").text.startswith("Active: Cloakfox")
            assert chrome(driver, "return Services.prefs.getStringPref('cloakfox.appearance.probe')") == "profile preserved"
            assert extension_branding(driver, "Cloakfox")["popup"] == original_extension["popup"], "Extension origin changed on restoration"
        finally:
            driver.quit()
    print("PASS — Firefox/Cloakfox appearance, native bundle metadata and icons, Fluent branding, settings and profile preservation")


if __name__ == "__main__":
    main()
