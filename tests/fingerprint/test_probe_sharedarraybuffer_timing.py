"""Static contract checks for the SharedArrayBuffer timing probe."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))
import probe_sharedarraybuffer_timing as probe
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


class DistributionOrderTests(unittest.TestCase):
    def test_both_distribution_orders_map_to_distinct_execution_sequences(self) -> None:
        self.assertTrue(hasattr(probe, "distribution_masking_order"))
        self.assertEqual(
            probe.distribution_masking_order("disabled-first"), (False, True)
        )
        self.assertEqual(
            probe.distribution_masking_order("enabled-first"), (True, False)
        )

    def test_unknown_distribution_order_is_rejected(self) -> None:
        self.assertTrue(hasattr(probe, "distribution_masking_order"))
        with self.assertRaises(ValueError):
            probe.distribution_masking_order("unknown")


if __name__ == "__main__":
    unittest.main()
