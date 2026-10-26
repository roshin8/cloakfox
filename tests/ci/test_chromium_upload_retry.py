"""Publication retries must stay bounded and fail closed without touching old artifacts."""
import re
import unittest
from pathlib import Path

class PublicationRetryTests(unittest.TestCase):
    def test_checkpoint_uploads_retry_and_fail_closed(self):
        source=(Path(__file__).resolve().parents[2]/'.github/workflows/chromium-source-segment.yml').read_text()
        for prefix,title in [('producer','Publish checkpoint producer lineage'),('workspace','Preserve unfinished source and compiled objects for next job')]:
            for attempt in range(1,4):
                block=re.search(r'      - name: Upload '+prefix+r' artifact \(attempt '+str(attempt)+r'\)\n(.*?)(?=      - |\Z)',source,re.S)
                self.assertIsNotNone(block)
                block=block.group(1)
                self.assertIn(f'id: {prefix}_upload_{attempt}',block)
                self.assertIn('uses: actions/upload-artifact@v4',block)
                self.assertIn('overwrite: true',block)
                self.assertIn('if-no-files-found: error',block)
                self.assertIn('retention-days: 7',block)
                self.assertIn(f'timeout-minutes: {5 if prefix=="producer" else 20}',block)
                self.assertEqual('continue-on-error: true' in block,attempt<3)
                if attempt>1:self.assertIn(f"steps.{prefix}_upload_{attempt-1}.outcome == 'failure'",block)
                if prefix=='workspace':self.assertIn("steps.build.outputs.complete == 'false'",block)
            gate=source.split('      - name: '+title+'\n',1)[1].split('      - ',1)[0]
            for attempt in range(1,4):self.assertIn(f"steps.{prefix}_upload_{attempt}.outcome == 'success'",gate)
            self.assertIn('!= "true"',gate)
            self.assertIn('exit 1',gate)
            self.assertLess(source.index(f'id: {prefix}_upload_3'),source.index('      - name: '+title+'\n'))
        self.assertNotIn('continue-on-error: true\n        run:',source)
        self.assertIn('artifact-id: ${{ steps.sdk.outputs.artifact-id }}',source)
        self.assertEqual(sum(int(n) for n in re.findall(r'Upload (?:producer|workspace) artifact \(attempt \d\).*?timeout-minutes: (\d+)',source,re.S)),75)

if __name__=='__main__':unittest.main()
