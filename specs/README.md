# specs/ — Especificaciones VQL (Spec-Driven Development)

Este directorio guarda las especificaciones de cada módulo de GRUPO VICAF según la
metodología VQL. **La especificación va primero y el código después:** ningún cambio
entra al código sin un `requirements.md` aprobado.

## Ciclo SDD

```
/sdd-requirements ──► revisión ──► /sdd-design ──► revisión ──► /sdd-tasks ──► revisión ──► /sdd-implement
        ▲                                                                                        │
        └──────────────────────── cambio de alcance (vuelve a requirements) ─────────────────────┘
```

| Paso | Comando | Archivo que produce | Revisión antes de seguir |
|---|---|---|---|
| 1 | `/sdd-requirements` | `requirements.md`: requisitos EARS trazados a historias de usuario | El dueño aprueba el alcance y los requisitos (gate G1) |
| 2 | `/sdd-design` | `design.md`: modelo de datos, vistas/URLs, componentes, riesgos | Revisión técnica: cada vista y cada tarea apunta a un REQ |
| 3 | `/sdd-tasks` | `tasks.md`: tareas pequeñas y verificables, cada una con su REQ | Revisión: todo REQ queda cubierto por al menos una tarea |
| 4 | `/sdd-implement` | Código + commits `VCF-<MOD> T<n>: <qué>` | Verificación de cada tarea antes de marcarla `[x]` |

Entre un paso y el siguiente siempre hay revisión humana. Ningún paso se salta.

## Módulos

| Módulo | Alcance | Carpeta | Gate |
|---|---|---|---|
| VCF-LIMS | Sistema de laboratorio (`laboratorio.grupovicaf.com`): `core`, `clientes`, `trabajadores`, `servicios`, `proyectos`, `actividades` | [`VCF-LIMS/`](VCF-LIMS/) | G0 abierto [Propuesto] |
| VCF-WEB | Web institucional pública (`www.grupovicaf.com`): apps `web_*` y `siteconfig` | [`VCF-WEB/`](VCF-WEB/) | G0 abierto [Propuesto] |
| VCF-INFRA | Docker, gunicorn por `SITE_ROLE`, Celery/beat, Redis, Postgres, Nginx, Certbot, backups y despliegue en EC2 | [`VCF-INFRA/`](VCF-INFRA/) | G0 abierto [Propuesto] |

Cada carpeta de módulo contiene `requirements.md`, `design.md` y `tasks.md`.

## Reglas

1. **No se escribe código sin `requirements.md` aprobado.** Mientras el módulo no pase
   el gate G1, su `requirements.md` es una plantilla y `/sdd-implement` no aplica.
2. **Un cambio de alcance vuelve a requirements.** Si en diseño, tareas o implementación
   aparece algo que no cubre ningún REQ aprobado, se para, se actualiza
   `requirements.md`, se revisa otra vez y después se rehacen `design.md` y `tasks.md`.
3. **Trazabilidad completa:** HU → REQ → vista/componente → tarea → commit.
4. **`proc/`, `dev/`, `qa/` y `estado/` viven en el Proyecto de Claude, no en el repo.**
   En este repositorio solo se versionan las especificaciones (`specs/`) y el código.
5. Las reglas no negociables y las reglas SEO de [`CLAUDE.md`](../CLAUDE.md) aplican a
   todo diseño. Cada `design.md` indica cuáles le afectan.
