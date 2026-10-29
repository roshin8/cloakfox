"""Headless acceptance for the new159 native backend/layout; owned app only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'tests/fingerprint'))
import run_all

parser = argparse.ArgumentParser()
parser.add_argument('phase', choices=('native', 'regression', 'libraries', 'python'))
args = parser.parse_args()
evidence = root / 'docs/firefox-159/native-reference-layout'
output = root / 'tests/fingerprint/reports/firefox159-native-reference-layout'
output.mkdir(parents=True, exist_ok=True)
binary = root / 'firefox-src/.tools159/acceptance-native-reference-layout/Cloakfox.app/Contents/MacOS/cloakfox'
assert binary.is_file(), 'New self-contained Firefox159 app is missing'
assert json.loads((evidence / 'build-status.json').read_text())['state'] == 'built'
obj = root / 'firefox-src/obj-aarch64-apple-darwin'
env = dict(os.environ, MOZ_HEADLESS='1', MOZ_REMOTE_ALLOW_SYSTEM_ACCESS='1',
           LIBRARY_HEADLESS='1', CLOAKFOX_BIN=str(binary),
           GECKODRIVER='/opt/homebrew/bin/geckodriver',
           SE_GECKODRIVER='/opt/homebrew/bin/geckodriver',
           PROBE_REPORT_ROOT=str(output),
           ALPS_SERVER=str(root / 'firefox-src/.tools159/alps-fixture/alps-server'),
           MONACO_PROBE_ASSETS=str(root / 'firefox-src/.tools159/monaco-probe-assets'),
           POINTER_PROBE_INPUT='widget',
           FIREFOX_BIN=str(root / 'firefox-src/.tools159/stock159/Firefox.app/Contents/MacOS/firefox'),
           CLOAKFOX_XPCSHELL=str(obj / 'dist/bin/xpcshell'),
           CANONICAL_CODEC_SOURCE_DIR=str(root / 'firefox-src'),
           CANONICAL_CODEC_LIB_DIR=str(obj / 'dist/bin'),
           CLOAKFOX_CANONICAL_GPU_DIR=str(binary.parents[1] / 'Resources/canonical-gpu'))
for name in ('CLOAKFOX_HEADFUL', 'ALPS_CHROME_REFERENCE', 'SIGNATURE_CHROME_REFERENCE',
             'FIREFOX158_STOCK_ONLY', 'CLOAK_CONFIG', 'CLOAK_CONFIG_1'):
    env.pop(name, None)
os.environ.clear()
os.environ.update(env)
result = {'binary': str(binary), 'xulSHA256': hashlib.sha256((binary.parent / 'XUL').read_bytes()).hexdigest(),
          'phase': args.phase, 'headless': True, 'probes': []}


def execute(name, path, timeout=900):
    print('RUN', name, flush=True)
    started = time.monotonic()
    code, text = run_all.run_probe(path, timeout)
    (output / (name + '.log')).write_text(text)
    result['probes'].append({'probe': name, 'exitCode': code,
                             'seconds': round(time.monotonic() - started, 2)})
    (evidence / (args.phase + '-runtime.json')).write_text(json.dumps(result, indent=2) + '\n')
    print(name, code, flush=True)
    return code


if args.phase in ('native', 'regression'):
    probes = ['probe_gpu_reference_backend_admission.py', 'probe_gpu_reference_profiles.py',
              'probe_touch_document_policy.py', 'probe_canonical_geometry.py',
              'probe_container_rendering_settings.py'] if args.phase == 'native' else [
        'probe_container_gpu_profiles.py', 'probe_canvas_canonical_gpu.py',
        'probe_container_rendering_feasibility.py', 'probe_webgl_backend_profile.py',
        'probe_webgpu_canvas_owner.py', 'probe_canvas_owner_transfer.py',
        'probe_strict_graphics_settings.py', 'probe_graphics_optins_settings.py',
        'probe_graphics_privacy.py', 'probe_webgl_readback.py',
        'probe_dom_geometry_consistency.py', 'probe_font_metric_noise.py',
        'probe_container_fonts.py', 'probe_bundled_font_rendering.py',
        'probe_canvas_canonical_svg_golden.py', 'probe_canvas_canonical_adversarial.py',
        'probe_screen_presentation.py', 'probe_window_geometry_tz.py',
        'probe_canvas_canonical_text.py', 'probe_canvas_canonical_backing.py',
        'probe_canvas_canonical_fonts.py', 'probe_canvas_canonical_performance.py']
    for name in probes:
        if execute(name, root / 'tests/fingerprint' / name) and args.phase == 'native':
            break
elif args.phase == 'libraries':
    for canonical in ('0', '1'):
        mode = output / ('libraries-reference-layout-' + canonical)
        mode.mkdir(exist_ok=True)
        os.environ.clear()
        os.environ.update(env)
        os.environ.update(LIBRARY_WEBGPU_ENABLED='1', LIBRARY_CONTAINER_GPU_PROFILES=canonical,
                          CLOAKFOX_TEST_CANVAS_PIPELINE=canonical, LIBRARY_REFERENCE_LAYOUT=canonical,
                          REPORT_DIR=str(mode), PROBE_REPORT_ROOT=str(mode))
        execute(mode.name, root / 'tests/fingerprint/probe_fingerprint_libraries.py', 2100)
else:
    wrapper = output / 'all_pytest_runtime.py'
    wrapper.write_text("import pytest,sys\nfrom pathlib import Path\nroot=Path(" + repr(str(root)) + ")\n"
                       "sys.exit(pytest.main(['--noconftest','-q',*[str(p) for p in sorted((root/'tests/fingerprint').glob('test_*.py'))]]))\n")
    execute('all-python-tests', wrapper, 2100)
sys.exit(0 if all(row['exitCode'] == 0 for row in result['probes']) else 1)
