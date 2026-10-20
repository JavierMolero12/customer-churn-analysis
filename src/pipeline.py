"""Ejecuta el pipeline de datos completo, de principio a fin.

    descarga -> base de datos raw -> limpieza -> tabla customer_features (SQL) -> CSV

Uso: python -m src.pipeline
"""

from contextlib import closing
from pathlib import Path

import pandas as pd

from src import config
from src.build_database import build_database
from src.data_cleaning import clean_database
from src.database import get_connection, query, run_sql_script
from src.download_data import download_dataset


def build_customer_features(
    db_path: Path = config.DB_PATH,
    csv_path: Path = config.FEATURES_CSV_PATH,
) -> pd.DataFrame:
    """Ejecuta sql/02_customer_features.sql y exporta la tabla a data/processed/."""
    with closing(get_connection(db_path)) as conn:
        run_sql_script(conn, "02_customer_features.sql")
        features = query(conn, "SELECT * FROM customer_features")

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(csv_path, index=False)
    print(
        f"customer_features: {len(features):,} clientes x {features.shape[1]} columnas "
        f"-> {config.relative_to_project(csv_path)}"
    )
    return features


def run_pipeline() -> pd.DataFrame:
    download_dataset()
    build_database()
    clean_database()
    return build_customer_features()


if __name__ == "__main__":
    run_pipeline()
