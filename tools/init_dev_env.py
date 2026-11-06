"""Create independent development secrets. Never overwrite or print credentials."""
import argparse
from pathlib import Path
import secrets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('.env'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    passwords = {key: secrets.token_hex(24) for key in (
        'POSTGRES_PASSWORD', 'CONTROL_OWNER_PASSWORD', 'CONTROL_APP_PASSWORD',
        'WAREHOUSE_OWNER_PASSWORD', 'SUPERSET_OWNER_PASSWORD', 'REDIS_PASSWORD',
    )}
    values = {
        'APP_ENV': 'development', 'DJANGO_SECRET_KEY': secrets.token_hex(48),
        'ALLOWED_HOSTS': 'localhost,127.0.0.1', 'CSRF_TRUSTED_ORIGINS': 'http://localhost:8000,http://127.0.0.1:8000',
        **passwords,
        'CONTROL_DATABASE_URL': f"postgresql://control_app:{passwords['CONTROL_APP_PASSWORD']}@127.0.0.1:55432/control",
        'CONTROL_MIGRATION_DATABASE_URL': f"postgresql://control_owner:{passwords['CONTROL_OWNER_PASSWORD']}@127.0.0.1:55432/control",
        'REDIS_URL': f"redis://:{passwords['REDIS_PASSWORD']}@127.0.0.1:56379/0",
        'BLOB_BACKEND': 'local', 'BLOB_ROOT': (root / '.local/objects').as_posix(),
        'AI_ENABLED': 'false', 'AI_ALLOW_RAW_SAMPLE_EGRESS': 'false',
    }
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write('# Generated independent development secrets. Do not commit or share.\n')
        for key, value in values.items():
            output.write(f'{key}={value}\n')
    print('Created development environment file without printing secrets. Protect its filesystem permissions.')


if __name__ == '__main__':
    main()
