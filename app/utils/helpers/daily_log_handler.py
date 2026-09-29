import os
import glob
import time
import logging
from datetime import datetime

class DailyFileHandler(logging.Handler):

    def __init__(self, log_dir="logs", prefix="flask", backup_days=14, encoding="utf-8"):
        super().__init__()
        self.log_dir = log_dir
        self.prefix = prefix
        self.backup_days = backup_days
        self.encoding = encoding
        os.makedirs(log_dir, exist_ok=True)
        self._current_date = None
        self._stream = None
        self._open_stream()

    def _filename_for(self, date):
        return os.path.join(self.log_dir, f"{self.prefix}-{date.isoformat()}.log")

    def _open_stream(self):
        today = datetime.now().date()
        self._current_date = today
        self._stream = open(self._filename_for(today), "a", encoding=self.encoding)
        self._cleanup_old_logs()

    def _cleanup_old_logs(self):
        cutoff = time.time() - self.backup_days * 86400
        for path in glob.glob(os.path.join(self.log_dir, f"{self.prefix}-*.log")):
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
            except OSError:
                pass

    def emit(self, record):
        try:
            if datetime.now().date() != self._current_date:
                self._stream.close()
                self._open_stream()
            self._stream.write(self.format(record) + "\n")
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self):
        try:
            if self._stream:
                self._stream.close()
        finally:
            super().close()