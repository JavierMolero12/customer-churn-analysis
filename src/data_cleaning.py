"""Limpieza de la capa raw_* -> clean_*.

Reglas de diseño:
- La limpieza NO lee el manifiesto de defectos inyectados: detecta los problemas con reglas
  generales, igual que haría con datos reales. Los tests comparan después con el manifiesto.
- No se borra nada "por si acaso": cada eliminación o corrección tiene un motivo y queda en el log.
- Lo que no sabemos corregir con seguridad detiene el proceso (ValueError) en vez de inventarse.

Uso: python -m src.data_cleaning
"""

from contextlib import closing
from pathlib import Path

import pandas as pd

from src import config
from src.build_database import months_between
from src.database import get_connection, load_named_queries, query

CLEAN_TABLES_IN_DEPENDENCY_ORDER = ["customers", "subscriptions", "services", "payments"]


class CleaningLog:
    """Registro de cada decisión de limpieza: qué tabla, cuántas filas y por qué."""

    def __init__(self) -> None:
        self.entries: list[dict] = []

    def add(self, table: str, action: str, rows_affected: int, reason: str) -> None:
        self.entries.append(
            {"table": table, "action": action, "rows_affected": int(rows_affected), "reason": reason}
        )

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.entries)


# ---------------------------------------------------------------- comprobaciones de calidad


def run_quality_checks(conn, layer: str = "raw") -> dict[str, pd.DataFrame]:
    """Ejecuta las consultas `check_*` de sql/01_data_quality.sql sobre la capa indicada.

    Las consultas están escritas contra raw_*. Para la capa limpia se sustituye el prefijo,
    así las MISMAS reglas verifican el resultado de la limpieza.
    """
    checks = load_named_queries("01_data_quality.sql")
    return {
        name: query(conn, sql.replace("raw_", f"{layer}_"))
        for name, sql in checks.items()
        if name.startswith("check_")
    }


def quality_summary(results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return pd.DataFrame(
        {"check": list(results), "rows_flagged": [len(df) for df in results.values()]}
    )


# ---------------------------------------------------------------- reglas de limpieza


def standardize_labels(values: pd.Series, canonical: list[str]) -> pd.Series:
    """Lleva cada etiqueta a su forma canónica ignorando mayúsculas y espacios sobrantes.

    Un valor que no corresponde a ninguna categoría conocida no se adivina: se lanza un error.
    """
    lookup = {label.lower(): label for label in canonical}
    standardized = values.str.strip().str.lower().map(lookup)
    unknown = values[standardized.isna() & values.notna()]
    if not unknown.empty:
        raise ValueError(f"Categorías desconocidas en {values.name}: {sorted(unknown.unique())}")
    return standardized


def clean_customers(raw: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    customers = raw.drop_duplicates(ignore_index=True)
    log.add("customers", "drop exact duplicates", len(raw) - len(customers),
            "Filas idénticas en todas las columnas: eliminar copias no pierde información.")

    if customers["customer_id"].duplicated().any():
        raise ValueError("Hay customer_id repetidos con datos distintos: requieren revisión manual.")
    return customers


def clean_payments(
    raw: pd.DataFrame,
    subscriptions: pd.DataFrame,
    log: CleaningLog,
    snapshot_date: str = config.SNAPSHOT_DATE,
) -> pd.DataFrame:
    payments = raw.copy()

    is_orphan = ~payments["customer_id"].isin(subscriptions["customer_id"])
    payments = payments[~is_orphan]
    log.add("payments", "drop orphan payments", is_orphan.sum(),
            "El cliente no existe: el pago no se puede atribuir a nadie ni conciliar.")

    start_date = payments["customer_id"].map(subscriptions.set_index("customer_id")["start_date"])
    out_of_period = (payments["payment_date"] >= snapshot_date) | (payments["payment_date"] < start_date)
    payments = payments[~out_of_period]
    log.add("payments", "drop payments outside subscription period", out_of_period.sum(),
            "Fecha anterior al alta o posterior a la fecha de corte: imposible en una foto a esa fecha.")

    payments = payments.sort_values("payment_id")
    is_duplicate = payments.duplicated(subset=["customer_id", "payment_date", "amount"], keep="first")
    payments = payments[~is_duplicate]
    log.add("payments", "drop duplicated payments (keep lowest payment_id)", is_duplicate.sum(),
            "Mismo cliente, mes e importe: cobro registrado dos veces. Se conserva el registro original.")

    if payments.duplicated(subset=["customer_id", "payment_date"]).any():
        raise ValueError("Pagos del mismo cliente y mes con importes distintos: requieren revisión manual.")
    return payments.sort_values(["payment_date", "customer_id"], ignore_index=True)


def clean_subscriptions(
    raw: pd.DataFrame,
    payments: pd.DataFrame,
    log: CleaningLog,
    snapshot_date: str = config.SNAPSHOT_DATE,
) -> pd.DataFrame:
    """`payments` debe estar ya limpio: la última factura se usa para validar la cuota."""
    subscriptions = raw.copy()

    catalogs = {
        "contract_type": config.CONTRACT_TYPES,
        "payment_method": config.PAYMENT_METHODS,
        "internet_service": config.INTERNET_SERVICES,
        "paperless_billing": ["Yes", "No"],
    }
    for column, canonical in catalogs.items():
        standardized = standardize_labels(subscriptions[column], canonical)
        n_changed = (standardized != subscriptions[column]).sum()
        subscriptions[column] = standardized
        if n_changed:
            log.add("subscriptions", f"standardize {column} labels", n_changed,
                    "Variantes de mayúsculas/espacios de una categoría válida: se unifican.")

    # total_charges: texto -> número. Vacío solo es aceptable si el cliente aún no ha sido facturado.
    tenure = months_between(subscriptions["start_date"], snapshot_date)
    text = subscriptions["total_charges"].str.strip()
    is_blank = text == ""
    if (is_blank & (tenure > 0)).any():
        raise ValueError("total_charges vacío en clientes con meses facturados: no es un 0 estructural.")
    subscriptions["total_charges"] = pd.to_numeric(text.mask(is_blank, "0"))
    log.add("subscriptions", "convert total_charges to number (blank -> 0)", is_blank.sum(),
            "Todos los vacíos tienen tenure = 0: clientes aún sin facturar, el total real es 0.")

    # monthly_charges: la última factura emitida es la fuente de verdad del importe cobrado.
    last_payment = (
        payments.sort_values(["payment_date", "payment_id"]).groupby("customer_id")["amount"].last()
    )
    last = subscriptions["customer_id"].map(last_payment)
    charges = subscriptions["monthly_charges"]

    is_missing = charges.isna() & last.notna()
    differs = charges.notna() & last.notna() & ((charges - last).abs() > 0.005)
    is_decimal_shift = differs & ((charges / 100 - last).abs() <= 0.005)
    if (differs & ~is_decimal_shift).any():
        raise ValueError("Cuotas que no cuadran con la última factura sin patrón conocido: revisión manual.")

    subscriptions.loc[is_missing | is_decimal_shift, "monthly_charges"] = last
    log.add("subscriptions", "recover missing monthly_charges from last payment", is_missing.sum(),
            "La cuota falta pero la última factura indica el importe cobrado.")
    log.add("subscriptions", "fix monthly_charges decimal shift (x100)", is_decimal_shift.sum(),
            "Valor extremo exactamente 100 veces la última factura: error de coma decimal.")

    if subscriptions["monthly_charges"].isna().any():
        raise ValueError("Quedan cuotas vacías sin factura desde la que recuperarlas.")
    return subscriptions


def clean_services(raw: pd.DataFrame, customers: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    services = raw.drop_duplicates(ignore_index=True)
    log.add("services", "drop exact duplicates", len(raw) - len(services),
            "Un servicio contratado solo puede figurar una vez por cliente.")

    is_orphan = ~services["customer_id"].isin(customers["customer_id"])
    services = services[~is_orphan]
    log.add("services", "drop services without customer", is_orphan.sum(),
            "Servicio de un cliente inexistente.")

    unknown = set(services["service_name"]) - set(config.SERVICE_COLUMNS.values())
    if unknown:
        raise ValueError(f"Servicios desconocidos: {sorted(unknown)}")
    return services


# ---------------------------------------------------------------- orquestación


def load_raw_tables(conn) -> dict[str, pd.DataFrame]:
    return {name: query(conn, f"SELECT * FROM raw_{name}") for name in CLEAN_TABLES_IN_DEPENDENCY_ORDER}


def clean_tables(raw: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Aplica todas las reglas en orden y devuelve (tablas limpias, log de decisiones)."""
    log = CleaningLog()
    customers = clean_customers(raw["customers"], log)
    payments = clean_payments(raw["payments"], raw["subscriptions"], log)
    subscriptions = clean_subscriptions(raw["subscriptions"], payments, log)
    services = clean_services(raw["services"], customers, log)
    tables = {
        "customers": customers,
        "subscriptions": subscriptions,
        "services": services,
        "payments": payments,
    }
    return tables, log.to_frame()


def write_clean_tables(conn, tables: dict[str, pd.DataFrame]) -> None:
    """Vacía y rellena las tablas clean_*. Sus restricciones (PK, FK, CHECK) validan el resultado."""
    for name in reversed(CLEAN_TABLES_IN_DEPENDENCY_ORDER):
        conn.execute(f"DELETE FROM clean_{name}")
    for name in CLEAN_TABLES_IN_DEPENDENCY_ORDER:
        tables[name].to_sql(f"clean_{name}", conn, if_exists="append", index=False)
    conn.commit()


def clean_database(db_path: Path = config.DB_PATH) -> pd.DataFrame:
    with closing(get_connection(db_path)) as conn:
        tables, log = clean_tables(load_raw_tables(conn))
        write_clean_tables(conn, tables)
        remaining = quality_summary(run_quality_checks(conn, layer="clean"))

    print("Decisiones de limpieza:")
    print(log.to_string(index=False, columns=["table", "action", "rows_affected"]))
    print(f"\nComprobaciones de calidad sobre clean_* con problemas: {(remaining['rows_flagged'] > 0).sum()}")
    return log


if __name__ == "__main__":
    clean_database()
