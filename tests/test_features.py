"""Tests de la tabla final por cliente (customer_features, construida en SQL)."""

import pandas as pd
import pytest

from src.config import ADDON_SERVICES, SERVICE_COLUMNS
from src.database import query, run_sql_script

MONEY_AND_COUNT_COLUMNS = [
    "tenure_months",
    "monthly_charges",
    "n_payments",
    "total_revenue",
    "n_services",
    "n_addon_services",
]
# Sin historial de pagos previos (tenure < 2) no hay media histórica: NaN esperado y documentado.
COLUMNS_ALLOWED_TO_BE_MISSING = ["avg_historical_charge", "price_change_ratio"]


@pytest.fixture(scope="module")
def features(test_db) -> pd.DataFrame:
    conn, _ = test_db
    run_sql_script(conn, "02_customer_features.sql")
    return query(conn, "SELECT * FROM customer_features").set_index("customer_id")


def test_one_row_per_customer(features, source):
    assert features.index.is_unique
    assert set(features.index) == set(source["customerID"])


def test_churn_is_binary_and_matches_the_source(features, source):
    assert set(features["churn"].unique()) == {0, 1}
    assert features["churn"].sum() == (source["Churn"] == "Yes").sum()


def test_no_negative_values(features):
    assert (features[MONEY_AND_COUNT_COLUMNS] >= 0).all().all()


def test_key_features_have_no_missing_values(features):
    required = features.drop(columns=COLUMNS_ALLOWED_TO_BE_MISSING)
    assert required.notna().all().all(), required.columns[required.isna().any()].tolist()

    missing_history = features["avg_historical_charge"].isna()
    assert (missing_history == (features["tenure_months"] < 2)).all()


def test_sql_date_arithmetic_recovers_the_original_tenure(features, source):
    original_tenure = source.set_index("customerID")["tenure"].astype(int)
    assert (features["tenure_months"] == original_tenure.loc[features.index]).all()


def test_total_revenue_matches_total_charges(features, source):
    total_charges = pd.to_numeric(source.set_index("customerID")["TotalCharges"].str.strip().replace("", "0"))
    assert (features["total_revenue"] - total_charges.loc[features.index]).abs().max() < 0.01


def test_service_counts_match_service_flags(features):
    all_flags = [f"has_{service}" for service in SERVICE_COLUMNS.values()]
    addon_flags = [f"has_{service}" for service in ADDON_SERVICES]
    assert (features[all_flags].sum(axis=1) == features["n_services"]).all()
    assert (features[addon_flags].sum(axis=1) == features["n_addon_services"]).all()
