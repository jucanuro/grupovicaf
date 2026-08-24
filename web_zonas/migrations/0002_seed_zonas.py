from django.db import migrations
from django.utils.text import slugify

# Coordenadas aproximadas del centro de cada capital de provincia (Google Maps),
# sin confirmar en campo. Cajamarca sí es exacta: coincide con la sede en
# siteconfig/migrations/0003_seed_negocioconfig.py. Ajustar el resto si el
# equipo confirma una ubicación más precisa (ej. la del propio punto de acopio).
ZONAS = [
    {
        'nombre': 'Cajamarca', 'provincia': 'Cajamarca', 'es_sede': True,
        'latitud': '-7.163736', 'longitud': '-78.506165', 'orden': 0,
    },
    {
        'nombre': 'Jaén', 'provincia': 'Jaén', 'es_sede': False,
        'latitud': '-5.706944', 'longitud': '-78.805833', 'orden': 1,
    },
    {
        'nombre': 'Chota', 'provincia': 'Chota', 'es_sede': False,
        'latitud': '-6.554444', 'longitud': '-78.648611', 'orden': 2,
    },
    {
        'nombre': 'Celendín', 'provincia': 'Celendín', 'es_sede': False,
        'latitud': '-6.866389', 'longitud': '-78.149444', 'orden': 3,
    },
    {
        'nombre': 'Bambamarca', 'provincia': 'Hualgayoc', 'es_sede': False,
        'latitud': '-6.677222', 'longitud': '-78.530278', 'orden': 4,
    },
    {
        'nombre': 'Cajabamba', 'provincia': 'Cajabamba', 'es_sede': False,
        'latitud': '-7.615278', 'longitud': '-78.050278', 'orden': 5,
    },
    {
        'nombre': 'Cutervo', 'provincia': 'Cutervo', 'es_sede': False,
        'latitud': '-6.373611', 'longitud': '-78.811389', 'orden': 6,
    },
]


def placeholder_contenido(nombre):
    return (
        f'PENDIENTE DE REDACCIÓN — {nombre}\n\n'
        'Este texto debe reemplazarse por contenido único de esta zona antes de '
        'quitarle el noindex. Incluir:\n'
        f'- Proyectos reales ejecutados en {nombre} (obra, tipo de ensayo, cliente si es público).\n'
        f'- Tiempos de respuesta típicos desde {nombre} hasta el laboratorio en Cajamarca.\n'
        f'- Cómo se envían las muestras desde {nombre} (transporte, encomienda, recojo).\n'
        f'- Referencias locales de {nombre} (vías de acceso, gremios, obras conocidas).\n\n'
        'No copiar este texto en otra zona: contenido duplicado o casi-idéntico entre '
        'zonas es una doorway page y Google la penaliza (ver CLAUDE.md regla 16).'
    )


def placeholder_introduccion(nombre):
    return f'PENDIENTE DE REDACCIÓN — resumen breve (1-2 líneas) de la cobertura en {nombre}.'


def seed_zonas(apps, schema_editor):
    ZonaCobertura = apps.get_model('web_zonas', 'ZonaCobertura')
    for datos in ZONAS:
        nombre = datos['nombre']
        titulo_h1 = (
            f'Laboratorio de suelos y materiales en {nombre}' if datos['es_sede']
            else f'Laboratorio de suelos en {nombre}'
        )
        ZonaCobertura.objects.update_or_create(
            slug=slugify(nombre),
            defaults={
                'nombre': nombre,
                'provincia': datos['provincia'],
                'departamento': 'Cajamarca',
                'titulo_h1': titulo_h1,
                'introduccion': placeholder_introduccion(nombre),
                'contenido': placeholder_contenido(nombre),
                'latitud': datos['latitud'],
                'longitud': datos['longitud'],
                'es_sede': datos['es_sede'],
                'orden': datos['orden'],
                'activo': True,
                # Contenido aún no redactado (ver placeholder arriba): noindex
                # hasta que el equipo escriba el texto único de cada zona.
                'noindex': True,
            },
        )


def unseed_zonas(apps, schema_editor):
    ZonaCobertura = apps.get_model('web_zonas', 'ZonaCobertura')
    slugs = [slugify(z['nombre']) for z in ZONAS]
    ZonaCobertura.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('web_zonas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_zonas, unseed_zonas),
    ]
