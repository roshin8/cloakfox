"""Persist network probe observations and logs outside disposable profiles."""
import json
import os
from pathlib import Path
import tempfile


class ProbeEvidence:
    def __init__(self, name, report_variable):
        configured = os.environ.get('REPORT_DIR')
        self.root = Path(configured) if configured else Path(tempfile.mkdtemp(prefix=f'cloakfox-{name}-evidence-'))
        self.root.mkdir(parents=True, exist_ok=True)
        self.destination = Path(os.environ.get(report_variable, str(self.root / f'{name}.json')))
        self.report = {}

    def __enter__(self):
        self.previous = os.environ.get('ALPS_FIXTURE_LOG_DIR')
        os.environ['ALPS_FIXTURE_LOG_DIR'] = str(self.root)
        return self

    def __exit__(self, error_type, error, traceback):
        self.report['outcome'] = 'fail' if error_type else 'pass'
        if error_type:
            self.report['error'] = f'{error_type.__name__}: {error}'
        try:
            self.destination.parent.mkdir(parents=True, exist_ok=True)
            self.destination.write_text(json.dumps(self.report, indent=2) + '\n')
        finally:
            if self.previous is None:
                os.environ.pop('ALPS_FIXTURE_LOG_DIR', None)
            else:
                os.environ['ALPS_FIXTURE_LOG_DIR'] = self.previous
