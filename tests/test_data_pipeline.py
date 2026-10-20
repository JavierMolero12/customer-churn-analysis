"""Tests del pipeline de datos: la normalización no pierde información y los defectos son los diseñados."""

import pandas as pd

from src.build_database import denormalize, inject_defects, months_between
from src.config import SNAPSHOT_DATE


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
