from django.db import migrations


def immutable_table_grants(apps, schema_editor, grant=False):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = 'control_app'")
        if not cursor.fetchone():
            return
        for table in ('foundation_projectconfigversion', 'foundation_auditevent'):
            if grant:
                cursor.execute(f'GRANT UPDATE, DELETE ON TABLE {table} TO control_app')
            else:
                cursor.execute(f'REVOKE UPDATE, DELETE ON TABLE {table} FROM control_app')


def restore_grants(apps, schema_editor):
    immutable_table_grants(apps, schema_editor, grant=True)


class Migration(migrations.Migration):
    dependencies = [('foundation', '0001_initial')]
    operations = [migrations.RunPython(immutable_table_grants, restore_grants)]
