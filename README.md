# Azure SQL → Google Drive Hourly Export

A small Python automation that, every 6 hours (00:00 / 06:00 / 12:00 / 18:00 local time), pulls the **last N rows** of a configurable table from Azure SQL Database, writes them to a timestamped Excel workbook, and uploads the file to a Google Drive folder. Failures are recorded to a daily log file (optional Gmail SMTP alerts can be turned on with one env var).

Originally built for a "coking coal articles" use case (`coal_articles` table, 100 rows, `ORDER BY id DESC`) — fully parameterizable via `.env`.

## Architecture

```
┌──────────────────┐      ┌─────────────────────┐      ┌────────────────────┐
│ Task Scheduler   │─6h──▶│ scripts/            │─────▶│  python -m src.main│
│ (00/06/12/18)    │      │ run_export.bat      │      │                    │
└──────────────────┘      └─────────────────────┘      └─────────┬──────────┘
                                                                 │
              ┌──────────────────────────────────────────────────┼──────────────────────────────────────────────┐
              ▼                                                  ▼                                              ▼
      ┌───────────────┐                                  ┌───────────────┐                              ┌───────────────┐
      │  Azure SQL    │  pyodbc, TOP N ORDER BY x DESC   │  pandas →     │   OAuth (drive.file scope)   │ Google Drive  │
      │  (your DB)    │ ──────────────────────────────▶ │   openpyxl →  │ ─────────────────────────▶  │ (your folder) │
      └───────────────┘                                  │   .xlsx       │                              └───────────────┘
                                                         └───────────────┘
```

## What's in the repo

```
.
├── .env.example                # Copy to .env, fill in real values (.env is gitignored)
├── .gitignore
├── README.md
├── requirements.txt            # Pinned Python deps
├── src/
│   ├── config.py               # Loads + validates env vars
│   ├── db.py                   # Azure SQL connection + query
│   ├── exporter.py             # DataFrame → formatted .xlsx
│   ├── drive_uploader.py       # OAuth user-credentials Drive upload
│   ├── notifier.py             # Optional SMTP failure-email alerts
│   └── main.py                 # Orchestrator (entry point)
└── scripts/
    ├── run_export.bat          # Windows Task Scheduler invokes this
    └── register_task.ps1       # One-time PowerShell to register the schedule
```

## Setup

### 1. Clone and install deps

```cmd
git clone https://github.com/<you>/<this-repo>.git
cd <this-repo>
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Install the SQL Server ODBC driver

`pyodbc` needs an OS-level driver. The code auto-detects either ODBC Driver 17 or 18 for SQL Server.

- Download from https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server
- Or check if one is already installed: `python -c "import pyodbc; print(pyodbc.drivers())"`

### 3. Set up Google OAuth (Desktop app, not Service Account)

> ⚠️ **For personal Gmail accounts, you must use OAuth user credentials — not a Service Account.** Google does not give service accounts any Drive storage quota, so uploads will fail with `storageQuotaExceeded` unless the destination is a Workspace Shared Drive. OAuth user creds work for personal `@gmail.com` users.

a. **Create a Google Cloud project** at https://console.cloud.google.com/projectcreate (no billing required).

b. **Enable the Drive API**: open https://console.cloud.google.com/apis/library/drive.googleapis.com → **Enable**.

c. **Configure the OAuth consent screen**: https://console.cloud.google.com/auth/overview
   - User type: **External**
   - App name: anything (e.g., `coal-export`)
   - Support email + developer email: your Google address
   - Skip scopes (we use the non-sensitive `drive.file` scope which doesn't need to be listed)
   - Click **PUBLISH APP** → CONFIRM. (Publishing without verification is allowed because `drive.file` is non-sensitive.)

d. **Create an OAuth Client ID**: https://console.cloud.google.com/apis/credentials → **+ Create Credentials** → **OAuth client ID**
   - Application type: **Desktop app**
   - Name: anything
   - Click **Create** → **DOWNLOAD JSON** from the popup
   - Save the file as `credentials/oauth_client_secret.json` in this project

### 4. Set up the destination Drive folder

- Create a folder in your personal Drive (any name)
- Open the folder, copy the ID from the URL: `https://drive.google.com/drive/folders/<FOLDER_ID>`
- Put it in `.env` as `GDRIVE_FOLDER_ID`

### 5. Configure `.env`

```cmd
copy .env.example .env
```

Then edit `.env` and fill in:
- `DB_SERVER`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` — Azure SQL connection
- `GDRIVE_FOLDER_ID` — from step 4
- `EXPORT_TABLE`, `EXPORT_ORDER_BY`, `EXPORT_ROW_LIMIT` — what to export (defaults: `coal_articles`, `id`, `100`)
- (Optional) `SMTP_*` keys for failure-email alerts — leave empty to disable

### 6. First run — authorize Google access (one time)

```cmd
.venv\Scripts\activate
python -u -m src.main
```

The first run will print an OAuth URL. Copy it into a browser, sign in with your Google account, click through the "unverified app" warning (Advanced → Continue → Allow), then the script finishes the upload. The refresh token is saved to `credentials/oauth_token.json` and all future runs work without a browser.

You should see `coal_articles_<date>_<hour>00.xlsx` appear in your Drive folder.

### 7. Schedule the every-6-hours job (Windows Task Scheduler)

Open **PowerShell as Administrator** and run:

```powershell
cd <path-to-this-repo>
.\scripts\register_task.ps1
```

This registers a task named **`CokingCoalExport`** that fires at 00:00, 06:00, 12:00, 18:00 daily. The task uses `S4U` logon (runs even when you're logged off) and `WakeToRun` (wakes a sleeping PC).

**Verify:**
```powershell
Start-ScheduledTask -TaskName CokingCoalExport
Get-ScheduledTask -TaskName CokingCoalExport | Get-ScheduledTaskInfo
```
`LastTaskResult: 0` means the manual fire succeeded.

## Operations

| Action | Command |
|---|---|
| Run on demand | `python -m src.main` (with venv active) |
| Force-trigger scheduled task | `Start-ScheduledTask -TaskName CokingCoalExport` |
| View today's log | open `logs\export_<YYYY-MM-DD>.log` |
| Disable temporarily | `Disable-ScheduledTask -TaskName CokingCoalExport` |
| Delete entirely | `Unregister-ScheduledTask -TaskName CokingCoalExport -Confirm:$false` |
| Change cadence | Edit `scripts\register_task.ps1` and re-run as Admin |

## Troubleshooting

**`ImportError: DLL load failed while importing pyodbc`** → ODBC driver not installed (step 2).

**`Login failed for user`** → Wrong DB creds OR Azure SQL firewall blocking your IP. In Azure Portal → SQL Server → Networking → Add client IP.

**`HttpError 403: storageQuotaExceeded`** → You used a Service Account on personal Gmail. Re-do step 3 with an OAuth Desktop client.

**`Access blocked: app has not completed verification`** → OAuth consent screen still in Testing mode. Step 3c: click **PUBLISH APP**.

**`localhost refused to connect` during OAuth callback** → IPv4/IPv6 mismatch. Already mitigated in `src/drive_uploader.py` by binding to `127.0.0.1` explicitly.

**Scheduled task `LastTaskResult: 0x1`** → Script ran but exited non-zero. Check the day's log file for the traceback.

## Security notes

- `.env`, `credentials/`, `logs/`, `output/` are all gitignored — secrets never leave your machine
- The OAuth client secret JSON is also a secret; keep it in `credentials/`
- The `drive.file` scope is the minimum-privilege scope: the app can only see files it created, not your entire Drive
