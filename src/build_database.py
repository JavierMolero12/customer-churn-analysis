"""Construye la base de datos SQLite "operativa" (capa raw_*) a partir del CSV de IBM.

Pasos:
1. normalize(): reparte el CSV en customers, subscriptions, services y payments sin perder información.
2. inject_defects(): introduce defectos de calidad controlados (D1–D7) y los registra en un manifiesto.
3. Guarda las tablas raw_* en SQLite.

denormalize() hace el camino inverso. Los tests la usan para comprobar que no se pierde información.

Uso: python -m src.build_database
"""

import string
from contextlib import closing
from pathlib import Path

import numpy as np
import pandas as pd

from src import config
from src.database import get_connection, run_sql_script

# ---------------------------------------------------------------- fechas (meses completos)


def month_index(dates: pd.Series | str) -> pd.Series | int:
    """'2024-10-01' -> nº de meses desde el año 0. Permite sumar y restar meses con enteros."""
    if isinstance(dates, str):
        return int(dates[:4]) * 12 + int(dates[5:7]) - 1
    return dates.str[:4].astype(int) * 12 + dates.str[5:7].astype(int) - 1


def month_index_to_date(index: pd.Series) -> pd.Series:
    """Inverso de month_index: siempre devuelve el día 1 del mes."""
    years = (index // 12).astype(str)
    months = (index % 12 + 1).astype(str).str.zfill(2)
    return years + "-" + months + "-01"


def months_between(start_dates: pd.Series, end_date: str) -> pd.Series:
    return month_index(end_date) - month_index(start_dates)


# ---------------------------------------------------------------- CSV <-> tablas


def load_source_csv(path: Path = config.RAW_CSV_PATH) -> pd.DataFrame:
    """Lee el CSV como texto, sin convertir tipos: queremos ver los datos tal y como vienen."""
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def build_payments(subscriptions: pd.DataFrame, tenure: pd.Series) -> pd.DataFrame:
    """Reconstruye una fila por mes facturado a partir de los totales reales (diseño §3.4).

    - Último pago = cuota actual real (monthly_charges).
    - Pagos anteriores = el resto del total real repartido a partes iguales.
    - El redondeo a céntimos se compensa en el primer pago, para que SUM(amount) = total_charges.
    - tenure = 1: un único pago igual al total. tenure = 0: sin pagos.
    """
    billed = subscriptions.assign(tenure=tenure.to_numpy())
    billed = billed[billed["tenure"] > 0]
    rows = billed.loc[billed.index.repeat(billed["tenure"])].copy()
    k = rows.groupby(level=0).cumcount()  # 0 = primer mes, tenure - 1 = último mes

    n_months = rows["tenure"]
    current = rows["monthly_charges"]
    total = rows["total_charges"].astype(float)

    history_months = (n_months - 1).where(n_months > 1)  # evita dividir entre 0
    base = ((total - current) / history_months).round(2)
    rounding_fix = (total - current - base * history_months).round(2)

    amount = np.select(
        [n_months == 1, k == n_months - 1, k == 0],
        [total, current, base + rounding_fix],
        default=base,
    )
    payment_index = month_index(rows["start_date"]) + k

    payments = pd.DataFrame(
        {
            "customer_id": rows["customer_id"].to_numpy(),
            "payment_date": month_index_to_date(payment_index).to_numpy(),
            "amount": np.round(amount, 2),
        }
    )
    payments = payments.sort_values(["payment_date", "customer_id"], ignore_index=True)
    payments.insert(0, "payment_id", np.arange(1, len(payments) + 1))
    return payments


def normalize(source: pd.DataFrame, snapshot_date: str = config.SNAPSHOT_DATE) -> dict[str, pd.DataFrame]:
    """Reparte el CSV plano en las cuatro tablas del modelo de datos."""
    tenure = source["tenure"].astype(int)
    start_date = month_index_to_date(month_index(snapshot_date) - tenure)

    customers = pd.DataFrame(
        {
            "customer_id": source["customerID"],
            "gender": source["gender"],
            "senior_citizen": source["SeniorCitizen"].astype(int),
            "partner": source["Partner"],
            "dependents": source["Dependents"],
            "signup_date": start_date,
        }
    )
    subscriptions = pd.DataFrame(
        {
            "customer_id": source["customerID"],
            "contract_type": source["Contract"],
            "internet_service": source["InternetService"],
            "paperless_billing": source["PaperlessBilling"],
            "payment_method": source["PaymentMethod"],
            "monthly_charges": source["MonthlyCharges"].astype(float),
            "total_charges": source["TotalCharges"],  # texto, como en origen
            "start_date": start_date,
            "end_date": source["Churn"].map({"Yes": snapshot_date, "No": None}),
        }
    )
    services = (
        source[["customerID", *config.SERVICE_COLUMNS]]
        .melt(id_vars="customerID", var_name="source_column", value_name="value")
        .query("value == 'Yes'")
        .assign(service_name=lambda df: df["source_column"].map(config.SERVICE_COLUMNS))
        .rename(columns={"customerID": "customer_id"})
        .sort_values(["customer_id", "service_name"])[["customer_id", "service_name"]]
        .reset_index(drop=True)
    )
    # Para los clientes sin facturar (tenure = 0) el total viene en blanco: en el reparto cuenta como 0.
    billing = subscriptions.assign(total_charges=subscriptions["total_charges"].str.strip().replace("", "0"))
    payments = build_payments(billing, tenure)

    return {
        "customers": customers,
        "subscriptions": subscriptions,
        "services": services,
        "payments": payments,
    }


def denormalize(tables: dict[str, pd.DataFrame], snapshot_date: str = config.SNAPSHOT_DATE) -> pd.DataFrame:
    """Reconstruye el CSV original (mismas 21 columnas) a partir de las tablas normalizadas."""
    customers = tables["customers"].set_index("customer_id")
    subscriptions = tables["subscriptions"].set_index("customer_id").loc[customers.index]
    contracted = pd.crosstab(tables["services"]["customer_id"], tables["services"]["service_name"])
    contracted = contracted.reindex(index=customers.index, columns=list(config.SERVICE_COLUMNS.values()), fill_value=0)

    yes_no = {1: "Yes", 0: "No"}
    has_phone = contracted["phone_service"] == 1
    has_internet = subscriptions["internet_service"] != "No"

    flat = pd.DataFrame(index=customers.index)
    flat["gender"] = customers["gender"]
    flat["SeniorCitizen"] = customers["senior_citizen"]
    flat["Partner"] = customers["partner"]
    flat["Dependents"] = customers["dependents"]
    flat["tenure"] = months_between(subscriptions["start_date"], snapshot_date)
    flat["PhoneService"] = contracted["phone_service"].map(yes_no)
    flat["MultipleLines"] = contracted["multiple_lines"].map(yes_no).where(has_phone, "No phone service")
    flat["InternetService"] = subscriptions["internet_service"]
    for source_column, service in config.SERVICE_COLUMNS.items():
        if service in config.ADDON_SERVICES:
            flat[source_column] = contracted[service].map(yes_no).where(has_internet, "No internet service")
    flat["Contract"] = subscriptions["contract_type"]
    flat["PaperlessBilling"] = subscriptions["paperless_billing"]
    flat["PaymentMethod"] = subscriptions["payment_method"]
    flat["MonthlyCharges"] = subscriptions["monthly_charges"]
    flat["TotalCharges"] = subscriptions["total_charges"]
    flat["Churn"] = np.where(subscriptions["end_date"].notna(), "Yes", "No")
    return flat.rename_axis("customerID").reset_index()


# ---------------------------------------------------------------- defectos inyectados (SINTÉTICO)


def _label_variant(value: str, rng: np.random.Generator) -> str:
    """Devuelve una variante "sucia" de una etiqueta: mayúsculas, minúsculas o espacios."""
    variants = [value.lower(), value.upper(), f"{value} ", f" {value}"]
    return variants[rng.integers(len(variants))]


def _fake_customer_id(rng: np.random.Generator) -> str:
    """ID con el mismo formato que los reales (p. ej. 7590-VHVEG)."""
    letters = "".join(rng.choice(list(string.ascii_uppercase), size=5))
    return f"{rng.integers(1000, 10000)}-{letters}"


def inject_defects(
    tables: dict[str, pd.DataFrame],
    seed: int = config.RANDOM_SEED,
    snapshot_date: str = config.SNAPSHOT_DATE,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Introduce los defectos D1–D7 del diseño (§3.6) y devuelve (tablas, manifiesto).

    El manifiesto solo lo usan los tests: la limpieza NO lo lee (sería limpiar con las respuestas).
    """
    rng = np.random.default_rng(seed)
    customers = tables["customers"].copy()
    subscriptions = tables["subscriptions"].copy()
    payments = tables["payments"].copy()
    manifest = []

    def log(defect_id, table, key, column=None, original=None, injected=None):
        manifest.append(
            {
                "defect_id": defect_id,
                "table_name": table,
                "record_key": key,
                "column_name": column,
                "original_value": original,
                "injected_value": injected,
            }
        )

    # D1: 20 clientes duplicados exactamente (p. ej. una carga del CRM ejecutada dos veces).
    duplicated = customers.loc[rng.choice(customers.index, size=20, replace=False)]
    customers = pd.concat([customers, duplicated], ignore_index=True)
    for customer_id in duplicated["customer_id"]:
        log("D1", "customers", customer_id, injected="exact duplicate row")

    # D2: 70 etiquetas inconsistentes (35 en payment_method y 35 en contract_type).
    d2_rows = rng.choice(subscriptions.index, size=70, replace=False)
    for position, row in enumerate(d2_rows):
        column = "payment_method" if position < 35 else "contract_type"
        original = subscriptions.at[row, column]
        subscriptions.at[row, column] = _label_variant(original, rng)
        log("D2", "subscriptions", subscriptions.at[row, "customer_id"], column, original, subscriptions.at[row, column])

    # D3 y D4: solo clientes con algún pago, que permiten recuperar la cuota desde facturación.
    has_payments = subscriptions["start_date"] < snapshot_date
    eligible = subscriptions.index[has_payments & ~subscriptions.index.isin(d2_rows)]
    d3_rows, d4_rows = np.split(rng.choice(eligible, size=20, replace=False), 2)
    for row in d3_rows:  # D3: error de coma decimal (29.85 -> 2985.0)
        original = subscriptions.at[row, "monthly_charges"]
        subscriptions.at[row, "monthly_charges"] = round(original * 100, 2)
        log("D3", "subscriptions", subscriptions.at[row, "customer_id"], "monthly_charges", original, round(original * 100, 2))
    for row in d4_rows:  # D4: valor perdido
        original = subscriptions.at[row, "monthly_charges"]
        subscriptions.at[row, "monthly_charges"] = np.nan
        log("D4", "subscriptions", subscriptions.at[row, "customer_id"], "monthly_charges", original, None)

    # D5–D7: filas extra en pagos. Reciben IDs posteriores, como pasaría con un reproceso.
    next_id = int(payments["payment_id"].max()) + 1
    extra_rows = []

    source_rows = payments.loc[rng.choice(payments.index, size=50, replace=False)]
    for _, original in source_rows.iterrows():  # D5: pago duplicado
        extra_rows.append(("D5", original.to_dict(), f"duplicate of payment_id {original['payment_id']}"))

    existing_ids = set(customers["customer_id"])
    for _, original in payments.loc[rng.choice(payments.index, size=30, replace=False)].iterrows():
        fake_id = _fake_customer_id(rng)
        while fake_id in existing_ids:
            fake_id = _fake_customer_id(rng)
        row = original.to_dict() | {"customer_id": fake_id}  # D6: cliente inexistente
        extra_rows.append(("D6", row, f"orphan customer_id {fake_id}"))

    for _, original in payments.loc[rng.choice(payments.index, size=10, replace=False)].iterrows():
        future = month_index_to_date(pd.Series([month_index(snapshot_date) + int(rng.integers(0, 24))]))[0]
        row = original.to_dict() | {"payment_date": future}  # D7: fecha posterior al corte
        extra_rows.append(("D7", row, f"payment_date {future}"))

    new_payments = []
    for order in rng.permutation(len(extra_rows)):  # mezcla los IDs entre los tres tipos
        defect_id, row, description = extra_rows[order]
        row["payment_id"] = next_id
        log(defect_id, "payments", next_id, injected=description)
        new_payments.append(row)
        next_id += 1
    payments = pd.concat([payments, pd.DataFrame(new_payments)], ignore_index=True)

    defective = tables | {"customers": customers, "subscriptions": subscriptions, "payments": payments}
    return defective, pd.DataFrame(manifest)


# ---------------------------------------------------------------- base de datos


def write_raw_tables(conn, tables: dict[str, pd.DataFrame], snapshot_date: str = config.SNAPSHOT_DATE) -> None:
    run_sql_script(conn, "00_schema.sql")
    conn.execute("INSERT INTO snapshot_info (snapshot_date) VALUES (?)", (snapshot_date,))
    for name, df in tables.items():
        df.to_sql(f"raw_{name}", conn, if_exists="append", index=False)
    conn.commit()


def build_database(
    csv_path: Path = config.RAW_CSV_PATH,
    db_path: Path = config.DB_PATH,
    manifest_path: Path = config.DEFECTS_MANIFEST_PATH,
) -> pd.DataFrame:
    """CSV -> tablas normalizadas -> defectos inyectados -> SQLite. Devuelve el manifiesto."""
    tables = normalize(load_source_csv(csv_path))
    raw_tables, manifest = inject_defects(tables)
    with closing(get_connection(db_path)) as conn:
        write_raw_tables(conn, raw_tables)
    manifest.to_csv(manifest_path, index=False)

    print(f"Base de datos creada: {config.relative_to_project(db_path)}")
    for name, df in raw_tables.items():
        print(f"  raw_{name:<14} {len(df):>8,} filas")
    print(f"Defectos inyectados: {len(manifest)} (manifiesto: {config.relative_to_project(manifest_path)})")
    return manifest


if __name__ == "__main__":
    build_database()
