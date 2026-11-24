"""Quién ve cada calendario y cada actividad (rediseño del calendario, 2026-11).

Reglas aprobadas por el Gerente:

- Calendario de EQUIPO sin miembros: lo ven todos (así funcionaban las
  «categorías» antes). Con miembros: solo ellos; crean eventos los miembros
  con ``puede_crear``.
- Calendario PERSONAL: solo su dueño (ni el superusuario lo ve).
- Actividad CON participantes: solo la ven ellos y quien la creó.
- Actividad SIN participantes: la ve quien ve su calendario (sin calendario,
  todos, como antes).

Toda vista del calendario o del Gantt pasa por aquí; una actividad que el
usuario no ve responde 404, no 403, para no confirmar que existe.
"""
from django.db.models import Q

from trabajadores.permissions import trabajador_tiene_permiso

from .models import CalendarioActividad, CalendarioCategoria


def calendarios_visibles(user):
    equipo = Q(tipo=CalendarioCategoria.TIPO_EQUIPO) & (
        Q(miembros__isnull=True) | Q(miembros__user=user)
    )
    if user.is_superuser:
        equipo = Q(tipo=CalendarioCategoria.TIPO_EQUIPO)
    personal = Q(tipo=CalendarioCategoria.TIPO_PERSONAL, propietario=user)
    ids = CalendarioCategoria.objects.filter(activo=True).filter(equipo | personal).values('id')
    return CalendarioCategoria.objects.filter(id__in=ids).order_by('tipo', 'nombre')


def puede_crear_en(user, calendario):
    """¿Puede ``user`` crear o mover eventos en ``calendario``?"""
    if calendario is None:
        return trabajador_tiene_permiso(user, 'calendario.crear')
    if not calendario.activo:
        return False
    if calendario.es_personal:
        return calendario.propietario_id == user.id
    if not trabajador_tiene_permiso(user, 'calendario.crear'):
        return False
    if user.is_superuser:
        return True
    miembros = calendario.miembros.all()
    if not miembros.exists():
        return True
    return miembros.filter(user=user, puede_crear=True).exists()


def actividades_visibles(user):
    participa = Q(participantes__trabajador__user=user)
    sin_participantes = ~Q(id__in=CalendarioActividad.objects.filter(
        participantes__isnull=False).values('id'))
    por_calendario = Q(categoria__isnull=True) | Q(categoria__in=calendarios_visibles(user))
    ids = CalendarioActividad.objects.filter(
        Q(creado_por=user) | participa | (sin_participantes & por_calendario)
    ).values('id')
    # Un calendario personal ajeno nunca se ve, aunque te hayan puesto de participante
    # en un evento suyo: el dueño lo eligió como «solo yo».
    personal_ajeno = Q(categoria__tipo=CalendarioCategoria.TIPO_PERSONAL) & ~Q(categoria__propietario=user)
    return CalendarioActividad.objects.filter(id__in=ids).exclude(personal_ajeno)
