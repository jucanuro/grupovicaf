from django.db import migrations

# Encargo #4: fijar el H1 (titulo_h1) de cada línea con página propia a su
# keyword objetivo, todas ancladas a Cajamarca. Solo se toca la fila si su
# titulo_h1 sigue en el valor por defecto sembrado ("<Nombre> en Cajamarca"),
# para no pisar una redacción posterior del equipo desde el admin.
KEYWORDS = {
    # slug: (titulo_h1_anterior, titulo_h1_nuevo)
    'mecanica-de-suelos': (
        'Mecánica de Suelos en Cajamarca',
        'Laboratorio de suelos en Cajamarca',
    ),
    'diseno-de-mezclas': (
        'Diseño de Mezclas en Cajamarca',
        'Diseño de mezclas de concreto en Cajamarca',
    ),
    'ensayos-quimicos': (
        'Ensayos Químicos en Cajamarca',
        'Ensayos químicos para materiales de construcción',
    ),
    'control-de-calidad': (
        'Control de Calidad en Cajamarca',
        'Control de calidad de materiales en Cajamarca',
    ),
}


def aplicar(apps, schema_editor):
    LineaServicio = apps.get_model('web_catalogo', 'LineaServicio')
    for slug, (anterior, nuevo) in KEYWORDS.items():
        LineaServicio.objects.filter(slug=slug, titulo_h1=anterior).update(titulo_h1=nuevo)


def revertir(apps, schema_editor):
    LineaServicio = apps.get_model('web_catalogo', 'LineaServicio')
    for slug, (anterior, nuevo) in KEYWORDS.items():
        LineaServicio.objects.filter(slug=slug, titulo_h1=nuevo).update(titulo_h1=anterior)


class Migration(migrations.Migration):

    dependencies = [
        ('web_catalogo', '0009_alter_serviciopublicado_zona_principal'),
    ]

    operations = [
        migrations.RunPython(aplicar, revertir),
    ]
