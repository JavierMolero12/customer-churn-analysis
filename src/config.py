"""Configuración central: rutas, origen de los datos, fecha de corte y semilla.

Todo lo que se repetiría en varios scripts o notebooks vive aquí, en un único sitio.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SQL_DIR = PROJECT_ROOT / "sql"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures"

DB_PATH = DATA_DIR / "churn.db"
RAW_CSV_PATH = RAW_DIR / "Telco-Customer-Churn.csv"
DEFECTS_MANIFEST_PATH = RAW_DIR / "injected_defects.csv"
FEATURES_CSV_PATH = PROCESSED_DIR / "customer_features.csv"

# Fichero fijado a un commit concreto del repositorio de IBM (Apache 2.0) para que la descarga
# sea siempre idéntica. El hash permite detectar cualquier cambio o corrupción.
DATASET_URL = (
    "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/"
    "1fd6fd70906479be1712e64cfc0ea89f58466629/data/Telco-Customer-Churn.csv"
)
DATASET_SHA256 = "16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91"

# Suposición documentada (diseño §3.3): el dataset no trae fechas.
SNAPSHOT_DATE = "2024-10-01"

RANDOM_SEED = 42

# Servicios del CSV original -> nombre en la tabla `services`.
SERVICE_COLUMNS = {
    "PhoneService": "phone_service",
    "MultipleLines": "multiple_lines",
    "OnlineSecurity": "online_security",
    "OnlineBackup": "online_backup",
    "DeviceProtection": "device_protection",
    "TechSupport": "tech_support",
    "StreamingTV": "streaming_tv",
    "StreamingMovies": "streaming_movies",
}
ADDON_SERVICES = [
    "online_security",
    "online_backup",
    "device_protection",
    "tech_support",
    "streaming_tv",
    "streaming_movies",
]

CONTRACT_TYPES = ["Month-to-month", "One year", "Two year"]
PAYMENT_METHODS = [
    "Electronic check",
    "Mailed check",
    "Bank transfer (automatic)",
    "Credit card (automatic)",
]
INTERNET_SERVICES = ["DSL", "Fiber optic", "No"]

# Tramos de antigüedad fijados en el diseño (H4). Límites superiores incluidos: 0–6, 7–12…
TENURE_BUCKET_EDGES = [0, 6, 12, 24, 48, 72]
TENURE_BUCKETS = ["0-6", "7-12", "13-24", "25-48", "49-72"]

# División train/test fijada en el diseño (§6.2).
TEST_SIZE = 0.2


def relative_to_project(path: Path) -> Path:
    """Ruta relativa al proyecto para mostrar en mensajes (no expone rutas personales del equipo)."""
    path = Path(path).resolve()
    return path.relative_to(PROJECT_ROOT) if path.is_relative_to(PROJECT_ROOT) else path
