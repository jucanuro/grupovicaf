from django.db import migrations
from django.db.models import Q

# Equipos que declara el informe real VCF-INF-2026-4582 (FOR-039). Los datos de
# calibración (marca, serie, certificado, vencimiento) quedan vacíos hasta que
# el laboratorio los entregue (P-05); se completan en Equipos del LIMS.
EQUIPOS = [
    ('VCF-EQ-PRC-001', 'Prensa de compresión', 'PRC'),
    ('VCF-EQ-BAL-011', 'Balanza', 'BAL'),
    ('VCF-EQ-VER-001', 'Vernier', 'VER'),
    ('VCF-EQ-TMG-006', 'Termohigrómetro', 'TMG'),
    ('VCF-EQ-CUÑ-001', 'Cuña', 'CUÑ'),
    ('VCF-EQ-ESC-001', 'Escuadra', 'ESC'),
]


def forwards(apps, schema_editor):
    Equipo = apps.get_model('proyectos', 'Equipo')
    for codigo, nombre, tipo in EQUIPOS:
        Equipo.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre, 'tipo': tipo})


def backwards(apps, schema_editor):
    # Solo borra los que nadie usó todavía.
    Equipo = apps.get_model('proyectos', 'Equipo')
    SesionEnsayo = apps.get_model('proyectos', 'SesionEnsayo')
    for codigo, _, _ in EQUIPOS:
        equipo = Equipo.objects.filter(codigo=codigo).first()
        if equipo is None:
            continue
        usado = SesionEnsayo.objects.filter(
            Q(prensa=equipo) | Q(balanza=equipo) | Q(vernier=equipo)
            | Q(termohigrometro=equipo) | Q(cuna=equipo) | Q(escuadra=equipo)
        ).exists()
        if not usado:
            equipo.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0003_compresion_medidas_equipos'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
