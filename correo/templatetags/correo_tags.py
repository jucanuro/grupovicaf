from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def fecha_corta(valor):
    """Hoy: 14:05 · este año: 12 nov · antes: 12/11/25."""
    if not valor:
        return ''
    local = timezone.localtime(valor)
    hoy = timezone.localdate()
    if local.date() == hoy:
        return local.strftime('%H:%M')
    if local.year == hoy.year:
        meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
        return f'{local.day} {meses[local.month - 1]}'
    return local.strftime('%d/%m/%y')


@register.filter
def iniciales(texto):
    partes = [p for p in (texto or '').replace('@', ' ').split() if p[:1].isalnum()]
    return ''.join(p[0] for p in partes[:2]).upper() or '?'


@register.filter
def remitente(mensaje):
    return mensaje.de_nombre or mensaje.de


ICONOS_CARPETA = {
    'entrada': 'bandeja', 'salida': 'reloj', 'enviados': 'enviar', 'borradores': 'lapiz',
    'archivados': 'archivar', 'spam': 'spam', 'papelera': 'papelera',
}


@register.filter
def icono_carpeta(tipo):
    return ICONOS_CARPETA.get(tipo, 'carpeta')


@register.filter
def grupo_fecha(valor):
    """Encabezado de grupo de la lista, como Outlook: Hoy, Ayer, Esta semana…"""
    if not valor:
        return ''
    dia = timezone.localtime(valor).date()
    dias = (timezone.localdate() - dia).days
    if dias <= 0:
        return 'Hoy'
    if dias == 1:
        return 'Ayer'
    if dias < 7:
        return 'Esta semana'
    if dias < 14:
        return 'La semana pasada'
    if dia.year == timezone.localdate().year:
        meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
                 'septiembre', 'octubre', 'noviembre', 'diciembre']
        return meses[dia.month - 1].capitalize()
    return str(dia.year)


@register.simple_tag
def puede_administrar_correo(user):
    """Muestra el acceso a «Administrar cuentas» en la barra superior."""
    from correo.administracion import puede_administrar_algo
    return puede_administrar_algo(user)
