"""Repository and fixture integrity guards, with local Git only and no network."""
import hashlib
import importlib.util
import subprocess
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('fixture_setup', Path(__file__).resolve().parents[2] / 'scripts/setup-fingerprint-libraries.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()


def make_fixture(tmp_path):
    fixture = tmp_path / 'fixture'
    fixture.mkdir()
    git(fixture, 'init', '-q')
    git(fixture, 'remote', 'add', 'origin', 'https://github.com/abrahamjuliot/creepjs.git')
    (fixture / 'docs').mkdir()
    bundle = fixture / 'docs/creep.js'
    bundle.write_text('trusted fixture')
    git(fixture, 'add', 'docs/creep.js')
    git(fixture, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
    config = {'repository': 'https://github.com/abrahamjuliot/creepjs.git', 'commit': git(fixture, 'rev-parse', 'HEAD'),
              'bundle': 'docs/creep.js', 'bundleSHA256': hashlib.sha256(bundle.read_bytes()).hexdigest()}
    return fixture, config


def test_existing_non_repo_does_not_mutate_parent_checkout(tmp_path):
    git(tmp_path, 'init', '-q')
    fixture = tmp_path / 'fixture'
    fixture.mkdir()
    parent_head = (tmp_path / '.git/HEAD').read_bytes()
    with pytest.raises(RuntimeError, match='own Git directory'):
        setup.ensure_creep_fixture(fixture, {})
    assert (tmp_path / '.git/HEAD').read_bytes() == parent_head
    assert not (fixture / '.git').exists()
    assert git(tmp_path, 'remote') == ''


def test_modified_tracked_fixture_is_rejected(tmp_path):
    fixture, config = make_fixture(tmp_path)
    (fixture / 'docs/creep.js').write_text('modified')
    with pytest.raises(RuntimeError, match='Fixture is modified'):
        setup.ensure_creep_fixture(fixture, config)
    assert (fixture / 'docs/creep.js').read_text() == 'modified'


def test_untracked_fixture_shadow_is_rejected(tmp_path):
    fixture, config = make_fixture(tmp_path)
    (fixture / 'docs/worker.js').write_text('untrusted')
    with pytest.raises(RuntimeError, match='Fixture is modified'):
        setup.ensure_creep_fixture(fixture, config)


def test_wrong_origin_is_not_fetched_or_changed(tmp_path):
    fixture, config = make_fixture(tmp_path)
    git(fixture, 'remote', 'set-url', 'origin', 'https://example.invalid/untrusted.git')
    with pytest.raises(RuntimeError, match='Unexpected fixture origin'):
        setup.ensure_creep_fixture(fixture, config)
    assert git(fixture, 'rev-parse', 'HEAD') == config['commit']


def test_clean_fixture_checksum_is_enforced(tmp_path):
    fixture, config = make_fixture(tmp_path)
    setup.ensure_creep_fixture(fixture, config)
    with pytest.raises(RuntimeError, match='checksum mismatch'):
        setup.ensure_creep_fixture(fixture, {**config, 'bundleSHA256': '0' * 64})
