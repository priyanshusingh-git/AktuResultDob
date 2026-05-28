import logging
import os
from datetime import datetime
from queue import Queue

class GUIQueueHandler(logging.Handler):
    """
    Custom logging handler that puts log messages into a queue.
    The GUI thread will read from this queue and update the text widget.
    """
    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    def emit(self, record):
        log_entry = self.format(record)
        self.queue.put(log_entry)

from runtime.utils import get_logs_dir

class AppLogger:
    def __init__(self):
        self.output_dir = get_logs_dir()
        os.makedirs(self.output_dir, exist_ok=True)
        
        # We'll set this up exactly once
        self.logger = logging.getLogger("AktuBotHTTP")
        
        # Only configure if not already configured
        if not self.logger.handlers:
            self.logger.setLevel(logging.DEBUG)
            
            # File Handler (logs everything, including debug status)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_filename = f"aktu_bot_http_session_{timestamp}.log"
            file_handler = logging.FileHandler(os.path.join(self.output_dir, log_filename), encoding='utf-8')
            file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(logging.DEBUG)
            self.logger.addHandler(file_handler)
            
            # Console Handler removed to prevent terminal prints
            pass

        self.gui_queue = None

    def setup_gui_logging(self, log_queue: Queue):
        """Attaches a GUI queue handler so logs can be displayed in the app."""
        if self.gui_queue is None:
            self.gui_queue = log_queue
            gui_handler = GUIQueueHandler(self.gui_queue)
            gui_formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S')
            gui_handler.setFormatter(gui_formatter)
            gui_handler.setLevel(logging.INFO)  # GUI only receives INFO, WARNING, and ERROR
            self.logger.addHandler(gui_handler)

    def info(self, msg):
        self.logger.info(msg)

    def debug(self, msg):
        self.logger.debug(msg)

    def error(self, msg):
        self.logger.error(msg)
        
    def warning(self, msg):
        self.logger.warning(msg)
        
    def __getattr__(self, name):
        return getattr(self.logger, name)
        
    def get_logger(self):
        return self.logger

# Global instance
app_logger = AppLogger()
