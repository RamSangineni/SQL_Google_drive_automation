from __future__ import annotations

import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

# drive.file: per-file access — non-sensitive scope, no Google verification required.
# Lets the app create files in any folder the user can access, manage files it created.
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _load_or_create_credentials(client_secret_path: Path, token_path: Path) -> Credentials:
    creds: Credentials | None = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        log.info("Refreshing expired OAuth token...")
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    # No token, or token unusable -> interactive browser flow (first-time setup)
    if not client_secret_path.exists():
        raise FileNotFoundError(
            f"OAuth client secret not found: {client_secret_path}.\n"
            "Create one at https://console.cloud.google.com/apis/credentials\n"
            "  -> + Create Credentials -> OAuth client ID -> Desktop application\n"
            "Download the JSON and save it to the path above."
        )

    import sys as _sys
    print("\n" + "=" * 70, flush=True)
    print("ONE-TIME GOOGLE DRIVE AUTHORIZATION REQUIRED", flush=True)
    print("=" * 70, flush=True)
    print("A URL will appear below. Copy it, paste it into your browser,", flush=True)
    print("sign in as ramsangineni@gmail.com, and click Allow.", flush=True)
    print("=" * 70 + "\n", flush=True)
    _sys.stdout.flush()

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
    creds = flow.run_local_server(
        host="127.0.0.1",  # avoid Windows localhost->IPv6 / IPv4 mismatch
        port=8765,         # fixed port so user knows what to expect
        prompt="consent",
        access_type="offline",
        open_browser=False,
        authorization_prompt_message="\n>>> COPY THIS URL INTO YOUR BROWSER:\n\n    {url}\n",
        success_message="Authorization complete. You may close this browser tab and return to the script.",
    )
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    log.info("OAuth token saved to %s", token_path)
    return creds


def _build_service(client_secret_path: Path, token_path: Path):
    creds = _load_or_create_credentials(Path(client_secret_path), Path(token_path))
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, HttpError):
        return exc.resp.status in (429, 500, 502, 503, 504)
    return isinstance(exc, (TimeoutError, ConnectionError))


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((HttpError, TimeoutError, ConnectionError)),
)
def upload(
    local_path: Path,
    drive_folder_id: str,
    client_secret_path: Path,
    token_path: Path,
) -> str:
    local_path = Path(local_path)
    if not local_path.exists():
        raise FileNotFoundError(f"File to upload does not exist: {local_path}")

    service = _build_service(client_secret_path, token_path)
    metadata = {"name": local_path.name, "parents": [drive_folder_id]}
    media = MediaFileUpload(str(local_path), mimetype=XLSX_MIME, resumable=True)

    log.info("Uploading %s to Drive folder %s ...", local_path.name, drive_folder_id)
    try:
        created = (
            service.files()
            .create(body=metadata, media_body=media, fields="id,name,webViewLink")
            .execute()
        )
    except HttpError as e:
        if not _is_transient(e):
            log.error("Non-retryable Drive error %s: %s", e.resp.status, e)
        raise

    file_id = created["id"]
    log.info("Uploaded as Drive file_id=%s url=%s", file_id, created.get("webViewLink"))
    return file_id
