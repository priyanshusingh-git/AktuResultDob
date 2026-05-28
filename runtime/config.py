import os

# Application Constants
APP_LABEL = "AKTU Result"

# Scraper Settings
DEFAULT_PAGE_LOAD_TIMEOUT = 30 # seconds
MAX_NETWORK_RETRIES = 3
STUDENT_RETRY_DELAY = 2        # seconds between students
DEFAULT_SAFE_HTTP_SESSION_POOL_SIZE = 1
SAFE_HTTP_SESSION_POOL_SIZE = max(
    1,
    min(10, int(os.environ.get("AKTUBOT_SESSION_POOL_SIZE", str(DEFAULT_SAFE_HTTP_SESSION_POOL_SIZE)))),
)

# Paths are handled in utils.py
