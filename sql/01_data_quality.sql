-- =====================================================================================
-- 01_data_quality.sql — Comprobaciones de calidad de datos
--
-- Convención:
--   * Cada bloque "-- name: check_<algo>" devuelve las FILAS PROBLEMÁTICAS.
--     0 filas = comprobación superada.
--   * Las consultas se escriben contra la capa raw_*. src/data_cleaning.py puede ejecutarlas
--     también contra clean_* para demostrar que, tras la limpieza, todas devuelven 0 filas.
-- =====================================================================================


-- name: check_duplicate_customers
-- Clientes que aparecen más de una vez. n_versions = 1 significa que las copias son idénticas
-- (duplicado exacto, se puede eliminar sin perder nada). Si fuera > 1, habría datos contradictorios.
SELECT customer_id,
       COUNT(*) AS n_rows,
       COUNT(DISTINCT gender || '|' || senior_citizen || '|' || partner || '|' ||
                      dependents || '|' || signup_date) AS n_versions
FROM raw_customers
GROUP BY customer_id
HAVING COUNT(*) > 1
ORDER BY customer_id;


-- name: check_duplicate_subscriptions
-- En este modelo cada cliente tiene exactamente una suscripción.
SELECT customer_id, COUNT(*) AS n_rows
FROM raw_subscriptions
GROUP BY customer_id
HAVING COUNT(*) > 1;


-- name: check_duplicate_payments
-- Mismo cliente, mismo mes y mismo importe con distinto payment_id: cobro registrado dos veces.
SELECT customer_id,
       payment_date,
       amount,
       COUNT(*)        AS n_rows,
       MIN(payment_id) AS first_payment_id,
       MAX(payment_id) AS last_payment_id
FROM raw_payments
GROUP BY customer_id, payment_date, amount
HAVING COUNT(*) > 1
ORDER BY customer_id, payment_date;


-- name: check_conflicting_payments
-- Mismo cliente y mes con importes DISTINTOS: no sabríamos cuál es el bueno (requeriría revisión manual).
SELECT customer_id, payment_date, COUNT(DISTINCT amount) AS n_amounts
FROM raw_payments
GROUP BY customer_id, payment_date
HAVING COUNT(DISTINCT amount) > 1;


-- name: check_missing_values
-- NULLs o textos vacíos por columna. end_date no se incluye: NULL es válido (cliente activo).
WITH missing AS (
    SELECT 'raw_customers' AS table_name, 'customer_id' AS column_name,
           SUM(customer_id IS NULL OR TRIM(customer_id) = '') AS n_missing FROM raw_customers
    UNION ALL SELECT 'raw_customers', 'gender', SUM(gender IS NULL OR TRIM(gender) = '') FROM raw_customers
    UNION ALL SELECT 'raw_customers', 'senior_citizen', SUM(senior_citizen IS NULL) FROM raw_customers
    UNION ALL SELECT 'raw_customers', 'partner', SUM(partner IS NULL OR TRIM(partner) = '') FROM raw_customers
    UNION ALL SELECT 'raw_customers', 'dependents', SUM(dependents IS NULL OR TRIM(dependents) = '') FROM raw_customers
    UNION ALL SELECT 'raw_customers', 'signup_date', SUM(signup_date IS NULL) FROM raw_customers
    UNION ALL SELECT 'raw_subscriptions', 'contract_type', SUM(contract_type IS NULL OR TRIM(contract_type) = '') FROM raw_subscriptions
    UNION ALL SELECT 'raw_subscriptions', 'internet_service', SUM(internet_service IS NULL OR TRIM(internet_service) = '') FROM raw_subscriptions
    UNION ALL SELECT 'raw_subscriptions', 'paperless_billing', SUM(paperless_billing IS NULL OR TRIM(paperless_billing) = '') FROM raw_subscriptions
    UNION ALL SELECT 'raw_subscriptions', 'payment_method', SUM(payment_method IS NULL OR TRIM(payment_method) = '') FROM raw_subscriptions
    UNION ALL SELECT 'raw_subscriptions', 'monthly_charges', SUM(monthly_charges IS NULL) FROM raw_subscriptions
    UNION ALL SELECT 'raw_subscriptions', 'total_charges', SUM(total_charges IS NULL OR TRIM(total_charges) = '') FROM raw_subscriptions
    UNION ALL SELECT 'raw_subscriptions', 'start_date', SUM(start_date IS NULL) FROM raw_subscriptions
    UNION ALL SELECT 'raw_services', 'service_name', SUM(service_name IS NULL OR TRIM(service_name) = '') FROM raw_services
    UNION ALL SELECT 'raw_payments', 'customer_id', SUM(customer_id IS NULL) FROM raw_payments
    UNION ALL SELECT 'raw_payments', 'payment_date', SUM(payment_date IS NULL) FROM raw_payments
    UNION ALL SELECT 'raw_payments', 'amount', SUM(amount IS NULL) FROM raw_payments
)
SELECT table_name, column_name, n_missing
FROM missing
WHERE n_missing > 0;


-- name: check_non_canonical_categories
-- Valores fuera del catálogo esperado (mayúsculas, espacios, erratas...).
WITH category_values AS (
    SELECT 'contract_type' AS column_name, contract_type AS value, COUNT(*) AS n_rows,
           contract_type IN ('Month-to-month', 'One year', 'Two year') AS is_canonical
    FROM raw_subscriptions GROUP BY contract_type
    UNION ALL
    SELECT 'payment_method', payment_method, COUNT(*),
           payment_method IN ('Electronic check', 'Mailed check',
                              'Bank transfer (automatic)', 'Credit card (automatic)')
    FROM raw_subscriptions GROUP BY payment_method
    UNION ALL
    SELECT 'internet_service', internet_service, COUNT(*), internet_service IN ('DSL', 'Fiber optic', 'No')
    FROM raw_subscriptions GROUP BY internet_service
    UNION ALL
    SELECT 'paperless_billing', paperless_billing, COUNT(*), paperless_billing IN ('Yes', 'No')
    FROM raw_subscriptions GROUP BY paperless_billing
    UNION ALL
    SELECT 'gender', gender, COUNT(*), gender IN ('Female', 'Male')
    FROM raw_customers GROUP BY gender
)
SELECT column_name, '[' || value || ']' AS value_with_brackets, n_rows   -- los corchetes hacen visibles los espacios
FROM category_values
WHERE is_canonical = 0
ORDER BY column_name, n_rows DESC;


-- name: check_impossible_values
-- Valores que no pueden existir: importes no positivos, indicadores fuera de 0/1, texto no numérico.
SELECT 'raw_subscriptions' AS table_name, customer_id AS record_key,
       'monthly_charges <= 0' AS rule, CAST(monthly_charges AS TEXT) AS value
FROM raw_subscriptions WHERE monthly_charges <= 0
UNION ALL
SELECT 'raw_subscriptions', customer_id, 'total_charges no numérico', total_charges
FROM raw_subscriptions
WHERE TRIM(total_charges) <> '' AND TRIM(total_charges) GLOB '*[^0-9.]*'
UNION ALL
SELECT 'raw_customers', customer_id, 'senior_citizen fuera de {0, 1}', CAST(senior_citizen AS TEXT)
FROM raw_customers WHERE senior_citizen NOT IN (0, 1)
UNION ALL
SELECT 'raw_payments', CAST(payment_id AS TEXT), 'amount <= 0', CAST(amount AS TEXT)
FROM raw_payments WHERE amount <= 0;


-- name: check_monthly_charges_outliers
-- Valores extremos con la regla del rango intercuartílico (IQR): fuera de [Q1 - 1,5·IQR, Q3 + 1,5·IQR].
-- SQLite no tiene función de percentil: Q1 y Q3 se aproximan ordenando las filas con ROW_NUMBER().
WITH ordered AS (
    SELECT monthly_charges,
           ROW_NUMBER() OVER (ORDER BY monthly_charges) AS position,
           COUNT(*) OVER ()                              AS n
    FROM raw_subscriptions
    WHERE monthly_charges IS NOT NULL
),
quartiles AS (
    SELECT MAX(CASE WHEN position = CAST(0.25 * n AS INTEGER) THEN monthly_charges END) AS q1,
           MAX(CASE WHEN position = CAST(0.75 * n AS INTEGER) THEN monthly_charges END) AS q3
    FROM ordered
)
SELECT s.customer_id,
       s.monthly_charges,
       ROUND(q.q1 - 1.5 * (q.q3 - q.q1), 2) AS lower_fence,
       ROUND(q.q3 + 1.5 * (q.q3 - q.q1), 2) AS upper_fence
FROM raw_subscriptions AS s
CROSS JOIN quartiles AS q
WHERE s.monthly_charges < q.q1 - 1.5 * (q.q3 - q.q1)
   OR s.monthly_charges > q.q3 + 1.5 * (q.q3 - q.q1)
ORDER BY s.monthly_charges DESC;


-- name: check_orphan_payments
-- Pagos cuyo customer_id no existe en la tabla de clientes (LEFT JOIN + IS NULL = "anti-join").
-- DISTINCT es necesario: si un cliente estuviera duplicado, el JOIN multiplicaría las filas de sus pagos.
SELECT p.payment_id, p.customer_id, p.payment_date, p.amount
FROM raw_payments AS p
LEFT JOIN (SELECT DISTINCT customer_id FROM raw_customers) AS c
       ON c.customer_id = p.customer_id
WHERE c.customer_id IS NULL
ORDER BY p.payment_id;


-- name: check_unmatched_records
-- Integridad referencial del resto de tablas: suscripciones o servicios sin cliente y clientes sin suscripción.
SELECT 'subscription without customer' AS issue, s.customer_id
FROM raw_subscriptions AS s
LEFT JOIN raw_customers AS c ON c.customer_id = s.customer_id
WHERE c.customer_id IS NULL
UNION ALL
SELECT 'service without customer', sv.customer_id
FROM raw_services AS sv
LEFT JOIN raw_customers AS c ON c.customer_id = sv.customer_id
WHERE c.customer_id IS NULL
UNION ALL
SELECT 'customer without subscription', c.customer_id
FROM raw_customers AS c
LEFT JOIN raw_subscriptions AS s ON s.customer_id = c.customer_id
WHERE s.customer_id IS NULL;


-- name: check_payments_outside_subscription
-- Pagos fuera del periodo posible: antes del alta o en/después de la fecha de corte.
SELECT p.payment_id,
       p.customer_id,
       p.payment_date,
       s.start_date,
       si.snapshot_date,
       CASE WHEN p.payment_date >= si.snapshot_date THEN 'on or after snapshot date'
            ELSE 'before subscription start' END AS issue
FROM raw_payments AS p
INNER JOIN raw_subscriptions AS s ON s.customer_id = p.customer_id
CROSS JOIN snapshot_info AS si
WHERE p.payment_date >= si.snapshot_date
   OR p.payment_date < s.start_date
ORDER BY p.payment_id;


-- name: check_inconsistent_dates
-- Fechas imposibles o incoherentes entre tablas. date(x) devuelve NULL si x no es una fecha válida.
SELECT s.customer_id, c.signup_date, s.start_date, s.end_date,
       CASE
           WHEN date(s.start_date) IS NULL OR date(c.signup_date) IS NULL THEN 'invalid date format'
           WHEN s.start_date <> c.signup_date                             THEN 'start_date differs from signup_date'
           WHEN s.end_date < s.start_date                                 THEN 'end_date before start_date'
           WHEN s.start_date > si.snapshot_date OR s.end_date > si.snapshot_date THEN 'date after snapshot'
       END AS issue
FROM raw_subscriptions AS s
INNER JOIN (SELECT DISTINCT customer_id, signup_date FROM raw_customers) AS c
        ON c.customer_id = s.customer_id
CROSS JOIN snapshot_info AS si
WHERE date(s.start_date) IS NULL
   OR date(c.signup_date) IS NULL
   OR s.start_date <> c.signup_date
   OR s.end_date < s.start_date
   OR s.start_date > si.snapshot_date
   OR s.end_date > si.snapshot_date;


-- name: check_billing_reconciliation
-- Conciliación facturación vs contratación: lo cobrado (suma de pagos) debe coincidir con total_charges.
-- Un total en blanco cuenta como 0 (cliente aún sin facturar).
WITH paid AS (
    SELECT customer_id, ROUND(SUM(amount), 2) AS total_paid, COUNT(*) AS n_payments
    FROM raw_payments
    GROUP BY customer_id
),
compared AS (
    SELECT s.customer_id,
           COALESCE(CAST(NULLIF(TRIM(s.total_charges), '') AS REAL), 0) AS total_charges,
           COALESCE(p.total_paid, 0)                                    AS total_paid,
           COALESCE(p.n_payments, 0)                                    AS n_payments
    FROM raw_subscriptions AS s
    LEFT JOIN paid AS p ON p.customer_id = s.customer_id
)
SELECT customer_id, total_charges, total_paid, n_payments,
       ROUND(total_paid - total_charges, 2) AS difference
FROM compared
WHERE ABS(total_paid - total_charges) > 0.01
ORDER BY ABS(total_paid - total_charges) DESC;


-- name: check_monthly_charge_vs_last_payment
-- La cuota registrada en contratación debería coincidir con la última factura emitida.
-- ROW_NUMBER() numera los pagos de cada cliente del más reciente al más antiguo (rn = 1 = último).
WITH ranked AS (
    SELECT customer_id, payment_date, amount,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY payment_date DESC, payment_id) AS rn
    FROM raw_payments
    WHERE payment_date < (SELECT snapshot_date FROM snapshot_info)
)
SELECT s.customer_id,
       s.monthly_charges,
       r.amount       AS last_payment_amount,
       r.payment_date AS last_payment_date
FROM raw_subscriptions AS s
INNER JOIN ranked AS r ON r.customer_id = s.customer_id AND r.rn = 1
WHERE s.monthly_charges IS NULL
   OR ABS(s.monthly_charges - r.amount) > 0.005
ORDER BY s.customer_id;
