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
