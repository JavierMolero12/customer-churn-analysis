-- =====================================================================================
-- 03_analysis.sql — Preguntas de negocio respondidas con SQL
--
-- Se ejecutan sobre customer_features (una fila por cliente). Dan una primera lectura
-- DESCRIPTIVA: tasas de churn por segmento. El contraste formal de las hipótesis
-- (intervalos de confianza, tests estadísticos, criterio de decisión) se hace en el notebook 02.
--
-- churn_rate_pct = % de clientes del grupo que se dieron de baja = 100 * AVG(churn),
-- porque churn vale 0 o 1 y su media es la proporción de unos.
-- =====================================================================================


-- name: churn_overall
SELECT COUNT(*)                          AS customers,
       SUM(churn)                        AS churned,
       ROUND(100.0 * AVG(churn), 1)      AS churn_rate_pct,
       ROUND(SUM(monthly_charges), 2)    AS monthly_revenue,
       ROUND(SUM(CASE WHEN churn = 1 THEN monthly_charges ELSE 0 END), 2) AS monthly_revenue_lost
FROM customer_features;


-- name: churn_by_contract
SELECT contract_type,
       COUNT(*)                     AS customers,
       SUM(churn)                   AS churned,
       ROUND(100.0 * AVG(churn), 1) AS churn_rate_pct
FROM customer_features
GROUP BY contract_type
ORDER BY churn_rate_pct DESC;


-- name: churn_by_internet_service
SELECT internet_service,
       COUNT(*)                     AS customers,
       ROUND(100.0 * AVG(churn), 1) AS churn_rate_pct,
       ROUND(AVG(monthly_charges), 2) AS avg_monthly_charges
FROM customer_features
GROUP BY internet_service
ORDER BY churn_rate_pct DESC;


-- name: churn_by_payment_method
SELECT payment_method,
       CASE WHEN is_auto_payment = 1 THEN 'automatic' ELSE 'manual' END AS payment_type,
       COUNT(*)                     AS customers,
       ROUND(100.0 * AVG(churn), 1) AS churn_rate_pct
FROM customer_features
GROUP BY payment_method, is_auto_payment
ORDER BY churn_rate_pct DESC;


-- name: churn_by_tenure_band
-- Tramos definidos en el diseño (H4). El ORDER BY usa el límite inferior del tramo, no el texto.
SELECT CASE
           WHEN tenure_months <= 6  THEN '00-06'
           WHEN tenure_months <= 12 THEN '07-12'
           WHEN tenure_months <= 24 THEN '13-24'
           WHEN tenure_months <= 48 THEN '25-48'
           ELSE '49-72'
       END                          AS tenure_band,
       COUNT(*)                     AS customers,
       ROUND(100.0 * AVG(churn), 1) AS churn_rate_pct
FROM customer_features
GROUP BY tenure_band
ORDER BY MIN(tenure_months);


-- name: churn_by_addon_services
-- Solo clientes con internet (H1): sin internet no se pueden contratar servicios adicionales.
SELECT n_addon_services,
       COUNT(*)                     AS customers,
       ROUND(100.0 * AVG(churn), 1) AS churn_rate_pct
FROM customer_features
WHERE internet_service <> 'No'
GROUP BY n_addon_services
ORDER BY n_addon_services;


-- name: monthly_revenue_lost_by_contract
-- ¿Dónde se concentra el ingreso mensual que se pierde con las bajas?
WITH lost AS (
    SELECT contract_type,
           SUM(CASE WHEN churn = 1 THEN monthly_charges ELSE 0 END) AS revenue_lost
    FROM customer_features
    GROUP BY contract_type
)
SELECT contract_type,
       ROUND(revenue_lost, 2)                                          AS monthly_revenue_lost,
       ROUND(100.0 * revenue_lost / (SELECT SUM(revenue_lost) FROM lost), 1) AS share_of_lost_pct
FROM lost
ORDER BY revenue_lost DESC;


-- name: high_risk_segments
-- Segmentos (contrato x plan x tipo de pago) con más churn.
-- HAVING descarta segmentos de menos de 100 clientes: en grupos pequeños una tasa alta puede ser azar.
SELECT contract_type,
       internet_service,
       CASE WHEN is_auto_payment = 1 THEN 'automatic' ELSE 'manual' END AS payment_type,
       COUNT(*)                     AS customers,
       SUM(churn)                   AS churned,
       ROUND(100.0 * AVG(churn), 1) AS churn_rate_pct
FROM customer_features
GROUP BY contract_type, internet_service, is_auto_payment
HAVING COUNT(*) >= 100
ORDER BY churn_rate_pct DESC
LIMIT 10;


-- name: churn_vs_plan_average_price
-- Subconsulta correlacionada: ¿paga cada cliente más o menos que la media de SU plan de internet?
-- Comparar dentro del mismo plan evita confundir "precio alto" con "tener fibra".
SELECT internet_service,
       CASE WHEN f.monthly_charges > (SELECT AVG(f2.monthly_charges)
                                      FROM customer_features AS f2
                                      WHERE f2.internet_service = f.internet_service)
            THEN 'above plan average'
            ELSE 'at or below plan average'
       END                          AS price_position,
       COUNT(*)                     AS customers,
       ROUND(100.0 * AVG(churn), 1) AS churn_rate_pct
FROM customer_features AS f
GROUP BY internet_service, price_position
ORDER BY internet_service, price_position;
