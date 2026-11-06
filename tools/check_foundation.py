"""Offline structural checks, not container or runtime integration acceptance."""
import json
import os
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.environ['DJANGO_SETTINGS_MODULE'] = 'arp_control.test_settings'
    import django
    django.setup()
    from arp_control.urls import urlpatterns

    api = yaml.safe_load((ROOT / 'contracts/control-api.v1.yaml').read_text('utf-8'))
    actual = {}
    for pattern in urlpatterns:
        route = '/' + re.sub(r'<uuid:(\w+)>', r'{\1}', str(pattern.pattern))
        cls = pattern.callback.view_class
        actual[route] = {method for method in ('get', 'post', 'patch', 'put', 'delete') if hasattr(cls, method)}
    documented = {path: {method for method in body if method in ('get', 'post', 'patch', 'put', 'delete')}
                  for path, body in api['paths'].items()}
    assert actual == documented, 'OpenAPI paths/methods differ from implemented routes.'

    def check_refs(value):
        if isinstance(value, dict):
            if '$ref' in value:
                target = value['$ref']
                assert target.startswith('#/'), 'Only local OpenAPI references are supported.'
                resolved = api
                for part in target[2:].split('/'):
                    resolved = resolved[part]
            for child in value.values():
                check_refs(child)
        elif isinstance(value, list):
            for child in value:
                check_refs(child)
    check_refs(api)
    images = json.loads((ROOT / 'infra/images.lock.json').read_text('utf-8'))['images']
    assert set(images) == {'python', 'postgres', 'redis'}
    for name, value in images.items():
        assert re.fullmatch(r'sha256:[a-f0-9]{64}', value['digest'])
        assert value['image'] == f'{name}:{value["tag"]}@{value["digest"]}'
        assert 'latest' not in value['image']
    compose = yaml.safe_load((ROOT / 'infra/compose.yaml').read_text('utf-8'))
    assert set(compose['services']) == {'db', 'redis', 'migrate', 'control'}
    assert compose['services']['control']['environment']['AI_ENABLED'] == 'false'
    assert 'POSTGRES_PASSWORD' not in compose['services']['control']['environment']
    assert yaml.safe_load((ROOT / '.github/workflows/p0.yaml').read_text('utf-8'))['jobs']
    legacy = 'D:\\' + '\u5305\u88f9\u7269\u6d41\u65f6\u6548'
    for directory in ('apps/control', 'packages/contracts', 'infra'):
        for path in (ROOT / directory).rglob('*'):
            if path.is_file() and (path.suffix in ('.py', '.sh', '.yaml', '.json') or path.name.endswith('Dockerfile')):
                content = path.read_text('utf-8')
                assert legacy.casefold() not in content.casefold(), f'Legacy runtime path in {path.relative_to(ROOT)}'
                assert 'sys.path.insert' not in content, f'Non-independent import path in {path.relative_to(ROOT)}'
    print('PASS: OpenAPI route parity/local refs, immutable image metadata, Compose structure, CI syntax and independent code paths.')
    print('Scope: offline structure only; Docker/PG/Redis and Python 3.12 execution are not proved by this check.')


if __name__ == '__main__':
    main()
