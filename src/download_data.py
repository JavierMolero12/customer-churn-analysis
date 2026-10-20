"""Descarga el CSV de IBM Telco Customer Churn y verifica su integridad con SHA-256.

Uso: python -m src.download_data
"""

import hashlib
import urllib.request
from pathlib import Path

from src.config import DATASET_SHA256, DATASET_URL, RAW_CSV_PATH


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def download_dataset(
    dest: Path = RAW_CSV_PATH,
    url: str = DATASET_URL,
    expected_sha256: str = DATASET_SHA256,
) -> Path:
    """Descarga el fichero si no existe ya una copia válida. Falla si el hash no coincide."""
    dest = Path(dest)
    if dest.exists() and sha256_of(dest) == expected_sha256:
        print(f"Dataset ya descargado y verificado: {dest}")
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(".part")
    urllib.request.urlretrieve(url, partial)

    actual_sha256 = sha256_of(partial)
    if actual_sha256 != expected_sha256:
        partial.unlink()
        raise ValueError(
            f"SHA-256 inesperado ({actual_sha256}): el fichero descargado no es el esperado."
        )
    partial.replace(dest)
    print(f"Dataset descargado y verificado: {dest}")
    return dest


if __name__ == "__main__":
    download_dataset()
