# PR #3 — feat: SQL data quality checks and documented cleaning

**Rama:** `feature/data-quality` → `develop` · **Fase:** 2b (Calidad y limpieza)

## Description

Detecta los problemas de calidad de la capa `raw_*` con SQL, los corrige con reglas generales en Pandas (cada decisión justificada y registrada) y escribe la capa `clean_*`, cuyas restricciones validan el resultado. El notebook 01 cuenta todo el proceso: inspección inicial, comprobaciones, decisiones, verificación, y outliers y sesgos.

## Changes

- `sql/01_data_quality.sql`: 14 comprobaciones con nombre. Cada una devuelve las filas problemáticas (0 filas = superada):
  - duplicados (clientes, suscripciones, pagos) y pagos contradictorios;
  - valores perdidos, incluidos textos vacíos;
  - categorías fuera de catálogo;
  - valores imposibles;
  - extremos por IQR, con cuartiles calculados mediante window functions;
  - IDs sin correspondencia (anti-joins);
  - pagos fuera de periodo y fechas incoherentes;
  - conciliación facturación vs contratación;
  - cuota vs última factura (`ROW_NUMBER() OVER (PARTITION BY ...)`).
- `src/data_cleaning.py`:
  - `run_quality_checks()`: ejecuta las comprobaciones sobre la capa `raw` o `clean`;
  - reglas de limpieza por tabla y `CleaningLog`, que registra cada decisión con su motivo;
  - escritura en `clean_*`.
  - Lo que no sabe resolver con seguridad lanza `ValueError` en vez de adivinar.
- `src/viz.py`: estilo común de gráficos. Paleta validada para daltonismo; azul = no churn y naranja = churn en todo el proyecto.
- `src/config.py`, `src/download_data.py`, `src/build_database.py`: los mensajes muestran rutas relativas al proyecto (evita publicar rutas personales en las salidas de los notebooks).
- `notebooks/01_data_exploration.ipynb`: notebook ejecutado de principio a fin, con salidas.
- `reports/figures/01_*.png`: cuota antes/después de limpiar y distribución de la antigüedad.
- `tests/`: 4 tests nuevos (8 en total). Usan una base de datos temporal construida desde cero.

## Validation

```text
python -m src.data_cleaning      -> 11 decisiones registradas; 0 comprobaciones fallidas sobre clean_*
python -m pytest                 -> 8 passed
jupyter nbconvert --execute notebooks/01_data_exploration.ipynb -> sin errores
```

- Las comprobaciones encuentran los 200 defectos inyectados, sin leer el manifiesto.
- Las tablas `clean_*` reconstruyen el CSV original (única diferencia prevista: 11 `TotalCharges` vacíos → 0).
- Ningún pago inyectado sobrevive y no se pierde ningún pago real (227.990).
- Tasa de churn idéntica antes y después (26,54 %): la limpieza no sesga la variable objetivo.
- Gráficos revisados visualmente (se corrigió una etiqueta que chocaba con el eje).

## Potential issues

- **Recuperar la cuota desde la última factura funciona aquí por construcción** (la tabla de pagos se reconstruyó así). En datos reales es una regla razonable, pero habría que validarla con el equipo de facturación.
- `run_quality_checks(layer="clean")` sustituye el prefijo `raw_` en el texto SQL. Es sencillo, pero frágil si una columna contuviera "raw_".
- Los cuartiles en SQL son aproximados (posición en la lista ordenada). Son suficientes para detectar errores ×100, no para estadística fina.
- Hallazgos que afectan a análisis posteriores: posible tope de `tenure` en 72 meses (362 clientes frente a 170 en 71) y sesgo de supervivencia en la foto.
