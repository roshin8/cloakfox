"""Explicit Intl locale tags must remain intact under a configured default.

The inherited locale patch replaced low-level tag components on every read,
including Firefox Settings' translation/language initialization. This probe
catches that corruption, checks native default changes/master toggling, and
records the cost of repeated maximize operations without a timing-only gate.
"""
import json
import os
import tempfile
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

FIXTURES = [("de", "de-Latn-DE"), ("fr", "fr-Latn-FR"),
            ("ja", "ja-Jpan-JP"), ("zh-TW", "zh-Hant-TW"),
            ("ar", "ar-Arab-EG"), ("en-GB", "en-Latn-GB")]


def main():
    report = Path(os.environ.get("REPORT_DIR", tempfile.mkdtemp(prefix="cloakfox-locale-report-")))
    report.mkdir(parents=True, exist_ok=True)
    opts = Options()
    opts.binary_location = os.environ["CLOAKFOX_BIN"]
    opts.add_argument("-headless")
    driver = webdriver.Firefox(options=opts, service=Service(
        service_args=["--allow-system-access"], log_output=str(report / "gecko.log")))
    checks, observations = [], {}

    def chrome(script, *args):
        driver.set_context("chrome")
        try:
            return driver.execute_script(script, *args)
        finally:
            driver.set_context("content")

    def configure(enabled, language="en", region="US"):
        chrome("""
            Services.prefs.setBoolPref('cloakfox.enabled',arguments[0]);
            const key='cloakfox.s.cloak_cfg_0',cfg=JSON.parse(Services.prefs.getStringPref(key,'{}'));
            cfg['navigator.language']=arguments[1]+'-'+arguments[2];
            cfg['locale:language']=arguments[1];cfg['locale:region']=arguments[2];cfg['locale:script']='Latn';
            Services.prefs.setStringPref(key,JSON.stringify(cfg));
            """, enabled, language, region)

    def measure():
        return driver.execute_script("""
            const tags=arguments[0],start=performance.now(),result=[];
            for(const [tag] of tags){try{
                const l=new Intl.Locale(tag);
                result.push({tag,language:l.language,region:l.region??null,script:l.script??null,
                    max:l.maximize().toString(),min:l.maximize().minimize().toString(),
                    format:new Intl.DateTimeFormat(tag).resolvedOptions().locale});
            }catch(e){result.push({tag,error:String(e)})}}
            const checkMs=performance.now()-start,begin=performance.now();
            for(let i=0;i<100;i++)new Intl.Locale(tags[i%tags.length][0]).maximize();
            return {result,checkMs,benchmarkMs:performance.now()-begin,defaultLocale:new Intl.DateTimeFormat().resolvedOptions().locale};
            """, FIXTURES)

    def system_locale():
        return chrome("return Cc['@mozilla.org/intl/ospreferences;1'].getService(Ci.mozIOSPreferences).systemLocale")

    def check(ok, name, data):
        checks.append({"name": name, "pass": bool(ok), "data": data})
        print(("PASS " if ok else "FAIL ") + name, flush=True)

    try:
        driver.get("data:text/html,<title>Locale probe</title>")
        # Capture both states before asserting so the RED run retains its control.
        configure(False)
        observations["nativeBaseline"] = system_locale()
        observations["off"] = measure()
        configure(True)
        observations["on"] = measure()
        for mode in ("off", "on"):
            for (tag, expected), value in zip(FIXTURES, observations[mode]["result"]):
                check(value.get("max") == expected and value.get("language") == tag.split("-")[0]
                      and value.get("format") == tag,
                      f"{mode}: explicit {tag} retains its language, region and script", value)
        if not all(item["pass"] for item in checks):
            raise AssertionError("Explicit locale tag corruption; see result.json")
        configure(True, "fr", "FR")
        french = measure()
        observations["french"] = french
        native_french = system_locale()
        observations["nativeFrench"] = native_french
        check(native_french == "fr-FR", "configured native default locale remains supported", native_french)
        check(french["result"][2]["max"] == "ja-Jpan-JP", "default locale changes preserve explicit tags", french)
        chrome("""
            const key='cloakfox.s.cloak_cfg_0',cfg=JSON.parse(Services.prefs.getStringPref(key));
            delete cfg['navigator.language'];delete cfg['locale:language'];delete cfg['locale:region'];
            Services.prefs.setStringPref(key,JSON.stringify(cfg));
            """)
        removed = system_locale()
        check(removed == observations["nativeBaseline"], "removing native default override clears stale value", removed)
        configure(True, "fr", "FR")
        check(system_locale() == "fr-FR", "native default override can be restored", system_locale())
        configure(False)
        restored = measure()
        observations["restored"] = restored
        check(system_locale() == observations["nativeBaseline"],
              "master off clears the previous native default override", restored)
        assert all(item["pass"] for item in checks), "Locale regression; see result.json"
        print(f"{len(checks)} checks passed; benchmark off/on milliseconds: "
              f"{observations['off']['benchmarkMs']:.2f}/{observations['on']['benchmarkMs']:.2f}")
    finally:
        driver.quit()
        (report / "result.json").write_text(json.dumps({"checks": checks, "observations": observations}, indent=2))


if __name__ == "__main__":
    main()
