"""Pinned native patch replay and tamper detection, using owned local source."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]

def copy_native_fixture(source, destination, wanted):
    """Normalize later reviewed increments in the owned copy, never live source."""
    here=ROOT/'engines/chromium';inputs={};wanted_chain=set()
    def inherit(name, selected=False):
        value=json.loads((here/name).read_text())
        if value.get('applyAfter'):inherit(value['applyAfter'],selected)
        if selected:wanted_chain.add(name)
        for item in value['inputs']:inputs[item['path']]=item
    inherit(wanted,True)
    extensions=['browserforge-patch-lock.json','initial-snapshot-patch-lock.json','fixture-network-patch-lock.json','owned-ime-patch-lock.json','owned-ime-state-patch-lock.json','display-patch-lock.json']
    for name in extensions:
        if (here/name).exists():inherit(name)
    for name in inputs:
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/name,target)
    for name in reversed(extensions):
        if name in wanted_chain or not (here/name).exists():continue
        value=json.loads((here/name).read_text())
        def matches(key):
            return all(hashlib.sha256((destination/item['path']).read_bytes()).hexdigest()==item[key] for item in value['inputs'])
        if matches('afterSha256'):
            subprocess.run(['patch','-p1','-R','--batch','-i',str(here/value['patch'])],cwd=destination,check=True,capture_output=True)
        elif not matches('beforeSha256'):
            raise AssertionError('Unexpected later native fixture state: '+name)


class IdentityPatch(unittest.TestCase):
    def test_pinned_patch_replays_and_rejects_changed_inputs(self):
        source=Path(os.environ.get('CLOAKFOX_CHROMIUM_SOURCE','/Users/zeus/cloakfox-builds/chromium/full-source/chromium/src'))
        if not source.is_dir():self.skipTest('Requires local pinned native source for replay check')
        here=ROOT/'engines/chromium';lock=json.loads((here/'identity-patch-lock.json').read_text())
        inputs={}
        def inherit(name):
            parent=json.loads((here/name).read_text())
            if parent.get('applyAfter'):inherit(parent['applyAfter'])
            for item in parent['inputs']:inputs[item['path']]=item
        inherit('identity-patch-lock.json')
        with tempfile.TemporaryDirectory(prefix='cloakfox-identity-patch-') as folder:
            temp=Path(folder)
            copy_native_fixture(source,temp,'identity-patch-lock.json')
            for name,entry in inputs.items():
                self.assertEqual(hashlib.sha256((temp/name).read_bytes()).hexdigest(),entry['afterSha256'])
            # Reverse our patch only: inherited graphics patches remain applied.
            subprocess.run(['patch','-p1','-R','--batch','-i',str(here/lock['patch'])],cwd=temp,check=True,capture_output=True)
            for item in lock['inputs']:
                self.assertEqual(hashlib.sha256((temp/item['path']).read_bytes()).hexdigest(),item['beforeSha256'])
            command=[sys.executable,str(here/'apply_identity_patch.py'),'--source-root',str(temp)]
            subprocess.run(command,check=True,capture_output=True)
            subprocess.run(command+['--check'],check=True,capture_output=True)
            modified=temp/lock['inputs'][0]['path'];modified.write_text(modified.read_text()+'\n// unexpected mutation\n')
            rejected=subprocess.run(command+['--check'],capture_output=True,text=True)
            self.assertNotEqual(rejected.returncode,0)
            self.assertIn('Unexpected source input',rejected.stderr)

    def test_browserforge_extension_replays_on_the_existing_identity_patch(self):
        source=Path(os.environ.get('CLOAKFOX_CHROMIUM_SOURCE','/Users/zeus/cloakfox-builds/chromium/full-source/chromium/src'))
        if not source.is_dir():self.skipTest('Requires pinned native source')
        here=ROOT/'engines/chromium';lock=json.loads((here/'browserforge-patch-lock.json').read_text())
        inputs={}
        def inherit(name):
            value=json.loads((here/name).read_text())
            if value.get('applyAfter'):inherit(value['applyAfter'])
            for item in value['inputs']:inputs[item['path']]=item
        inherit('browserforge-patch-lock.json')
        with tempfile.TemporaryDirectory(prefix='cloakfox-browserforge-replay-') as folder:
            temp=Path(folder)
            copy_native_fixture(source,temp,'browserforge-patch-lock.json')
            command=[sys.executable,str(here/'apply_identity_patch.py'),'--source-root',str(temp),'--lock','browserforge-patch-lock.json']
            subprocess.run(command,check=True,capture_output=True)
            for name,entry in inputs.items():
                self.assertEqual(hashlib.sha256((temp/name).read_bytes()).hexdigest(),entry['afterSha256'])
            subprocess.run(['patch','-p1','-R','--batch','-i',str(here/lock['patch'])],cwd=temp,check=True,capture_output=True)
            subprocess.run(command,check=True,capture_output=True)
            changed=temp/lock['inputs'][0]['path'];changed.write_text(changed.read_text()+'\n// unexpected mutation\n')
            rejected=subprocess.run(command+['--check'],capture_output=True,text=True)
            self.assertNotEqual(rejected.returncode,0);self.assertIn('Unexpected source input',rejected.stderr)

    def test_initial_snapshot_extension_replays_and_rejects_tampering(self):
        source=Path(os.environ.get('CLOAKFOX_CHROMIUM_SOURCE','/Users/zeus/cloakfox-builds/chromium/full-source/chromium/src'))
        if not source.is_dir():self.skipTest('Requires pinned native source')
        here=ROOT/'engines/chromium';lock=json.loads((here/'initial-snapshot-patch-lock.json').read_text())
        with tempfile.TemporaryDirectory(prefix='cloakfox-initial-snapshot-replay-') as folder:
            temp=Path(folder);copy_native_fixture(source,temp,'initial-snapshot-patch-lock.json')
            command=[sys.executable,str(here/'apply_identity_patch.py'),'--source-root',str(temp),'--lock','initial-snapshot-patch-lock.json']
            subprocess.run(command,check=True,capture_output=True)
            subprocess.run(['patch','-p1','-R','--batch','-i',str(here/lock['patch'])],cwd=temp,check=True,capture_output=True)
            for item in lock['inputs']:
                self.assertEqual(hashlib.sha256((temp/item['path']).read_bytes()).hexdigest(),item['beforeSha256'])
            subprocess.run(command,check=True,capture_output=True)
            subprocess.run(command+['--check'],check=True,capture_output=True)
            changed=temp/lock['inputs'][0]['path'];changed.write_text(changed.read_text()+'\n// unexpected mutation\n')
            rejected=subprocess.run(command+['--check'],capture_output=True,text=True)
            self.assertNotEqual(rejected.returncode,0);self.assertIn('Unexpected source input',rejected.stderr)

    def test_fixture_network_extension_replays_and_rejects_tampering(self):
        source=Path(os.environ.get('CLOAKFOX_CHROMIUM_SOURCE','/Users/zeus/cloakfox-builds/chromium/full-source/chromium/src'))
        if not source.is_dir():self.skipTest('Requires pinned native source')
        here=ROOT/'engines/chromium';lock=json.loads((here/'fixture-network-patch-lock.json').read_text())
        with tempfile.TemporaryDirectory(prefix='cloakfox-fixture-network-replay-') as folder:
            temp=Path(folder);copy_native_fixture(source,temp,'fixture-network-patch-lock.json')
            command=[sys.executable,str(here/'apply_identity_patch.py'),'--source-root',str(temp),'--lock','fixture-network-patch-lock.json']
            subprocess.run(command,check=True,capture_output=True)
            subprocess.run(['patch','-p1','-R','--batch','-i',str(here/lock['patch'])],cwd=temp,check=True,capture_output=True)
            for item in lock['inputs']:
                self.assertEqual(hashlib.sha256((temp/item['path']).read_bytes()).hexdigest(),item['beforeSha256'])
            subprocess.run(command,check=True,capture_output=True)
            subprocess.run(command+['--check'],check=True,capture_output=True)
            changed=temp/lock['inputs'][0]['path'];changed.write_text(changed.read_text()+'\n// unexpected mutation\n')
            rejected=subprocess.run(command+['--check'],capture_output=True,text=True)
            self.assertNotEqual(rejected.returncode,0);self.assertIn('Unexpected source input',rejected.stderr)

    def test_owned_ime_extension_replays_and_rejects_tampering(self):
        source=Path(os.environ.get('CLOAKFOX_CHROMIUM_SOURCE','/Users/zeus/cloakfox-builds/chromium/full-source/chromium/src'))
        if not source.is_dir():self.skipTest('Requires pinned native source')
        here=ROOT/'engines/chromium';lock=json.loads((here/'owned-ime-patch-lock.json').read_text())
        with tempfile.TemporaryDirectory(prefix='cloakfox-owned-ime-replay-') as folder:
            temp=Path(folder);copy_native_fixture(source,temp,'owned-ime-patch-lock.json')
            command=[sys.executable,str(here/'apply_identity_patch.py'),'--source-root',str(temp),'--lock','owned-ime-patch-lock.json']
            subprocess.run(command,check=True,capture_output=True)
            subprocess.run(['patch','-p1','-R','--batch','-i',str(here/lock['patch'])],cwd=temp,check=True,capture_output=True)
            for item in lock['inputs']:
                self.assertEqual(hashlib.sha256((temp/item['path']).read_bytes()).hexdigest(),item['beforeSha256'])
            subprocess.run(command,check=True,capture_output=True)
            subprocess.run(command+['--check'],check=True,capture_output=True)
            changed=temp/lock['inputs'][0]['path'];changed.write_text(changed.read_text()+'\n// unexpected mutation\n')
            rejected=subprocess.run(command+['--check'],capture_output=True,text=True)
            self.assertNotEqual(rejected.returncode,0);self.assertIn('Unexpected source input',rejected.stderr)

    def test_owned_ime_state_extension_replays_and_rejects_tampering(self):
        source=Path(os.environ.get('CLOAKFOX_CHROMIUM_SOURCE','/Users/zeus/cloakfox-builds/chromium/full-source/chromium/src'))
        if not source.is_dir():self.skipTest('Requires pinned native source')
        here=ROOT/'engines/chromium';lock=json.loads((here/'owned-ime-state-patch-lock.json').read_text())
        with tempfile.TemporaryDirectory(prefix='cloakfox-owned-ime-state-replay-') as folder:
            temp=Path(folder);copy_native_fixture(source,temp,'owned-ime-state-patch-lock.json')
            command=[sys.executable,str(here/'apply_identity_patch.py'),'--source-root',str(temp),'--lock','owned-ime-state-patch-lock.json']
            subprocess.run(command,check=True,capture_output=True)
            subprocess.run(['patch','-p1','-R','--batch','-i',str(here/lock['patch'])],cwd=temp,check=True,capture_output=True)
            for item in lock['inputs']:
                self.assertEqual(hashlib.sha256((temp/item['path']).read_bytes()).hexdigest(),item['beforeSha256'])
            subprocess.run(command,check=True,capture_output=True)
            subprocess.run(command+['--check'],check=True,capture_output=True)
            changed=temp/lock['inputs'][0]['path'];changed.write_text(changed.read_text()+'\n// unexpected mutation\n')
            rejected=subprocess.run(command+['--check'],capture_output=True,text=True)
            self.assertNotEqual(rejected.returncode,0);self.assertIn('Unexpected source input',rejected.stderr)

    def test_display_extension_replays_and_rejects_tampering(self):
        source=Path(os.environ.get('CLOAKFOX_CHROMIUM_SOURCE','/Users/zeus/cloakfox-builds/chromium/full-source/chromium/src'))
        if not source.is_dir():self.skipTest('Requires pinned native source')
        here=ROOT/'engines/chromium';lock=json.loads((here/'display-patch-lock.json').read_text())
        with tempfile.TemporaryDirectory(prefix='cloakfox-display-replay-') as folder:
            temp=Path(folder);copy_native_fixture(source,temp,'display-patch-lock.json')
            command=[sys.executable,str(here/'apply_identity_patch.py'),'--source-root',str(temp),'--lock','display-patch-lock.json']
            subprocess.run(command,check=True,capture_output=True)
            subprocess.run(['patch','-p1','-R','--batch','-i',str(here/lock['patch'])],cwd=temp,check=True,capture_output=True)
            for item in lock['inputs']:
                self.assertEqual(hashlib.sha256((temp/item['path']).read_bytes()).hexdigest(),item['beforeSha256'])
            subprocess.run(command,check=True,capture_output=True)
            subprocess.run(command+['--check'],check=True,capture_output=True)
            changed=temp/lock['inputs'][0]['path'];changed.write_text(changed.read_text()+'\n// unexpected mutation\n')
            rejected=subprocess.run(command+['--check'],capture_output=True,text=True)
            self.assertNotEqual(rejected.returncode,0);self.assertIn('Unexpected source input',rejected.stderr)
