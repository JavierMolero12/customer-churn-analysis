# PR #5 — docs: beginner-friendly README with step-by-step guide

**Rama:** `feature/readme-guide` → `develop` · **Fase:** documentación (adelanto de la Fase 8)

## Description

Reescribe el README para que **cualquier persona, aunque no sepa programar**, pueda descargar, ejecutar y entender el proyecto. Mantiene una guía rápida de cinco comandos para perfiles técnicos. Los resultados del análisis (estadística, modelo, recomendaciones) se añadirán al README cuando existan (fases 3–8).

## Changes

- **¿Qué es este proyecto?** Problema de negocio en lenguaje llano y aviso de que los datos son ficticios.
- **Guía rápida** para quien ya programa.
- **Guía paso a paso** (11 pasos). Cada uno dice qué escribir, qué hace y qué se debería ver, con instrucciones para Windows, macOS y Linux. Incluye la salida real esperada del pipeline y de los tests, y una primera consulta SQL para probar.
- **Cómo funciona por dentro:** analogía de la cadena de montaje, diagrama, tabla de pasos con su código y resultado, las 4 tablas explicadas, etiquetas REAL / DERIVADO / SINTÉTICO y columnas principales de la tabla final.
- **Qué hay en cada carpeta** y una tabla "si quieres… mira…".
- **Problemas frecuentes** (desplegables): Python no encontrado, scripts bloqueados en PowerShell, módulos no encontrados, fallos de instalación o descarga, Jupyter sin navegador, empezar de cero.
- **Glosario** de 12 términos y **estado del proyecto** por fases.

## Validation

- Comandos probados en **PowerShell** (Windows) con el entorno del proyecto: `python -m src.pipeline` y la consulta SQL de ejemplo dan exactamente la salida documentada.
- La salida del pipeline y `15 passed` están copiadas de ejecuciones reales.
- Espacio en disco medido: entorno virtual ≈ 641 MB y datos ≈ 32 MB (se documenta "1 GB libre").
- Enlaces internos (anclas del índice y rutas a ficheros) revisados en la vista de GitHub de la rama.

## Potential issues

- La activación con `Activate.ps1` falla en Windows si la política de ejecución bloquea scripts. La guía ofrece una alternativa **sin cambiar ajustes de seguridad** (`.venv\Scripts\python`).
- `git clone` y "Download ZIP" descargan la rama por defecto (`main`), que todavía no contiene este trabajo. Hay que decidir cómo exponerlo (release a `main` o cambiar la rama por defecto) para que la guía funcione a quien llegue al repositorio.
- No se ha probado en macOS ni en Linux. Los comandos son los estándar de Python, pero conviene verificarlos.
