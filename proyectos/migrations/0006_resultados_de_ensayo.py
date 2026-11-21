# Compresión pasa a ser una plantilla de «Resultados de ensayo» (fase 1).
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import proyectos.models


def marcar_compresion(apps, schema_editor):
    # Todo lo registrado hasta hoy es de compresión.
    apps.get_model('proyectos', 'ResultadoEnsayo').objects.update(plantilla='compresion')


class Migration(migrations.Migration):

    dependencies = [
        ("trabajadores", "0011_permisos_informes_compresion"),
        ("proyectos", "0005_compresion_revision_informe"),
    ]

    operations = [
        migrations.RenameModel("EnsayoCompresion", "ResultadoEnsayo"),
        migrations.AlterModelOptions(
            name="resultadoensayo",
            options={"verbose_name": "Resultado de ensayo", "verbose_name_plural": "Resultados de ensayo"},
        ),
        migrations.AlterField(
            model_name="resultadoensayo",
            name="detalle",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE, related_name="resultado",
                to="proyectos.detallesolicitudensayo", verbose_name="Ensayo de la solicitud",
            ),
        ),
        migrations.AlterField(
            model_name="resultadoensayo",
            name="tecnico",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="resultados_ejecutados", to="trabajadores.trabajadorprofile",
                verbose_name="Ejecutado por",
            ),
        ),
        migrations.AlterField(
            model_name="resultadoensayo",
            name="aprobado_por",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="resultados_aprobados", to="trabajadores.trabajadorprofile",
            ),
        ),
        migrations.AddField(
            model_name="resultadoensayo",
            name="plantilla",
            field=models.CharField(
                choices=[("compresion", "Compresión de probetas (ASTM C39)"), ("general", "General")],
                default="general", max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="resultadoensayo",
            name="resumen",
            field=models.TextField(blank=True, default="", verbose_name="Resumen de resultados"),
        ),
        migrations.AddField(
            model_name="resultadoensayo",
            name="hoja_calculo",
            field=models.FileField(
                blank=True, storage=proyectos.models._almacen_fotos_ensayo,
                upload_to=proyectos.models.ruta_hoja_ensayo, verbose_name="Hoja de cálculo",
            ),
        ),
        migrations.AlterField(
            model_name="fotoensayo",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("carga", "Lectura de carga máxima"),
                    ("antes", "Probeta antes del ensayo"),
                    ("antes_pizarra", "Probeta antes del ensayo, con pizarra"),
                    ("despues", "Probeta fallada"),
                    ("despues_pizarra", "Probeta fallada, con pizarra"),
                    ("general_muestra", "Muestra o montaje del ensayo"),
                    ("general_resultado", "Resultado o lectura del equipo"),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(marcar_compresion, migrations.RunPython.noop),
    ]
