"""Firefox159 privileged automation is enabled only in disposable test jobs."""
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[2]
class RuntimeAccess(unittest.TestCase):
    def test_gecko_runtime_jobs_opt_in_to_upstream_automation_gate(self):
        for filename,job in [('build-macos.yml','fingerprint-tests'),('build-linux.yml','fingerprint-tests-linux')]:
            text=(ROOT/'.github/workflows'/filename).read_text()
            block=re.search(r'^  '+re.escape(job)+r':\n(.*?)(?=^  [a-zA-Z_][\w-]*:|\Z)',text,re.M|re.S).group(1)
            with self.subTest(workflow=filename):
                self.assertRegex(block,r'(?m)^      MOZ_REMOTE_ALLOW_SYSTEM_ACCESS: [\'\"]1[\'\"]$')

    def test_owned_headless_runner_overrides_inherited_desktop_and_artifact_settings(self):
        import os
        from unittest.mock import patch
        source=(ROOT/'docs/firefox-159/run-headless-acceptance.py').read_text()
        start=source.index('env=dict(os.environ,')
        end=source.index('identity=subprocess.run(',start)
        root=Path('/tmp/owned-gecko159')
        scope={'os':os,'root':root,'obj':root/'obj','binary':root/'obj/cloakfox','output':root/'reports'}
        inherited={'CLOAKFOX_HEADFUL':'1','POINTER_PROBE_INPUT':'desktop',
                   'CLOAKFOX_XPCSHELL':'/old/xpcshell','ALPS_CHROME_REFERENCE':'1'}
        with patch.dict(os.environ,inherited,clear=True):
            exec(source[start:end],scope)
        env=scope['env']
        self.assertEqual(env['MOZ_HEADLESS'],'1')
        self.assertEqual(env['LIBRARY_HEADLESS'],'1')
        self.assertEqual(env['MOZ_REMOTE_ALLOW_SYSTEM_ACCESS'],'1')
        self.assertEqual(env['POINTER_PROBE_INPUT'],'widget')
        self.assertNotIn('CLOAKFOX_HEADFUL',env)
        self.assertNotIn('ALPS_CHROME_REFERENCE',env)
        self.assertEqual(env['CLOAKFOX_XPCSHELL'],str(root/'obj/dist/bin/xpcshell'))
        self.assertEqual(env['CLOAKFOX_BIN'],str(root/'obj/cloakfox'))
