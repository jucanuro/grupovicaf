from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.db import migrations
from django.utils.text import slugify

# Imágenes ya presentes en static/web/img/servicios/ (reutilizadas de vicafpro,
# ver _ref/vicafpro/servicios/templates/servicios/servicios.html). Se copian a
# MEDIA_ROOT porque LineaServicio.imagen es un ImageField gestionado por el
# admin, no un static asset fijo.
STATIC_IMG_DIR = Path(settings.BASE_DIR) / 'static' / 'web' / 'img' / 'servicios'

LINEAS = [
    {
        'nombre': 'Control de Calidad',
        'slug': 'control-de-calidad',
        'resumen': 'Supervisión de procesos constructivos y verificación del cumplimiento de estándares técnicos y normativos.',
        'imagen': 'CC-1.webp',
        'orden': 0,
    },
    {
        'nombre': 'Mecánica de Suelos',
        'slug': 'mecanica-de-suelos',
        'resumen': 'Estudios geotécnicos especializados para evaluar estabilidad, resistencia y comportamiento del terreno.',
        'imagen': 'e_mecanica_suelos1.webp',
        'orden': 1,
    },
    {
        'nombre': 'Estudio de Canteras',
        'slug': 'estudio-de-canteras',
        'resumen': 'Evaluación de materiales de cantera para garantizar calidad, rendimiento y viabilidad técnica en obras civiles.',
        'imagen': 'EC-1.webp',
        'orden': 2,
    },
    {
        'nombre': 'Evaluación Estructural',
        'slug': 'evaluacion-estructural',
        'resumen': 'Inspección de estructuras y edificaciones para determinar seguridad, comportamiento estructural y condiciones operativas.',
        'imagen': 'ES-1.webp',
        'orden': 3,
    },
    {
        'nombre': 'Ensayos de Laboratorio',
        'slug': 'ensayos-de-laboratorio',
        'resumen': 'Ejecución de ensayos especializados en materiales de construcción bajo estándares técnicos y protocolos certificados.',
        'imagen': 'LB-3.webp',
        'orden': 4,
    },
    {
        'nombre': 'Ensayos Químicos',
        'slug': 'ensayos-quimicos',
        'resumen': 'Análisis de composición química y propiedades de materiales para validar compatibilidad, resistencia y durabilidad.',
        'imagen': 'QM-1.webp',
        'orden': 5,
    },
]


def placeholder_contenido(nombre):
    return (
        f'PENDIENTE DE REDACCIÓN — {nombre}\n\n'
        'Este texto debe reemplazarse por contenido comercial único de esta línea '
        'antes de quitarle el noindex. Incluir:\n'
        f'- Qué problema resuelve {nombre} para el cliente.\n'
        '- Ensayos que agrupa y para qué tipo de proyecto aplica cada uno.\n'
        '- Por qué la acreditación INACAL respalda estos resultados.\n\n'
        'No copiar este texto en otra línea de servicio: contenido duplicado o '
        'casi-idéntico es una doorway page y Google la penaliza (ver CLAUDE.md regla 16).'
    )


def seed_lineas(apps, schema_editor):
    LineaServicio = apps.get_model('web_catalogo', 'LineaServicio')
    for datos in LINEAS:
        nombre = datos['nombre']
        linea, _creada = LineaServicio.objects.update_or_create(
            slug=datos['slug'],
            defaults={
                'nombre': nombre,
                'titulo_h1': f'{nombre} en Cajamarca',
                'resumen': datos['resumen'],
                'contenido': placeholder_contenido(nombre),
                'orden': datos['orden'],
                'activo': True,
                # Contenido aún no redactado (ver placeholder arriba): noindex
                # hasta que el equipo escriba el texto único de cada línea.
                'noindex': True,
            },
        )

        ruta_imagen = STATIC_IMG_DIR / datos['imagen']
        if ruta_imagen.exists() and not linea.imagen:
            with open(ruta_imagen, 'rb') as archivo:
                linea.imagen.save(datos['imagen'], File(archivo), save=False)
            linea.imagen_alt = nombre
            linea.save(update_fields=['imagen', 'imagen_alt'])


def unseed_lineas(apps, schema_editor):
    LineaServicio = apps.get_model('web_catalogo', 'LineaServicio')
    slugs = [slugify(l['slug']) for l in LINEAS]
    LineaServicio.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('web_catalogo', '0002_lineaservicio_serviciopublicado_linea'),
    ]

    operations = [
        migrations.RunPython(seed_lineas, unseed_lineas),
    ]
