"""Cold first-draw glyph regression with operator/pixel evidence.

Uses the fixed Linux persona that reproduced the bug. Each launch has a fresh,
then deleted profile. The async override is solely a causal diagnostic control;
acceptance must use the default true value, with no warmup/retry of failed draws.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import ThreadingHTTPServer
from PIL import Image
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_canvas_consistency import Page
from probe_canvas_render_privacy import PROBE

SEED = 'S0xF6Xe/aX3WSHGxfhL9OCXvLEebp0Rl1gm5Vl9+NTw='
OPERATORS = ["x.fillRect(0,0,240,100);", "x.fillText('Arbitrary ink Ω',4.3,29.7);",
             "x.strokeText('مرحبا שלום',220.4,59.2,135);",
             "x.fillText('Color 😀',14.2,87.3,120);", "x.fillText('bounded',130,85,31);"]


def instrumented_probe():
    # Keep the original glyph sample and its draw ordering authoritative.
    script = PROBE.replace(" x.fillStyle='#87a2bc';", " const snapshots=[]; function snap(op){snapshots.push({op,bytes:Array.from(x.getImageData(0,0,240,100).data)});} x.fillStyle='#87a2bc';")
    for operator in OPERATORS:
        script = script.replace(operator, operator + 'snap(' + json.dumps(operator) + ');')
    return script.replace('return {hash:hash.toString(16),', 'return {snapshots,hash:hash.toString(16),')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--async-fallback', choices=['true', 'false'], default='true')
    parser.add_argument('--report', type=Path, default=Path('/tmp/cloakfox-first-glyph/report.json'))
    args = parser.parse_args()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    binary = Path(os.environ['CLOAKFOX_BIN']).resolve()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    report = {'binary': str(binary), 'seed': SEED, 'asyncFallback': args.async_fallback, 'runs': []}
    try:
        for run in range(args.runs):
            with tempfile.TemporaryDirectory(prefix='cloakfox-first-glyph-') as profile:
                options = Options(); options.binary_location = str(binary)
                for arg in ['-headless', '-profile', profile, '-purgecaches']:
                    options.add_argument(arg)
                options.set_preference('cloakfox.experimental.canvas_pipeline', True)
                options.set_preference('gfx.font_rendering.fallback.async', args.async_fallback == 'true')
                Path(profile, 'user.js').write_text('user_pref("cloakfox.enabled",true);\nuser_pref("cloakfox.container.0.math_seed",' + json.dumps(SEED) + ');\n')
                driver = webdriver.Firefox(options=options, service=Service(os.environ.get('GECKODRIVER', '/opt/homebrew/bin/geckodriver'), service_args=['--allow-system-access'], log_output=str(args.report.parent / f'gecko-{run}.log')))
                driver.set_script_timeout(30)
                try:
                    driver.set_context('chrome')
                    config = driver.execute_script("Services.prefs.setBoolPref('cloakfox.opt.canvas_render_privacy',false);const key='cloakfox.s.cloak_cfg_0';const cfg=JSON.parse(Services.prefs.getStringPref(key,'{}'));cfg['canvas:render_privacy']=false;Services.prefs.setStringPref(key,JSON.stringify(cfg));return cfg;")
                    runtime = driver.execute_script('return {buildID:Services.appinfo.appBuildID,version:Services.appinfo.version};')
                    driver.set_context('content'); driver.get(f'http://127.0.0.1:{server.server_port}/')
                    result = driver.execute_async_script(instrumented_probe())
                    assert 'error' not in result, result
                    entries = result['results']
                    first, later = entries['html'], entries['offscreen']
                    comparisons = []
                    for a, b in zip(first['snapshots'], later['snapshots']):
                        left, right = bytes(a['bytes']), bytes(b['bytes'])
                        differing = [i for i, (x, y) in enumerate(zip(left, right)) if x != y]
                        pixels = {(i // 4 % 240, i // 4 // 240) for i in differing}
                        comparisons.append({'operator': a['op'], 'differentChannels': len(differing), 'bounds': [min(x for x,y in pixels), min(y for x,y in pixels), max(x for x,y in pixels), max(y for x,y in pixels)] if pixels else None, 'firstSHA256': hashlib.sha256(left).hexdigest(), 'laterSHA256': hashlib.sha256(right).hexdigest()})
                    for kind in ['html', 'offscreen']:
                        Image.frombytes('RGBA', (240,100), bytes(entries[kind]['snapshots'][-1]['bytes'])).save(args.report.parent / f'run-{run}-{kind}.png')
                    report['runs'].append({'run':run, 'runtime':runtime, 'config':config, 'pass':first['hash']==later['hash'], 'hashes':{k:v['hash'] for k,v in entries.items()}, 'operators':comparisons})
                    print(json.dumps({'run':run, 'pass':report['runs'][-1]['pass'], 'operators':comparisons}), flush=True)
                    args.report.write_text(json.dumps(report, indent=2))
                finally:
                    driver.quit()
    finally:
        server.shutdown()
    return 0 if all(run['pass'] for run in report['runs']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
