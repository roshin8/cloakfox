"""Trusted engine-intent primitives for the pending schema2 controller.

These functions do not launch an engine, attest privacy capability, or migrate
v1 records. The production controller must also validate the complete policy,
packaged native capabilities and immutable owner acknowledgement before use.
"""
import re

_ENGINES={'gecko','chromium'}
_VERSION=re.compile(r'(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){1,3}\Z',re.ASCII)
_FAMILY=re.compile(r'(?<![A-Za-z0-9_])(?P<brand>Firefox|Chrome|Chromium|Edg|EdgA|EdgiOS|OPR|CriOS|FxiOS)/(?P<version>[^\s;()]+)',re.ASCII)


def _version(value):
    if type(value) is not str or len(value)>64 or not _VERSION.fullmatch(value):
        raise ValueError('Invalid engine version')
    components=tuple(int(item) for item in value.split('.'))
    if components[0]<1 or any(item>2147483647 for item in components):
        raise ValueError('Invalid engine version')
    return components


def resolve_engine(ua,versions):
    """Resolve a desktop identity only when its version matches the backend.

    Chromium's standard reduced version and Firefox's public major/minor UA are
    accepted alongside their actual full versions. An arbitrary same-major
    custom version is not. Edge and other brands require native support first.
    """
    if type(versions) is not dict or not versions or not set(versions)<=_ENGINES:
        raise ValueError('Invalid installed engines')
    installed={key:_version(value) for key,value in versions.items()}
    if type(ua) is not str or not 1<=len(ua)<=1024 or ua!=ua.strip() or any(ord(c)<32 or ord(c)>126 for c in ua):
        raise ValueError('Invalid user agent')
    matches=list(_FAMILY.finditer(ua))
    if len(matches)!=1:
        raise ValueError('Missing or ambiguous browser identity')
    brand=matches[0]['brand'];requested=_version(matches[0]['version'])
    if brand=='Firefox':engine='gecko'
    elif brand in ('Chrome','Chromium'):engine='chromium'
    else:raise ValueError('Unsupported browser brand')
    if engine not in installed:raise ValueError('Requested engine is unavailable')
    actual=installed[engine]
    allowed={actual}
    if engine=='chromium':allowed.add((actual[0],0,0,0))
    else:allowed.add(actual[:2])
    if requested not in allowed:
        raise ValueError('Identity version differs from installed engine')
    return engine


def backend_container_id(external_id):
    """Map external Default 0 to a distinct, positive native owner ID.

    Schema2 reserves the complete positive v1 backend namespace; records must
    be explicitly migrated into it, never reopened using this mapping in v1.
    Reject the upper external boundary rather than wrap or alias another owner.
    """
    if type(external_id) is not int or not 0<=external_id<2147483647:
        raise ValueError('Container is outside the backend mapping range')
    return str(external_id+1)


# A group version describes the COMPLETE maintained policy for that group.
# Existing partial canvas/identity hook versions must never be advertised here.
# Schema2 stays independent from the explicit legacy v1 development protocol.
import json as _json
from pathlib import Path as _Path
from types import MappingProxyType as _MappingProxyType

_contract = _json.loads((_Path(__file__).with_name('privacy_contract.json')).read_text())
if (type(_contract) is not dict or set(_contract) != {'schemaVersion', 'groupVersions', 'presentationVersions'} or
        type(_contract['schemaVersion']) is not int or _contract['schemaVersion'] != 2 or
        type(_contract['groupVersions']) is not dict or not _contract['groupVersions'] or
        any(type(name) is not str or not name or type(version) is not int or version != 1
            for name, version in _contract['groupVersions'].items()) or
        _contract['presentationVersions'] != {'same-window': 1, 'separate-window': 1}):
    raise ValueError('Invalid packaged engine policy contract')
POLICY_SCHEMA_VERSION = _contract['schemaVersion']
POLICY_GROUPS = tuple(_contract['groupVersions'])
_REQUIRED_GROUP_VERSIONS = _MappingProxyType(dict(_contract['groupVersions']))
_PRESENTATIONS = frozenset(_contract['presentationVersions'])


def _fields(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError('Unsupported engine policy fields')


def _json_data(value, depth=0, _budget=None):
    """Bound TOTAL nodes and encoded bytes, not only each nested container."""
    if _budget is None:
        _budget = [4096, 65536]
    _budget[0] -= 1
    if _budget[0] < 0 or depth > 16:
        raise ValueError('Engine policy traversal exceeds bounds')

    def charge(count):
        _budget[1] -= count
        if _budget[1] < 0:
            raise ValueError('Engine policy exceeds byte bounds')

    if value is None:
        charge(4)
    elif type(value) is bool:
        charge(4 if value else 5)
    elif type(value) is int:
        if abs(value) > 9007199254740991:
            raise ValueError('Engine policy integer exceeds bounds')
        charge(len(str(value)))
    elif type(value) is float:
        import math
        if not math.isfinite(value):
            raise ValueError('Invalid engine policy number')
        charge(len(repr(value)))
    elif type(value) is str:
        if len(value) > 65536:
            raise ValueError('Engine policy text exceeds bounds')
        charge(2)  # JSON quotes and escapes, matching ensure_ascii=True.
        for character in value:
            code = ord(character)
            if 0xD800 <= code <= 0xDFFF:
                raise ValueError('Invalid engine policy text')
            if character in ('"', '\\', '\b', '\f', '\n', '\r', '\t'):
                charge(2)
            elif code < 32 or code >= 127:
                charge(6 if code <= 65535 else 12)
            else:
                charge(1)
    elif type(value) is dict:
        if len(value) > 4096 or any(type(key) is not str for key in value):
            raise ValueError('Invalid engine policy object')
        charge(2 + max(0, len(value)-1) + len(value))
        result = {}
        for key, item in value.items():
            _json_data(key, depth + 1, _budget)
            result[key] = _json_data(item, depth + 1, _budget)
        return result
    elif type(value) is list:
        if len(value) > 4096:
            raise ValueError('Engine policy list exceeds bounds')
        charge(2 + max(0, len(value)-1))
        result = []
        for item in value:
            result.append(_json_data(item, depth + 1, _budget))
        return result
    else:
        raise ValueError('Engine policy requires JSON data')
    return value


def _freeze_data(value):
    import json
    try:
        # Copy while spending the cumulative budget. The encoder sees only this
        # private copy, never caller data that can grow after the bounds check.
        value = _json_data(value)
        encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')
    except (ValueError, TypeError, UnicodeError, RuntimeError):
        raise ValueError('Invalid engine policy encoding') from None
    if len(encoded) > 65536:
        raise ValueError('Engine policy exceeds bounds')
    return encoded, json.loads(encoded)


class ValidatedPolicy:
    """Immutable encoded snapshot; its repr never includes persona secrets.

    Construction is internal to validate_policy. Validation is a protocol gate,
    not evidence that a backend implements these groups or is release eligible.
    """
    __slots__ = ('__encoded',)

    def __init__(self, encoded):
        object.__setattr__(self, '_ValidatedPolicy__encoded', encoded)

    def __setattr__(self, *_):
        raise AttributeError('Validated engine policy is immutable')

    def __repr__(self):
        return '<ValidatedPolicy schema=2>'

    def snapshot(self):
        import json
        return json.loads(self.__encoded)

    def validate_ack(self, reply):
        import json
        keys = ('schemaVersion', 'engine', 'engineVersion', 'owner', 'revision')
        _, reply = _freeze_data(reply)
        _fields(reply, keys)
        value = self.snapshot()
        expected = {key: value[key] for key in keys}
        if json.dumps(reply, sort_keys=True, allow_nan=False) != json.dumps(expected, sort_keys=True):
            raise ValueError('Engine acknowledgement differs from reserved policy')


def validate_policy(value, capabilities, *, validators=None, expected_owner=None, expected_revision=None):
    """Validate the complete schema2 contract against trusted native adapters.

    The caller must authenticate the backend/packaged capability report. A group
    version is necessary, never sufficient: every group needs its own trusted
    native-equivalent config validator as well. There are deliberately no stub
    validators or partial-hook defaults. Until each native port exists, calling
    this gate fails; it does not acknowledge unavailable protections as working.
    No browser, context, store or network request is created here.
    """
    import copy
    import json
    # Validate a single private snapshot. Callbacks and concurrent UI changes
    # cannot replace the data that a later group validates or the caller receives.
    encoded, value = _freeze_data(value)
    _, capabilities = _freeze_data(capabilities)
    _, expected_owner = _freeze_data(expected_owner)
    _fields(value, ('schemaVersion', 'engine', 'engineVersion', 'owner',
                    'revision', 'enabled', 'presentation', 'personaSeed', 'groups'))
    _fields(capabilities, ('schemaVersion', 'engine', 'engineVersion', 'groups', 'presentations'))
    if (type(value['schemaVersion']) is not int or value['schemaVersion'] != POLICY_SCHEMA_VERSION or
            type(capabilities['schemaVersion']) is not int or capabilities['schemaVersion'] != POLICY_SCHEMA_VERSION):
        raise ValueError('Unsupported engine policy schema')
    if (type(value['engine']) is not str or value['engine'] not in _ENGINES or
            value['engine'] != capabilities['engine']):
        raise ValueError('Engine policy belongs to another backend')
    _version(value['engineVersion']); _version(capabilities['engineVersion'])
    if value['engineVersion'] != capabilities['engineVersion']:
        raise ValueError('Engine policy version differs from installed backend')
    owner = value['owner']
    _fields(owner, ('containerId', 'backendContainerId', 'private', 'privateSession'))
    if backend_container_id(owner['containerId']) != owner['backendContainerId']:
        raise ValueError('Engine policy container mapping differs')
    if type(owner['private']) is not bool:
        raise ValueError('Invalid engine policy private flag')
    if owner['private']:
        if type(owner['privateSession']) is not str or not re.fullmatch('[0-9a-f]{32}', owner['privateSession']):
            raise ValueError('Private engine policy needs its own session')
    elif owner['privateSession'] is not None:
        raise ValueError('Persistent engine policy cannot own a private session')
    # These bindings come from the trusted switch reservation, never from the
    # incoming snapshot. Validation alone must not authorize replay/retargeting.
    _fields(expected_owner, ('containerId', 'backendContainerId', 'private', 'privateSession'))
    if (type(expected_revision) is not int or not 1 <= expected_revision <= 2147483647 or
            type(value['revision']) is not int or value['revision'] != expected_revision or
            json.dumps(owner, sort_keys=True) != json.dumps(expected_owner, sort_keys=True)):
        raise ValueError('Engine policy differs from reserved owner or revision')
    if (type(value['revision']) is not int or not 1 <= value['revision'] <= 2147483647 or
            type(value['enabled']) is not bool):
        raise ValueError('Invalid engine policy revision or master flag')
    if type(value['personaSeed']) is not str or not re.fullmatch('[0-9a-f]{64}', value['personaSeed']):
        raise ValueError('Invalid engine policy seed')
    mode = value['presentation']
    if type(mode) is not str or mode not in _PRESENTATIONS:
        raise ValueError('Invalid engine policy presentation')
    _fields(capabilities['presentations'], _PRESENTATIONS)
    for name, version in capabilities['presentations'].items():
        if type(version) is not int or version not in (0, 1):
            raise ValueError('Invalid native presentation capability')
    if capabilities['presentations'][mode] != 1:
        raise ValueError('Requested presentation is unavailable')
    _fields(value['groups'], POLICY_GROUPS)
    _fields(capabilities['groups'], POLICY_GROUPS)
    if type(validators) is not dict or set(validators) != set(POLICY_GROUPS):
        raise ValueError('Native policy validators are incomplete')
    validators = dict(validators)
    for name in POLICY_GROUPS:
        entry = value['groups'][name]
        _fields(entry, ('version', 'config'))
        if (type(entry['version']) is not int or entry['version'] != _REQUIRED_GROUP_VERSIONS[name] or
                type(capabilities['groups'][name]) is not int or capabilities['groups'][name] != _REQUIRED_GROUP_VERSIONS[name] or
                type(entry['config']) is not dict or not callable(validators[name])):
            raise ValueError('Unsupported native privacy group: ' + name)
    for name in POLICY_GROUPS:
        try:
            if validators[name](copy.deepcopy(value['groups'][name]['config'])) is not True:
                raise ValueError('Native validator did not acknowledge its config')
        except Exception:
            # Native/persona diagnostics can include private field values.
            raise ValueError('Native privacy configuration rejected: ' + name) from None
    return ValidatedPolicy(encoded)
