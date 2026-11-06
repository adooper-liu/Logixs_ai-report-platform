"""Resolve public image manifests only; does not pull images or start services."""
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

IMAGES = {'python': '3.12-slim-bookworm', 'postgres': '17-bookworm', 'redis': '8.2-bookworm'}


def resolve(name, tag):
    # Public Docker Hub tag metadata also exposes the immutable index digest.
    # This avoids needing a Docker daemon merely to lock a deployment definition.
    source = f'https://hub.docker.com/v2/repositories/library/{name}/tags/{tag}'
    with urlopen(Request(source, headers={'User-Agent': 'arp-image-lock/0.1'}), timeout=30) as response:
        manifest = json.load(response)
    digest = manifest['digest']
    if not digest.startswith('sha256:') or len(digest) != 71:
        raise ValueError('Unexpected registry manifest digest.')
    return {'tag': tag, 'digest': digest, 'image': f'{name}:{tag}@{digest}',
            'metadata_source': source, 'media_type': manifest.get('media_type'), 'runtime_verified': False}


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--output', type=Path)
    group.add_argument('--from-lock', type=Path)
    parser.add_argument('--env-output', type=Path)
    args = parser.parse_args()
    if (args.output and args.output.exists()) or (args.env_output and args.env_output.exists()):
        raise SystemExit('Refusing to overwrite an existing image lock or environment file; review it first.')
    if args.from_lock:
        images = json.loads(args.from_lock.read_text('utf-8'))['images']
        if set(images) != set(IMAGES):
            raise SystemExit('Unexpected image lock entries.')
        for name, value in images.items():
            digest = value['digest']
            if (not digest.startswith('sha256:') or len(digest) != 71
                    or any(c not in '0123456789abcdef' for c in digest[7:])
                    or value['image'] != f'{name}:{value["tag"]}@{digest}'):
                raise SystemExit('Invalid immutable image reference.')
    else:
        images = {name: resolve(name, tag) for name, tag in IMAGES.items()}
        args.output.write_text(json.dumps({'schema_version': '1.0.0', 'images': images}, indent=2) + '\n', encoding='utf-8')
    if args.env_output:
        with args.env_output.open('x', encoding='utf-8', newline='\n') as output:
            for name, value in images.items():
                output.write(f'{name.upper()}_IMAGE={value["image"]}\n')
    print('Prepared immutable image references. Containers were not built or run.')


if __name__ == '__main__':
    main()
