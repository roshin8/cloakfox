"""Disabled WebGPU must return safely, including actor-free blank frames.

Runs against CLOAKFOX_BIN using loopback pages and disposable profiles. Never
requests a GPU adapter/device or changes the installed app/user profile.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        worker = self.path == "/worker.js"
        body = (
            "const a=navigator.gpu;postMessage({type:typeof a,nonnull:a!==null,"
            "same:a===navigator.gpu});"
            if worker else "<!doctype html><title>WebGPU null safety</title><body>Local regression</body>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/javascript" if worker else "text/html")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *args):
        pass


def chrome(driver, script, *args):
    driver.set_context("chrome")
    try:
        return driver.execute_script(script, *args)
    finally:
        driver.set_context("content")


def read_getter(driver, token, target):
    result = driver.execute_script("""
        const n=arguments[0]==='page'?navigator:window.probeFrame.contentWindow.navigator;
        const desc=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(n),'gpu');
        if(!desc) return {missing:true};
        const a=desc.get.call(n), b=desc.get.call(n);
        window.savedGpu={get:desc.get,nav:n};
        return {type:typeof a,isNull:a===null,same:a===b};
    """, target)
    # A crashing getter can return a null WebDriver response without throwing.
    assert isinstance(result, dict), "GPU getter did not complete; possible content-process crash"
    assert driver.execute_script("return window.probeToken") == token, "Original document was lost"
    driver.execute_script("document.body.dataset.alive='yes'")
    assert driver.execute_script("return document.body.dataset.alive") == "yes"
    return result


def run_case(binary, root, case, enabled, disabled):
    log_path = root / f"{case}-gecko.log"
    results = []
    with tempfile.TemporaryDirectory(prefix="cloakfox-webgpu-profile-") as tmp:
        profile = Path(tmp, "profile")
        profile.mkdir()
        (profile / "user.js").write_text(
            f'user_pref("cloakfox.enabled", {str(enabled).lower()});\n'
            'user_pref("dom.webgpu.enabled", true);\n'
        )
        options = Options()
        options.binary_location = binary
        if os.environ.get("CLOAKFOX_HEADFUL") != "1":
            options.add_argument("-headless")
        options.add_argument("-profile")
        options.add_argument(str(profile))
        driver = webdriver.Firefox(options=options, service=Service(
            service_args=["--allow-system-access"], log_output=str(log_path)))
        driver.set_script_timeout(15)
        try:
            config = chrome(driver, """
                const key='cloakfox.s.cloak_cfg_0';
                const cfg=JSON.parse(Services.prefs.getStringPref(key,'{}'));
                cfg['navigator:webgpu:disabled']=arguments[0];
                Services.prefs.setStringPref(key,JSON.stringify(cfg));
                return cfg['navigator:webgpu:disabled'];
            """, disabled)
            assert config == disabled
            driver.get(URL)
            token = str(uuid.uuid4())
            driver.execute_script("window.probeToken=arguments[0]", token)
            for kind in ("page", "blank", "srcdoc", "navigated"):
                if kind != "page":
                    driver.execute_async_script("""
                        const [kind,url,done]=arguments;
                        window.probeFrame?.remove();
                        const f=document.createElement('iframe');window.probeFrame=f;
                        f.onload=()=>done(true);
                        if(kind==='srcdoc')f.srcdoc='<!doctype html><body>srcdoc</body>';
                        else f.src=kind==='blank'?'about:blank':url+'frame';
                        document.body.append(f);
                    """, kind, URL)
                result = read_getter(driver, token, kind)
                assert not result.get("missing"), f"{case}/{kind}: GPU binding missing"
                if not enabled or (kind == "blank" and not disabled):
                    assert result == {"type": "object", "isNull": False, "same": True}, result
                elif kind == "blank":
                    assert result == {"type": "object", "isNull": True, "same": True}, result
                elif disabled:
                    # Existing page actors hide GPU; the native disabled return
                    # is null in any realm the actor doesn't reach.
                    assert result["type"] == "undefined" or result["isNull"], f"{kind}: {result}"
                else:
                    # The enabled control may retain the actor's undefined
                    # presentation or expose the enabled native GPU instance.
                    assert result["type"] == "undefined" or result == {
                        "type": "object", "isNull": False, "same": True
                    }, f"{kind}: {result}"
                results.append({"realm": kind, "value": result})
                if kind == "blank":
                    descriptor = driver.execute_script("""
                        const n=probeFrame.contentWindow.navigator;
                        const getter=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(n),'gpu').get;
                        let rejected=false;
                        try {getter.call({});} catch(e) {rejected=e.name==='TypeError';}
                        return {native:getter.toString().includes('[native code]'),rejected};
                    """)
                    assert descriptor == {"native": True, "rejected": True}, descriptor
                    results.append({"realm": "blank-descriptor", "value": descriptor})
                    driver.execute_async_script("""
                        const [url,done]=arguments;
                        window.probeFrame.onload=()=>done(true);window.probeFrame.src=url+'after';
                    """, URL)
                    saved = driver.execute_script("""
                        try {const a=savedGpu.get.call(savedGpu.nav);
                             return {complete:true,type:typeof a,isNull:a===null};}
                        catch(e){return {complete:true,error:e.name};}
                    """)
                    assert isinstance(saved, dict) and saved.get("complete"), "Saved getter crashed after navigation"
                    assert driver.execute_script("return window.probeToken") == token
                    results.append({"realm": "saved-after-navigation", "value": saved})
                    fresh = read_getter(driver, token, "frame")
                    assert not fresh.get("missing"), fresh
                    if not enabled:
                        assert fresh == {"type": "object", "isNull": False, "same": True}, fresh
                    elif disabled:
                        assert fresh["type"] == "undefined" or fresh["isNull"], fresh
                    else:
                        assert fresh["type"] == "undefined" or fresh == {
                            "type": "object", "isNull": False, "same": True
                        }, fresh
                    results.append({"realm": "fresh-after-navigation", "value": fresh})
            worker = driver.execute_async_script("""
                const done=arguments[0], w=new Worker('/worker.js');
                w.onmessage=e=>{w.terminate();done(e.data)};
                w.onerror=e=>{w.terminate();done({error:e.message})};
            """)
            assert worker == {"type": "object", "nonnull": True, "same": True}, worker
            results.append({"realm": "worker", "value": worker})
            WebDriverWait(driver, 5).until(lambda d: d.execute_script("return window.probeToken") == token)
        finally:
            driver.quit()
    log = log_path.read_text()
    assert "exited on signal 11" not in log and "EXC_BAD_ACCESS" not in log, "Native child process crashed"
    return results


def main():
    global URL
    binary = os.environ["CLOAKFOX_BIN"]
    root = Path(os.environ.get("REPORT_DIR") or tempfile.mkdtemp(prefix="cloakfox-webgpu-report-"))
    root.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    URL = f"http://127.0.0.1:{server.server_port}/"
    report = {"binary": binary, "cases": {}}
    try:
        for case, enabled, disabled in (("master-off", False, True),
                                        ("master-on-disabled", True, True),
                                        ("master-on-native-enabled", True, False)):
            try:
                report["cases"][case] = run_case(binary, root, case, enabled, disabled)
                print("PASS " + case, flush=True)
            except Exception as error:
                report["cases"][case] = {"error": str(error)}
                print("FAIL " + case + ": " + str(error), flush=True)
                raise
    finally:
        server.shutdown()
        server.server_close()
        (root / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        print("Report: " + str(root), flush=True)


if __name__ == "__main__":
    main()
