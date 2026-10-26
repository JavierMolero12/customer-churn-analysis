# Changelog

Cambios relevantes de cada versión del proyecto. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones siguen [versionado semántico](https://semver.org/lang/es/): mientras la versión empiece por `0.`, el proyecto está en desarrollo.

## [Sin publicar]

### Añadido

- **Feature engineering** (fase 4, [#7](https://github.com/JavierMolero12/customer-churn-analysis/pull/7)):
  - `src/feature_engineering.py`: variables `tenure_bucket` y `has_price_history`, selección de variables con su motivo, división train/test estratificada y `ColumnTransformer` que solo aprende de train;
  - redundancias medidas solo con train (VIF): fuera `n_payments`, `total_revenue`, `avg_historical_charge`, `n_services`, `n_addon_services` e `is_auto_payment`;
  - atributos sensibles (`is_male`, `is_senior`) excluidos por defecto;
  - 5 tests nuevos (20 en total).

## [0.2.0] — 2026-10-20

Primera versión publicada: **diseño, datos, SQL y limpieza** (fases 1 y 2 del [roadmap](docs/01_project_design.md#8-roadmap)). El proyecto se puede descargar y ejecutar de principio a fin con un comando; el análisis estadístico y el modelo llegarán en próximas versiones.

### Añadido

- **Diseño del proyecto** ([#1](https://github.com/JavierMolero12/customer-churn-analysis/pull/1)):
  - problema de negocio y elección del dataset (IBM Telco, Apache 2.0);
  - modelo de datos en 4 tablas;
  - 8 hipótesis con su criterio de decisión, fijadas antes del análisis;
  - registro de riesgos de *data leakage*, arquitectura y roadmap.
- **Pipeline de datos reproducible** ([#2](https://github.com/JavierMolero12/customer-churn-analysis/pull/2)):
  - descarga con verificación SHA-256;
  - normalización sin pérdida en SQLite, con dos capas (`raw_*` sin restricciones y `clean_*` con PK, FK y CHECK);
  - 200 defectos de calidad inyectados de forma documentada.
- **Calidad y limpieza** ([#3](https://github.com/JavierMolero12/customer-churn-analysis/pull/3)):
  - 14 comprobaciones SQL;
  - limpieza con registro de decisiones;
  - notebook 01 de exploración y limpieza;
  - estilo de gráficos común.
- **Tabla final por cliente en SQL** ([#4](https://github.com/JavierMolero12/customer-churn-analysis/pull/4)):
  - `customer_features` (7.043 × 27);
  - 9 consultas de negocio;
  - comando único `python -m src.pipeline`.
- **README para principiantes** ([#5](https://github.com/JavierMolero12/customer-churn-analysis/pull/5)): guía paso a paso, funcionamiento interno, problemas frecuentes y glosario.
- 15 tests automáticos.

### Limitaciones conocidas

- Datos de una empresa ficticia, en una sola foto sin fechas. La fecha de corte (`2024-10-01`) es una suposición.
- Posible tope de `tenure` en 72 meses y sesgo de supervivencia (documentados en el notebook 01).
- Probado en Windows con Python 3.13; pendiente de verificar en macOS y Linux.

[0.2.0]: https://github.com/JavierMolero12/customer-churn-analysis/releases/tag/v0.2.0
