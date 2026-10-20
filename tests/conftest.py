"""Fixtures compartidas: el CSV original, sus tablas normalizadas y una base de datos de prueba."""

from contextlib import closing

import pandas as pd
import pytest

from src.build_database import build_database, load_source_csv, normalize
from src.data_cleaning import clean_database
from src.database import get_connection
from src.download_data import download_dataset


@pytest.fixture(scope="session")
def source() -> pd.DataFrame:
    """CSV original de IBM (se descarga si no está, verificando el SHA-256)."""
    return load_source_csv(download_dataset())


@pytest.fixture(scope="session")
def normalized(source) -> dict[str, pd.DataFrame]:
    return normalize(source)


@pytest.fixture(scope="session")
def test_db(tmp_path_factory, source):
    """Base de datos construida y limpiada desde cero en una carpeta temporal.

    Devuelve (conexión, manifiesto de defectos). No toca data/churn.db.
    """
    folder = tmp_path_factory.mktemp("db")
    csv_path = download_dataset()
    manifest = build_database(csv_path, folder / "churn.db", folder / "injected_defects.csv")
    clean_database(folder / "churn.db")
    with closing(get_connection(folder / "churn.db")) as conn:
        yield conn, manifest
