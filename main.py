import os
import sys


PACKAGE_DIR = os.path.abspath(os.path.dirname(__file__))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

from gui import App
from runtime.logger import app_logger


def main():
    try:
        app_logger.info("Starting AKTU Result Application...")
        app = App()
        app.mainloop()
    except Exception:
        import traceback

        app_logger.error(f"FATAL ERROR during app startup:\n{traceback.format_exc()}")
        with open(os.path.expanduser("~/Desktop/aktu_result_crash.txt"), "w", encoding="utf-8") as handle:
            handle.write(traceback.format_exc())


if __name__ == "__main__":
    main()
