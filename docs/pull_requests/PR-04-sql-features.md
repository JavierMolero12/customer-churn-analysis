# PR #4 — feat: customer-level feature table and business queries in SQL

**Rama:** `feature/sql-features` → `develop` · **Fase:** 2c (SQL de negocio)

## Description

Construye en SQL la tabla final del proyecto, `customer_features`, con una fila por cliente. Une las cuatro tablas limpias y deja la variable objetivo `churn` como única columna derivada de `end_date`. Añade consultas de negocio que dan una primera lectura descriptiva y un comando que ejecuta todo el pipeline de principio a fin.

## Changes

- `sql/02_customer_features.sql`: la consulta principal del proyecto.
  - CTEs, INNER JOIN y LEFT JOIN + `COALESCE` (80 clientes sin servicios y 11 sin pagos no se pierden).
  - Agregación condicional para pivotar los servicios a columnas 0/1.
  - `ROW_NUMBER()` para separar el último pago del historial.
  - `strftime` para calcular la antigüedad.
  - `CASE WHEN` para unificar formatos.
- `sql/03_analysis.sql`: 9 consultas de negocio. Incluyen churn por contrato, plan, método de pago, tramo de antigüedad y servicios adicionales; ingreso mensual perdido; segmentos de alto riesgo con `HAVING COUNT(*) >= 100`; y una subconsulta correlacionada (precio frente a la media del propio plan).
- `src/pipeline.py`: `python -m src.pipeline` (descarga → raw → limpieza → features → CSV).
- `tests/test_features.py`: 7 tests sobre la tabla final.
  - Una fila por cliente.
  - `churn` binario y con el mismo recuento que el CSV.
  - Sin negativos.
  - Sin NaN salvo los documentados.
  - La antigüedad calculada en SQL coincide con la original.
  - `total_revenue` coincide con `TotalCharges`.
  - Los recuentos de servicios cuadran con sus columnas.
- `README.md`: cómo ejecutar el proyecto desde cero.
- `docs/data_dictionary.md`: tabla final documentada (27 columnas).

## Validation

```text
python -m src.pipeline   (desde cero, sin data/churn.db)  -> 7,043 clientes x 27 columnas en ~4 s
python -m pytest                                           -> 15 passed
```

- Las 9 consultas de `03_analysis.sql` se ejecutan sin errores.
- NaN solo en `avg_historical_charge` y `price_change_ratio`, exactamente en los 624 clientes con `tenure < 2` (no tienen meses anteriores).
- `end_date` aparece solo en la definición de `churn` (revisado en el SQL).

## Potential issues

- Las consultas de `03_analysis.sql` son **descriptivas**. No sustituyen al contraste formal de hipótesis (intervalos de confianza, tests y criterio fijado en el diseño), que se hace en el notebook 02.
- Ya se ve un posible **efecto de confusión** para H5: dentro de cada plan, pagar más que la media del plan se asocia a **menos** churn, aunque en el agregado la fibra (cara) tiene más churn. Hay que analizarlo antes de concluir nada sobre el precio.
- `price_change_ratio` se interpreta como cambio de precio, pero podría reflejar cargos puntuales o el ruido con el que IBM generó los datos (diseño, H6).
- La tabla se recrea completa en cada ejecución (`DROP` + `CREATE TABLE AS`). Con 7.043 filas es instantáneo; con millones convendría una carga incremental.
