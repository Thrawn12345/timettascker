import logging
import threading
import webbrowser
import time
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%H:%M:%S',
)

import database
from tracker import AppTracker
import server

PORT = 7878


def main():
    print()
    print("  ╔══════════════════════════════════╗")
    print("  ║        Time Tracker              ║")
    print(f"  ║   Dashboard → http://127.0.0.1:{PORT}  ║")
    print("  ║   Press Ctrl+C to stop           ║")
    print("  ╚══════════════════════════════════╝")
    print()

    database.init_db()

    tracker = AppTracker()
    tracker.start()

    def _open():
        time.sleep(1.2)
        webbrowser.open(f'http://127.0.0.1:{PORT}')

    threading.Thread(target=_open, daemon=True).start()

    try:
        server.run(PORT)
    except KeyboardInterrupt:
        print("\nShutting down…")
        tracker.stop()
        sys.exit(0)


if __name__ == '__main__':
    main()
