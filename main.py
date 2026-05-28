import os
import sys


PACKAGE_DIR = os.path.abspath(os.path.dirname(__file__))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

PROJECT_ROOT = os.path.abspath(os.path.join(PACKAGE_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from gui import App
    from runtime.logger import app_logger
except (ImportError, ModuleNotFoundError):
    from http_bot.gui import App
    from http_bot.runtime.logger import app_logger


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
