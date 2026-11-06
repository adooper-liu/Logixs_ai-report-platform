"""Resolve public image manifests only; does not pull images or start services."""
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

IMAGES = {'python': '3.12-slim-bookworm', 'postgres': '17-bookworm', 'redis': '8.2-bookworm'}


def resolve(name, tag):
    token_url = f'https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/{name}:pull'
    with urlopen(token_url, timeout=30) as response:
        token = json.load(response)['token']
    request = Request(
        f'https://registry-1.docker.io/v2/library/{name}/manifests/{tag}',
        headers={'Authorization': f'Bearer {token}', 'Accept': ', '.join([
            'application/vnd.oci.image.index.v1+json',
            'application/vnd.docker.distribution.manifest.list.v2+json',
            'application/vnd.oci.image.manifest.v1+json',
        ])},
    )
    with urlopen(request, timeout=30) as response:
        digest = response.headers['Docker-Content-Digest']
        manifest = json.load(response)
    if not digest.startswith('sha256:') or len(digest) != 71:
        raise ValueError('Unexpected registry manifest digest.')
    return {'tag': tag, 'digest': digest, 'image': f'{name}:{tag}@{digest}',
            'media_type': manifest.get('mediaType'), 'runtime_verified': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Refusing to overwrite an existing image lock; review it first.')
    images = {name: resolve(name, tag) for name, tag in IMAGES.items()}
    args.output.write_text(json.dumps({'schema_version': '1.0.0', 'images': images}, indent=2) + '\n', encoding='utf-8')
    print('Resolved public image digests. Containers were not built or run.')


if __name__ == '__main__':
    main()
