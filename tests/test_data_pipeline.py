"""Tests del pipeline de datos.

- La normalización no pierde información y los defectos inyectados son los diseñados.
- La limpieza corrige todos los defectos sin tocar nada más: las tablas limpias reconstruyen el CSV original.
"""

import pandas as pd

from src.build_database import denormalize, inject_defects, months_between
from src.config import SNAPSHOT_DATE
from src.data_cleaning import quality_summary, run_quality_checks
from src.database import query


def _typed(flat: pd.DataFrame) -> pd.DataFrame:
    """Mismos tipos en ambos lados para comparar (el CSV original se lee todo como texto)."""
    return flat.astype(str).astype(
        {"SeniorCitizen": int, "tenure": int, "MonthlyCharges": float}
    )


def test_normalization_rebuilds_the_original_csv(source, normalized):
    rebuilt = denormalize(normalized)
    pd.testing.assert_frame_equal(_typed(rebuilt), _typed(source), check_dtype=False)


def test_payments_add_up_to_total_charges(normalized):
    subscriptions = normalized["subscriptions"].set_index("customer_id")
    payments = normalized["payments"]

    expected_total = pd.to_numeric(subscriptions["total_charges"].str.strip().replace("", "0"))
    paid = payments.groupby("customer_id")["amount"].sum().reindex(subscriptions.index, fill_value=0)
    assert (paid - expected_total).abs().max() < 0.01

    tenure = months_between(subscriptions["start_date"], SNAPSHOT_DATE)
    n_payments = payments.groupby("customer_id").size().reindex(subscriptions.index, fill_value=0)
    assert (n_payments == tenure).all()


def test_last_payment_is_the_current_monthly_charge(normalized):
    subscriptions = normalized["subscriptions"].set_index("customer_id")
    last = normalized["payments"].sort_values("payment_date").groupby("customer_id").last()
    assert (last["amount"] - subscriptions.loc[last.index, "monthly_charges"]).abs().max() < 0.005
    assert (last["payment_date"] < SNAPSHOT_DATE).all()


def test_injected_defects_match_the_design(normalized):
    _, manifest = inject_defects(normalized)
    expected = {"D1": 20, "D2": 70, "D3": 10, "D4": 10, "D5": 50, "D6": 30, "D7": 10}
    assert manifest["defect_id"].value_counts().to_dict() == expected

    _, manifest_again = inject_defects(normalized)
    pd.testing.assert_frame_equal(manifest, manifest_again)  # reproducible con la misma semilla


# ---------------------------------------------------------------- limpieza


def _clean_tables(conn) -> dict[str, pd.DataFrame]:
    return {name: query(conn, f"SELECT * FROM clean_{name}") for name in ["customers", "subscriptions", "services"]}


def test_cleaning_rebuilds_the_original_csv(test_db, source):
    conn, _ = test_db
    rebuilt = denormalize(_clean_tables(conn))

    # Única diferencia esperada: los 11 TotalCharges vacíos pasan a 0 (decisión R1).
    expected = source.assign(TotalCharges=source["TotalCharges"].str.strip().replace("", "0"))
    pd.testing.assert_frame_equal(
        _typed(rebuilt).astype({"TotalCharges": float}),
        _typed(expected).astype({"TotalCharges": float}),
        check_dtype=False,
    )


def test_cleaning_removes_every_injected_payment(test_db, normalized):
    conn, manifest = test_db
    injected_ids = manifest.loc[manifest["table_name"] == "payments", "record_key"].astype(int)
    clean_ids = set(query(conn, "SELECT payment_id FROM clean_payments")["payment_id"])

    assert clean_ids.isdisjoint(injected_ids)
    assert clean_ids == set(normalized["payments"]["payment_id"])  # y no se pierde ningún pago real


def test_customer_id_is_unique_after_cleaning(test_db):
    conn, _ = test_db
    customers = query(conn, "SELECT customer_id FROM clean_customers")
    assert customers["customer_id"].is_unique
    assert len(customers) == 7043


def test_clean_layer_passes_every_quality_check(test_db):
    conn, _ = test_db
    summary = quality_summary(run_quality_checks(conn, layer="clean"))
    assert summary["rows_flagged"].sum() == 0, summary[summary["rows_flagged"] > 0]
