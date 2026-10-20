-- =====================================================================================
-- 02_customer_features.sql — Tabla final: UNA FILA POR CLIENTE
--
-- Une las cuatro tablas limpias y calcula indicadores por cliente:
--   * CTEs (WITH ...) para preparar cada bloque por separado y que la consulta se lea por partes.
--   * INNER JOIN donde la relación es obligatoria (todo cliente tiene suscripción).
--   * LEFT JOIN donde puede no haber filas (clientes sin pagos o sin servicios) + COALESCE a 0.
--   * Agregación condicional (MAX/SUM de CASE WHEN) para pasar servicios de filas a columnas.
--   * Window function (ROW_NUMBER) para separar el último pago del historial.
--   * Funciones de fecha (strftime) para calcular la antigüedad desde las fechas.
--
-- Control de leakage (diseño §4):
--   end_date SOLO se usa para construir la variable objetivo `churn`. Ninguna otra variable
--   se calcula con end_date; la antigüedad se mide siempre hasta la fecha de corte.
-- =====================================================================================

DROP TABLE IF EXISTS customer_features;

CREATE TABLE customer_features AS
WITH
-- Facturación agregada por cliente.
payment_summary AS (
    SELECT customer_id,
           COUNT(*)              AS n_payments,
           ROUND(SUM(amount), 2) AS total_revenue
    FROM clean_payments
    GROUP BY customer_id
),

-- Cuota media de los meses anteriores al último (rn > 1). Solo existe si tenure >= 2.
payment_history AS (
    SELECT customer_id,
           ROUND(AVG(amount), 2) AS avg_historical_charge
    FROM (
        SELECT customer_id,
               amount,
               ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY payment_date DESC) AS rn
        FROM clean_payments
    ) AS ranked
    WHERE rn > 1
    GROUP BY customer_id
),

-- Servicios: de formato largo (una fila por servicio) a columnas indicadoras 0/1.
service_summary AS (
    SELECT customer_id,
           COUNT(*) AS n_services,
           SUM(CASE WHEN service_name IN ('online_security', 'online_backup', 'device_protection',
                                          'tech_support', 'streaming_tv', 'streaming_movies')
                    THEN 1 ELSE 0 END)                                         AS n_addon_services,
           MAX(CASE WHEN service_name = 'phone_service'     THEN 1 ELSE 0 END) AS has_phone_service,
           MAX(CASE WHEN service_name = 'multiple_lines'    THEN 1 ELSE 0 END) AS has_multiple_lines,
           MAX(CASE WHEN service_name = 'online_security'   THEN 1 ELSE 0 END) AS has_online_security,
           MAX(CASE WHEN service_name = 'online_backup'     THEN 1 ELSE 0 END) AS has_online_backup,
           MAX(CASE WHEN service_name = 'device_protection' THEN 1 ELSE 0 END) AS has_device_protection,
           MAX(CASE WHEN service_name = 'tech_support'      THEN 1 ELSE 0 END) AS has_tech_support,
           MAX(CASE WHEN service_name = 'streaming_tv'      THEN 1 ELSE 0 END) AS has_streaming_tv,
           MAX(CASE WHEN service_name = 'streaming_movies'  THEN 1 ELSE 0 END) AS has_streaming_movies
    FROM clean_services
    GROUP BY customer_id
)

SELECT
    c.customer_id,

    -- Demografía: texto Yes/No y 0/1 unificados a indicadores 0/1.
    CASE WHEN c.gender = 'Male' THEN 1 ELSE 0 END      AS is_male,
    c.senior_citizen                                   AS is_senior,
    CASE WHEN c.partner = 'Yes' THEN 1 ELSE 0 END      AS has_partner,
    CASE WHEN c.dependents = 'Yes' THEN 1 ELSE 0 END   AS has_dependents,

    -- Contrato y facturación.
    s.contract_type,
    s.internet_service,
    s.payment_method,
    CASE WHEN s.payment_method LIKE '%(automatic)' THEN 1 ELSE 0 END AS is_auto_payment,
    CASE WHEN s.paperless_billing = 'Yes' THEN 1 ELSE 0 END          AS is_paperless,

    -- Antigüedad en meses completos entre el alta y la fecha de corte.
    (CAST(strftime('%Y', si.snapshot_date) AS INTEGER) - CAST(strftime('%Y', s.start_date) AS INTEGER)) * 12
  + (CAST(strftime('%m', si.snapshot_date) AS INTEGER) - CAST(strftime('%m', s.start_date) AS INTEGER))
                                                       AS tenure_months,

    s.monthly_charges,
    COALESCE(p.n_payments, 0)                          AS n_payments,
    COALESCE(p.total_revenue, 0)                       AS total_revenue,
    h.avg_historical_charge,                                         -- NULL si tenure < 2
    ROUND(s.monthly_charges / h.avg_historical_charge, 4) AS price_change_ratio,  -- NULL si tenure < 2

    -- Adopción de servicios (clientes sin ninguna fila en services -> 0).
    COALESCE(sv.n_services, 0)            AS n_services,
    COALESCE(sv.n_addon_services, 0)      AS n_addon_services,
    COALESCE(sv.has_phone_service, 0)     AS has_phone_service,
    COALESCE(sv.has_multiple_lines, 0)    AS has_multiple_lines,
    COALESCE(sv.has_online_security, 0)   AS has_online_security,
    COALESCE(sv.has_online_backup, 0)     AS has_online_backup,
    COALESCE(sv.has_device_protection, 0) AS has_device_protection,
    COALESCE(sv.has_tech_support, 0)      AS has_tech_support,
    COALESCE(sv.has_streaming_tv, 0)      AS has_streaming_tv,
    COALESCE(sv.has_streaming_movies, 0)  AS has_streaming_movies,

    -- Variable objetivo: la ÚNICA columna que usa end_date.
    CASE WHEN s.end_date IS NOT NULL THEN 1 ELSE 0 END AS churn

FROM clean_customers AS c
INNER JOIN clean_subscriptions AS s ON s.customer_id = c.customer_id
CROSS JOIN snapshot_info       AS si
LEFT JOIN payment_summary      AS p  ON p.customer_id  = c.customer_id
LEFT JOIN payment_history      AS h  ON h.customer_id  = c.customer_id
LEFT JOIN service_summary      AS sv ON sv.customer_id = c.customer_id
ORDER BY c.customer_id;
