from __future__ import annotations

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

from src import db, drive_uploader, exporter, notifier
from src.config import PROJECT_ROOT, Config

LOG_DIR = PROJECT_ROOT / "logs"
OUT_DIR = PROJECT_ROOT / "output"


def setup_logging(stamp_day: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"export_{stamp_day}.log"

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        log_path, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(stream_handler)


def main() -> int:
    now = datetime.now()
    stamp_day = now.strftime("%Y-%m-%d")
    stamp_run = now.strftime("%Y-%m-%d_%H00")
    setup_logging(stamp_day)
    log = logging.getLogger("export")

    log.info("=" * 60)
    log.info("Coal articles export run starting (%s)", stamp_run)

    out_path = OUT_DIR / f"coal_articles_{stamp_run}.xlsx"
    log_path = LOG_DIR / f"export_{stamp_day}.log"

    try:
        cfg = Config.load()

        with db.get_connection(cfg) as conn:
            df = db.fetch_latest_articles(
                conn, cfg.export_table, cfg.export_order_by, cfg.export_row_limit
            )

        if df.empty:
            log.warning("Query returned 0 rows. Uploading empty workbook anyway for audit trail.")

        exporter.to_excel(df, out_path)
        file_id = drive_uploader.upload(
            out_path,
            cfg.gdrive_folder_id,
            cfg.gdrive_oauth_client_secret_path,
            cfg.gdrive_oauth_token_path,
        )

        log.info("Run succeeded. Drive file_id=%s", file_id)
        return 0

    except Exception as e:
        log.exception("Run failed")
        try:
            cfg = Config.load()
            if cfg.email_enabled:
                notifier.send_failure_email(
                    cfg=cfg,
                    subject=f"[FAIL] Coal articles export {stamp_run}",
                    body=(
                        f"The scheduled export failed.\n\n"
                        f"Run timestamp: {stamp_run}\n"
                        f"Error type: {type(e).__name__}\n"
                        f"Error: {e!r}\n\n"
                        f"See attached log for full traceback.\n"
                    ),
                    error_signature=type(e).__name__,
                    attachment_path=log_path,
                )
            else:
                log.warning(
                    "Email alerts disabled (SMTP_* not configured in .env). "
                    "Failure recorded in log only: %s",
                    log_path,
                )
        except Exception:
            log.exception("Also failed to dispatch alert")
        return 1


if __name__ == "__main__":
    sys.exit(main())
