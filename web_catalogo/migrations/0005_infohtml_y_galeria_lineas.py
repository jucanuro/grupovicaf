"""Migra el infoHtml de _ref/vicafpro (detalleservicios.html) al campo
contenido de LineaServicio, crea las 2 líneas que faltaban (mezclas,
equipos) y siembra ImagenLinea con las fotos reales de _ref, reencodeadas a
webp (ya usamos Pillow vía ImageField; sin esto la galería de la línea más
pesada — Ensayos de Laboratorio, 46 fotos .jpg de cámara — pesaría ~50 MB).

Con contenido real, se quita el noindex que puso 0003_seed_lineas_servicio
para el placeholder "PENDIENTE DE REDACCIÓN" (regla 15/16 de CLAUDE.md).
"""
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import migrations
from PIL import Image

DETALLE_IMG_DIR = Path(settings.BASE_DIR) / '_ref' / 'vicafpro' / 'static' / 'img' / 'detalleservicios'

EXTENSIONES_VALIDAS = {'.jpg', '.jpeg', '.png', '.webp'}

# Ancho máximo para las fotos de galería: son ilustrativas, no material de
# archivo, así que 1600px de lado largo es de sobra para pantalla y para el
# lightbox (ver linea_detalle.html).
ANCHO_MAXIMO = 1600
CALIDAD_WEBP = 78

LINEAS = [
    {
        'slug': 'control-de-calidad',
        'carpeta': 'controlcalidad',
        'contenido': (
            '<p>Garantizamos que los proyectos se completen de manera satisfactoria y cumplan '
            'con los estándares de calidad requeridos.</p>'
            '<h4>Servicios ofrecidos:</h4>'
            '<ul>'
            '<li>Densidad campo mediante el cono y arena</li>'
            '<li>Contenido de humedad en campo</li>'
            '<li>Medición de asentamiento del concreto con el cono de Abrams</li>'
            '<li>Medición de la temperatura del concreto fresco</li>'
            '<li>Toma de muestra de concreto</li>'
            '<li>Esclerometría</li>'
            '<li>Extracción de núcleos de concreto con diamantina</li>'
            '<li>Ensayos de control de calidad de agregados</li>'
            '</ul>'
            '<h4>Beneficios:</h4>'
            '<ul>'
            '<li>Personal competente</li>'
            '<li>Acompañamiento técnico</li>'
            '<li>Imparcialidad y confidencialidad</li>'
            '<li>Cumplimiento normativo</li>'
            '<li>Equipos calibrados por entidades acreditadas en INACAL</li>'
            '<li>Resultados inmediatos</li>'
            '</ul>'
        ),
    },
    {
        'slug': 'mecanica-de-suelos',
        'carpeta': 'ems',
        'contenido': (
            '<p>Ofrecemos estudios de mecánica de suelos con análisis precisos, ensayos '
            'especializados y asesoramiento técnico, garantizando resultados confiables para '
            'cimentaciones seguras en proyectos de construcción.</p>'
            '<h4>Beneficios:</h4>'
            '<ul>'
            '<li>Previsión de posibles problemas de cimentación a causa de suelos perjudiciales</li>'
            '<li>Personal competente</li>'
            '<li>Acompañamiento técnico</li>'
            '<li>Imparcialidad y confidencialidad</li>'
            '<li>Cumplimiento normativo</li>'
            '<li>Equipos calibrados por entidades acreditadas en INACAL</li>'
            '<li>Entrega de informes claros y estructurados</li>'
            '</ul>'
        ),
    },
    {
        'slug': 'estudio-de-canteras',
        'carpeta': 'canteras',
        'contenido': (
            '<p>Realizamos estudios de canteras con ensayos de laboratorio para determinar la '
            'calidad, resistencia y viabilidad de los materiales, asegurando el cumplimiento '
            'normativo y de las especificaciones del proyecto.</p>'
            '<h4>Beneficios:</h4>'
            '<ul>'
            '<li>Análisis detallado de materiales</li>'
            '<li>Evaluación de resistencia y calidad</li>'
            '<li>Optimización de la selección de materiales</li>'
            '<li>Aseguramiento de la viabilidad del proyecto</li>'
            '<li>Resultados confiables para decisiones informadas</li>'
            '<li>Control de calidad en todas las etapas</li>'
            '<li>Equipos calibrados por entidades acreditadas en INACAL</li>'
            '</ul>'
        ),
    },
    {
        'slug': 'evaluacion-estructural',
        'carpeta': 'estructuras',
        'contenido': (
            '<p>Nuestros ensayos para evaluación estructural brindan resultados detallados, '
            'esenciales para la fase de reforzamiento. Garantizamos información precisa que '
            'respalda la seguridad y estabilidad de sus proyectos en cada etapa.</p>'
            '<h4>Beneficios:</h4>'
            '<ul>'
            '<li>Precisión en resultados</li>'
            '<li>Identificación de posibles fallos</li>'
            '<li>Mejora en la seguridad estructural</li>'
            '<li>Soporte para decisiones de reforzamiento</li>'
            '<li>Optimización de la vida útil de la estructura</li>'
            '<li>Reducción de riesgos en la construcción</li>'
            '<li>Aseguramiento de la estabilidad a largo plazo</li>'
            '<li>Equipos calibrados por entidades acreditadas en INACAL</li>'
            '</ul>'
        ),
    },
    {
        'slug': 'ensayos-de-laboratorio',
        'carpeta': 'laboratorio',
        'contenido': (
            '<p>Realizamos ensayos de suelos, agregados y concreto con los más altos estándares '
            'de calidad. Contamos con acreditación INACAL-DA, garantizando resultados confiables '
            'y precisos para tus proyectos de construcción.</p>'
            '<p>Ya sea para control de calidad, diseño de mezclas o estudios geotécnicos, te '
            'brindamos el respaldo técnico que necesitas.</p>'
            '<h4>Beneficios:</h4>'
            '<ul>'
            '<li>Ensayos con acreditación INACAL (ver alcance de acreditación)</li>'
            '<li>Alta precisión y confiabilidad</li>'
            '<li>Cumplimiento de normativas técnicas nacionales e internacionales</li>'
            '<li>Resultados respaldados por profesionales especializados</li>'
            '<li>Equipos calibrados por entidades acreditadas en INACAL</li>'
            '<li>Garantía de resultados trazables</li>'
            '<li>Entrega de informes en el menor tiempo posible</li>'
            '</ul>'
        ),
    },
    {
        'slug': 'ensayos-quimicos',
        'carpeta': 'quimicos',
        'contenido': (
            '<p>Realizamos ensayos químicos especializados para identificar la agresividad de '
            'suelos y agregados, evaluando su impacto en estructuras y materiales. Prevenimos '
            'daños y optimizamos la durabilidad de tu proyecto.</p>'
            '<h4>Beneficios:</h4>'
            '<ul>'
            '<li>Evaluación de riesgo para cimentaciones y concreto</li>'
            '<li>Identificación de agresividad química</li>'
            '<li>Prevención de deterioro en estructuras por efectos químicos</li>'
            '<li>Optimización en la selección de materiales adecuados</li>'
            '<li>Mayor durabilidad y resistencia de las obras</li>'
            '<li>Reducción de costos por mantenimiento y reparaciones</li>'
            '<li>Resultados precisos y confiables con métodos especializados</li>'
            '<li>Decisiones más seguras en diseño y construcción</li>'
            '</ul>'
        ),
    },
    # Líneas que faltaban en 0003_seed_lineas_servicio (creadas aquí).
    {
        'slug': 'diseno-de-mezclas',
        'carpeta': 'mezclas',
        'nombre': 'Diseño de Mezclas',
        'orden': 6,
        'resumen': 'Diseño de mezclas de concreto adaptado a las necesidades específicas de cada proyecto.',
        'contenido': (
            '<p>Ofrecemos servicios de diseño de mezclas de concreto, adaptados a las necesidades '
            'específicas de su proyecto. Garantizamos resistencia, durabilidad y cumplimiento con '
            'las normativas vigentes para un rendimiento óptimo.</p>'
            '<h4>Beneficios:</h4>'
            '<ul>'
            '<li>Resistencia y durabilidad</li>'
            '<li>Optimización de costos</li>'
            '<li>Cumplimiento normativo</li>'
            '<li>Reducción de riesgos</li>'
            '<li>Asesoría técnica</li>'
            '<li>Eficiencia en el uso de recursos</li>'
            '<li>Equipos calibrados por entidades acreditadas en INACAL</li>'
            '</ul>'
        ),
    },
    {
        'slug': 'alquiler-de-equipos',
        'carpeta': 'equipos',
        'nombre': 'Alquiler de Equipos',
        'orden': 7,
        'resumen': 'Equipos de laboratorio para ensayos de suelos, agregados y concreto, calibrados y listos para su uso.',
        'contenido': '<p>Ponemos a tu disposición equipos de laboratorio para ensayos de suelos, agregados y concreto, calibrados y listos para su uso.</p>',
    },
]


def _archivos_imagen(carpeta):
    ruta = DETALLE_IMG_DIR / carpeta
    if not ruta.exists():
        return []
    return sorted(
        p for p in ruta.iterdir()
        if p.is_file() and p.suffix.lower() in EXTENSIONES_VALIDAS
    )


def _a_webp(ruta_origen):
    """Abre una foto de _ref, la reduce a ANCHO_MAXIMO y la reencodea a webp
    en memoria. Devuelve (nombre_archivo, ContentFile) o None si no se pudo
    leer (p. ej. un archivo corrupto colado en _ref)."""
    try:
        with Image.open(ruta_origen) as img:
            img = img.convert('RGB')
            if img.width > ANCHO_MAXIMO:
                alto = round(img.height * ANCHO_MAXIMO / img.width)
                img = img.resize((ANCHO_MAXIMO, alto), Image.LANCZOS)
            buffer = BytesIO()
            img.save(buffer, format='WEBP', quality=CALIDAD_WEBP)
    except Exception:
        return None
    nombre = ruta_origen.stem + '.webp'
    return nombre, ContentFile(buffer.getvalue())


def seed_contenido_y_galeria(apps, schema_editor):
    LineaServicio = apps.get_model('web_catalogo', 'LineaServicio')
    ImagenLinea = apps.get_model('web_catalogo', 'ImagenLinea')

    for datos in LINEAS:
        defaults = {'contenido': datos['contenido'], 'noindex': False}
        if 'nombre' in datos:
            defaults.update({
                'nombre': datos['nombre'],
                'titulo_h1': f"{datos['nombre']} en Cajamarca",
                'resumen': datos['resumen'],
                'orden': datos['orden'],
                'activo': True,
            })
            linea, _creada = LineaServicio.objects.update_or_create(
                slug=datos['slug'], defaults=defaults,
            )
        else:
            actualizadas = LineaServicio.objects.filter(slug=datos['slug']).update(**defaults)
            if not actualizadas:
                continue
            linea = LineaServicio.objects.get(slug=datos['slug'])

        if linea.galeria.exists():
            continue

        for orden, ruta_origen in enumerate(_archivos_imagen(datos['carpeta'])):
            resultado = _a_webp(ruta_origen)
            if resultado is None:
                continue
            nombre, contenido_archivo = resultado
            imagen_linea = ImagenLinea(
                linea=linea,
                alt_text=f"{linea.nombre} — evidencia fotográfica {orden + 1}",
                orden=orden,
                activo=True,
            )
            imagen_linea.imagen.save(nombre, contenido_archivo, save=False)
            imagen_linea.save()


def revertir(apps, schema_editor):
    LineaServicio = apps.get_model('web_catalogo', 'LineaServicio')
    slugs_nuevas = [d['slug'] for d in LINEAS if 'nombre' in d]
    LineaServicio.objects.filter(slug__in=slugs_nuevas).delete()
    # El contenido migrado y la galería de las líneas preexistentes se dejan
    # tal cual: no hay forma segura de volver al placeholder sin perder las
    # fotos subidas después por el equipo editorial.


class Migration(migrations.Migration):

    dependencies = [
        ('web_catalogo', '0004_imagenlinea'),
    ]

    operations = [
        migrations.RunPython(seed_contenido_y_galeria, revertir),
    ]
