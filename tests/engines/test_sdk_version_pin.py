"""Real CMake version gate: accept reviewed SDKs, refuse lookalike versions."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]

class SdkVersionPin(unittest.TestCase):
    def check(self,version,owned=False):
        with tempfile.TemporaryDirectory(prefix='cloakfox-sdk-pin-') as folder:
            sdk=Path(folder);(sdk/'include').mkdir()
            (sdk/'include/cef_version.h').write_text('#define CEF_VERSION "'+version+'"\n')
            (sdk/'include/cef_frame.h').write_text('#define CEF_CLOAKFOX_OWNED_IME_VERSION 1\n' if owned else '')
            return subprocess.run(['cmake','-DCEF_ROOT='+str(sdk),'-P',str(ROOT/'engines/chromium/cmake/VerifyCefVersion.cmake')],capture_output=True,text=True)
    def test_reviewed_upstream_and_native_api_sdk_versions(self):
        for version,owned in [('154.0.34+g14c5a08+chromium-154.0.8037.98',False),('154.2.34+g14c5a08+chromium-154.0.8037.98',True)]:
            result=self.check(version,owned);self.assertEqual(result.returncode,0,result.stderr)
    def test_unreviewed_same_major_other_revision_and_engine_versions_refuse(self):
        for version in ['154.3.34+g14c5a08+chromium-154.0.8037.98','154.2.34+gBAD+chromium-154.0.8037.98','154.2.34+g14c5a08+chromium-155.0.0.0','garbage']:
            result=self.check(version,True);self.assertNotEqual(result.returncode,0);self.assertIn('CEF version differs',result.stderr)
    def test_native_api_sdk_without_the_required_header_contract_refuses(self):
        result=self.check('154.2.34+g14c5a08+chromium-154.0.8037.98')
        self.assertNotEqual(result.returncode,0);self.assertIn('native editing contract',result.stderr)
