from django.db import migrations


def limpiar_web_zonas(apps, schema_editor):
    """Suelta la FK `zona` y las tablas de web_zonas (app eliminada).

    Idempotente y portable: solo actúa sobre lo que existe, así una base
    nueva —donde 0001_initial ya no crea la columna ni las tablas— lo salta
    sin error.
    """
    conn = schema_editor.connection
    with conn.cursor() as cursor:
        tablas = set(conn.introspection.table_names(cursor))
        columnas = set()
        if 'web_contacto_solicitudcotizacionweb' in tablas:
            columnas = {
                col.name
                for col in conn.introspection.get_table_description(
                    cursor, 'web_contacto_solicitudcotizacionweb'
                )
            }

    if 'zona_id' in columnas:
        schema_editor.execute(
            'ALTER TABLE "web_contacto_solicitudcotizacionweb" DROP COLUMN "zona_id"'
        )

    for tabla in ('web_zonas_zonacobertura_servicios', 'web_zonas_zonacobertura'):
        if tabla in tablas:
            schema_editor.execute('DROP TABLE "%s"' % tabla)


class Migration(migrations.Migration):

    dependencies = [
        ('web_contacto', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    limpiar_web_zonas, migrations.RunPython.noop, elidable=True
                ),
            ],
            state_operations=[],
        ),
    ]
