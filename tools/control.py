"""Explicit environment-file wrapper, not a shell and not an implicit settings loader."""
import argparse
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--migration-role', action='store_true')
    parser.add_argument('--sqlite-tests', action='store_true')
    args, command = parser.parse_known_args()
    if args.sqlite_tests:
        if args.env_file or args.migration_role or (command and command[0] not in ('test', 'check', 'makemigrations')):
            parser.error('SQLite is only allowed for explicit tests/checks, never for serving the application.')
        os.environ['DJANGO_SETTINGS_MODULE'] = 'arp_control.test_settings'
        command = command or ['test', 'tests/control']
    else:
        os.environ['DJANGO_SETTINGS_MODULE'] = 'arp_control.settings'
        if args.env_file:
            for line in args.env_file.read_text('utf-8').splitlines():
                if not line.strip() or line.lstrip().startswith('#'):
                    continue
                key, separator, value = line.partition('=')
                if not separator or not key.replace('_', '').isalnum() or not key[0].isalpha():
                    parser.error('Invalid environment-file syntax; values are literal, without shell interpolation.')
                os.environ[key] = value
        if args.migration_role:
            os.environ['CONTROL_DATABASE_URL'] = os.environ['CONTROL_MIGRATION_DATABASE_URL']
    from arp_control.cli import main as control_main
    sys.argv = ['arp-control', *command]
    control_main()


if __name__ == '__main__':
    main()
