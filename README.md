# Azure SQL → Google Drive Hourly Export

A small Python automation that, every 6 hours (00:00 / 06:00 / 12:00 / 18:00 local time), pulls the **last N rows** of a configurable table from Azure SQL Database, writes them to a timestamped Excel workbook, and uploads the file to a Google Drive folder. Failures are recorded to a daily log file (optional Gmail SMTP alerts can be turned on with one env var).

Originally built for a "coking coal articles" use case (`coal_articles` table, 100 rows, `ORDER BY id DESC`) — fully parameterizable via `.env`.

---

## 🚀 Quick Start (~15 min, for someone who just cloned)

> Prerequisites: **Python 3.10+**, **Windows 10/11**, an Azure SQL DB you can connect to, and a Google account.

### 1. Install — 2 min
```cmd
git clone https://github.com/RamSangineni/SQL_Google_drive_automation.git
cd SQL_Google_drive_automation
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Check ODBC driver — 30 sec
```cmd
python -c "import pyodbc; print(pyodbc.drivers())"
```
The output must list **"ODBC Driver 17 for SQL Server"** or **"ODBC Driver 18 for SQL Server"**.
If neither is there → install from https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server

### 3. Google Cloud setup — 5 min ⚠️ Two non-obvious gotchas, read carefully

**3a.** Create a project: https://console.cloud.google.com/projectcreate → any name → **Create**. **Dismiss** the "$300 free trial" banner (you don't need billing).

**3b.** Enable Drive API: https://console.cloud.google.com/apis/library/drive.googleapis.com → **Enable**.

**3c.** Configure OAuth consent screen: https://console.cloud.google.com/auth/overview
- User type: **External**
- App name: anything (e.g. `drive-export`)
- Support email + developer email: your email
- Save → ⚠️ **click PUBLISH APP → CONFIRM** ← *don't skip this — Testing mode breaks the script after 7 days*

**3d.** Create OAuth Client ID: https://console.cloud.google.com/apis/credentials
- + Create Credentials → **OAuth client ID**
- Application type: **Desktop app** ← *NOT Web application — service accounts and Web app types do not work for personal Gmail*
- Create → **DOWNLOAD JSON** from the popup
- Save the file as `credentials/oauth_client_secret.json` inside this project folder

### 4. Drive folder — 30 sec
- Create a new folder in https://drive.google.com (any name)
- Open the folder; copy the long ID from the URL: `drive.google.com/drive/folders/<ID>` — the `<ID>` part

### 5. Fill `.env` — 2 min
```cmd
copy .env.example .env
notepad .env
```
Set these values, save, close:

- `DB_SERVER` — your Azure SQL server (e.g. `your-server.database.windows.net`)
- `DB_NAME` — your database name
- `DB_USER` — your Azure SQL username
- `DB_PASSWORD` — your Azure SQL password
- `GDRIVE_FOLDER_ID` — the folder ID from step 4
- `EXPORT_TABLE` — your table name (default: `coal_articles`)
- `EXPORT_ORDER_BY` — column to sort DESC by, must exist on your table (default: `id`)
- `EXPORT_ROW_LIMIT` — how many rows per run (default: `100`)

### 6. First run — authorize Google once — 1 min
```cmd
python -u -m src.main
```
- An auth URL prints in the console. **Copy it**, paste in your browser
- Sign in with the Google account that owns the Drive folder from step 4
- On "Google hasn't verified this app" → **Advanced** → **Go to (unsafe)** → **Continue** → **Allow**
- Console finishes uploading; check your Drive folder — there's a new `.xlsx` file ✅
- The OAuth refresh token is now saved to `credentials/oauth_token.json` — **no browser ever again**

### 7. Schedule every-6-hours — 1 min
Right-click **PowerShell** → **Run as Administrator**:
```powershell
cd path\to\SQL_Google_drive_automation
.\scripts\register_task.ps1
```
Verify it works:
```powershell
Start-ScheduledTask -TaskName CokingCoalExport
Get-ScheduledTask -TaskName CokingCoalExport | Get-ScheduledTaskInfo
```
`LastTaskResult: 0` = success. Job now fires at 00:00, 06:00, 12:00, 18:00 daily.

---

### Common errors

**`storageQuotaExceeded` from Google Drive**
You created a Service Account in step 3d instead of an OAuth Desktop client. Personal Gmail accounts can't use Service Accounts (they have no Drive quota). Redo step 3d and choose **Desktop app** as the Application type.

**`Access blocked: app has not completed verification`**
Your OAuth consent screen is still in Testing mode. Go back to step 3c and click **PUBLISH APP → CONFIRM**.

**`Login failed for user` from SQL**
Wrong DB credentials, or Azure SQL firewall is blocking your IP. Open Azure portal → SQL Server → Networking → click **Add client IP** → save.

**`ImportError: DLL load failed while importing pyodbc`**
The ODBC driver isn't installed. Redo step 2.

**Browser shows `localhost refused to connect` after clicking Allow**
Already mitigated in the code — it binds to `127.0.0.1:8765`. If you still see this, your antivirus or firewall is blocking that port. Whitelist Python or try a different port by editing `src/drive_uploader.py`.

---

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
