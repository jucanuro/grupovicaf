#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Carga el catálogo de condiciones de la oferta técnico-económica
(VCF-LAB-FOR-001) en CatalogoCondicionSeccion / CatalogoCondicionItem.

Uso:
    python cargar_condiciones.py                 # dry-run: solo muestra
    python cargar_condiciones.py --apply         # escribe en la BD

Los datos y la lógica de escritura viven en `servicios/seeds/condiciones.py`
(la misma fuente que usa `python manage.py sembrar_demo`). Es idempotente.
"""

import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "grupovicaf.settings.dev")
django.setup()

from servicios.seeds.condiciones import iter_preview, sembrar_condiciones  # noqa: E402


def main():
    apply = "--apply" in sys.argv

    for linea in iter_preview():
        print(linea)

    print("\n" + "=" * 70)
    if apply:
        n_sec, n_item = sembrar_condiciones()
        print(f"Secciones procesadas : {n_sec}")
        print(f"Ítems procesados     : {n_item}")
    else:
        print("DRY-RUN — no se escribió nada.")
        print("Corre con --apply para guardar en la base de datos.")
    print("=" * 70)


if __name__ == "__main__":
    main()
