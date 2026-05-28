from __future__ import annotations

from importlib import import_module
import os
import sys


PACKAGE_DIR = os.path.abspath(os.path.dirname(__file__))
PACKAGE_NAME = os.path.basename(PACKAGE_DIR)
PROJECT_ROOT = os.path.abspath(os.path.join(PACKAGE_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

App = import_module(f"{PACKAGE_NAME}.gui").App  # noqa: E402
app_logger = import_module(f"{PACKAGE_NAME}.runtime.logger").app_logger  # noqa: E402


def main():
    try:
        app_logger.info("Starting AktuBot HTTP Application...")
        app = App()
        app.mainloop()
    except Exception:
        import traceback

        app_logger.error(f"FATAL ERROR during HTTP app startup:\n{traceback.format_exc()}")
        with open(os.path.expanduser("~/Desktop/aktubot_http_crash.txt"), "w", encoding="utf-8") as handle:
            handle.write(traceback.format_exc())


if __name__ == "__main__":
    main()
