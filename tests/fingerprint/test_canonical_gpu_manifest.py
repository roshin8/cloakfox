"""Integrity checks for separately packaged canonical GPU artifacts."""
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]


def module():
    path = ROOT / 'scripts' / 'build-canonical-gpu.py'
    spec = importlib.util.spec_from_file_location('canonical_gpu_build', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def package_metadata(tool, directory):
    for name in tool.LIBRARIES:
        (directory / name).write_bytes(b'original')
    return {'rendererVersion': 1, 'platform': 'macos-arm64',
            'hostRendererFallback': False, 'driverEnvironmentMutation': False,
            'revisions': {'.': tool.ANGLE_REVISION,
                          'third_party/SwiftShader': tool.SWIFTSHADER_REVISION}}


def test_manifest_detects_changed_library(tmp_path):
    tool = module()
    library = tmp_path / 'libvk_swiftshader.dylib'
    library.write_bytes(b'original')
    tool.write_integrity_manifest(tmp_path, package_metadata(tool, tmp_path))
    tool.verify_integrity_manifest(tmp_path)
    library.write_bytes(b'changed')
    with pytest.raises(ValueError, match='digest mismatch'):
        tool.verify_integrity_manifest(tmp_path)


def test_manifest_rejects_parent_escape(tmp_path):
    tool = module()
    (tmp_path / 'manifest.json').write_text(json.dumps({'files': {'../outside': '0' * 64}}))
    with pytest.raises(ValueError, match='unsafe artifact path'):
        tool.verify_integrity_manifest(tmp_path)


def test_manifest_covers_notice_bytes_and_missing_files(tmp_path):
    tool = module()
    notices = tmp_path / 'notices'
    notices.mkdir()
    license = notices / 'LICENSE.txt'
    license.write_text('a required license')
    tool.write_integrity_manifest(tmp_path, package_metadata(tool, tmp_path))
    data = json.loads((tmp_path / 'manifest.json').read_text())
    assert 'notices/LICENSE.txt' in data['files']
    license.unlink()
    with pytest.raises(ValueError, match='missing artifact'):
        tool.verify_integrity_manifest(tmp_path)


def test_manifest_requires_the_complete_renderer_and_reviewed_identity(tmp_path):
    tool = module()
    tool.write_integrity_manifest(tmp_path, {'rendererVersion': 1})
    with pytest.raises(ValueError, match='required GPU library'):
        tool.verify_integrity_manifest(tmp_path)
