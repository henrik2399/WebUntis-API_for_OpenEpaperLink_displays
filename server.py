from flask import Flask, jsonify, request
from flask_cors import CORS
from webuntis_api import WebUntisRoomScraper
import threading
import time
import re
from datetime import datetime

app = Flask(__name__)
CORS(app)

cache = {
    'data': None,
    'last_update': None,
    'scraper': None
}

UPDATE_INTERVAL = 300

DISPLAY_CONFIG = {
    'room_name_y': 9,
    'room_name_font': 'fonts/bahnschrift20',
    'lesson_start_y': 36,
    'lesson_spacing': 33,
    'lesson_font': 'fonts/bahnschrift30',
    'x_margin': 16
}

def update_data():
    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching data...")

            if not cache['scraper']:
                cache['scraper'] = WebUntisRoomScraper(headless=True)
                cache['scraper'].start_browser()

            data = cache['scraper'].fetch_room_data()

            if data:
                cache['data'] = data
                cache['last_update'] = datetime.now().isoformat()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Data updated successfully")

        except Exception as e:
            print(f"Error updating data: {e}")

        time.sleep(UPDATE_INTERVAL)

WEEKDAYS_DE = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']

def parse_time_range(time_str):
    times = re.findall(r'\d{1,2}:\d{2}', time_str or '')
    start = times[0] if times else ''
    end = times[-1] if len(times) > 1 else ''
    return start, end

def merge_double_lessons(lessons):
    groups = []
    for lesson in lessons:
        key = (
            lesson.get('class', ''),
            lesson.get('subject', ''),
            lesson.get('teacher', ''),
            lesson.get('status', 'normal'),
        )
        start, end = parse_time_range(lesson.get('time', ''))
        if groups and groups[-1]['key'] == key and groups[-1]['end'] and groups[-1]['end'] == start:
            groups[-1]['end'] = end or groups[-1]['end']
        else:
            groups.append({'key': key, 'start': start, 'end': end, 'lesson': lesson})
    return groups

def _fit(text, max_chars):
    text = text or ''
    return text if len(text) <= max_chars else text[:max_chars - 2] + '..'

CHAR_W_20 = 12

def _dash(commands, x, y_mid):
    commands.append({"line": [x, y_mid, x + 9, y_mid, 1]})

def shorten_classes(class_name):
    parts = [p.strip() for p in (class_name or '').split(',') if p.strip()]
    if len(parts) > 2:
        return parts[0], parts[-1]
    return (class_name or '---'), None

def create_display_json(room_data, room_name):
    commands = []

    commands.append({"text": [4, 2, room_name, "fonts/bahnschrift30", 1]})

    now = datetime.now()
    stand = f"Stand: {WEEKDAYS_DE[now.weekday()]}, {now.strftime('%H:%M')}"
    commands.append({"text": [292, 8, stand, "fonts/bahnschrift20", 1, 2]})

    commands.append({"line": [0, 28, 296, 28, 2]})

    groups = merge_double_lessons(room_data.get('lessons', []))[:2]

    if not groups:
        commands.append({"text": [55, 70, "Keine Belegungen", "fonts/bahnschrift30", 1]})
        return commands

    card_top = [34, 81]
    for i, group in enumerate(groups):
        y0 = card_top[i]
        lesson = group['lesson']
        subject = lesson.get('subject', '')
        teacher = lesson.get('teacher', '')
        class_name = lesson.get('class', '') or '---'
        status = lesson.get('status', 'normal')

        commands.append({"text": [4, y0, group['start'], "fonts/bahnschrift20", 1]})
        if group['end']:
            dx = 4 + len(group['start']) * CHAR_W_20 + 5
            _dash(commands, dx, y0 + 9)
            commands.append({"text": [dx + 16, y0, group['end'], "fonts/bahnschrift20", 1]})
        subj_teacher = ' '.join(p for p in (subject, teacher) if p)
        if subj_teacher:
            commands.append({"text": [186, y0, _fit(subj_teacher, 12), "fonts/bahnschrift20", 1]})

        first, last = shorten_classes(class_name)
        commands.append({"text": [4, y0 + 22, _fit(first, 30), "fonts/bahnschrift20", 1]})
        if last:
            cx = 4 + len(first) * CHAR_W_20 + 5
            _dash(commands, cx, y0 + 22 + 9)
            commands.append({"text": [cx + 16, y0 + 22, last, "fonts/bahnschrift20", 1]})

        if status == 'cancelled':
            commands.append({"line": [0, y0 + 9, 296, y0 + 9, 2]})
            commands.append({"line": [0, y0 + 31, 296, y0 + 31, 2]})

    if len(groups) > 1:
        commands.append({"line": [0, 76, 296, 76, 1]})

    return commands

update_thread = threading.Thread(target=update_data, daemon=True)
update_thread.start()

@app.route('/')
def home():
    return jsonify({
        'message': 'WebUntis Display API',
        'endpoints': {
            '/display/<room_name>': 'Get display commands for a room',
            '/display/Aul': 'Example: Get Aula display data',
            '/api/raw/<room_name>': 'Get raw room data (debug)',
            '/api/rooms': 'Get all available rooms'
        }
    })

@app.route('/display/<room_name>')
def get_display(room_name):
    if not cache['data']:
        return jsonify([
            {"text": [16, 9, room_name, "fonts/bahnschrift20", 1]},
            {"text": [16, 36, "Lade Daten...", "fonts/bahnschrift30", 1]}
        ])

    rooms = cache['data'].get('rooms', {})

    room_data = None
    actual_room_name = room_name
    for key, value in rooms.items():
        if key.lower() == room_name.lower():
            room_data = value
            actual_room_name = key
            break

    if not room_data:
        return jsonify([
            {"text": [16, 9, room_name, "fonts/bahnschrift20", 1]},
            {"text": [16, 36, "Raum nicht gefunden", "fonts/bahnschrift30", 1]}
        ])

    commands = create_display_json(room_data, actual_room_name)
    return jsonify(commands)

@app.route('/api/raw/<room_name>')
def get_raw_room(room_name):
    if not cache['data']:
        return jsonify({'error': 'No data available yet'}), 503

    rooms = cache['data'].get('rooms', {})

    for key, value in rooms.items():
        if key.lower() == room_name.lower():
            return jsonify({
                'room': value,
                'date': cache['data'].get('date'),
                'last_update': cache['last_update']
            })

    return jsonify({
        'error': f'Room "{room_name}" not found',
        'available_rooms': list(rooms.keys())
    }), 404

@app.route('/api/rooms')
def get_rooms():
    if not cache['data']:
        return jsonify({'error': 'No data available yet'}), 503

    return jsonify({
        'rooms': cache['data'].get('available_rooms', []),
        'total': cache['data'].get('total_rooms', 0),
        'last_update': cache['last_update']
    })

@app.route('/api/refresh')
def refresh():
    try:
        if not cache['scraper']:
            cache['scraper'] = WebUntisRoomScraper(headless=True)
            cache['scraper'].start_browser()

        data = cache['scraper'].fetch_room_data()

        if data:
            cache['data'] = data
            cache['last_update'] = datetime.now().isoformat()
            return jsonify({
                'success': True,
                'message': 'Data refreshed',
                'last_update': cache['last_update']
            })
        else:
            return jsonify({'error': 'Failed to fetch data'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/config', methods=['GET', 'POST'])
def config():
    global DISPLAY_CONFIG

    if request.method == 'POST':
        new_config = request.json
        DISPLAY_CONFIG.update(new_config)
        return jsonify({'success': True, 'config': DISPLAY_CONFIG})

    return jsonify(DISPLAY_CONFIG)

if __name__ == '__main__':
    print("Starting server... Fetching initial data...")
    time.sleep(2)

    app.run(host='0.0.0.0', port=5000, debug=False)
