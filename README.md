# Coking Coal Articles → Google Drive Export

Every 6 hours (00:00, 06:00, 12:00, 18:00 local time), fetch the **last 100 rows** of the `coal_articles` table from Azure SQL and upload them as a timestamped `.xlsx` file to a Google Drive folder. Failures are recorded in `logs/`. (Optional: enable Gmail email alerts by filling in the `SMTP_*` keys in `.env` later.)

---

## What you need to do — one-time setup

Do these in order. Each step is independent until the test in step 7.

### 1. Install Python virtual environment + dependencies

Open **Command Prompt** (or PowerShell) in the project folder:

```cmd
cd C:\Users\0200705\Downloads\dimpu
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. ODBC Driver — already installed ✅

Your machine already has **ODBC Driver 17 for SQL Server** installed, which works fine for Azure SQL. The code auto-detects whichever driver is present and prefers newer versions if you ever install Driver 18.

(Optional upgrade later, requires admin: download Driver 18 from https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server — newer security defaults, but Driver 17 is fully functional today.)

### 3. Create a Google Cloud Service Account + Drive folder

The script logs into Google as a robot account. You need to (a) make the robot, (b) make a folder for it to write into, (c) share the folder with the robot's email.

**(a) Make the robot:**
1. Go to https://console.cloud.google.com
2. Top bar → project dropdown → **New Project** → name it `coal-export` (or reuse an existing project)
3. Left menu → **APIs & Services → Library** → search **"Google Drive API"** → click **Enable**
4. Left menu → **IAM & Admin → Service Accounts** → **+ Create Service Account**
   - Service account name: `coal-export-bot`
   - Skip the optional grant-access steps → **Done**
5. Click the new service account → **Keys** tab → **Add Key → Create new key → JSON** → **Create**
6. A `.json` file downloads. **Move/rename it to:**
   ```
   C:\Users\0200705\Downloads\dimpu\credentials\service_account.json
   ```
7. Open that JSON and copy the value of `"client_email"` — looks like
   `coal-export-bot@coal-export-xxxxx.iam.gserviceaccount.com`. You'll need it in the next step.

**(b) Make the Drive folder:**
1. Go to https://drive.google.com (signed in as **ramsangineni@gmail.com**)
2. **+ New → Folder** → name it `Coking Coal Daily Export`

**(c) Share the folder with the robot:**
1. Right-click the folder → **Share**
2. Paste the service account email from step (a)7
3. Set permission to **Editor** → uncheck "Notify people" → **Share**

**(d) Get the folder ID:**
1. Open the folder. The URL looks like:
   `https://drive.google.com/drive/folders/1A2b3C4d5E6f7G8H9iJkLmNoP`
2. The part after `/folders/` is the folder ID. Copy it.
3. Open `.env` and paste it:
   ```
   GDRIVE_FOLDER_ID="1A2b3C4d5E6f7G8H9iJkLmNoP"
   ```

### 4. (Optional, skipped for now) Email alerts

This step is **disabled by default**. Failures get written to `logs\export_<date>.log` and the script exits non-zero, but no email is sent.

To enable later: generate a Gmail App Password at https://myaccount.google.com/apppasswords (requires 2FA on your Google account), paste the 16-char password into `.env` as `SMTP_APP_PASSWORD`, and the next run will start alerting automatically — no code change needed.

### 5. Rotate exposed credentials (security hygiene)

⚠️ During plan/conversation, the contents of `.env` were visible. **Rotate these now:**

| Credential | Where to rotate |
|---|---|
| `DB_PASSWORD` (Azure SQL) | Azure portal → SQL Server `material-analysis` → Reset password. Update `.env`. |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys → revoke the old key, create a new one. Update `.env`. |
| `SPGCI_PASSWORD` | SPGCI portal → change password. Update `.env`. |

`.env` is now in `.gitignore` so future commits won't include it.

### 6. Test the export end-to-end manually

```cmd
cd C:\Users\0200705\Downloads\dimpu
.venv\Scripts\activate
python -m src.main
```

You should see:
- Console output ending with `Run succeeded. Drive file_id=...`
- A new file `output\coal_articles_<date>_<hour>00.xlsx` created locally
- The same file appearing in your Drive folder
- A new file `logs\export_<date>.log` with timestamped INFO lines

**Test the failure path** (optional but recommended):
1. Edit `.env`, temporarily change `DB_PASSWORD` to garbage
2. Run `python -m src.main` again
3. Confirm: exit code 1, traceback in `logs\export_<date>.log`. (No email — alerting is disabled until you set up SMTP per step 4.)
4. Restore `DB_PASSWORD` to the real value

### 7. Register the scheduled task

Open **PowerShell as Administrator** (right-click PowerShell → Run as Administrator):

```powershell
cd C:\Users\0200705\Downloads\dimpu
.\scripts\register_task.ps1
```

This creates a Windows Task Scheduler job named **`CokingCoalExport`** that fires at 00:00, 06:00, 12:00, 18:00 daily.

**Verify:**
```powershell
Start-ScheduledTask -TaskName CokingCoalExport      # trigger immediately
Get-ScheduledTask -TaskName CokingCoalExport | Get-ScheduledTaskInfo
```

`LastTaskResult` should be `0`. Then open **Task Scheduler** (`taskschd.msc`) → Task Scheduler Library → confirm `CokingCoalExport` is listed and shows the next run time.

---

## Project layout

```
dimpu/
├── .env                          # secrets — never commit
├── .env.example                  # safe template
├── .gitignore
├── requirements.txt
├── README.md                     # ← you are here
├── credentials/
│   └── service_account.json      # Google SA key (you place this)
├── src/
│   ├── config.py                 # env loader / validator
│   ├── db.py                     # Azure SQL fetch (TOP 100 ORDER BY id DESC)
│   ├── exporter.py               # DataFrame → .xlsx
│   ├── drive_uploader.py         # upload to Drive folder
│   ├── notifier.py               # SMTP failure alert + suppression
│   └── main.py                   # orchestrator entry point
├── scripts/
│   ├── run_export.bat            # Task Scheduler invokes this
│   └── register_task.ps1         # one-time task registration
├── output/                       # local .xlsx staging (gitignored)
└── logs/                         # daily logs + .last_alert.json (gitignored)
```

## Operations

| What | How |
|---|---|
| Run on demand | `python -m src.main` (with venv activated) |
| Force-trigger scheduled task | `Start-ScheduledTask -TaskName CokingCoalExport` |
| View today's log | `notepad logs\export_<YYYY-MM-DD>.log` |
| Disable temporarily | `Disable-ScheduledTask -TaskName CokingCoalExport` |
| Re-enable | `Enable-ScheduledTask -TaskName CokingCoalExport` |
| Delete entirely | `Unregister-ScheduledTask -TaskName CokingCoalExport -Confirm:$false` |
| Change times / cadence | Edit `scripts\register_task.ps1` and re-run as Admin |

## Common issues

**`ImportError: DLL load failed while importing pyodbc`** → ODBC Driver 18 not installed (step 2).

**`pyodbc.OperationalError: Login failed for user`** → wrong `DB_USER`/`DB_PASSWORD` in `.env`, or Azure SQL firewall blocking your machine's IP. Add your IP in Azure portal → SQL Server → Networking.

**`HttpError 403: File not found`** on Drive upload → folder ID wrong, OR you didn't share the Drive folder with the service account email. Re-do step 3(c).

**`smtplib.SMTPAuthenticationError`** → `SMTP_APP_PASSWORD` is wrong, OR you used your regular Gmail password instead of an App Password. Re-do step 4.

**Task shows `Last Run Result: 0x1`** → script ran but exited non-zero. Check `logs\export_<date>.log` for the traceback; you'll also get an email.

**Task didn't fire at scheduled time** → PC was off or asleep without `WakeToRun` permission. Check Power & Battery → Sleep settings, or just leave the PC plugged in.
