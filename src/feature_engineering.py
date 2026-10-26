"""Feature engineering (Fase 4): variables extra, selección y preprocesado sin leakage.

    customer_features (SQL) -> add_model_features -> split_train_test -> build_preprocessor

Reglas de diseño:
- Las variables que se añaden aquí son deterministas (no aprenden nada de los datos), así que
  se pueden calcular antes de dividir sin fuga de información.
- Todo lo que aprende de los datos (escalado, codificación, imputación) va dentro de un
  ColumnTransformer que solo se ajusta con train (diseño §4, L4).
- Cada variable que NO entra en el modelo tiene su motivo escrito en EXCLUDED_FEATURES.
  Las redundancias (R5) se midieron solo con train: ver `collinearity_report`.

Uso: python -m src.feature_engineering
"""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src import config

ID_COLUMN = "customer_id"
TARGET = "churn"

# Columnas que nunca pueden ser variables del modelo (diseño §4: L1, L2 y L6).
FORBIDDEN_FEATURES = {ID_COLUMN, TARGET, "end_date", "start_date", "signup_date"}

NUMERIC_FEATURES = ["tenure_months", "monthly_charges"]
# Sin meses anteriores (tenure < 2) no hay cambio de precio que medir: se imputa 1,0 ("sin
# cambio") y `has_price_history` marca esas filas para que el modelo las distinga.
PRICE_RATIO_FEATURE = "price_change_ratio"
BINARY_FEATURES = [
    "has_partner",
    "has_dependents",
    "is_paperless",
    "has_phone_service",
    "has_multiple_lines",
    *[f"has_{service}" for service in config.ADDON_SERVICES],
    "has_price_history",
]
# Orden fijo de categorías: la primera es la referencia (drop="first"), así cada coeficiente
# de la logística se lee "frente a contrato mensual", "frente a DSL", etc.
CATEGORICAL_FEATURES = {
    "contract_type": config.CONTRACT_TYPES,
    "internet_service": config.INTERNET_SERVICES,
    "payment_method": config.PAYMENT_METHODS,
    "tenure_bucket": config.TENURE_BUCKETS,
}
# Atributos sensibles (diseño H8 y diccionario de datos). Fuera por defecto: no son una palanca
# de negocio y decidir a quién se ofrece una retención por sexo o edad puede discriminar.
# La Fase 5 puede medir con include_sensitive=True cuánto rendimiento cuesta excluirlos.
SENSITIVE_FEATURES = ["is_male", "is_senior"]

EXCLUDED_FEATURES = {
    ID_COLUMN: "Identificador: no describe al cliente (L6).",
    TARGET: "Variable objetivo.",
    "is_male": "Atributo sensible (H8): excluido por principio.",
    "is_senior": "Atributo sensible (edad): excluido por principio.",
    "n_payments": "Idéntica a tenure_months (un pago por mes facturado).",
    "total_revenue": "Casi igual a tenure_months × monthly_charges (r = 0,9996 en train): redundante (R5).",
    "avg_historical_charge": "Casi igual a monthly_charges (r = 0,992, VIF de 200 en train): se usa vía price_change_ratio.",
    "n_services": "Suma exacta de los indicadores has_*: se usan los indicadores.",
    "n_addon_services": "Suma exacta de los 6 indicadores de servicios adicionales.",
    "is_auto_payment": "Se deduce de payment_method, que entra con sus 4 categorías.",
}


# ---------------------------------------------------------------- variables nuevas


def add_model_features(features: pd.DataFrame) -> pd.DataFrame:
    """Añade las variables deterministas de la Fase 4 a la tabla customer_features.

    - `tenure_bucket`: tramos de antigüedad del diseño, para que un modelo lineal capte que el
      riesgo cae sobre todo en el primer año.
    - `has_price_history`: 1 si el cliente tiene meses anteriores (tenure >= 2) y, por tanto,
      `price_change_ratio` es un valor observado y no imputado.
    """
    out = features.copy()
    tenure = out["tenure_months"]
    if tenure.isna().any() or not tenure.between(0, config.TENURE_BUCKET_EDGES[-1]).all():
        raise ValueError("tenure_months fuera del rango 0–72: revisa la tabla customer_features.")

    out["tenure_bucket"] = pd.cut(
        tenure,
        bins=config.TENURE_BUCKET_EDGES,
        labels=config.TENURE_BUCKETS,
        include_lowest=True,
    ).astype(str)
    out["has_price_history"] = (tenure >= 2).astype(int)
    return out


# ---------------------------------------------------------------- selección de variables


def model_feature_columns(include_sensitive: bool = False) -> list[str]:
    """Columnas que entran en el preprocesado, en el orden del ColumnTransformer."""
    columns = [
        *NUMERIC_FEATURES,
        PRICE_RATIO_FEATURE,
        *BINARY_FEATURES,
        *(SENSITIVE_FEATURES if include_sensitive else []),
        *CATEGORICAL_FEATURES,
    ]
    check_no_leakage(columns)
    return columns


def check_no_leakage(columns: list[str]) -> None:
    """Detiene el proceso si una columna prohibida (identificador, objetivo o fechas) se cuela."""
    leaked = sorted(set(columns) & FORBIDDEN_FEATURES)
    if leaked:
        raise ValueError(f"Columnas con riesgo de leakage en las variables del modelo: {leaked}")


# ---------------------------------------------------------------- división train / test


def split_train_test(
    features: pd.DataFrame, include_sensitive: bool = False
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Divide 80/20 estratificado por churn, con la semilla del proyecto.

    Antes comprueba que no hay clientes repetidos: un duplicado repartido entre train y test
    haría que el modelo se evaluara con clientes que ya vio (L6). El índice es customer_id.
    """
    if not features[ID_COLUMN].is_unique:
        raise ValueError("customer_id repetido: deduplica antes de dividir (L6).")

    data = features.set_index(ID_COLUMN)
    X = data[model_feature_columns(include_sensitive)]
    y = data[TARGET]
    return train_test_split(
        X, y, test_size=config.TEST_SIZE, stratify=y, random_state=config.RANDOM_SEED
    )


# ---------------------------------------------------------------- preprocesado


def build_preprocessor(include_sensitive: bool = False) -> ColumnTransformer:
    """ColumnTransformer sin ajustar: se ajusta dentro del Pipeline del modelo, solo con train.

    - Numéricas: StandardScaler (la logística necesita escalas comparables).
    - price_change_ratio: imputación constante 1,0 (no aprende nada de los datos) + escalado.
    - Binarias 0/1: tal cual, para que sus coeficientes se lean directamente.
    - Categóricas: one-hot con categorías fijas; una categoría desconocida es un error de datos
      aguas arriba, así que el encoder falla en vez de ignorarla.
    """
    binary = BINARY_FEATURES + (SENSITIVE_FEATURES if include_sensitive else [])
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", StandardScaler(), NUMERIC_FEATURES),
            (
                "price_ratio",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="constant", fill_value=1.0)),
                        ("scale", StandardScaler()),
                    ]
                ),
                [PRICE_RATIO_FEATURE],
            ),
            ("binary", "passthrough", binary),
            (
                "categorical",
                OneHotEncoder(
                    categories=list(CATEGORICAL_FEATURES.values()),
                    drop="first",
                    handle_unknown="error",
                    sparse_output=False,
                ),
                list(CATEGORICAL_FEATURES),
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
    return preprocessor.set_output(transform="pandas")


# ---------------------------------------------------------------- evidencia de la selección


def variance_inflation_factors(X: pd.DataFrame) -> pd.Series:
    """VIF de cada columna: 1 / (1 − R²) al explicarla con las demás. > 10 = muy redundante."""
    standardized = (X - X.mean()) / X.std()
    vif = {}
    for column in standardized.columns:
        y = standardized[column].to_numpy()
        others = standardized.drop(columns=column).to_numpy()
        A = np.column_stack([np.ones(len(standardized)), others])
        beta, *_ = np.linalg.lstsq(A, y, rcond=None)
        r2 = 1 - ((y - A @ beta) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        vif[column] = np.inf if r2 >= 1 else 1 / (1 - r2)
    return pd.Series(vif, name="vif")


def collinearity_report(train_features: pd.DataFrame) -> pd.DataFrame:
    """VIF de las numéricas candidatas antes y después de la selección, SOLO con train (L5).

    Se usan los clientes con historial (tenure >= 2) porque price_change_ratio no existe sin él.
    """
    with_history = train_features[train_features["tenure_months"] >= 2]
    candidates = ["tenure_months", "monthly_charges", "total_revenue", "avg_historical_charge", PRICE_RATIO_FEATURE]
    selected = [*NUMERIC_FEATURES, PRICE_RATIO_FEATURE]
    return pd.DataFrame(
        {
            "vif_candidates": variance_inflation_factors(with_history[candidates]),
            "vif_selected": variance_inflation_factors(with_history[selected]),
        }
    ).round(1)


# ---------------------------------------------------------------- ejecución


def main() -> None:
    if not config.FEATURES_CSV_PATH.exists():
        raise SystemExit("No existe customer_features.csv: ejecuta antes `python -m src.pipeline`.")

    features = add_model_features(pd.read_csv(config.FEATURES_CSV_PATH))
    X_train, X_test, y_train, y_test = split_train_test(features)
    preprocessor = build_preprocessor().fit(X_train)
    train_matrix = preprocessor.transform(X_train)
    test_matrix = preprocessor.transform(X_test)

    print(f"train: {len(X_train):,} clientes, churn {y_train.mean():.1%}")
    print(f"test:  {len(X_test):,} clientes, churn {y_test.mean():.1%}")
    print(
        f"variables: {len(model_feature_columns())} columnas de entrada -> "
        f"{train_matrix.shape[1]} tras el preprocesado; NaN en test: {int(test_matrix.isna().sum().sum())}"
    )
    print("\nExcluidas del modelo:")
    for column, reason in EXCLUDED_FEATURES.items():
        print(f"  - {column}: {reason}")

    train_rows = features.set_index(ID_COLUMN).loc[X_train.index].reset_index()
    print("\nColinealidad en train (clientes con tenure >= 2):")
    print(collinearity_report(train_rows).to_string())


if __name__ == "__main__":
    main()
