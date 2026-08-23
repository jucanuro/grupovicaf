from .models import DocumentoNosotros


def obtener_documentos_nosotros():
    """Agrupa documentos activos priorizando certificados, luego destacados.

    Portado de _ref/vicafpro/nosotros/services.py.
    """
    documentos = list(
        DocumentoNosotros.objects.filter(activo=True)
        .select_related('tipo')
        .only(
            'id', 'titulo', 'descripcion', 'imagen', 'archivo',
            'orden', 'destacado', 'fecha_publicacion',
            'tipo__nombre', 'tipo__slug',
        )
        .order_by('orden', '-destacado', '-creado')
    )

    certificados = [doc for doc in documentos if doc.es_certificado]
    otros = [doc for doc in documentos if not doc.es_certificado]

    if len(certificados) >= 3:
        documentos_principales = certificados[:3]
    else:
        documentos_principales = certificados + otros[:4 - len(certificados)]

    ids_principales = {doc.id for doc in documentos_principales}
    documentos_restantes = [doc for doc in documentos if doc.id not in ids_principales]

    return {
        'documentos': documentos,
        'documentos_principales': documentos_principales,
        'documentos_restantes': documentos_restantes,
    }
