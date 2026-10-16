import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('fetch_cef', Path(__file__).parents[2] / 'engines/chromium/fetch_cef.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


class ExtractionRecovery(unittest.TestCase):
    def test_partial_destination_is_preserved_and_replaced_atomically(self):
        with tempfile.TemporaryDirectory() as root:
            cache = Path(root)
            destination = cache / 'sdk'
            destination.mkdir()
            (destination / 'partial').write_text('keep')
            archive = cache / 'sdk.tar.bz2'
            with tarfile.open(archive, 'w:bz2') as bundle:
                data = b'complete'
                entry = tarfile.TarInfo('sdk/include/cef.h')
                entry.size = len(data)
                bundle.addfile(entry, io.BytesIO(data))
            fetch.extract_atomic(archive, destination, 'verified-digest')
            self.assertEqual((destination / 'include/cef.h').read_bytes(), b'complete')
            self.assertEqual((cache / 'sdk.incomplete/partial').read_text(), 'keep')
            fetch.extract_atomic(archive, destination, 'verified-digest')
            self.assertTrue((destination / 'include/cef.h').exists())

    def test_failure_does_not_publish_partial_directory(self):
        with tempfile.TemporaryDirectory() as root:
            cache = Path(root)
            archive = cache / 'bad.tar.bz2'
            archive.write_bytes(b'not an archive')
            with self.assertRaises(tarfile.ReadError):
                fetch.extract_atomic(archive, cache / 'sdk', 'digest')
            self.assertFalse((cache / 'sdk').exists())


if __name__ == '__main__':
    unittest.main()
