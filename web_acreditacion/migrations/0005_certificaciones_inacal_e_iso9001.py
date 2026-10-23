# specs/WEB v4 (T18), paso 2 de 3: pasa las certificaciones de v3 (ISO 9001)
# al formato de card y crea la acreditación INACAL LE-230 (REQ-WEB-41).
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.db import migrations

# Imagen del certificado que la web mostraba en el hero y en el modal INACAL.
IMAGEN_INACAL = Path(settings.BASE_DIR) / 'static' / 'web' / 'img' / 'certificaciones' / 'GRUPO-VICAF-CERTIFICADO.webp'
ARCHIVO_INACAL = 'certificaciones/inacal-le-230.webp'
TITULO_INACAL = 'Acreditación INACAL LE-230'


def convertir_v3(apps, schema_editor):
    Certificacion = apps.get_model('web_acreditacion', 'Certificacion')
    for cert in Certificacion.objects.all():
        cert.titulo = f'Certificación {cert.norma}'[:120]
        partes = [cert.sistema or cert.norma]
        if cert.organismo:
            partes[0] += f' certificado por {cert.organismo.split(" S.A")[0]}'
        partes.append(f'Certificado N.º {cert.numero_certificado}')
        cert.descripcion = '. '.join(partes)[:199] + '.'
        cert.tipo = 'iso' if cert.norma.upper().startswith('ISO') else 'otro'
        cert.institucion = cert.organismo[:150]
        # INACAL va primero, como en la web de antes.
        cert.orden = cert.orden + 1
        cert.save(update_fields=['titulo', 'descripcion', 'tipo', 'institucion', 'orden'])


def crear_inacal(apps, schema_editor):
    Certificacion = apps.get_model('web_acreditacion', 'Certificacion')
    if Certificacion.objects.filter(tipo='acreditacion', titulo=TITULO_INACAL).exists():
        return
    archivo = ''
    if default_storage.exists(ARCHIVO_INACAL):
        archivo = ARCHIVO_INACAL
    elif IMAGEN_INACAL.exists():
        try:
            with IMAGEN_INACAL.open('rb') as origen:
                archivo = default_storage.save(ARCHIVO_INACAL, File(origen))
        except OSError as error:
            # Sin permiso de escritura en /media/ la fila se crea sin archivo
            # (no se publica, RN-15) y el administrador lo sube desde el admin.
            print(f'\n  Aviso: no se pudo copiar el certificado INACAL a {ARCHIVO_INACAL}: {error}')
    # La 0003 exige N.º único hasta que la 0006 lo quite.
    Certificacion.objects.create(
        titulo=TITULO_INACAL,
        descripcion=(
            'Laboratorio de ensayo acreditado según la NTP-ISO/IEC 17025:2017. '
            'Registro N.º LE-230.'
        ),
        tipo='acreditacion',
        institucion='Instituto Nacional de Calidad (INACAL)',
        archivo=archivo,
        vigencia_hasta=date(2027, 5, 27),
        orden=0,
        activo=True,
        norma='NTP-ISO/IEC 17025:2017',
        numero_certificado='LE-230',
        organismo='INACAL',
        alcance='',
    )


def adelante(apps, schema_editor):
    convertir_v3(apps, schema_editor)
    crear_inacal(apps, schema_editor)


def atras(apps, schema_editor):
    # El archivo copiado en /media/ se deja: puede estar en uso por otra fila.
    Certificacion = apps.get_model('web_acreditacion', 'Certificacion')
    Certificacion.objects.filter(tipo='acreditacion', titulo=TITULO_INACAL, numero_certificado='LE-230').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('web_acreditacion', '0004_certificacion_campos_card'),
    ]

    operations = [
        migrations.RunPython(adelante, atras),
    ]
