import importlib.util
import json
from pathlib import Path
from unittest.mock import patch
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('engine_artifact', ROOT / 'scripts/ci/engine_artifact.py')
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class EngineArtifact(unittest.TestCase):
    def git(self, root, *args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()

    def commit(self, root):
        self.git(root, 'add', '.')
        self.git(root, '-c', 'user.name=Fixture', '-c', 'user.email=f@invalid', 'commit', '-qm', 'fixture')

    def test_committed_engine_key_ignores_client_and_dirty_changes_but_tracks_patch_and_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.git(root, 'init', '-q')
            (root / 'engines/chromium/patches').mkdir(parents=True)
            (root / 'engines/chromium/src').mkdir()
            patch = root / 'engines/chromium/patches/native.patch'
            patch.write_text('native')
            client = root / 'engines/chromium/src/client.cc'
            client.write_text('app')
            self.commit(root)
            key = api.input_key(root, 'chromium')
            patch.write_text('dirty')
            self.assertEqual(key, api.input_key(root, 'chromium'))
            patch.write_text('native')
            client.write_text('new app')
            self.commit(root)
            self.assertEqual(key, api.input_key(root, 'chromium'))
            patch.write_text('new native')
            self.commit(root)
            self.assertNotEqual(key, api.input_key(root, 'chromium'))

    def test_gecko_key_includes_bundled_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.git(root, 'init', '-q')
            (root / 'additions').mkdir()
            asset = root / 'additions/extension.js'
            asset.write_text('old')
            self.commit(root)
            before = api.input_key(root, 'gecko')
            asset.write_text('new')
            self.commit(root)
            self.assertNotEqual(before, api.input_key(root, 'gecko'))

    def test_gecko_key_includes_font_bundle_and_chromium_key_tracks_executable_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.git(root,'init','-q')
            (root/'bundle/fonts').mkdir(parents=True)
            font=root/'bundle/fonts/font.ttf';font.write_bytes(b'font')
            (root/'engines/chromium/patches').mkdir(parents=True)
            native=root/'engines/chromium/patches/a.patch';native.write_bytes(b'patch')
            self.commit(root)
            before=api.input_key(root,'gecko');chromium=api.input_key(root,'chromium')
            font.write_bytes(b'new font');self.commit(root)
            self.assertNotEqual(before,api.input_key(root,'gecko'))
            native.chmod(0o755);self.commit(root)
            self.assertNotEqual(chromium,api.input_key(root,'chromium'))

    def test_gecko_current_source_dependent_regressions_invalidate_old_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.git(root,'init','-q')
            (root/'tests/fingerprint').mkdir(parents=True)
            source_test=root/'tests/fingerprint/test_source.mjs';source_test.write_text('old assertion')
            self.commit(root);before=api.input_key(root,'gecko')
            source_test.write_text('new firefox-src assertion');self.commit(root)
            self.assertNotEqual(before,api.input_key(root,'gecko'))

    def test_resolver_ignores_expired_untrusted_and_wrong_engine_completion(self):
        run={'repository':{'full_name':'roshin8/cloakfox'},'head_repository':{'full_name':'roshin8/cloakfox'},
             'event':'push','head_branch':'codex/firefox-158-port','head_sha':'b'*40,
             'path':'.github/workflows/build-macos.yml'}
        name='chromium-macos-arm64-'+'a'*64
        items=[{'name':name,'expired':True,'id':1,'workflow_run':{'id':11,'head_sha':'b'*40}},
               {'name':name,'expired':False,'id':2,'workflow_run':{'id':22,'head_sha':'b'*40}},
               {'name':name,'expired':False,'id':3,'workflow_run':{'id':33,'head_sha':'b'*40}}]
        def fake(path):
            if '/actions/artifacts?' in path:return {'artifacts':items}
            if path.endswith('/22'):return {**run,'event':'pull_request'}
            if path.endswith('/33'):return run
            return {'jobs':[{'name':'build-macos / gecko-engine-complete','status':'completed','conclusion':'success'},
                            {'name':'chromium / engine / chromium-engine-complete','status':'completed','conclusion':'failure'}]}
        with patch.object(api,'api',fake):
            self.assertEqual(api.find('roshin8/cloakfox','chromium','a'*64),{'found':'false','key':'a'*64})
        def success(path):
            if '/jobs?' in path:return {'jobs':[{'name':'chromium / engine / chromium-engine-complete','status':'completed','conclusion':'success'}]}
            return fake(path)
        with patch.object(api,'api',success):
            self.assertEqual(api.find('roshin8/cloakfox','chromium','a'*64)['artifact-id'],'3')

    def test_seal_verifies_exact_payload_key_producer_and_consumer_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'sdk.tar.gz').write_bytes(b'fixture')
            api.seal(root, 'chromium', 'a'*64, 'b'*40, '123')
            record = api.verify(root, 'chromium', 'a'*64, 'b'*40, '123')
            self.assertEqual(record['producerSha'], 'b'*40)
            for field, value in [('kind','gecko'),('key','c'*64),('producerSha','d'*40),('producerRun','456')]:
                with self.subTest(field=field), self.assertRaises(ValueError):
                    args = dict(kind='chromium',key='a'*64,producerSha='b'*40,producerRun='123')
                    args[field] = value
                    api.verify(root, args['kind'], args['key'], args['producerSha'], args['producerRun'])
            (root / 'extra').write_text('unexpected')
            with self.assertRaises(ValueError):api.verify(root,'chromium','a'*64,'b'*40,'123')
            (root / 'extra').unlink()
            (root / 'sdk.tar.gz').write_bytes(b'changed')
            with self.assertRaises(ValueError):api.verify(root,'chromium','a'*64,'b'*40,'123')

    def test_symlink_payload_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'outside').symlink_to('/etc/hosts')
            with self.assertRaises(ValueError):api.seal(root,'gecko','a'*64,'b'*40,'1')

    def test_only_repository_owned_trusted_push_or_manual_producers(self):
        run = {'repository':{'full_name':'roshin8/cloakfox'},'head_repository':{'full_name':'roshin8/cloakfox'},
               'event':'push','head_branch':'codex/firefox-158-port','head_sha':'a'*40,
               'path':'.github/workflows/build-macos.yml'}
        self.assertTrue(api.trusted_run(run,'roshin8/cloakfox','chromium'))
        for change in ({'event':'pull_request'},{'head_branch':'untrusted'},{'path':'.github/workflows/test.yml'},
                       {'head_repository':{'full_name':'other/fork'}}):
            with self.subTest(change=change):self.assertFalse(api.trusted_run({**run,**change},'roshin8/cloakfox','chromium'))

    def test_completed_engine_gate_required_even_if_unrelated_parent_failed(self):
        self.assertTrue(api.completed_gate([{'name':'chromium / engine / chromium-engine-complete','conclusion':'success','status':'completed'}],'chromium'))
        for conclusion in ('failure','skipped',None):
            self.assertFalse(api.completed_gate([{'name':'chromium / engine / chromium-engine-complete','conclusion':conclusion,'status':'completed'}],'chromium'))
        self.assertFalse(api.completed_gate([{'name':'unit-tests','conclusion':'success','status':'completed'}],'chromium'))

if __name__ == '__main__':unittest.main()
