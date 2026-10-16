#!/usr/bin/env python3
"""Run the actual engine suite; missing native coverage is a failure in CI."""
import os
from pathlib import Path
import sys
import unittest


def run_suite(suite, stream):
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    allowed = {
        # Full Xcode is deliberately selected on CI; CLT-only characterization
        # is a separate developer-tool compatibility test, not browser coverage.
        'native CLT characterization requires CLT selected',
        # Source hash/replay validation runs in the source job. The runtime job
        # downloads only the same-run app, not a second 60+ GiB source tree.
        'Requires local pinned native source for replay check',
    }
    unexpected = [(str(test), reason) for test, reason in result.skipped if reason not in allowed]
    if unexpected:
        print('ERROR: runtime coverage skipped:', unexpected, file=stream)
    return result.wasSuccessful() and result.testsRun > 0 and not unexpected


def main():
    root = Path(__file__).resolve().parents[2]
    for name in ('CLOAKFOX_CHROMIUM_BIN', 'CLOAKFOX_UNPATCHED_CHROMIUM_BIN'):
        if not Path(os.environ.get(name, '/missing-native-binary')).is_file():
            raise SystemExit('Missing required built binary: ' + name)
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / 'tests/engines'))
    suite = unittest.defaultTestLoader.discover(str(root / 'tests/engines'), pattern='test_*.py')
    raise SystemExit(0 if run_suite(suite, sys.stdout) else 1)


if __name__ == '__main__':
    main()
