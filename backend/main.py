import logging
import threading
import webbrowser
import time
import sys
import socket

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%H:%M:%S',
)

import os
import database
from tracker import AppTracker, DEVICE_NAME
import server

PORT = 7878


def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def main():
    lan_ip   = get_lan_ip()
    cloud    = os.environ.get('TRACKER_SERVER', '')
    db_cloud = os.environ.get('DATABASE_URL', '')

    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║             Time Tracker                     ║")
    print(f"  ║  Device   : {DEVICE_NAME:<34}║")
    print(f"  ║  Local    → http://127.0.0.1:{PORT}             ║")
    if lan_ip:
        print(f"  ║  Network  → http://{lan_ip}:{PORT}       ║")
    if db_cloud:
        print(f"  ║  Database : Neon PostgreSQL (cloud)          ║")
    if cloud:
        print(f"  ║  Tracker  : POSTing to {cloud[:30]:<30}  ║")
    print("  ║  Ctrl+C to stop                              ║")
    print("  ╚══════════════════════════════════════════════╝")
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
