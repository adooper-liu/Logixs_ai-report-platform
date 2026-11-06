import copy
import hashlib
from importlib.resources import files
import json

from jsonschema import Draft202012Validator


DEFAULT_POLICY = {
    'schema_version': '1.0.0',
    'ai': {'enabled': False, 'allow_raw_sample_egress': False},
    'storage': {'max_object_bytes': 104857600, 'retention_days': None},
}


def policy_schema():
    return json.loads(files('arp_contracts').joinpath('schemas/project-policy.v1.json').read_text('utf-8'))


def validate_policy(value):
    # No remote references or provider calls: this is a closed, packaged schema.
    Draft202012Validator(policy_schema()).validate(value)
    return copy.deepcopy(value)


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()
