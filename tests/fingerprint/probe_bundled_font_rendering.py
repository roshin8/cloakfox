#!/usr/bin/env python3
"""Desktop glyph regression fixture, including browser chrome.

Run with CLOAKFOX_BIN and CLOAKFOX_HEADFUL=1. Inspect the native window while
it remains open (CLOAKFOX_PREVIEW_SECONDS, default 45). Each family has two
identical lines: the registered bundled face and a webfont loaded from the
same bundled file. They must look identical, including dots, multiplication
signs and fi/ff ligatures. Without the renderer IPC fix, the native chrome
lines have wrong/missing glyphs even though WebDriver screenshots look fine.

Automated checks only cover fixture text, font readiness and reference widths.
Native compositor verification requires a desktop capture/visual inspection;
do not count an ordinary WebDriver screenshot as verification of that path.
Profiles are disposable. No installed profile is changed.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

from probe_bundled_fonts import fonts_dir_for
from probe_focus_masking import chrome

FAMILIES = {"Helvetica": "Helvetica.ttf", "Menlo": "Menlo.ttf",
            "Arial": "Arial.ttf", "Times New Roman": "TimesNewRoman.ttf"}
TEXT = "Linux x86_64 · 1536×864@1.25x — fi ff ffi files offline Graphics"


def fixture(fonts):
    styles = ["body{margin:0;background:white;color:black}"
              "#glyph-fixture{position:fixed;inset:0;z-index:2147483647;"
              "background:white;padding:12px;overflow:auto}"
              ".sample{font-size:24px;line-height:36px;white-space:nowrap;"
              "font-kerning:none;letter-spacing:0}"
              "h2{font:16px sans-serif;margin:12px 0 0}"]
    rows = []
    for i, (family, filename) in enumerate(FAMILIES.items()):
        data = base64.b64encode((fonts / filename).read_bytes()).decode()
        reference = f"GlyphReference{i}"
        styles.append(f"@font-face{{font-family:{reference};"
                      f"src:url(data:font/ttf;base64,{data})}}")
        rows.append(f"<h2>{family}: registered / exact-file reference</h2>")
        for name in [family, reference]:
            rows.append(f'<div class="sample" style="font-family:\'{name}\'">'
                        f'<span>{TEXT}</span></div>')
    return '<style>' + ''.join(styles) + '</style><section id="glyph-fixture">' + ''.join(rows) + '</section>'


def main():
    binary = os.environ["CLOAKFOX_BIN"]
    fonts = fonts_dir_for(binary)
    assert fonts, "Bundled font directory missing"
    headful = os.environ.get("CLOAKFOX_HEADFUL") == "1"
    with tempfile.TemporaryDirectory(prefix="cloakfox-glyphs-") as tmp:
        opts = Options()
        opts.binary_location = binary
        opts.add_argument("-profile")
        opts.add_argument(tmp)
        if not headful:
            opts.add_argument("-headless")
        opts.set_preference("cloakfox.s.cloak_cfg_0", json.dumps({
            # The font-table allowlist also applies to custom webfont family
            # names. Explicitly allow the test references so an enabled run
            # cannot silently compare fallback faces after a load error.
            "fonts": sorted([*FAMILIES, *(f"GlyphReference{i}" for i in range(4))]),
            "fonts:spacing_seed": 0,
            "canvas:seed": 0, "font:seed": 0,
        }))
        driver = webdriver.Firefox(options=opts, service=Service(
            shutil.which("geckodriver"), service_args=["--allow-system-access"],
            log_output=str(Path(tmp) / "gecko.log")))
        try:
            driver.set_window_size(1200, 900)
            for enabled in [False, True]:
                chrome(driver, 'Services.prefs.setBoolPref("cloakfox.enabled",arguments[0])', enabled)
                for page in ["data:text/html,<meta charset=utf-8>", "about:cloakfox"]:
                    driver.get(page)
                    driver.execute_script('document.body.innerHTML=arguments[0]', fixture(fonts))
                    driver.execute_async_script('document.fonts.ready.then(arguments[0])')
                    faces = driver.execute_script('return [...document.fonts].filter(f=>f.family.startsWith("GlyphReference")).map(f=>f.status)')
                    assert len(faces) == 4 and all(s == "loaded" for s in faces), faces
                    values = driver.execute_script('return [...document.querySelectorAll(".sample span")].map(e=>({text:e.textContent,width:e.getBoundingClientRect().width}))')
                    assert len(values) == 8 and all(v['text'] == TEXT for v in values), values
                    for a, b in zip(values[::2], values[1::2]):
                        assert abs(a['width'] - b['width']) < .1, values
                    print(f"PASS fixture text/reference widths: {page.split(':')[0]}, master={enabled}", flush=True)
                    if headful:
                        print("Inspect native desktop glyph pairs now; WebDriver captures bypass the failure.", flush=True)
                        time.sleep(float(os.environ.get("CLOAKFOX_PREVIEW_SECONDS", "45")))
            if not headful:
                print("Native compositor NOT checked: rerun with CLOAKFOX_HEADFUL=1.")
        finally:
            driver.quit()


if __name__ == "__main__":
    main()
