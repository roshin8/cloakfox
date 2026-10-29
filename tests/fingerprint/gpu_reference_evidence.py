"""Offline rendering-reference checks; never activates a production GPU profile.

Structural validation is not authentication of a claimed source or driver.
Even exact corpus matches do not establish complete hardware emulation.
"""
import re
from urllib.parse import urlsplit


DIGEST = re.compile(r'[0-9a-f]{64}')
TARGET_FIELDS = ('family', 'model', 'driver', 'backend', 'os', 'browserEngine', 'browserVersion')


def validate_reference(record):
    try:
        if type(record['schemaVersion']) is not int or record['schemaVersion'] != 1:
            raise ValueError('Unsupported reference schema')
        source = record['source']
        url = urlsplit(source['url'])
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            raise ValueError('Reference needs a public HTTPS source')
        if not isinstance(source['sha256'], str) or not DIGEST.fullmatch(source['sha256']):
            raise ValueError('Reference source digest missing')
        target = record['target']
        for field in TARGET_FIELDS:
            value = target[field]
            if not isinstance(value, str) or not value.strip() or value.lower() in ('unknown', 'none') or len(value) > 512:
                raise ValueError('Missing concrete reference target: ' + field)
        if target['family'] not in ('apple', 'intel', 'amd', 'nvidia'):
            raise ValueError('Unsupported reference family')
        if target['browserEngine'] not in ('gecko', 'chromium'):
            raise ValueError('Reference is not a browser execution corpus')
        if not re.fullmatch(r'\d+\.\d+(?:\.\d+)?', target['browserVersion']):
            raise ValueError('Reference browser version missing')
        corpus = record['corpus']
        if not isinstance(corpus['sha256'], str) or not DIGEST.fullmatch(corpus['sha256']):
            raise ValueError('Exact corpus input digest required')
        cases = corpus['cases']
        if not isinstance(cases, list) or not 1 <= len(cases) <= 64 or any(not isinstance(c, str) or not c or len(c) > 128 for c in cases) or len(set(cases)) != len(cases):
            raise ValueError('Invalid or duplicate corpus cases')
        caps = record['capabilities']
        if not isinstance(caps, dict) or not caps or len(caps) > 256 or any(not isinstance(k, str) or type(v) is not int or not 0 <= v <= 2**53-1 for k, v in caps.items()):
            raise ValueError('Exact finite integer capability observations required')
        outputs = record['outputs']
        if not isinstance(outputs, dict) or set(outputs) != set(cases):
            raise ValueError('Capability-only or incomplete rendering evidence')
        total = 0
        for case in cases:
            output = outputs[case]
            width, height, rgba = output['width'], output['height'], output['rgba']
            if type(width) is not int or type(height) is not int or not 1 <= width <= 2048 or not 1 <= height <= 2048:
                raise ValueError('Invalid corpus dimensions')
            total += width * height * 4
            if total > 4*1024*1024 or not isinstance(rgba, list) or len(rgba) != width * height * 4 or any(type(v) is not int or not 0 <= v <= 255 for v in rgba):
                raise ValueError('Invalid or excessive pixel evidence')
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('Incomplete rendering reference') from error
    return record


def compare_reference(reference, candidate):
    validate_reference(reference)
    validate_reference(candidate)
    # Compare the requested target, not whichever host GPU happens to run it.
    # Actual backend/driver provenance stays in both records for audit.
    for field in ('family', 'model', 'os', 'browserEngine', 'browserVersion'):
        if reference['target'][field] != candidate['target'][field]:
            raise ValueError('Incomparable reference target: ' + field)
    if reference['corpus'] != candidate['corpus']:
        raise ValueError('Incomparable corpus inputs')
    differences = []
    if reference['capabilities'] != candidate['capabilities']:
        differences.append('capabilities')
    differences.extend(case for case in reference['corpus']['cases'] if reference['outputs'][case] != candidate['outputs'][case])
    return {'corpusMatches': not differences, 'differences': differences,
            'fullEmulationValidated': False,
            'qualification': 'Finite corpus only; source authentication and driver provenance need separate review'}
