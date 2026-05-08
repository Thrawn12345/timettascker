import time
import threading
import logging

logger = logging.getLogger(__name__)

try:
    import win32gui
    import win32process
    import psutil
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False
    logger.warning("pywin32/psutil not installed — desktop app tracking disabled")

import database

SKIP_NAMES = {
    'python', 'python3', 'pythonw', 'python3.exe',
    'cmd', 'conhost', 'windowsterminal', 'powershell', 'pwsh',
    'taskhostw', 'sihost', 'shellexperiencehost', 'startmenuexperiencehost',
    'searchhost', 'searchapp', 'textinputhost',
}


def _get_active_app():
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        name = proc.name().lower().replace('.exe', '')
        if name in SKIP_NAMES:
            return None
        title = win32gui.GetWindowText(hwnd)
        display = proc.name().replace('.exe', '').replace('.EXE', '')
        if title and len(title) < 80:
            display = f"{display} — {title}" if title.lower() != display.lower() else display
        return display
    except Exception:
        return None


class AppTracker:
    def __init__(self):
        self._running = False
        self._thread = None
        self._current_app = None
        self._entry_id = None
        self._start_time = None

    def _loop(self):
        while self._running:
            app = _get_active_app() if HAS_WIN32 else None

            if app != self._current_app:
                if self._entry_id is not None:
                    database.finalize_entry(self._entry_id, self._start_time)

                if app:
                    self._entry_id, self._start_time = database.insert_entry(app, 'app')
                else:
                    self._entry_id = None
                    self._start_time = None

                self._current_app = app

            time.sleep(1)

        if self._entry_id is not None:
            database.finalize_entry(self._entry_id, self._start_time)

    def start(self):
        if not HAS_WIN32:
            logger.warning("Desktop tracking unavailable — install pywin32 and psutil")
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name='AppTracker')
        self._thread.start()
        logger.info("Desktop app tracker started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("Desktop app tracker stopped")
