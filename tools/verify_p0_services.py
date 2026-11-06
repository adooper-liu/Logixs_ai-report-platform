"""Run only against disposable local P0 services, never production databases."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote, urlsplit
from urllib.request import urlopen

import psycopg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env-file', type=Path, required=True)
    args = parser.parse_args()
    values = dict(line.split('=', 1) for line in args.env_file.read_text('utf-8').splitlines()
                  if line and not line.startswith('#'))
    if values.get('APP_ENV') != 'development':
        raise SystemExit('Integration runner is limited to disposable development services.')
    parsed = urlsplit(values['CONTROL_DATABASE_URL'])
    if parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.path != '/control':
        raise SystemExit('Integration runner requires the documented loopback development database.')
    with psycopg.connect(values['CONTROL_DATABASE_URL']) as conn:
        role = conn.execute('SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=current_user').fetchone()
        assert role == (False, False, False), 'Application role is overprivileged.'
        allowed = conn.execute("SELECT has_schema_privilege(current_user, 'public', 'CREATE')").fetchone()[0]
        assert allowed is False, 'Application role must not perform DDL.'
        for table in ('foundation_projectconfigversion', 'foundation_auditevent'):
            for privilege in ('UPDATE', 'DELETE'):
                allowed = conn.execute('SELECT has_table_privilege(current_user, %s, %s)', (table, privilege)).fetchone()[0]
                assert allowed is False, 'Application role must not rewrite version/audit history.'
        for database in ('warehouse', 'superset'):
            allowed = conn.execute('SELECT has_database_privilege(current_user, %s, %s)', (database, 'CONNECT')).fetchone()[0]
            assert allowed is False, 'Application role must not connect to other platform databases.'
    with urlopen('http://127.0.0.1:8000/health/ready', timeout=15) as response:
        assert response.status == 200
    # Django creates and destroys a separate test_postgres database. The runtime
    # app and migrator never receive these bootstrap credentials.
    env = {**os.environ, **values,
           'DJANGO_SETTINGS_MODULE': 'arp_control.integration_settings', 'P0_REQUIRE_SERVICES': '1',
           'CONTROL_DATABASE_URL': f"postgresql://bootstrap:{quote(values['POSTGRES_PASSWORD'], safe='')}@{parsed.hostname}:{parsed.port}/postgres"}
    result = subprocess.run([sys.executable, '-I', '-m', 'arp_control.cli', 'test', 'tests/control', '--noinput'], env=env)
    if result.returncode:
        raise SystemExit(result.returncode)
    print('PASS: real PostgreSQL/Redis readiness, role boundaries, migrations, concurrency and control API tests.')


if __name__ == '__main__':
    main()
