from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _require(key: str) -> str:
    val = os.getenv(key, "").strip().strip('"').strip("'")
    if not val:
        raise RuntimeError(
            f"Missing required env var: {key}. "
            f"Edit {PROJECT_ROOT / '.env'} and set it (see .env.example)."
        )
    return val


def _optional(key: str, default: str) -> str:
    val = os.getenv(key, "").strip().strip('"').strip("'")
    return val or default


def _safe_identifier(name: str, kind: str) -> str:
    if not _IDENT_RE.match(name):
        raise ValueError(f"Unsafe {kind} name (must match {_IDENT_RE.pattern}): {name!r}")
    return name


@dataclass(frozen=True)
class Config:
    # Azure SQL
    db_server: str
    db_name: str
    db_user: str
    db_password: str

    # Google Drive (OAuth user credentials — service accounts blocked on personal Gmail)
    gdrive_folder_id: str
    gdrive_oauth_client_secret_path: Path
    gdrive_oauth_token_path: Path

    # SMTP alerting (all optional — if any is empty, email alerts are disabled)
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_app_password: str
    alert_email: str

    # Export config
    export_table: str
    export_order_by: str
    export_row_limit: int

    @property
    def email_enabled(self) -> bool:
        return all([self.smtp_host, self.smtp_user, self.smtp_app_password, self.alert_email])

    @classmethod
    def load(cls) -> "Config":
        load_dotenv(PROJECT_ROOT / ".env", override=False)

        def _abs(p: str) -> Path:
            path = Path(p)
            return path if path.is_absolute() else PROJECT_ROOT / path

        client_secret_path = _abs(_require("GDRIVE_OAUTH_CLIENT_SECRET_PATH"))
        token_path = _abs(_optional("GDRIVE_OAUTH_TOKEN_PATH", "credentials/oauth_token.json"))

        return cls(
            db_server=_require("DB_SERVER"),
            db_name=_require("DB_NAME"),
            db_user=_require("DB_USER"),
            db_password=_require("DB_PASSWORD"),
            gdrive_folder_id=_require("GDRIVE_FOLDER_ID"),
            gdrive_oauth_client_secret_path=client_secret_path,
            gdrive_oauth_token_path=token_path,
            smtp_host=_optional("SMTP_HOST", ""),
            smtp_port=int(_optional("SMTP_PORT", "587")),
            smtp_user=_optional("SMTP_USER", ""),
            smtp_app_password=_optional("SMTP_APP_PASSWORD", ""),
            alert_email=_optional("ALERT_EMAIL", ""),
            export_table=_safe_identifier(_optional("EXPORT_TABLE", "coal_articles"), "table"),
            export_order_by=_safe_identifier(_optional("EXPORT_ORDER_BY", "id"), "column"),
            export_row_limit=int(_optional("EXPORT_ROW_LIMIT", "100")),
        )
