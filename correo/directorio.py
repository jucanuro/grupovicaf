"""Directorio para el autocompletado de Para/CC/CCO (como la libreta de Outlook).

Fuentes, en este orden de prioridad:
1. Personas con las que ya se habló desde las cuentas que el usuario puede
   abrir (participantes de sus hilos), las más recientes primero.
2. Las cuentas VICAF activas (informes@, laboratorio@…).
3. El equipo VICAF: trabajadores activos (TrabajadorProfile) con correo.
4. Clientes del LIMS, solo si el usuario tiene `clientes.ver`.

Regla de privacidad: un contacto que solo aparece en hilos de una cuenta que
el usuario no puede abrir no se le sugiere (el servidor filtra, no el JS).

Sin texto (el campo acaba de recibir el foco) devuelve los contactos recientes.
La búsqueda no distingue mayúsculas ni tildes en Postgres («perez» = «Pérez»).
"""
import unicodedata

from django.db import connection
from django.db.models import Max, Q

from clientes.models import Cliente
from trabajadores.models import TrabajadorProfile
from trabajadores.permissions import trabajador_tiene_permiso

from .cuentas import cuentas_de
from .models import Contacto, CuentaCorreo

LIMITE = 10
POR_FUENTE = 25


def _plano(texto):
    texto = unicodedata.normalize('NFKD', texto or '')
    return ''.join(c for c in texto if not unicodedata.combining(c)).lower()


def _q(campos, q):
    """OR de `campo contiene q`, sin tildes cuando la base lo permite."""
    sufijo = '__unaccent__icontains' if connection.vendor == 'postgresql' else '__icontains'
    filtro = Q()
    for campo in campos:
        filtro |= Q(**{campo + sufijo: q})
    return filtro


def _puntaje(item, q):
    """0 = el correo empieza por q; 1 = una palabra del nombre empieza por q; 2 = lo contiene."""
    correo = item['correo']
    if correo.startswith(q):
        return 0
    palabras = _plano(f"{item['nombre']} {item.get('detalle', '')}").replace('.', ' ').split()
    palabras += correo.replace('.', ' ').replace('@', ' ').split()
    return 1 if any(p.startswith(q) for p in palabras) else 2


def sugerir(user, q='', limite=LIMITE, excluir=()):
    q = (q or '').strip()
    plano = _plano(q)
    cuentas = list(cuentas_de(user).values_list('pk', flat=True))
    excluir = {e.strip().lower() for e in excluir if e}
    resultados, vistos = [], set(excluir)

    def agregar(correo, nombre, detalle, tipo):
        correo = (correo or '').strip().lower()
        if '@' in correo and correo not in vistos:
            vistos.add(correo)
            resultados.append({'correo': correo, 'nombre': (nombre or '').strip(), 'detalle': detalle, 'tipo': tipo})

    # 1. Contactos de los hilos de mis cuentas, los más recientes primero.
    contactos = (Contacto.objects.filter(hilos__cuenta_id__in=cuentas)
                 .annotate(ultimo=Max('hilos__ultimo_mensaje_en')).order_by('-ultimo'))
    if q:
        contactos = contactos.filter(_q(('correo', 'nombre', 'empresa'), q))
    for c in contactos[:POR_FUENTE if q else limite]:
        agregar(c.correo, c.nombre, c.empresa, 'reciente')
    if not q:
        return resultados[:limite]

    # 2. Cuentas VICAF.
    for c in CuentaCorreo.objects.filter(_q(('direccion', 'nombre'), q), activa=True)[:POR_FUENTE]:
        agregar(c.direccion, c.nombre, 'Cuenta VICAF', 'vicaf')

    # 3. Equipo VICAF.
    # Solo trabajadores: un usuario del portal de clientes no es «equipo».
    perfiles = (TrabajadorProfile.objects.filter(user__is_active=True)
                .filter(_q(('user__email', 'correo_contacto', 'nombre_completo', 'user__first_name', 'user__last_name'), q))
                .select_related('user')[:POR_FUENTE])
    for p in perfiles:
        agregar(p.user.email or p.correo_contacto, p.nombre_completo or p.user.get_full_name(), 'Equipo VICAF', 'equipo')

    # 4. Clientes del LIMS (solo con permiso).
    if trabajador_tiene_permiso(user, 'clientes.ver'):
        clientes = (Cliente.objects.filter(_q(('correo_contacto', 'razon_social', 'persona_contacto'), q))
                    .values('correo_contacto', 'persona_contacto', 'razon_social')[:POR_FUENTE])
        for c in clientes:
            agregar(c['correo_contacto'], c['persona_contacto'], f'Cliente LIMS · {c["razon_social"]}', 'cliente')

    # Orden estable: primero lo que empieza por q; dentro de cada grupo, el orden de las fuentes.
    resultados.sort(key=lambda item: _puntaje(item, plano))
    return resultados[:limite]
