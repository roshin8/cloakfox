"""Only verified GPU resources enter Gecko's install manifest."""
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'scripts' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_invalid_bundle_preserves_previous_stage(tmp_path):
    target = tmp_path / 'target'
    target.mkdir()
    (target / 'old').write_text('preserve')
    with pytest.raises((ValueError, FileNotFoundError)):
        load('stage-canonical-gpu').stage(tmp_path / 'missing', target)
    assert (target / 'old').read_text() == 'preserve'


def test_stage_installs_verified_notice_tree(tmp_path):
    build = load('build-canonical-gpu')
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    for name in build.LIBRARIES:
        (bundle / name).write_bytes(b'library')
    (bundle / 'notices').mkdir()
    (bundle / 'notices' / 'LICENSE.txt').write_text('license')
    (bundle / 'notices' / 'license-checker.cfg').write_text('config')
    build.write_integrity_manifest(bundle, {'rendererVersion': 1, 'platform': 'macos-arm64', 'hostRendererFallback': False, 'driverEnvironmentMutation': False, 'revisions': {'.': build.ANGLE_REVISION, 'third_party/SwiftShader': build.SWIFTSHADER_REVISION}})
    target = tmp_path / 'target'
    load('stage-canonical-gpu').stage(bundle, target)
    assert (target / 'notices/LICENSE.txt').read_text() == 'license'
    generated = (target / 'resources.mozbuild').read_text()
    assert 'FINAL_TARGET_FILES["canonical-gpu"]["notices"]' in generated
    assert 'manifest.json' in generated
    assert generated.index('notices/license-checker.cfg') < generated.index('notices/LICENSE.txt')
    build.verify_integrity_manifest(target)
