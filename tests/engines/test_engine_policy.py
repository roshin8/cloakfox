"""Engine intent is constrained by real backend identity, not UA substitution."""
import unittest
from engines.shared.engine_policy import backend_container_id, resolve_engine

VERSIONS={'gecko':'158.0.26','chromium':'154.0.8037.98'}
FIREFOX='Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:158.0) Gecko/20100101 Firefox/158.0'
CHROME='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'

class EngineIntent(unittest.TestCase):
    def test_real_families_select_their_backend(self):
        self.assertEqual(resolve_engine(FIREFOX,VERSIONS),'gecko')
        self.assertEqual(resolve_engine(CHROME,VERSIONS),'chromium')
        self.assertEqual(resolve_engine(CHROME.replace('Chrome/','Chromium/'),VERSIONS),'chromium')
        self.assertEqual(resolve_engine(CHROME.replace('154.0.0.0','154.0.8037.98'),VERSIONS),'chromium')

    def test_unsupported_brands_versions_and_ambiguous_identity_fail(self):
        for ua in [CHROME+' Edg/154.0.0.0',CHROME+' OPR/154.0.0.0',
                   CHROME+' Firefox/158.0',CHROME+' Chrome/154.0.0.0',
                   CHROME.replace('154.0.0.0','153.0.0.0'),
                   CHROME.replace('154.0.0.0','154.0.8037.99'),
                   CHROME.replace('154.0.0.0','154.1.0.0'),
                   FIREFOX.replace('Firefox/158.0','Firefox/157.0'),
                   FIREFOX.replace('Firefox/158.0','Firefox/158.0.27'),
                   'Chrome/154.0.0.0 trailing\n', '',None,True]:
            with self.subTest(ua=ua),self.assertRaises(ValueError):resolve_engine(ua,VERSIONS)

    def test_missing_or_invalid_installed_version_fails(self):
        for versions in [{}, {'gecko':'158.0.26'}, {**VERSIONS,'chromium':True},
                         {**VERSIONS,'chromium':'154.bad'}, {**VERSIONS,'unexpected':'1.0'}]:
            with self.subTest(versions=versions),self.assertRaises(ValueError):resolve_engine(CHROME,versions)

    def test_default_and_real_container_never_alias(self):
        self.assertEqual(backend_container_id(0),'1')
        self.assertEqual(backend_container_id(1),'2')
        self.assertEqual(backend_container_id(2147483646),'2147483647')
        for value in [-1,True,False,1.0,'0',None,2147483647]:
            with self.subTest(value=value),self.assertRaises(ValueError):backend_container_id(value)
