"""
Cloud entry point — runs only the Flask API (no Windows tracker).
Start with:  gunicorn cloud_main:app
Env vars:
  DATABASE_URL   PostgreSQL connection string (required for cloud)
  PORT           Port to listen on (Render sets this automatically)
"""
import os
import database
from server import app

database.init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 7878))
    app.run(host='0.0.0.0', port=port, debug=False)
