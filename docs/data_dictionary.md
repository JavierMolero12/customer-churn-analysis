# Diccionario de datos

**v1.2 (Fase 2c).** Tamaños de tabla y columnas verificados sobre la base de datos generada por `python -m src.pipeline`.

**Etiquetas de origen** (ver [diseño §3.2](01_project_design.md#32-origen-de-cada-dato-tres-etiquetas)):

- **REAL**: valor del CSV de IBM, quizá renombrado.
- **DERIVADO**: cálculo determinista a partir de valores reales y una suposición documentada.
- **SINTÉTICO**: introducido por nosotros. Solo defectos de calidad inyectados, registrados en `data/raw/injected_defects.csv`.

**Fecha de corte asumida:** `2024-10-01`.

Los recuentos de valores salen del perfil del CSV original (7.043 filas) y no incluyen los defectos inyectados.

---

## Capa `raw_*`: extracción "operativa" (con defectos)

### `raw_customers`

Una fila por cliente, más 20 duplicados inyectados (D1): **7.063 filas**.

| Columna | Tipo | Origen | Columna original | Descripción | Valores |
|---|---|---|---|---|---|
| `customer_id` | TEXT | REAL | `customerID` | Identificador del cliente | 7.043 únicos |
| `gender` | TEXT | REAL | `gender` | Género | Male 3.555 · Female 3.488 |
| `senior_citizen` | INTEGER | REAL | `SeniorCitizen` | 1 = cliente mayor. Viene en 0/1, a diferencia del resto de binarias | 0: 5.901 · 1: 1.142 |
| `partner` | TEXT | REAL | `Partner` | Tiene pareja | No 3.641 · Yes 3.402 |
| `dependents` | TEXT | REAL | `Dependents` | Tiene personas dependientes | No 4.933 · Yes 2.110 |
| `signup_date` | TEXT (ISO) | DERIVADO | `tenure` | Fecha de corte − `tenure` meses (día 1) | 2018-10-01 … 2024-10-01 |

### `raw_subscriptions`

Una fila por cliente.

| Columna | Tipo | Origen | Columna original | Descripción | Valores |
|---|---|---|---|---|---|
| `customer_id` | TEXT | REAL | `customerID` | PK y FK a `raw_customers` | 7.043 |
| `contract_type` | TEXT | REAL (+ D2) | `Contract` | Duración del contrato | Month-to-month 3.875 · Two year 1.695 · One year 1.473 |
| `internet_service` | TEXT | REAL | `InternetService` | Plan de internet (hace el papel de "plan") | Fiber optic 3.096 · DSL 2.421 · No 1.526 |
| `paperless_billing` | TEXT | REAL | `PaperlessBilling` | Factura electrónica | Yes 4.171 · No 2.872 |
| `payment_method` | TEXT | REAL (+ D2) | `PaymentMethod` | Método de pago | Electronic check 2.365 · Mailed check 1.612 · Bank transfer (automatic) 1.544 · Credit card (automatic) 1.522 |
| `monthly_charges` | REAL | REAL (+ D3, D4) | `MonthlyCharges` | Cuota mensual actual | 18,25 – 118,75 |
| `total_charges` | TEXT | REAL | `TotalCharges` | Total facturado hasta la fecha. Texto, como en origen | 18,8 – 8.684,8; 11 vacíos (todos con `tenure = 0`) |
| `start_date` | TEXT (ISO) | DERIVADO | `tenure` | Inicio de la suscripción (= `signup_date`) | 2018-10-01 … 2024-10-01 |
| `end_date` | TEXT (ISO) / NULL | DERIVADO | `Churn` | Fecha de baja. NULL = activo; `2024-10-01` = baja en el último mes. **Define el objetivo → nunca es una variable del modelo (L1)** | NULL 5.174 · no nulo 1.869 |

### `raw_services`

Formato largo: una fila por servicio contratado. Un cliente puede tener entre 0 y 8 filas. En total, **23.685 filas** de 6.963 clientes.

Filas por servicio: phone_service 6.361 · multiple_lines 2.971 · streaming_movies 2.732 · streaming_tv 2.707 · online_backup 2.429 · device_protection 2.422 · tech_support 2.044 · online_security 2.019.

| Columna | Tipo | Origen | Columna original | Descripción |
|---|---|---|---|---|
| `customer_id` | TEXT | REAL | `customerID` | FK a `raw_customers` |
| `service_name` | TEXT | REAL | Columnas de servicio con valor "Yes" | Uno de: `phone_service`, `multiple_lines`, `online_security`, `online_backup`, `device_protection`, `tech_support`, `streaming_tv`, `streaming_movies` |

- Solo se guardan los servicios contratados. "No", "No internet service" y "No phone service" se recuperan sin pérdida: si no hay fila, el cliente no tiene el servicio, y `internet_service` indica si podía tenerlo.
- 80 clientes no tienen ninguna fila → hace falta `LEFT JOIN` para no perderlos.
- **Servicios adicionales** (usados en H1): `online_security`, `online_backup`, `device_protection`, `tech_support`, `streaming_tv`, `streaming_movies`.

### `raw_payments`

Una fila por mes facturado: 227.990 filas reconstruidas (de 2018-10-01 a 2024-09-01) más 90 inyectadas (D5–D7) = **228.080 filas**.

| Columna | Tipo | Origen | Descripción |
|---|---|---|---|
| `payment_id` | INTEGER | DERIVADO | Identificador secuencial |
| `customer_id` | TEXT | REAL | FK a `raw_customers` (D6: 30 huérfanos inyectados) |
| `payment_date` | TEXT (ISO) | DERIVADO | `start_date + (k − 1)` meses para k = 1…`tenure`. Último pago: `2024-09-01` (D7: 10 con fecha ≥ corte) |
| `amount` | REAL | DERIVADO | Último pago = `monthly_charges`; los anteriores = `(total_charges − monthly_charges) / (tenure − 1)`. Con `tenure = 1`: `amount = total_charges`. Cumple `SUM(amount) = total_charges` |

Los importes de meses concretos son una suposición de reparto y **no se usan como variables** (L7). Sí se usan los agregados que reproducen valores reales: número de pagos, total y media histórica.

---

## Capa `clean_*`: tras la limpieza (Fase 2)

Mismas columnas que la capa `raw_*`, con:

- duplicados (D1, D5), huérfanos (D6) y registros con fecha futura (D7) eliminados;
- categorías canónicas (D2);
- `monthly_charges` recuperado (D3, D4);
- `total_charges` convertido a REAL, con 0 en los 11 clientes de `tenure = 0` (R1).

Cada decisión se justifica en el notebook 01. Un test comprueba que las tablas `clean_*` reconstruyen exactamente el CSV original.

---

## `customer_features`: tabla final por cliente

La genera `sql/02_customer_features.sql` (Fase 2c): **7.043 filas × 27 columnas**, exportadas a `data/processed/customer_features.csv` con `python -m src.pipeline`. Las variables marcadas como *(Fase 4)* las calcula `src/feature_engineering.py` en Python; la selección para el modelo está en la sección siguiente.

| Variable | Cálculo previsto | Origen | Riesgo de leakage |
|---|---|---|---|
| `customer_id` | — | REAL | Identificador: no entra en el modelo |
| `is_male`, `is_senior`, `has_partner`, `has_dependents` | `CASE WHEN` a 0/1 | REAL | Ninguno. `is_male` y `is_senior` son atributos sensibles: su uso se decide en la Fase 4 (H8) |
| `contract_type`, `internet_service`, `payment_method` | Categorías limpias | REAL | Ninguno |
| `is_auto_payment` | `payment_method LIKE '%automatic%'` | REAL | Ninguno |
| `is_paperless` | `CASE WHEN` | REAL | Ninguno |
| `tenure_months` | Meses entre `start_date` y la fecha de corte (funciones de fecha) | REAL (recalculado) | Bajo, ver L3. Siempre hasta la fecha de corte, nunca hasta `end_date` (L2) |
| `monthly_charges` | — | REAL | Ninguno |
| `n_payments`, `total_revenue` | `COUNT` / `SUM` sobre `payments` | REAL (vía agregados) | `total_revenue ≈ tenure × cuota` → colinealidad (R5) |
| `avg_historical_charge` | Media de los pagos excepto el último (window function). NULL en 624 clientes con `tenure < 2` (11 con 0 + 613 con 1) | REAL (vía agregados) | Ninguno |
| `price_change_ratio` | `monthly_charges / avg_historical_charge` (`tenure ≥ 2`) | REAL (vía agregados) | Ninguno. Interpretación incierta (H6) |
| `n_services`, `n_addon_services` | `LEFT JOIN services` + `COUNT`, `COALESCE(…, 0)` | REAL | Ninguno |
| `has_<servicio>` | Agregación condicional `MAX(CASE WHEN …)` | REAL | Ninguno |
| `tenure_bucket` *(Fase 4)* | Tramos 0–6, 7–12, 13–24, 25–48, 49–72 (`pd.cut`, límite superior incluido) | DERIVADO | Ninguno |
| `has_price_history` *(Fase 4)* | 1 si `tenure_months ≥ 2`: `price_change_ratio` es un valor observado y no imputado | DERIVADO | Ninguno |
| **`churn`** | `CASE WHEN end_date IS NOT NULL THEN 1 ELSE 0 END` | REAL (codificado) | **Es el objetivo** |

`total_charges` no se incluye porque coincide con `total_revenue` (lo comprueba un test).

**Excluidas del modelo por diseño:** `customer_id`, `signup_date`, `start_date`, `end_date` y cualquier variable calculada con `end_date`.

---

## Variables del modelo (Fase 4)

Las elige y prepara `src/feature_engineering.py`. Las redundancias se midieron **solo con train** (80 %, estratificado, semilla 42), para no tomar decisiones de modelado mirando el test (L5). `python -m src.feature_engineering` imprime la división, las exclusiones y la tabla de VIF.

**Entran (19 columnas → 26 tras el preprocesado):**

| Grupo | Variables | Preprocesado |
|---|---|---|
| Numéricas | `tenure_months`, `monthly_charges` | `StandardScaler` |
| Cambio de precio | `price_change_ratio` | Imputación constante 1,0 ("sin cambio") si `tenure < 2` + `StandardScaler` |
| Binarias 0/1 | `has_partner`, `has_dependents`, `is_paperless`, `has_phone_service`, `has_multiple_lines`, los 6 `has_<servicio adicional>`, `has_price_history` | Sin cambios |
| Categóricas | `contract_type`, `internet_service`, `payment_method`, `tenure_bucket` | One-hot con categorías fijas; la primera es la referencia (contrato mensual, DSL, cheque electrónico, 0–6 meses) |

**No entran:**

| Variable | Motivo | Evidencia (train) |
|---|---|---|
| `is_male`, `is_senior` | Atributos sensibles. No son una palanca de negocio y decidir a quién se ofrece una retención por sexo o edad puede discriminar | `is_senior` sí está asociada al churn (42 % frente a 24 %). La Fase 5 medirá con `include_sensitive=True` cuánto rendimiento cuesta excluirla |
| `n_payments` | Idéntica a `tenure_months` (un pago por mes facturado) | Iguales en el 100 % de los clientes |
| `total_revenue` | `≈ tenure_months × monthly_charges` (R5) | r = 0,9996; VIF 10,4 |
| `avg_historical_charge` | `≈ monthly_charges`; su información útil ya está en `price_change_ratio` | r = 0,992; VIF 203 |
| `n_services`, `n_addon_services` | Sumas exactas de los indicadores `has_*`, que sí entran | Iguales en el 100 % de los clientes |
| `is_auto_payment` | Se deduce de `payment_method`, que entra con sus 4 categorías | — |

Con la selección, el VIF de las numéricas baja a 1,0–1,1 (sin redundancia relevante).
