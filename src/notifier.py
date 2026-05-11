from __future__ import annotations

import json
import logging
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

from .config import Config, PROJECT_ROOT

log = logging.getLogger(__name__)

SUPPRESSION_WINDOW = timedelta(minutes=60)
STATE_FILE = PROJECT_ROOT / "logs" / ".last_alert.json"


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _should_suppress(error_signature: str) -> bool:
    state = _load_state()
    last = state.get(error_signature)
    if not last:
        return False
    try:
        last_sent = datetime.fromisoformat(last)
    except ValueError:
        return False
    return datetime.now() - last_sent < SUPPRESSION_WINDOW


def _record_sent(error_signature: str) -> None:
    state = _load_state()
    state[error_signature] = datetime.now().isoformat(timespec="seconds")
    _save_state(state)


def send_failure_email(
    cfg: Config,
    subject: str,
    body: str,
    error_signature: str,
    attachment_path: Path | None = None,
) -> bool:
    if _should_suppress(error_signature):
        log.warning(
            "Email suppressed (same error '%s' alerted within last %d min)",
            error_signature,
            int(SUPPRESSION_WINDOW.total_seconds() / 60),
        )
        return False

    msg = EmailMessage()
    msg["From"] = cfg.smtp_user
    msg["To"] = cfg.alert_email
    msg["Subject"] = subject
    msg.set_content(body)

    if attachment_path and Path(attachment_path).exists():
        path = Path(attachment_path)
        msg.add_attachment(
            path.read_bytes(),
            maintype="text",
            subtype="plain",
            filename=path.name,
        )

    log.info("Sending alert email to %s ...", cfg.alert_email)
    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(cfg.smtp_user, cfg.smtp_app_password)
        smtp.send_message(msg)

    _record_sent(error_signature)
    log.info("Alert email sent.")
    return True
