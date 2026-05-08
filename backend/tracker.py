import os
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

CLOUD_URL  = os.environ.get('TRACKER_SERVER', '').rstrip('/')

SKIP_NAMES = {
    'python', 'python3', 'pythonw', 'cmd', 'conhost',
    'windowsterminal', 'powershell', 'pwsh',
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
        if title and len(title) < 80 and title.lower() != display.lower():
            display = f"{display} — {title}"
        return display
    except Exception:
        return None


def _save_session(name, start_time, end_time):
    if CLOUD_URL:
        threading.Thread(
            target=_post_app_session,
            args=(name, start_time, end_time),
            daemon=True,
        ).start()
    else:
        database.add_app_entry(name, start_time, end_time)


def _post_app_session(name, start_time, end_time):
    try:
        import requests
        r = requests.post(
            f'{CLOUD_URL}/api/app',
            json={'name': name, 'start_time': start_time, 'end_time': end_time},
            timeout=5,
        )
        if not r.ok:
            raise ValueError(r.text)
    except Exception as e:
        logger.warning(f"Cloud POST failed ({e}), saving locally")
        try:
            database.add_app_entry(name, start_time, end_time)
        except Exception:
            pass


class AppTracker:
    def __init__(self):
        self._running    = False
        self._thread     = None
        self._current_app = None
        self._start_time  = None
        # local-mode only (in-progress entry id so we can update it live)
        self._entry_id   = None

    def _begin(self, name):
        self._current_app = name
        self._start_time  = time.time()
        if not CLOUD_URL:
            self._entry_id, _ = database.insert_entry(name, 'app')

    def _end(self):
        if not self._current_app or not self._start_time:
            return
        end = time.time()
        if CLOUD_URL:
            _save_session(self._current_app, self._start_time, end)
        else:
            if self._entry_id is not None:
                database.finalize_entry(self._entry_id, self._start_time)
        self._current_app = None
        self._start_time  = None
        self._entry_id    = None

    def _loop(self):
        while self._running:
            app = _get_active_app() if HAS_WIN32 else None
            if app != self._current_app:
                self._end()
                if app:
                    self._begin(app)
            time.sleep(1)
        self._end()

    def start(self):
        if not HAS_WIN32:
            logger.warning("Desktop tracking unavailable — install pywin32 and psutil")
            return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True, name='AppTracker')
        self._thread.start()
        mode = f"cloud → {CLOUD_URL}" if CLOUD_URL else "local SQLite"
        logger.info(f"Desktop app tracker started ({mode})")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("Desktop app tracker stopped")
