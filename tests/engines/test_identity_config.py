"""Presentation generation/validation independent of browser runtimes."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engines.shared.persona_config import PersonaStore, validate_snapshot

class IdentityConfig(unittest.TestCase):
    def test_new_personas_generate_stable_regional_presentation(self):
        with tempfile.TemporaryDirectory() as folder:
            store=PersonaStore(Path(folder)); a=store.get('1','chromium')
            self.assertIn('presentation',a['persona'],'Native identity config not implemented')
            self.assertEqual(store.get('1','chromium'),a)
            p=a['persona']['presentation']
            self.assertIn(p['hardwareConcurrency'],(4,8,16))
            self.assertIn(p['deviceMemory'],(4,8))
            self.assertIn(p['languages'][0],('en-US','en-GB','de-DE','fr-FR','ja-JP'))
            self.assertEqual(validate_snapshot(a),a)
            b=store.regenerate(a)
            self.assertNotEqual(a['persona']['seed'],b['persona']['seed'])
            from engines.shared.persona_config import sample_presentation
            self.assertEqual(b['persona']['presentation'],sample_presentation(b['persona']['seed']))
    def test_invalid_identity_fields_and_values_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            a=PersonaStore(Path(folder)).get('1','chromium')
            self.assertIn('presentation',a['persona'])
            for key,bad in [('hardwareConcurrency',True),('hardwareConcurrency',1024),
                            ('deviceMemory',3),('languages',['xx-invalid']),
                            ('languages',['en-US','en-US']),('timezone','Etc/Unknown'),
                            ('userAgent','Fake Chrome'),('platform','Win32')]:
                value=copy.deepcopy(a); value['persona']['presentation'][key]=bad
                with self.subTest(key=key),self.assertRaises(ValueError):validate_snapshot(value)
    def test_explicit_values_survive_generation_unless_cleared(self):
        with tempfile.TemporaryDirectory() as folder:
            store=PersonaStore(Path(folder));a=store.get('1','chromium')
            self.assertIn('presentation',a['persona'])
            preset={'hardwareConcurrency':4,'deviceMemory':4,'languages':['fr-FR','fr'],'timezone':'Europe/Paris'}
            a=store.update(a,presentation=preset)
            b=store.regenerate(a)
            self.assertEqual(b['persona']['presentation'],preset)
            self.assertEqual(b['persona']['overrides']['presentation'],preset)
            c=store.regenerate(b,clear_overrides=True)
            self.assertNotIn('presentation',c['persona']['overrides'])
    def test_legacy_v1_snapshot_is_valid_without_silent_upgrade(self):
        with tempfile.TemporaryDirectory() as folder:
            store=PersonaStore(Path(folder));a=store.get('1','chromium')
            self.assertIn('presentation',a['persona'])
            a['persona'].pop('presentation')
            for name in ('navigator','language','timezone','display'):
                a['persona']['options'].pop(name,None)
            self.assertEqual(validate_snapshot(a),a)

    def test_display_option_requires_the_identity_presentation(self):
        with tempfile.TemporaryDirectory() as folder:
            a=PersonaStore(Path(folder)).get('1','chromium')
            a['persona'].pop('presentation')
            for name in ('navigator','language','timezone'):
                a['persona']['options'].pop(name,None)
            self.assertIn('display',a['persona']['options'],'Display option is presentation-gated')
            with self.assertRaises(ValueError):validate_snapshot(a)

    def test_disable_toggle_does_not_pin_generated_presentation(self):
        from types import SimpleNamespace
        from engines.chromium import launch_prototype
        self.assertTrue(hasattr(launch_prototype,'configure_snapshot'),'Extract launcher transform for lifecycle test')
        with tempfile.TemporaryDirectory() as folder:
            store=PersonaStore(Path(folder));config=store.get('1','chromium')
            args=SimpleNamespace(language=None,timezone=None,disable_navigator_privacy=False,
                disable_language_privacy=False,disable_timezone_privacy=True,disable_canvas_privacy=False,
                block_webgpu_readback=False,privacy_enabled=None,regenerate_persona=False,clear_overrides_when_generating=False)
            config=launch_prototype.configure_snapshot(store,config,args)
            self.assertNotIn('presentation',config['persona']['overrides'])
            regenerated=store.regenerate(config)
            from engines.shared.persona_config import sample_presentation
            self.assertEqual(regenerated['persona']['presentation'],sample_presentation(regenerated['persona']['seed']))

    def test_browserforge_processor_counts_do_not_fall_back_to_host_values(self):
        with tempfile.TemporaryDirectory() as folder:
            config=PersonaStore(Path(folder)).get('1','chromium')
            for count in (1,2,6,12,24,32,64,128):
                config['persona']['presentation']['hardwareConcurrency']=count
                self.assertEqual(validate_snapshot(config)['persona']['presentation']['hardwareConcurrency'],count)
            for count in (0,-1,129,True,2.5):
                config['persona']['presentation']['hardwareConcurrency']=count
                with self.subTest(count=count),self.assertRaises(ValueError):validate_snapshot(config)
