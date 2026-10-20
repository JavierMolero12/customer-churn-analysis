# PR #1 — docs: add project design and data dictionary

**Rama:** `feature/project-design` → `develop` · **Fase:** 1 (Diseño)

## Description

Define el proyecto antes de tocar los datos: problema de negocio, dataset, modelo de datos, hipótesis con su criterio de decisión, riesgos de leakage, arquitectura y roadmap. Este PR entra **antes que cualquier análisis**, así que el historial de Git demuestra que las hipótesis no se ajustaron a los resultados.

## Changes

- `docs/01_project_design.md`: documento de diseño completo.
  - Problema y criterios de éxito.
  - Dataset IBM Telco: fuente fijada a un commit + SHA-256, licencia Apache 2.0, limitaciones y alternativas descartadas.
  - Modelo de datos en 4 tablas, con etiquetas REAL / DERIVADO / SINTÉTICO.
  - Defectos de calidad inyectados D1–D7 y problemas reales R1–R5.
  - Registro de leakage L1–L8.
  - Hipótesis H1–H8 con criterio común de decisión.
  - Arquitectura, roadmap y estrategia Git.
- `docs/data_dictionary.md`: columnas, tipos, origen y valores de cada tabla.
- `README.md`: README provisional con enlaces a la documentación.
- `.github/pull_request_template.md`: plantilla de PR (Description, Changes, Validation, Potential issues).
- `.gitattributes`: saltos de línea normalizados a LF.

## Validation

- Perfil estructural del CSV verificado con un script antes de escribir el diseño (7.043 filas, 21 columnas, IDs únicos, 11 `TotalCharges` vacíos con `tenure = 0`, 26,5 % churn).
- URL fijada al commit `1fd6fd7` descargada y SHA-256 comprobado.
- Recuentos derivados comprobados: 227.990 pagos (suma de `tenure`) y 80 clientes sin ninguna fila en `services`.
- **No** se ha calculado ninguna tasa de churn por grupo: las hipótesis se fijan sin mirar esos resultados.

## Potential issues

- La fecha de corte (`2024-10-01`) es una suposición: cualquier análisis de calendario sería un artefacto.
- El dataset es muy conocido y sus patrones generales están publicados. Lo mitigamos fijando los criterios de decisión aquí, pero no es un prerregistro ciego.
- Los diagramas Mermaid solo se ven como diagramas en visores que lo soportan (GitHub sí).
