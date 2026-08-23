from django.db import migrations

# Datos NAP confirmados por el equipo (dirección y coordenadas verificadas
# contra el iframe de Google Maps de _ref/vicafpro/contactenos/templates;
# teléfono y horario confirmados directamente, ver historial de la Fase 3).
CIUDADES_COBERTURA = [
    'Cajamarca', 'Jaén', 'Chota', 'Celendín', 'Bambamarca', 'Cajabamba', 'Cutervo',
]


def seed_negocio(apps, schema_editor):
    NegocioConfig = apps.get_model('siteconfig', 'NegocioConfig')
    NegocioConfig.objects.update_or_create(
        pk=1,
        defaults={
            'nombre': 'Grupo VICAF SAC',
            'descripcion': (
                'Laboratorio de ensayo de materiales y geotecnia acreditado por '
                'INACAL, con sede en Cajamarca y cobertura en el norte del Perú.'
            ),
            'direccion_calle': 'Jr. Los Topacios 440',
            'direccion_localidad': 'Cajamarca',
            'direccion_region': 'Cajamarca',
            'direccion_codigo_postal': '06002',
            'direccion_pais': 'PE',
            'telefono': '+51 964 326 364',
            'whatsapp': '+51964326364',
            'correo': 'informes@grupovicaf.com',
            'latitud': '-7.163736',
            'longitud': '-78.506165',
            'horario_semana_apertura': '08:00',
            'horario_semana_cierre': '18:00',
            'horario_sabado_apertura': '08:00',
            'horario_sabado_cierre': '13:00',
            'ciudades_cobertura': CIUDADES_COBERTURA,
            'acreditacion_entidad': 'INACAL',
            'acreditacion_codigo': 'LE-230',
            'linkedin_url': 'https://pe.linkedin.com/company/grupo-vicaf-sac',
            'facebook_url': 'https://www.facebook.com/grupovicaf/',
            'instagram_url': 'https://www.instagram.com/grupovicaf/',
        },
    )


def unseed_negocio(apps, schema_editor):
    NegocioConfig = apps.get_model('siteconfig', 'NegocioConfig')
    NegocioConfig.objects.filter(pk=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('siteconfig', '0002_negocioconfig'),
    ]

    operations = [
        migrations.RunPython(seed_negocio, unseed_negocio),
    ]
