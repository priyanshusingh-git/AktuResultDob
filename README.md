# AKTU Result

Standalone AKTU OneView result scraper with a premium desktop GUI built on `customtkinter`.

This folder is self-contained. It can be shared or pushed as its own GitHub repository.

---

## What It Does

- Loads an Excel sheet with `Roll No` and `DOB`
- Logs into AKTU OneView through the HTTP flow (without Selenium, meaning it is fast and lightweight)
- Fetches semester results sequentially
- Exports a formatted Excel report with visual structures identical to original results
- Stores logs and resumable checkpoint state between runs

---

## Requirements

- Python 3.10+
- Internet access to `https://oneview.aktu.ac.in`

Python packages are listed in [requirements.txt](file:///Users/priyanshu/Files/Projects/http_bot/requirements.txt).

---

## Project Layout

- [main.py](file:///Users/priyanshu/Files/Projects/http_bot/main.py): Application entrypoint
- [gui.py](file:///Users/priyanshu/Files/Projects/http_bot/gui.py): Desktop interface
- [engine.py](file:///Users/priyanshu/Files/Projects/http_bot/engine.py): Worker orchestration and scraping loop
- [client.py](file:///Users/priyanshu/Files/Projects/http_bot/client.py): AKTU HTTP session client
- [parser.py](file:///Users/priyanshu/Files/Projects/http_bot/parser.py): Result page parsing
- [runtime/](file:///Users/priyanshu/Files/Projects/http_bot/runtime): Config, logs, checkpoints, Excel export, and path helpers
- [session_caches/](file:///Users/priyanshu/Files/Projects/http_bot/session_caches): Optional bundled session cache directory

---

## How to Run (Development)

### macOS or Linux

```bash
python3 -m pip install -r requirements.txt
python3 main.py
```

Or use the launcher:
```bash
./Run_AKTU_Result_Mac.command
```

### Windows

```bat
py -m pip install -r requirements.txt
py main.py
```

Or use the launcher:
```bat
Run_AKTU_Result_Windows.bat
```

---

## How to Build Standalone Executables

### 1. Automatic Builds (GitHub Actions)
A pre-configured GitHub Actions workflow is defined in [.github/workflows/build.yml](file:///Users/priyanshu/Files/Projects/http_bot/.github/workflows/build.yml). 
- Every time you push to `main`/`master` or manually trigger the workflow from the Actions tab, it builds zipped executables for both **Windows** and **macOS**.
- If you push a tag starting with `v` (e.g. `v1.0.0`), it will automatically create a GitHub Release and attach the built packages.

### 2. Local Builds (PyInstaller)
To compile the standalone app locally on your machine:
1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Build the app using the optimized spec file:
   ```bash
   pyinstaller --noconfirm aktu_result.spec
   ```
The compiled output folder and standalone application will be generated inside the `dist/` directory.

---

## Input Format

The input Excel file must contain these columns:
- `Roll No`
- `DOB`

---

## Output and Runtime Data

- Exported reports go to `Documents/AktuBot/output`
- Logs, checkpoints, and session state go to app data by default
- The included Mac and Windows launchers set `AKTUBOT_HTTP_HOME` automatically, so logs and checkpoints stay local to the `.aktubot_http_home` directory in the shared folder

If you want to override the runtime storage location manually:
```bash
AKTUBOT_HTTP_HOME=/custom/path python3 main.py
```

---

## Troubleshooting & Security (macOS Gatekeeper)

When sharing the macOS `.app` bundle, users may see a security warning stating the app is *"from an unidentified developer"* or *"cannot be opened because Apple cannot check it for malicious software"*. This is standard macOS behavior for apps that are not signed with a paid Apple Developer account.

To run the packaged app on macOS:
1. **Right-click (or Control-click)** the `AKTU_Result.app` file and select **Open**.
2. Click **Open** in the confirmation prompt. The system will remember this choice and run the app normally going forward.
3. Alternatively, you can clear the quarantine flag manually by opening the Terminal and running:
   ```bash
   xattr -cr /path/to/AKTU_Result.app
   ```

---

## Server Hosting & API Adaptability

Because the core scraper engine (`client.py` and `parser.py`) is written in pure Python using lightweight `requests` and `BeautifulSoup` (rather than browser-based automation like Selenium or Playwright), you can easily host this bot online on a server to run headless:

1. **Web Dashboard API**: You can build a web interface (e.g., using FastAPI or Flask) where users upload an Excel sheet and download the compiled results.
2. **Automated Cron Jobs**: Set up a server script that runs on a schedule (e.g., every morning), fetches input from a shared folder (Google Drive, S3 bucket), crawls the results, and uploads the exported file back.
3. **Serverless Functions**: Package the scraping client into AWS Lambda or Google Cloud Functions to retrieve individual results programmatically via on-demand HTTP API endpoints.
