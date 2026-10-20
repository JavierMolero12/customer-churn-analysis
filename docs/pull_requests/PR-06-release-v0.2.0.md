# PR #6 — release: v0.2.0 (design, data pipeline, SQL and cleaning)

**Rama:** `release/v0.2.0` → `main` · **Tipo:** release

## Description

Publica en `main` la primera versión estable del proyecto: fases 1 y 2 completas. Hasta ahora `main` solo contenía el esqueleto inicial. Por eso quien visitaba el repositorio, lo clonaba o lo descargaba en ZIP no recibía el código, y la guía del README no le servía. Tras esta release, `main` contiene una versión probada y etiquetada (`v0.2.0`).

## Changes

- Integra en `main` todo lo mergeado en `develop` mediante los PRs #1–#5 (ver [CHANGELOG](../../CHANGELOG.md)).
- `CHANGELOG.md`: registro de cambios por versión (formato *Keep a Changelog* y versionado semántico).
- Tras el merge: etiqueta `v0.2.0`, *GitHub Release* con notas y sincronización de `develop` con `main`.

## Validation

- `python -m pytest` → 15 passed en la rama de release.
- Tras el merge, **clon limpio de la rama por defecto** (`main`): pipeline completo y tests sin errores.
- README revisado en la vista de GitHub: enlaces internos, diagrama y desplegables.

## Potential issues

- Es una versión `0.x`: el análisis estadístico, el modelo y las recomendaciones aún no existen. El README lo indica en "Estado del proyecto".
- Según Gitflow, `main` solo recibe releases. Los próximos cambios seguirán entrando por `develop` y llegarán a `main` en la siguiente versión.
