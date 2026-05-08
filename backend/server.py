import os
import logging
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import database

logger = logging.getLogger(__name__)

DASHBOARD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dashboard')

app = Flask(__name__, static_folder=DASHBOARD_DIR)
CORS(app, origins='*')


@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


# ── write endpoints ────────────────────────────────────────────────────────

@app.route('/api/tab', methods=['POST'])
def receive_tab():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'bad request'}), 400
    try:
        database.add_tab_entry(
            str(data.get('name', 'Unknown'))[:120],
            str(data.get('url', ''))[:500],
            float(data['start_time']),
            float(data['end_time']),
            device=str(data.get('device', 'unknown'))[:60],
        )
        return jsonify({'ok': True})
    except (KeyError, ValueError) as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/app', methods=['POST'])
def receive_app():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'bad request'}), 400
    try:
        database.add_app_entry(
            str(data.get('name', 'Unknown'))[:120],
            float(data['start_time']),
            float(data['end_time']),
            device=str(data.get('device', 'unknown'))[:60],
        )
        return jsonify({'ok': True})
    except (KeyError, ValueError) as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/phone', methods=['POST'])
def receive_phone():
    data = request.get_json(silent=True)
    if not data or not isinstance(data.get('entries'), list):
        return jsonify({'error': 'bad request'}), 400
    device = str(data.get('device', 'Phone'))[:60]
    count = 0
    for e in data['entries']:
        try:
            database.add_app_entry(
                str(e.get('name', 'Unknown'))[:120],
                float(e['start_time']),
                float(e['end_time']),
                device=device,
            )
            count += 1
        except (KeyError, ValueError):
            pass
    return jsonify({'ok': True, 'saved': count})


# ── read endpoints ─────────────────────────────────────────────────────────

@app.route('/api/devices')
def devices():
    return jsonify(database.get_devices())


@app.route('/api/stats')
def stats():
    period = request.args.get('period', 'day')
    device = request.args.get('device') or None
    if period not in ('day', 'week', 'month', 'year'):
        return jsonify({'error': 'invalid period'}), 400
    return jsonify(database.get_stats(period, device))


@app.route('/api/timeline')
def timeline():
    period = request.args.get('period', 'day')
    device = request.args.get('device') or None
    if period not in ('day', 'week', 'month', 'year'):
        return jsonify({'error': 'invalid period'}), 400
    return jsonify(database.get_hourly_breakdown(period, device))


@app.route('/api/summary')
def summary():
    device = request.args.get('device') or None
    return jsonify({'today_seconds': database.get_total_today(device)})


@app.errorhandler(404)
def not_found(_):
    return jsonify({'error': 'not found'}), 404


def run(port=7878):
    logger.info(f"Dashboard at http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
