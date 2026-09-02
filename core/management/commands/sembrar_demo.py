"""Genera un dataset de demostración coherente para el LIMS.

Respeta la cadena de dependencias:

    RolTrabajador -> PermisoModulo -> User+TrabajadorProfile
    catálogos (TipoMuestra, UnidadMedida, Subcategoria, CalendarioCategoria)
    Cotizacion (+ grupos + detalles)
        -> Proyecto (por cotización aceptada)
        -> RecepcionMuestra (+ MuestraDetalle)
            -> SolicitudEnsayo (+ DetalleSolicitudEnsayo, + IncidenciaSolicitud)
    CalendarioActividad (ligada a proyectos / solicitudes)

NO genera InformeFinal (requiere un PDF real por informe).

Todo lo generado lleva un marcador para poder borrarlo:
    Cotizacion.numero_oferta      -> 'COT-DEMO-XXXX'
    Proyecto.codigo_proyecto      -> 'PROY-DEMO-XXXX'
    SolicitudEnsayo.codigo_solicitud -> 'SOL-DEMO-XXXX'
    User.username                 -> 'demo.trabNN'
    CalendarioActividad.origen_modelo -> 'demo'

Uso:
    python manage.py sembrar_demo            # crea (falla si ya hay datos demo)
    python manage.py sembrar_demo --reset    # borra los datos demo y los recrea
"""
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from clientes.models import Cliente
from servicios.models import (
    CategoriaServicio, Subcategoria, Servicio,
    Cotizacion, CotizacionGrupo, CotizacionDetalle,
)
from trabajadores.models import (
    ModuloSistema, AccionPermiso, PermisoModulo, RolTrabajador, TrabajadorProfile,
)
from proyectos.models import (
    Proyecto, TipoMuestra, UnidadMedida,
    RecepcionMuestra, MuestraDetalle,
    SolicitudEnsayo, DetalleSolicitudEnsayo, IncidenciaSolicitud,
)
from actividades.models import CalendarioCategoria, CalendarioActividad

RNG = random.Random(20260902)

NOMBRES = [
    "Carlos Mendoza Silva", "María Quispe Huamán", "Jorge Ramírez Vega",
    "Ana Torres Bautista", "Luis Vargas Cruz", "Rosa Flores Chávez",
    "Pedro Huamán Rojas", "Carmen Díaz Salazar", "José Castillo Ninaquispe",
    "Lucía Rojas Terán", "Miguel Paredes Cabrera", "Elena Chávez Idrogo",
]
TITULOS = ["Ing.", "Bach.", "Tec.", ""]
ROLES = [
    ("Gerente General", "Dirección, aprobación de cotizaciones y firma de informes."),
    ("Jefe de Laboratorio", "Revisión técnica, asignación de ensayos y control de calidad."),
    ("Técnico de Laboratorio", "Ejecución de ensayos y registro de resultados."),
    ("Recepción de Muestras", "Recepción, codificación y custodia de muestras."),
]
ASUNTOS = [
    "Estudio de Mecánica de Suelos con fines de cimentación",
    "Control de calidad de concreto en obra",
    "Diseño de mezcla de concreto f'c=210 kg/cm²",
    "Ensayos triaxiales para análisis de estabilidad de talud",
    "Caracterización de cantera para material de préstamo",
    "Ensayos de compactación y CBR para estructura de pavimento",
    "Evaluación de estructura de concreto existente",
    "Análisis granulométrico y límites de Atterberg",
    "Ensayos químicos de suelos y agua subterránea",
    "Control de densidad de campo en relleno estructural",
]
OBRAS = [
    "Carretera Cajamarca - Celendín Tramo II", "Edificio Multifamiliar Los Sauces",
    "I.E. N° 82016 San Marcos", "Planta de Tratamiento de Agua Potable SEDACAJ",
    "Puente Carrozable Río Chonta", "Pavimentación Jr. Los Cedros - Baños del Inca",
    "Mejoramiento del Canal de Riego La Colpa", "Losa Deportiva Multiusos Distrital",
]
INCIDENCIAS = [
    "Muestra recibida con humedad excesiva; se coordinó con el cliente reprogramar el ensayo.",
    "Prensa hidráulica en mantenimiento correctivo; ensayo trasladado al día siguiente.",
    "Cantidad de material insuficiente para el ensayo solicitado; se pidió muestra adicional.",
    "Discrepancia en la identificación de la muestra; corregida con el representante del cliente.",
    "Corte de energía durante el ensayo; se repitió el procedimiento completo.",
]
CATEGORIAS = [
    "Mecánica de Suelos", "Concreto y Agregados", "Geotecnia",
    "Química de Materiales", "Control de Calidad", "Diseño de Mezclas",
]
SUBCATEGORIAS = [
    "Ensayos de campo", "Ensayos de laboratorio", "Diseño y cálculo",
    "Muestreo", "Certificación", "Consultoría técnica",
]
TIPOS_MUESTRA = [
    ("Suelo", "S"), ("Concreto", "C"), ("Agregado", "AG"),
    ("Roca", "R"), ("Agua", "AGU"), ("Asfalto", "AS"),
]
UNIDADES = [
    ("Kilogramo", "KG"), ("Gramo", "G"), ("Unidad", "UND"),
    ("Metro cúbico", "M3"), ("Ensayo", "ENS"),
]
CAL_CATEGORIAS = [
    ("Recepción", "#0ea5e9"), ("Ensayos", "#8b5cf6"), ("Entregas", "#10b981"),
    ("Reuniones", "#f59e0b"), ("Mantenimiento", "#ef4444"),
]
CLASES_ACT = ["REUNION", "LLAMADA", "VISITA", "RECEPCION", "ENSAYO",
              "ENTREGA", "INFORME", "SEGUIMIENTO", "MANTENIMIENTO", "CAPACITACION"]
PRIORIDADES = ["BAJA", "MEDIA", "MEDIA", "ALTA", "URGENTE"]

PRECIOS_FALLBACK = [Decimal(x) for x in (80, 120, 150, 250, 320, 450, 600, 90)]


def tel():
    return "9" + "".join(RNG.choice("0123456789") for _ in range(8))


class Command(BaseCommand):
    help = "Genera un dataset de demostración coherente para el LIMS."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Borra los datos demo existentes antes de recrearlos.",
        )
        parser.add_argument(
            "--permitir-prod", action="store_true",
            help="Ejecuta aunque DEBUG=False. NO usar en producción.",
        )

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        # Salvaguarda: este comando es solo para dev. En prod DEBUG=False
        # (grupovicaf/settings/prod.py), así que sin --permitir-prod no corre.
        if not settings.DEBUG and not options["permitir_prod"]:
            raise CommandError(
                "sembrar_demo está pensado solo para desarrollo (DEBUG=True). "
                "Detectado DEBUG=False. Si de verdad querés correrlo acá, pasá "
                "--permitir-prod (y después limpialo con --reset)."
            )

        if options["reset"]:
            self._borrar_demo()
        elif Cotizacion.objects.filter(numero_oferta__startswith="COT-DEMO-").exists():
            self.stderr.write(self.style.ERROR(
                "Ya hay datos demo. Corré con --reset para borrarlos y recrearlos."
            ))
            return

        if Cliente.objects.count() < 10:
            self.stderr.write(self.style.ERROR(
                "Se necesitan clientes cargados (corré cargar_clientes.py primero)."
            ))
            return
        if Servicio.objects.count() < 10:
            self.stderr.write(self.style.ERROR(
                "Se necesitan servicios cargados (corré cargar_servicios.py primero)."
            ))
            return

        with transaction.atomic():
            roles = self._roles_y_permisos()
            trabajadores = self._trabajadores(roles)
            catalogos = self._catalogos()
            cotizaciones = self._cotizaciones(trabajadores)
            proyectos = self._proyectos(cotizaciones)
            recepciones = self._recepciones(proyectos, trabajadores, catalogos)
            self._solicitudes(recepciones, trabajadores)
            self._actividades(trabajadores, proyectos)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Dataset demo generado:"))
        for etiqueta, modelo, filtro in [
            ("RolTrabajador", RolTrabajador, {}),
            ("PermisoModulo", PermisoModulo, {}),
            ("TrabajadorProfile", TrabajadorProfile, {}),
            ("Cotizacion (demo)", Cotizacion, {"numero_oferta__startswith": "COT-DEMO-"}),
            ("  CotizacionDetalle", CotizacionDetalle, {"grupo__cotizacion__numero_oferta__startswith": "COT-DEMO-"}),
            ("Proyecto (demo)", Proyecto, {"codigo_proyecto__startswith": "PROY-DEMO-"}),
            ("RecepcionMuestra", RecepcionMuestra, {"cotizacion__numero_oferta__startswith": "COT-DEMO-"}),
            ("  MuestraDetalle", MuestraDetalle, {"recepcion__cotizacion__numero_oferta__startswith": "COT-DEMO-"}),
            ("SolicitudEnsayo (demo)", SolicitudEnsayo, {"codigo_solicitud__startswith": "SOL-DEMO-"}),
            ("  DetalleSolicitudEnsayo", DetalleSolicitudEnsayo, {"solicitud__codigo_solicitud__startswith": "SOL-DEMO-"}),
            ("  IncidenciaSolicitud", IncidenciaSolicitud, {"solicitud__codigo_solicitud__startswith": "SOL-DEMO-"}),
            ("CalendarioActividad (demo)", CalendarioActividad, {"origen_modelo": "demo"}),
        ]:
            self.stdout.write(f"  {etiqueta:32} {modelo.objects.filter(**filtro).count()}")

    # ------------------------------------------------------------------
    def _borrar_demo(self):
        self.stdout.write("Borrando datos demo...")
        DetalleSolicitudEnsayo.objects.filter(
            solicitud__codigo_solicitud__startswith="SOL-DEMO-"
        ).delete()
        IncidenciaSolicitud.objects.filter(
            solicitud__codigo_solicitud__startswith="SOL-DEMO-"
        ).delete()
        SolicitudEnsayo.objects.filter(codigo_solicitud__startswith="SOL-DEMO-").delete()
        MuestraDetalle.objects.filter(
            recepcion__cotizacion__numero_oferta__startswith="COT-DEMO-"
        ).delete()
        RecepcionMuestra.objects.filter(
            cotizacion__numero_oferta__startswith="COT-DEMO-"
        ).delete()
        Proyecto.objects.filter(codigo_proyecto__startswith="PROY-DEMO-").delete()
        CotizacionDetalle.objects.filter(
            grupo__cotizacion__numero_oferta__startswith="COT-DEMO-"
        ).delete()
        CotizacionGrupo.objects.filter(
            cotizacion__numero_oferta__startswith="COT-DEMO-"
        ).delete()
        Cotizacion.objects.filter(numero_oferta__startswith="COT-DEMO-").delete()
        CalendarioActividad.objects.filter(origen_modelo="demo").delete()
        TrabajadorProfile.objects.filter(user__username__startswith="demo.trab").delete()
        User.objects.filter(username__startswith="demo.trab").delete()

    # ------------------------------------------------------------------
    def _roles_y_permisos(self):
        modulos = list(ModuloSistema.objects.all())
        acciones = list(AccionPermiso.objects.all())
        creados = 0
        for m in modulos:
            for a in acciones:
                _, nuevo = PermisoModulo.objects.get_or_create(modulo_sistema=m, accion=a)
                creados += int(nuevo)
        todos = list(PermisoModulo.objects.all())
        self.stdout.write(f"PermisoModulo: +{creados} (total {len(todos)})")

        roles = {}
        for nombre, desc in ROLES:
            rol, _ = RolTrabajador.objects.get_or_create(
                nombre=nombre, defaults={"descripcion": desc},
            )
            # Gerente y Jefe: todos los permisos; los demás: un subconjunto.
            if nombre in ("Gerente General", "Jefe de Laboratorio"):
                rol.permisos.set(todos)
            else:
                rol.permisos.set(RNG.sample(todos, k=min(20, len(todos))))
            roles[nombre] = rol
        self.stdout.write(f"RolTrabajador: {RolTrabajador.objects.count()}")
        return roles

    def _trabajadores(self, roles):
        rol_por_indice = (
            ["Gerente General"]
            + ["Jefe de Laboratorio"]
            + ["Recepción de Muestras"] * 2
            + ["Técnico de Laboratorio"] * 6
        )
        perfiles = []
        for i, nombre in enumerate(NOMBRES[:10], start=1):
            username = f"demo.trab{i:02d}"
            first, *rest = nombre.split()
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": " ".join(rest),
                    "email": f"{username}@grupovicaf.test",
                    "is_staff": True,
                    "is_active": True,
                },
            )
            user.set_password("demo1234")
            user.save()
            rol = roles[rol_por_indice[i - 1]]
            perfil, _ = TrabajadorProfile.objects.get_or_create(
                user=user,
                defaults={
                    "rol": rol,
                    "nombre_completo": nombre,
                    "titulo_profesional": RNG.choice(TITULOS) or None,
                    "telefono_contacto": tel(),
                    "correo_contacto": f"{username}@grupovicaf.test",
                },
            )
            perfiles.append(perfil)
        self.stdout.write(f"TrabajadorProfile: {len(perfiles)}")
        return {
            "todos": perfiles,
            "gerente": perfiles[0],
            "jefe": perfiles[1],
            "recepcion": perfiles[2:4],
            "tecnicos": perfiles[4:],
        }

    def _catalogos(self):
        for nombre in CATEGORIAS:
            CategoriaServicio.objects.get_or_create(nombre=nombre)
        for nombre in SUBCATEGORIAS:
            Subcategoria.objects.get_or_create(nombre=nombre)
        tipos = [
            TipoMuestra.objects.get_or_create(sigla=s, defaults={"nombre": n})[0]
            for n, s in TIPOS_MUESTRA
        ]
        unidades = [
            UnidadMedida.objects.get_or_create(codigo=c, defaults={"nombre": n})[0]
            for n, c in UNIDADES
        ]
        cal_cats = [
            CalendarioCategoria.objects.get_or_create(nombre=n, defaults={"color": col})[0]
            for n, col in CAL_CATEGORIAS
        ]
        self.stdout.write(
            f"Catálogos: {len(tipos)} tipos muestra, {len(unidades)} unidades, "
            f"{len(cal_cats)} categorías calendario"
        )
        return {"tipos": tipos, "unidades": unidades, "cal_cats": cal_cats}

    # ------------------------------------------------------------------
    def _cotizaciones(self, trab):
        clientes = list(Cliente.objects.all())
        servicios = list(Servicio.objects.all())
        categorias = list(CategoriaServicio.objects.all())
        hoy = timezone.now().date()
        estados = (["Aceptada"] * 40 + ["Pendiente"] * 4
                   + ["Enviada"] * 3 + ["Rechazada"] * 2 + ["Anulada"] * 1)
        RNG.shuffle(estados)

        cotizaciones = []
        for i in range(1, 51):
            cliente = RNG.choice(clientes)
            estado = estados[i - 1]
            cot = Cotizacion.objects.create(
                cliente=cliente,
                trabajador_responsable=RNG.choice([trab["gerente"], trab["jefe"]]),
                numero_oferta=f"COT-DEMO-{i:04d}",
                fecha_generacion=hoy - timedelta(days=RNG.randint(5, 150)),
                servicio_general=RNG.choice(categorias),
                asunto_servicio=RNG.choice(ASUNTOS),
                proyecto_asociado=RNG.choice(OBRAS),
                persona_contacto=cliente.persona_contacto or RNG.choice(NOMBRES),
                correo_contacto=cliente.correo_contacto or f"contacto{i}@demo.local",
                telefono_contacto=(cliente.celular_contacto or tel())[:20],
                estado=estado,
                plazo_entrega_dias=RNG.choice([15, 20, 30, 45]),
                forma_pago=RNG.choice(["Contado", "15_dias", "30_dias"]),
            )
            grupos = [
                CotizacionGrupo.objects.create(
                    cotizacion=cot, nombre_grupo=g, orden=k + 1,
                )
                for k, g in enumerate(RNG.sample(CATEGORIAS, k=RNG.randint(1, 3)))
            ]
            detalles = []
            for g in grupos:
                for _ in range(RNG.randint(2, 4)):
                    serv = RNG.choice(servicios)
                    precio = (serv.precio_base if serv.precio_base and serv.precio_base > 0
                              else RNG.choice(PRECIOS_FALLBACK))
                    cant = RNG.randint(1, 6)
                    detalles.append(CotizacionDetalle(
                        grupo=g, servicio=serv,
                        descripcion_especifica=serv.nombre,
                        unidad_medida=serv.unidad_base or "Ensayo",
                        cantidad=cant, precio_unitario=precio,
                        total_detalle=Decimal(cant) * precio,
                    ))
            CotizacionDetalle.objects.bulk_create(detalles)
            cot.save()  # recalcula subtotal / IGV / total desde los detalles
            cotizaciones.append(cot)
        self.stdout.write(f"Cotizacion: {len(cotizaciones)}")
        return cotizaciones

    def _proyectos(self, cotizaciones):
        aceptadas = [c for c in cotizaciones if c.estado == "Aceptada"]
        estados = (["EN_CURSO"] * 14 + ["MUESTRAS_ASIGNADAS"] * 8
                   + ["MUESTRAS_VALIDADAS"] * 6 + ["FINALIZADO"] * 8
                   + ["PENDIENTE"] * 3 + ["CANCELADO"] * 1)
        proyectos = []
        for i, cot in enumerate(aceptadas, start=1):
            inicio = cot.fecha_generacion + timedelta(days=RNG.randint(2, 12))
            p = Proyecto.objects.create(
                cotizacion=cot,
                nombre_proyecto=f"{cot.asunto_servicio} — {cot.proyecto_asociado}"[:255],
                codigo_proyecto=f"PROY-DEMO-{i:04d}",
                cliente=cot.cliente,
                descripcion_proyecto=(
                    f"Servicios de laboratorio para la obra «{cot.proyecto_asociado}» "
                    f"del cliente {cot.cliente.razon_social}."
                ),
                monto_cotizacion=cot.monto_total,
                codigo_voucher=f"OP-{RNG.randint(100000, 999999)}",
                fecha_inicio=inicio,
                fecha_entrega_estimada=inicio + timedelta(days=cot.plazo_entrega_dias),
                estado=estados[(i - 1) % len(estados)],
            )
            proyectos.append(p)
        self.stdout.write(f"Proyecto: {len(proyectos)}")
        return proyectos

    def _recepciones(self, proyectos, trab, catalogos):
        users_recepcion = [p.user for p in trab["recepcion"]]
        unidad_kg = next(u for u in catalogos["unidades"] if u.codigo == "KG")
        recepciones = []
        for p in proyectos:
            for _ in range(RNG.randint(1, 2)):
                fr = datetime.combine(
                    p.fecha_inicio + timedelta(days=RNG.randint(0, 20)),
                    time(hour=RNG.randint(8, 16), minute=RNG.choice([0, 30])),
                )
                rec = RecepcionMuestra.objects.create(
                    cotizacion=p.cotizacion,
                    procedencia=f"Obra: {p.cotizacion.proyecto_asociado}",
                    responsable_cliente=p.cliente.persona_contacto or RNG.choice(NOMBRES),
                    telefono=tel(),
                    fecha_recepcion=timezone.make_aware(fr),
                    responsable_recepcion=RNG.choice(users_recepcion),
                )
                for k in range(1, RNG.randint(2, 6) + 1):
                    tm = RNG.choice(catalogos["tipos"])
                    MuestraDetalle.objects.create(
                        recepcion=rec,
                        tipo_muestra=tm,
                        nro_item=k,
                        descripcion=f"Muestra de {tm.nombre.lower()} — Calicata C-{k}",
                        masa_aprox=Decimal(f"{RNG.uniform(0.5, 25):.2f}"),
                        cantidad=RNG.randint(1, 3),
                        unidad_medida=unidad_kg,
                        observaciones=RNG.choice(
                            [None, "Muestra en bolsa hermética", "Testigo cilíndrico 6\"x12\""]
                        ),
                    )
                recepciones.append(rec)

        # numero_muestras del proyecto = muestras de su cotización
        for p in proyectos:
            n = MuestraDetalle.objects.filter(recepcion__cotizacion=p.cotizacion).count()
            Proyecto.objects.filter(pk=p.pk).update(numero_muestras=n)

        total_m = MuestraDetalle.objects.filter(
            recepcion__cotizacion__numero_oferta__startswith="COT-DEMO-"
        ).count()
        self.stdout.write(f"RecepcionMuestra: {len(recepciones)} · MuestraDetalle: {total_m}")
        return recepciones

    def _solicitudes(self, recepciones, trab):
        tecnicos = trab["tecnicos"]
        estados = ["pendiente"] * 3 + ["proceso"] * 4 + ["finalizado"] * 3
        n_sol = 0
        n_det = 0
        n_inc = 0
        for i, rec in enumerate(recepciones, start=1):
            muestras = list(rec.muestras.all())
            cot_detalles = list(CotizacionDetalle.objects.filter(grupo__cotizacion=rec.cotizacion))
            if not muestras or not cot_detalles:
                continue

            entrega = (rec.fecha_recepcion.date() + timedelta(days=RNG.randint(10, 25)))
            elaborado = RNG.choice(tecnicos + [trab["jefe"]])
            sol = SolicitudEnsayo.objects.create(
                codigo_solicitud=f"SOL-DEMO-{i:04d}",
                recepcion=rec,
                cotizacion=rec.cotizacion,
                estado=RNG.choice(estados),
                fecha_solicitud=rec.fecha_recepcion.date() + timedelta(days=RNG.randint(0, 3)),
                fecha_entrega_programada=entrega,
                elaborado_por=elaborado,
                revisado_por=RNG.choice([trab["jefe"], trab["gerente"], None]),
            )
            n_sol += 1

            detalles = []
            for muestra in RNG.sample(muestras, k=min(len(muestras), RNG.randint(1, 4))):
                cd = RNG.choice(cot_detalles)
                serv = cd.servicio
                detalles.append(DetalleSolicitudEnsayo(
                    solicitud=sol,
                    muestra=muestra,
                    servicio_cotizado=cd,
                    descripcion_ensayo=serv.nombre[:255],
                    norma=(serv.norma.codigo if serv.norma else "A solicitud del cliente")[:255],
                    metodo=(serv.metodo.codigo if serv.metodo else None),
                    tecnico_asignado=RNG.choice(tecnicos),
                    fecha_entrega_programada=entrega,
                ))
            DetalleSolicitudEnsayo.objects.bulk_create(detalles)
            n_det += len(detalles)

            if RNG.random() < 0.25:
                IncidenciaSolicitud.objects.create(
                    solicitud=sol,
                    detalle_incidencia=RNG.choice(INCIDENCIAS),
                    representante_cliente=RNG.choice(NOMBRES),
                    representante_laboratorio=trab["jefe"],
                    esta_autorizada=RNG.random() < 0.6,
                )
                n_inc += 1

        self.stdout.write(
            f"SolicitudEnsayo: {n_sol} · DetalleSolicitudEnsayo: {n_det} · IncidenciaSolicitud: {n_inc}"
        )

    def _actividades(self, trab, proyectos):
        cal_cats = list(CalendarioCategoria.objects.all())
        users = [p.user for p in trab["todos"]]
        solicitudes = list(SolicitudEnsayo.objects.filter(
            codigo_solicitud__startswith="SOL-DEMO-"
        ).select_related("recepcion__cotizacion__cliente"))
        ahora = timezone.now()

        creadas = 0
        for i in range(50):
            clase = RNG.choice(CLASES_ACT)
            dia = ahora + timedelta(days=RNG.randint(-60, 60))
            inicio = dia.replace(
                hour=RNG.randint(8, 16), minute=RNG.choice([0, 30]), second=0, microsecond=0
            )
            fin = inicio + timedelta(hours=RNG.randint(1, 4))
            estado = ("COMPLETADA" if inicio < ahora - timedelta(days=2)
                      else RNG.choice(["PROGRAMADA", "PROGRAMADA", "EN_CURSO", "REPROGRAMADA"]))

            proyecto = RNG.choice(proyectos) if proyectos and RNG.random() < 0.5 else None
            solicitud = RNG.choice(solicitudes) if solicitudes and RNG.random() < 0.4 else None
            cliente = (proyecto.cliente if proyecto
                       else (solicitud.recepcion.cotizacion.cliente if solicitud else None))

            titulos = {
                "RECEPCION": "Recepción de muestras",
                "ENSAYO": "Ejecución de ensayo programado",
                "ENTREGA": "Entrega de resultados al cliente",
                "INFORME": "Elaboración de informe final",
                "REUNION": "Reunión de coordinación",
                "VISITA": "Visita técnica a obra",
                "LLAMADA": "Llamada de seguimiento",
                "SEGUIMIENTO": "Seguimiento de proyecto",
                "MANTENIMIENTO": "Mantenimiento de equipo",
                "CAPACITACION": "Capacitación interna",
            }
            titulo = titulos.get(clase, "Actividad de laboratorio")
            if cliente:
                titulo = f"{titulo} — {cliente.razon_social}"

            CalendarioActividad.objects.create(
                titulo=titulo[:255],
                descripcion=RNG.choice([None, f"Actividad ligada a {clase.lower()}."]),
                tipo="MANUAL",
                clase=clase,
                estado=estado,
                prioridad=RNG.choice(PRIORIDADES),
                categoria=RNG.choice(cal_cats),
                fecha_inicio=inicio,
                fecha_fin=fin,
                ubicacion=RNG.choice([None, "Laboratorio central", RNG.choice(OBRAS)]),
                cliente=cliente,
                proyecto=proyecto,
                solicitud_ensayo=solicitud,
                creado_por=RNG.choice(users),
                origen_modelo="demo",
            )
            creadas += 1
        self.stdout.write(f"CalendarioActividad: {creadas}")
