"""Acceso a SQLite: conexión, ejecución de ficheros .sql y consultas con nombre."""

import re
import sqlite3
from pathlib import Path

import pandas as pd

from src.config import DB_PATH, SQL_DIR


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Abre la base de datos con las claves foráneas activadas (SQLite las trae desactivadas)."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def run_sql_script(conn: sqlite3.Connection, filename: str) -> None:
    """Ejecuta un fichero de la carpeta sql/ que contiene varias sentencias."""
    conn.executescript((SQL_DIR / filename).read_text(encoding="utf-8"))
    conn.commit()


def load_named_queries(filename: str) -> dict[str, str]:
    """Lee un fichero .sql dividido en bloques `-- name: <nombre>` y devuelve {nombre: consulta}.

    Así cada consulta vive en SQL puro (legible y revisable en un PR) y Python solo la ejecuta.
    """
    text = (SQL_DIR / filename).read_text(encoding="utf-8")
    parts = re.split(r"^--\s*name:\s*(\w+)\s*$", text, flags=re.MULTILINE)
    # parts = [preámbulo, nombre_1, consulta_1, nombre_2, consulta_2, ...]
    return {name: sql.strip() for name, sql in zip(parts[1::2], parts[2::2])}


def query(conn: sqlite3.Connection, sql: str, params: tuple | None = None) -> pd.DataFrame:
    """Ejecuta una consulta y devuelve el resultado como DataFrame."""
    return pd.read_sql_query(sql, conn, params=params)
