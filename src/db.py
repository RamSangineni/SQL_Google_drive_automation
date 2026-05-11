from __future__ import annotations

import logging

import pandas as pd
import pyodbc
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import Config

log = logging.getLogger(__name__)

# Prefer newest driver available; fall back to older ones.
PREFERRED_DRIVERS = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
)


def _pick_driver() -> str:
    available = pyodbc.drivers()
    for name in PREFERRED_DRIVERS:
        if name in available:
            return name
    raise RuntimeError(
        "No supported Microsoft SQL Server ODBC driver found. "
        f"Available drivers: {available}. "
        "Install ODBC Driver 18 from "
        "https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server"
    )


def _connection_string(cfg: Config) -> str:
    driver = _pick_driver()
    log.info("Using ODBC driver: %s", driver)
    return (
        f"Driver={{{driver}}};"
        f"Server=tcp:{cfg.db_server},1433;"
        f"Database={cfg.db_name};"
        f"Uid={cfg.db_user};"
        f"Pwd={cfg.db_password};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    retry=retry_if_exception_type((pyodbc.OperationalError, pyodbc.InterfaceError)),
)
def get_connection(cfg: Config) -> pyodbc.Connection:
    log.info("Connecting to Azure SQL: %s / %s", cfg.db_server, cfg.db_name)
    return pyodbc.connect(_connection_string(cfg))


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    retry=retry_if_exception_type((pyodbc.OperationalError, pyodbc.InterfaceError)),
)
def fetch_latest_articles(
    conn: pyodbc.Connection, table: str, order_by: str, limit: int
) -> pd.DataFrame:
    # Identifiers (table/column) are validated upstream via _safe_identifier;
    # the row-limit is parameterized.
    query = f"SELECT TOP (?) * FROM {table} ORDER BY {order_by} DESC"
    log.info("Executing: %s  (limit=%d)", query, limit)
    df = pd.read_sql(query, conn, params=[limit])
    log.info("Fetched %d rows from %s", len(df), table)
    return df
