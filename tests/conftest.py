"""Fixtures compartidas: el CSV original y sus tablas normalizadas."""

import pandas as pd
import pytest

from src.build_database import load_source_csv, normalize
from src.download_data import download_dataset


@pytest.fixture(scope="session")
def source() -> pd.DataFrame:
    """CSV original de IBM (se descarga si no está, verificando el SHA-256)."""
    return load_source_csv(download_dataset())


@pytest.fixture(scope="session")
def normalized(source) -> dict[str, pd.DataFrame]:
    return normalize(source)
