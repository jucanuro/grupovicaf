# Actualización: flujo completo de resultados → revisión → informe → envío (2026-11-26)

Cambios de T81 a T102 (VCF-LIMS). Esta guía es solo para esta actualización; el procedimiento general
está en `deploy/INSTRUCTIVO.md` y el script en `deploy/deploy.sh`.

## Qué trae

- Registro único de resultados (6 fotos, formulario FOR-009, video, sesión de ensayo grande), hoja de resumen, revisión por ensayo con marcas en rojo.
- Solicitudes por etapa, lista de resultados en filas, recepciones y detalle compactos; se elimina el formulario «Datos de probetas».
- Informe PDF con el diseño oficial (FOR-064 + FOR-039, sello INACAL, marca de agua, QR), «Informes» rehecho (sin emisión manual).
- Revisión de la solicitud a pantalla completa y envío inteligente al cliente (correo respondiendo el pedido, o WhatsApp).

## Antes de actualizar

1. Backup: `sudo deploy/scripts/backup.sh` (hay migraciones nuevas).
2. Confirmar que existe `ENSAYOS_FOTOS_DIR` (privado, escribible por el servicio y dentro del backup) — ya lo pedía la fase 1.
3. Fuentes para el PDF: `sudo apt install -y fonts-liberation` (el informe usa Liberation Sans; sin ella WeasyPrint cae a DejaVu y el diseño se desplaza).

## Actualizar

```bash
cd /var/www/projects/grupovicaf
bash deploy/deploy.sh main        # pull, pip, migrate, collectstatic, reinicia servicios
```

Migraciones nuevas de `proyectos` (se aplican solas en `deploy.sh`): **0011 a 0016**
(foto «durante», formulario configurable por servicio, video, marcas de revisión, canal y borrador de envío del informe).

## nginx (obligatorio para subir videos de hasta 300 MB)

```bash
diff /etc/nginx/sites-available/grupovicaf.conf deploy/nginx/grupovicaf.conf
sudo cp deploy/nginx/grupovicaf.conf /etc/nginx/sites-available/grupovicaf.conf
sudo nginx -t && sudo systemctl reload nginx
```

El bloque de `laboratorio.` admite 320 MB (`client_max_body_size 320M; client_body_timeout 300s;`).

## Después de actualizar

1. Pasar los informes ya emitidos por el editor al diseño nuevo (opcional pero recomendado; cambia lo que abre «Ver»):

   ```bash
   DJANGO_SETTINGS_MODULE=grupovicaf.settings.prod venv/bin/python manage.py regenerar_informes_diseno            # simulación
   DJANGO_SETTINGS_MODULE=grupovicaf.settings.prod venv/bin/python manage.py regenerar_informes_diseno --aplicar  # aplica
   ```

   Omite los informes con bloques convertidos en texto editable y los subidos a mano como PDF.
2. Probar a mano: abrir un informe con «Ver» (carátula + una hoja por ensayo + QR), «Enviar al cliente» (correo y WhatsApp) y un ensayo terminado en «Revisar».
3. Pendientes de contenido (no bloquean): reemplazar los dibujos de las fracturas por los oficiales si se tienen, y cargar la firma electrónica de quien firma los informes (sale en blanco si no hay).

## Si algo falla

- Volver al commit anterior: `git checkout <commit-anterior> && bash deploy/deploy.sh <rama>` (las migraciones 0011–0016 solo agregan columnas; no hace falta revertirlas).
- Restaurar el backup si hiciera falta (ver INSTRUCTIVO.md §Restaurar).
