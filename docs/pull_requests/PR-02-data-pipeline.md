# PR #2 — feat: reproducible data pipeline and normalized SQLite database

**Rama:** `feature/data-pipeline` → `develop` · **Fase:** 2a (Pipeline de datos)

## Description

Convierte el CSV de IBM en la base de datos "operativa" del proyecto, de forma reproducible y verificable:

1. Descarga el CSV desde una URL fijada a un commit y comprueba el SHA-256.
2. Lo normaliza en cuatro tablas (`customers`, `subscriptions`, `services`, `payments`) sin perder información.
3. Inyecta los defectos de calidad D1–D7 del diseño y los registra en un manifiesto.
4. Lo guarda todo en SQLite con un esquema de dos capas: `raw_*` sin restricciones y `clean_*` con PK, FK y CHECK.

## Changes

- `requirements.txt`: versiones fijadas (probado con Python 3.13 y pandas 3.0).
- `pytest.ini`: configuración mínima de pytest.
- `src/config.py`: rutas, URL y hash del dataset, fecha de corte, semilla y catálogos de categorías.
- `src/database.py`: conexión con claves foráneas activadas, ejecución de scripts `.sql` y lectura de consultas con nombre (`-- name: ...`).
- `src/download_data.py`: descarga idempotente con verificación SHA-256.
- `sql/00_schema.sql`: modelo de datos en dos capas. La capa limpia valida categorías, importes positivos, fechas ISO y `end_date >= start_date`.
- `src/build_database.py`:
  - `normalize()` / `denormalize()`: CSV ↔ tablas.
  - `build_payments()`: reconstrucción determinista de pagos a partir de los totales reales.
  - `inject_defects()`: defectos D1–D7 con semilla fija.
- `tests/`: 4 tests del pipeline.
- `docs/data_dictionary.md`: tamaños de tabla verificados.

## Validation

```text
python -m src.download_data      -> Dataset descargado y verificado
python -m src.build_database     -> raw_customers 7,063 · raw_subscriptions 7,043
                                    raw_services 23,685 · raw_payments 228,080
                                    200 defectos inyectados
python -m pytest                 -> 4 passed
```

- `denormalize(normalize(csv))` reproduce el CSV original columna a columna.
- Comprobación manual de que ese test **falla** si se quita un servicio, se cambia una cuota o se mueve una fecha de alta (el test no pasa por casualidad).
- `SUM(payments)` = `total_charges` con un margen de 1 céntimo, nº de pagos = `tenure` y último pago = cuota actual.
- Mismo manifiesto en dos ejecuciones con la misma semilla.

## Potential issues

- `payments` es una **reconstrucción**: el reparto mes a mes es una suposición. Solo deben usarse agregados que reproducen valores reales (diseño, L7).
- Los defectos son sintéticos y pocos (200 de ~265.000 filas). Sirven para demostrar las comprobaciones de calidad, no para medir la calidad de datos reales.
- La descarga necesita conexión a internet la primera vez.
- pandas 3.0 cambia el tipo de texto por defecto. El código está probado con 3.0.6 y podría comportarse distinto con pandas 2.x.
