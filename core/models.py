from django.db import IntegrityError, models, transaction


class Correlativo(models.Model):
    """Último número emitido de una serie documental (VCF-OTE-2026, INF-2026...).

    Sustituye al "leer el último código y sumar 1": con dos usuarios a la vez
    ambos leían el mismo último número, y el Max() sobre texto ordena
    "999" después de "1000". Aquí la fila de la serie se bloquea con
    select_for_update y el contador es un entero.
    """

    clave = models.CharField(max_length=100, unique=True)
    ultimo = models.PositiveIntegerField(default=0)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Correlativo'
        verbose_name_plural = 'Correlativos'

    def __str__(self):
        return f'{self.clave}: {self.ultimo}'


def _ultimo_numero(codigos_existentes):
    numeros = []
    for codigo in codigos_existentes:
        try:
            numeros.append(int(str(codigo).rsplit('-', 1)[-1]))
        except (TypeError, ValueError):
            continue
    return max(numeros, default=0)


def siguiente_correlativo(clave, codigos_existentes=()):
    """Reserva y devuelve el siguiente número (int) de la serie ``clave``.

    ``codigos_existentes`` solo se lee la primera vez que se usa la serie,
    para continuar la numeración que ya había en la base (p. ej. un
    queryset ``values_list('numero_oferta', flat=True)``). Si la transacción
    del llamador se revierte, el número también: no quedan huecos por errores.
    """
    with transaction.atomic():
        correlativo = Correlativo.objects.select_for_update().filter(clave=clave).first()
        if correlativo is None:
            try:
                with transaction.atomic():
                    Correlativo.objects.create(clave=clave, ultimo=_ultimo_numero(codigos_existentes))
            except IntegrityError:
                pass  # otra petición creó la serie a la vez; se bloquea la suya abajo
            correlativo = Correlativo.objects.select_for_update().get(clave=clave)
        correlativo.ultimo += 1
        correlativo.save(update_fields=['ultimo', 'actualizado'])
        return correlativo.ultimo
