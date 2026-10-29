"""Audit opt-in prerequisites fail before fixture or browser work."""
import os
import unittest
from unittest.mock import patch

import probe_fingerprint_libraries as audit


class ReferenceLayoutPrerequisites(unittest.TestCase):
    def test_missing_dependencies_reject_before_launch_or_fixture_access(self):
        for profiles, pipeline in [('0', '0'), ('1', '0'), ('0', '1')]:
            with self.subTest(profiles=profiles, pipeline=pipeline), patch.dict(os.environ, {
                'LIBRARY_REFERENCE_LAYOUT': '1',
                'LIBRARY_CONTAINER_GPU_PROFILES': profiles,
                'CLOAKFOX_TEST_CANVAS_PIPELINE': pipeline,
            }), patch.object(audit.webdriver, 'Firefox') as launch, patch.object(audit, 'verify_fixtures') as fixtures:
                with self.assertRaisesRegex(ValueError, 'requires LIBRARY_CONTAINER_GPU_PROFILES'):
                    audit.main()
                launch.assert_not_called()
                fixtures.assert_not_called()
