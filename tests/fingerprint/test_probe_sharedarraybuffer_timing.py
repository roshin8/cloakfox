"""Static contract checks for the SharedArrayBuffer timing probe."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))
from probe_sharedarraybuffer_timing import (
    TIMING_CONFIG_JSON,
    service_worker_scope_covers_client,
)


class TimingConfigTests(unittest.TestCase):
    def test_runtime_probe_starts_with_a_valid_nonzero_timing_key(self) -> None:
        config = json.loads(TIMING_CONFIG_JSON)
        self.assertNotEqual(config["timing:session_key_hi"], 0)
        self.assertNotEqual(config["timing:session_key_lo"], 0)
        self.assertIn("fonts", config)
        self.assertIn("fonts:spacing_seed", config)


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
