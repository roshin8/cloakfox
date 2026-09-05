"""Static contract checks for the SharedArrayBuffer timing probe."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))
from probe_sharedarraybuffer_timing import service_worker_scope_covers_client


class ServiceWorkerScopeTests(unittest.TestCase):
    def test_default_fixture_scope_does_not_control_root_client(self) -> None:
        self.assertFalse(
            service_worker_scope_covers_client(
                "/fixtures/sab-service-worker.js", "/"
            )
        )

    def test_default_fixture_scope_controls_fixture_client(self) -> None:
        self.assertTrue(
            service_worker_scope_covers_client(
                "/fixtures/sab-service-worker.js", "/fixtures/probe.html"
            )
        )


if __name__ == "__main__":
    unittest.main()
