"""Firefox158 typed CSS arithmetic and native JPEG XL decode compatibility.

Run with CLOAKFOX_BIN; FIREFOX158_STOCK_ONLY=1 and FIREFOX_BIN measure stock
instead. No feature prefs are overridden. The JPEG XL fixture is copied from
Firefox158 image/test/gtest/green.jxl (GreenJXLTestCase:100x100 green pixels).
Both master states use separate disposable profiles and application-data roots.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

FIXTURE = Path(__file__).with_name("fixtures") / "firefox158-green.jxl"


class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        image = self.path == "/green.jxl"
        body = FIXTURE.read_bytes() if image else b"<!doctype html><title>Firefox158 compatibility</title>"
        self.send_response(200)
        self.send_header("Content-Type", "image/jxl" if image else "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


PROBE = """
const done=arguments[0];
(async()=>{
  const arithmetic=[];
  for(const [expression,expected] of [
    ['calc(120px / 3px * 1px)',40],
    ['calc(10px * 6px / 2px)',30],
    ['calc(20px * (2s / 500ms))',80]]) {
    const element=document.createElement('div');
    element.style.cssText='position:absolute;height:10px';
    element.style.width=expression;document.body.append(element);
    arithmetic.push({expression,expected,supported:CSS.supports('width',expression),
      computed:getComputedStyle(element).width,width:element.getBoundingClientRect().width,offsetWidth:element.offsetWidth});
    element.remove();
  }
  const image=new Image();image.src='/green.jxl';await image.decode();
  const bitmap=await createImageBitmap(image);
  function draw(source){
    const canvas=document.createElement('canvas');canvas.width=canvas.height=100;
    const ctx=canvas.getContext('2d');ctx.drawImage(source,0,0);
    return {canvas,pixel:Array.from(ctx.getImageData(50,50,1,1).data)};
  }
  const direct=draw(image),fromBitmap=draw(bitmap);
  const exported=new Image();exported.src=direct.canvas.toDataURL('image/png');
  await exported.decode();const roundtrip=draw(exported);
  const result={arithmetic,image:[image.naturalWidth,image.naturalHeight],
    bitmap:[bitmap.width,bitmap.height],exported:[exported.naturalWidth,exported.naturalHeight],
    pixels:{direct:direct.pixel,bitmap:fromBitmap.pixel,roundtrip:roundtrip.pixel}};
  bitmap.close();return result;
})().then(done,error=>done({error:String(error)}));
"""


def main():
    stock = os.environ.get("FIREFOX158_STOCK_ONLY") == "1"
    binary = os.environ["FIREFOX_BIN" if stock else "CLOAKFOX_BIN"]
    driver_binary = os.environ.get("GECKODRIVER") or shutil.which("geckodriver")
    assert driver_binary, "Set GECKODRIVER or install geckodriver"
    server = ThreadingHTTPServer(("127.0.0.1", 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    report = {"stockOnly": stock, "cases": []}
    try:
        for enabled in (False, True):
            with tempfile.TemporaryDirectory(prefix="cloakfox158-features-") as temp:
                root = Path(temp)
                profile = root / "profile"
                profile.mkdir()
                options = Options()
                options.binary_location = binary
                options.add_argument("-headless")
                options.add_argument("-purgecaches")
                options.add_argument("-profile")
                options.add_argument(str(profile))
                options.set_preference("cloakfox.enabled", enabled)
                options.set_preference("cloakfox.s.cloak_cfg_0", json.dumps({"canvas:seed": 12345}))
                service = Service(executable_path=driver_binary,
                    service_args=["--allow-system-access"], log_output=str(root / "gecko.log"),
                    env={**os.environ, "MOZ_APP_DATA": str(root / "app-data"),
                         "MOZ_LOCAL_APP_DATA": str(root / "local-data")})
                driver = webdriver.Firefox(options=options, service=service)
                try:
                    driver.set_page_load_timeout(20)
                    driver.set_script_timeout(20)
                    driver.set_context("chrome")
                    identity = driver.execute_script("""const cfg=JSON.parse(
                      Services.prefs.getStringPref('cloakfox.s.cloak_cfg_0','{}'));
                      let validSecret=false;try{validSecret=typeof cfg['fingerprint:secret']==='string'&&
                        atob(cfg['fingerprint:secret']).length===32}catch{}
                      return {name:Services.appinfo.name,version:Services.appinfo.version,
                        buildID:Services.appinfo.appBuildID,
                        enabled:Services.prefs.getBoolPref('cloakfox.enabled'),
                        mask:{canvasSeed:cfg['canvas:seed'],validSecret,
                          policy:cfg['privacy:policy']??null}};""")
                    assert identity["name"] == ("Firefox" if stock else "Cloakfox"), identity
                    assert identity["version"].startswith("158."), identity
                    assert identity["enabled"] is enabled, identity
                    protected = enabled and not stock
                    if protected:
                        assert identity["mask"]["canvasSeed"] == 12345, identity
                        assert identity["mask"]["validSecret"], identity
                        assert identity["mask"]["policy"]["preset"] in ("standard", "strict"), identity
                        assert identity["mask"]["policy"]["exceptions"] == [], identity
                    driver.set_context("content")
                    driver.get(f"http://127.0.0.1:{server.server_port}/")
                    result = driver.execute_async_script(PROBE)
                    assert "error" not in result, result
                    for item in result["arithmetic"]:
                        assert item["supported"], item
                        assert item["computed"] == f"{item['expected']}px", item
                        # Native layout reads are intentionally presented with
                        # bounded geometry noise when protection is active.
                        # Keep grammar/computed-width checks exact; require both
                        # rendered measurements to obey their production bounds.
                        assert abs(item["width"] - item["expected"]) <= (0.20001 if protected else 0), item
                        assert abs(item["offsetWidth"] - item["expected"]) <= (1 if protected else 0), item
                    assert result["image"] == result["bitmap"] == result["exported"] == [100, 100], result
                    for route, pixel in result["pixels"].items():
                        # Seeded canvas noise may perturb RGB. Decode/render must
                        # retain solid green content and exact opaque alpha.
                        assert pixel[0] < 40 and pixel[1] > 215 and pixel[2] < 40 and pixel[3] == 255, (route, pixel)
                        if not enabled:
                            assert pixel == [0, 255, 0, 255], (route, pixel)
                    report["cases"].append({"browser": identity, "result": result})
                    print(json.dumps(report["cases"][-1]), flush=True)
                finally:
                    driver.quit()
    finally:
        server.shutdown()
        server.server_close()
    destination = os.environ.get("FIREFOX158_FEATURE_REPORT")
    if destination:
        Path(destination).write_text(json.dumps(report, indent=2) + "\n")
    print("PASS — Firefox158 typed CSS arithmetic, JPEG XL image/bitmap/canvas decode with both master states")


if __name__ == "__main__":
    main()
