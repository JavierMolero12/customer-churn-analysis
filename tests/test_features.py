"""Tests de la tabla final por cliente (SQL, Fase 2c) y del feature engineering (Fase 4)."""

import pandas as pd
import pytest

from src import feature_engineering as fe
from src.config import ADDON_SERVICES, SERVICE_COLUMNS, TENURE_BUCKETS, TEST_SIZE
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


# ---------------------------------------------------------------- Fase 4: feature engineering


@pytest.fixture(scope="module")
def model_data(features):
    """Variables de la Fase 4 y división train/test, sobre la base de datos de prueba."""
    enriched = fe.add_model_features(features.reset_index())
    return enriched, fe.split_train_test(enriched)


def test_tenure_buckets_follow_the_design(model_data):
    enriched, _ = model_data
    assert enriched["tenure_bucket"].isin(TENURE_BUCKETS).all()
    upper_limit = enriched.groupby("tenure_bucket")["tenure_months"].max()
    assert upper_limit.loc[TENURE_BUCKETS].tolist() == [6, 12, 24, 48, 72]
    assert ((enriched["has_price_history"] == 1) == enriched["price_change_ratio"].notna()).all()


def test_model_features_exclude_leakage_identifiers_and_sensitive_attributes():
    columns = fe.model_feature_columns()
    assert not set(columns) & fe.FORBIDDEN_FEATURES
    assert not set(columns) & set(fe.SENSITIVE_FEATURES)
    assert not set(columns) & set(fe.EXCLUDED_FEATURES)
    with pytest.raises(ValueError, match="leakage"):
        fe.check_no_leakage([*columns, "end_date"])


def test_split_is_stratified_and_has_no_shared_customers(model_data):
    _, (X_train, X_test, y_train, y_test) = model_data
    assert not set(X_train.index) & set(X_test.index)
    assert len(X_test) == pytest.approx(TEST_SIZE * (len(X_train) + len(X_test)), abs=1)
    assert abs(y_train.mean() - y_test.mean()) < 0.005


def test_preprocessor_learns_only_from_train(model_data):
    _, (X_train, X_test, _, _) = model_data
    preprocessor = fe.build_preprocessor().fit(X_train)
    scaler = preprocessor.named_transformers_["numeric"]
    assert scaler.mean_ == pytest.approx(X_train[fe.NUMERIC_FEATURES].mean().to_numpy())
    everyone = pd.concat([X_train, X_test])
    assert scaler.mean_ != pytest.approx(everyone[fe.NUMERIC_FEATURES].mean().to_numpy())


def test_preprocessed_test_matrix_is_complete_and_readable(model_data):
    _, (X_train, X_test, _, _) = model_data
    matrix = fe.build_preprocessor().fit(X_train).transform(X_test)
    assert matrix.notna().all().all()
    assert len(matrix) == len(X_test)
    # Una columna por numérica y binaria + (categorías − 1) por cada categórica.
    expected = (
        len(fe.NUMERIC_FEATURES) + 1 + len(fe.BINARY_FEATURES)
        + sum(len(categories) - 1 for categories in fe.CATEGORICAL_FEATURES.values())
    )
    assert matrix.shape[1] == expected
    assert "contract_type_Two year" in matrix.columns
