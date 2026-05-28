import os
import sys


PACKAGE_DIR = os.path.abspath(os.path.dirname(__file__))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

from gui import App
from runtime.logger import app_logger
from runtime.utils import get_logs_dir


def main():
    try:
        app_logger.info("Starting AKTU Result Application...")
        app = App()
        app.mainloop()
    except Exception:
        import traceback

        tb = traceback.format_exc()
        app_logger.error(f"FATAL ERROR during app startup:\n{tb}")
        crash_path = os.path.join(get_logs_dir(), "aktu_result_crash.txt")
        try:
            with open(crash_path, "w", encoding="utf-8") as handle:
                handle.write(tb)
        except Exception:
            pass


if __name__ == "__main__":
    main()
