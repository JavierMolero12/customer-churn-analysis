-- =====================================================================================
-- 00_schema.sql — Modelo de datos del proyecto (ver docs/01_project_design.md §3)
--
-- Dos capas:
--   raw_*   Volcado "operativo" tal y como llega, SIN restricciones. Por eso puede contener
--           duplicados, huérfanos o valores imposibles, igual que una extracción real.
--   clean_* Datos tras la limpieza, CON restricciones (PRIMARY KEY, FOREIGN KEY, CHECK).
--           Si la limpieza dejara pasar un error, la inserción fallaría: las restricciones
--           son la red de seguridad.
-- =====================================================================================

-- Se borra en orden inverso a las dependencias (primero las tablas que apuntan a otras).
DROP TABLE IF EXISTS customer_features;
DROP TABLE IF EXISTS clean_payments;
DROP TABLE IF EXISTS clean_services;
DROP TABLE IF EXISTS clean_subscriptions;
DROP TABLE IF EXISTS clean_customers;
DROP TABLE IF EXISTS raw_payments;
DROP TABLE IF EXISTS raw_services;
DROP TABLE IF EXISTS raw_subscriptions;
DROP TABLE IF EXISTS raw_customers;
DROP TABLE IF EXISTS snapshot_info;

-- Fecha de corte (una única fila). Las consultas la leen de aquí en vez de escribirla a mano.
CREATE TABLE snapshot_info (
    snapshot_date TEXT NOT NULL CHECK (snapshot_date = date(snapshot_date))
);

-- ------------------------------------------------------------------ capa raw
CREATE TABLE raw_customers (
    customer_id    TEXT,
    gender         TEXT,
    senior_citizen INTEGER,
    partner        TEXT,
    dependents     TEXT,
    signup_date    TEXT
);

CREATE TABLE raw_subscriptions (
    customer_id       TEXT,
    contract_type     TEXT,
    internet_service  TEXT,
    paperless_billing TEXT,
    payment_method    TEXT,
    monthly_charges   REAL,
    total_charges     TEXT,   -- texto, como en el CSV original (puede venir en blanco)
    start_date        TEXT,
    end_date          TEXT    -- NULL = cliente activo; con fecha = baja (define el churn)
);

CREATE TABLE raw_services (
    customer_id  TEXT,
    service_name TEXT
);

CREATE TABLE raw_payments (
    payment_id   INTEGER,
    customer_id  TEXT,
    payment_date TEXT,
    amount       REAL
);

-- ------------------------------------------------------------------ capa clean
CREATE TABLE clean_customers (
    customer_id    TEXT    PRIMARY KEY,
    gender         TEXT    NOT NULL CHECK (gender IN ('Female', 'Male')),
    senior_citizen INTEGER NOT NULL CHECK (senior_citizen IN (0, 1)),
    partner        TEXT    NOT NULL CHECK (partner IN ('Yes', 'No')),
    dependents     TEXT    NOT NULL CHECK (dependents IN ('Yes', 'No')),
    signup_date    TEXT    NOT NULL CHECK (signup_date = date(signup_date))
);

CREATE TABLE clean_subscriptions (
    customer_id       TEXT PRIMARY KEY REFERENCES clean_customers (customer_id),
    contract_type     TEXT NOT NULL CHECK (contract_type IN ('Month-to-month', 'One year', 'Two year')),
    internet_service  TEXT NOT NULL CHECK (internet_service IN ('DSL', 'Fiber optic', 'No')),
    paperless_billing TEXT NOT NULL CHECK (paperless_billing IN ('Yes', 'No')),
    payment_method    TEXT NOT NULL CHECK (payment_method IN (
                          'Electronic check', 'Mailed check',
                          'Bank transfer (automatic)', 'Credit card (automatic)')),
    monthly_charges   REAL NOT NULL CHECK (monthly_charges > 0),
    total_charges     REAL NOT NULL CHECK (total_charges >= 0),
    start_date        TEXT NOT NULL CHECK (start_date = date(start_date)),
    end_date          TEXT CHECK (end_date IS NULL OR end_date = date(end_date)),
    CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE TABLE clean_services (
    customer_id  TEXT NOT NULL REFERENCES clean_customers (customer_id),
    service_name TEXT NOT NULL CHECK (service_name IN (
                     'phone_service', 'multiple_lines', 'online_security', 'online_backup',
                     'device_protection', 'tech_support', 'streaming_tv', 'streaming_movies')),
    PRIMARY KEY (customer_id, service_name)
);

CREATE TABLE clean_payments (
    payment_id   INTEGER PRIMARY KEY,
    customer_id  TEXT NOT NULL REFERENCES clean_customers (customer_id),
    payment_date TEXT NOT NULL CHECK (payment_date = date(payment_date)),
    amount       REAL NOT NULL CHECK (amount > 0),
    UNIQUE (customer_id, payment_date)   -- como máximo un pago por cliente y mes
);
