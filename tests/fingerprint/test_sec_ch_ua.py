"""Native channel hints: actual local TLS, disposable profile, no warmup."""
import os
import pytest
from runtimeprobe_client_hints_headers import run_probe

@pytest.mark.skipif(not os.environ.get('CLOAKFOX_BIN'), reason='CLOAKFOX_BIN required')
def test_native_client_hints_headers():
    report = run_probe()
    assert all(check['pass'] for check in report['checks']), report
