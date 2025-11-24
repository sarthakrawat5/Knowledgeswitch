from flask import Flask, g, render_template, request, jsonify, url_for
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
import time # Import time for token expiration logic
import json
import requests
from flask_socketio import SocketIO, emit, join_room, leave_room
# import jwt # You would need to install PyJWT (pip install PyJWT)
# from datetime import datetime, timedelta # Needed for token expiration
# import random # Might be needed for unique meeting IDs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'knowledge_switch.db')

app = Flask(__name__, template_folder='Templates', static_folder='public')
app.config['SECRET_KEY'] = 'dev-secret-change-me'
socketio = SocketIO(app, cors_allowed_origins="*")

# Enable CORS for API endpoints
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


def init_db():
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            email TEXT UNIQUE,
            password_hash TEXT,
            username_change_count INTEGER DEFAULT 0,
            last_change_date DATETIME
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            token TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            skill_name TEXT NOT NULL,
            role TEXT NOT NULL,
            portfolio_link TEXT,
            github_link TEXT,
            linkedin_link TEXT,
            upload_sample TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    db.commit()
    db.close()


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/index.html')
def index_html():
    return render_template('index.html')


@app.route('/login.html')
def login_page():
    return render_template('Login.html')


@app.route('/registration.html')
def register_page():
    return render_template('Registration.html')


@app.route('/register')
def register_alias():
    return render_template('Registration.html')


@app.route('/dashboard.html')
def dashboard_page():
    return render_template('Dashboard.html')


@app.route('/add-new-skill')
def add_new_skill_page():
    # Note: Using the filename from the last interaction for consistency
    return render_template('Add_new_skill.html')


@app.route('/profile.html')
def profile_page():
    return render_template('profile.html')


@app.route('/find_matches.html')
def find_matches_page():
    return render_template('find_matches.html')


# --- WEBRTC VIDEO CALL API ENDPOINTS ---

# Store active rooms and their participants
active_rooms = {}

@app.route('/api/video/start_session', methods=['POST'])
def start_video_session():
    """
    Creates a new WebRTC video session/room.
    """
    data = request.get_json() or {}
    user_email = data.get('email')

    if not user_email:
        return jsonify({'success': False, 'message': 'Email required'}), 400

    # Securely fetch user_id
    db = get_db()
    user_row = db.execute('SELECT id, username FROM users WHERE email = ?', (user_email,)).fetchone()
    if not user_row:
        return jsonify({'success': False, 'message': 'Authentication error'}), 401

    current_user_id = user_row['id']
    current_username = user_row['username']

    # Generate unique room ID
    import uuid
    room_id = str(uuid.uuid4())[:8]

    # Create room
    active_rooms[room_id] = {
        'host': user_email,
        'participants': [user_email],
        'created_at': time.time()
    }

    # Generate join URL
    join_url = f"{request.host_url}video_call_api.html?room={room_id}"

    return jsonify({
        'success': True,
        'message': 'Video session created successfully',
        'room_id': room_id,
        'join_url': join_url,
        'username': current_username,
    }), 200

@app.route('/api/video/join_room', methods=['POST'])
def join_video_room():
    """
    Join an existing WebRTC video room.
    """
    data = request.get_json() or {}
    room_id = data.get('room_id')
    user_email = data.get('email')

    if not room_id or not user_email:
        return jsonify({'success': False, 'message': 'Room ID and email required'}), 400

    if room_id not in active_rooms:
        return jsonify({'success': False, 'message': 'Room not found'}), 404

    # Securely fetch username
    db = get_db()
    user_row = db.execute('SELECT username FROM users WHERE email = ?', (user_email,)).fetchone()
    if not user_row:
        return jsonify({'success': False, 'message': 'Authentication error'}), 401

    username = user_row['username']

    # Add participant to room
    if user_email not in active_rooms[room_id]['participants']:
        active_rooms[room_id]['participants'].append(user_email)

    return jsonify({
        'success': True,
        'room_id': room_id,
        'username': username,
        'participants': active_rooms[room_id]['participants']
    }), 200

@app.route('/api/video/leave_room', methods=['POST'])
def leave_video_room():
    """
    Leave a WebRTC video room.
    """
    data = request.get_json() or {}
    room_id = data.get('room_id')
    user_email = data.get('email')

    if room_id in active_rooms and user_email in active_rooms[room_id]['participants']:
        active_rooms[room_id]['participants'].remove(user_email)

        # Clean up empty rooms
        if not active_rooms[room_id]['participants']:
            del active_rooms[room_id]

    return jsonify({'success': True}), 200

# --- END WEBRTC VIDEO CALL API ENDPOINTS ---

# --- SOCKET.IO EVENT HANDLERS ---

@socketio.on('join-room')
def handle_join_room(data):
    room_id = data.get('roomId')
    username = data.get('username')
    email = data.get('email')

    if not room_id or not email:
        return

    # Join the Socket.IO room
    join_room(room_id)

    # Notify other participants in the room
    emit('user-joined', {
        'username': username,
        'email': email,
        'socketId': request.sid
    }, room=room_id, skip_sid=request.sid)

    print(f"User {username} ({email}) joined room {room_id}")

@socketio.on('offer')
def handle_offer(data):
    to_socket_id = data.get('to')
    offer = data.get('offer')

    if to_socket_id and offer:
        emit('offer', {
            'offer': offer,
            'from': request.sid
        }, room=to_socket_id)

@socketio.on('answer')
def handle_answer(data):
    to_socket_id = data.get('to')
    answer = data.get('answer')

    if to_socket_id and answer:
        emit('answer', {
            'answer': answer,
            'from': request.sid
        }, room=to_socket_id)

@socketio.on('ice-candidate')
def handle_ice_candidate(data):
    to_socket_id = data.get('to')
    candidate = data.get('candidate')

    if to_socket_id and candidate:
        emit('ice-candidate', {
            'candidate': candidate,
            'from': request.sid
        }, room=to_socket_id)

@socketio.on('disconnect')
def handle_disconnect():
    print(f"User {request.sid} disconnected")

# --- END SOCKET.IO EVENT HANDLERS ---


@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json() or {}
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not (email and password):
        return jsonify({'success': False, 'message': 'Email and password required'}), 400

    hashed = generate_password_hash(password)
    db = get_db()
    try:
        db.execute('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)', (username, email, hashed))
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Email already registered'}), 409

    return jsonify({'success': True, 'message': 'Registered successfully', 'email': email, 'username': username})


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')

    if not (email and password):
        return jsonify({'success': False, 'message': 'Email and password required'}), 400

    db = get_db()
    row = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    if not row:
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

    # Support DBs that name the hashed column either 'password' or 'password_hash'
    keys = list(row.keys())
    pw_hash = None
    if 'password' in keys:
        pw_hash = row['password']
    elif 'password_hash' in keys:
        pw_hash = row['password_hash']

    if not pw_hash or not check_password_hash(pw_hash, password):
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

    # Basic response (client stores auth in localStorage)
    return jsonify({'success': True, 'message': 'Login successful', 'email': row['email'], 'username': row['username']})


@app.route('/api/users', methods=['GET'])
def api_users():
    db = get_db()
    rows = db.execute('SELECT id, username, email FROM users').fetchall()
    users = [dict(r) for r in rows]
    return jsonify({'users': users})


@app.route('/api/verify-auth', methods=['POST'])
def api_verify_auth():
    data = request.get_json() or {}
    email = data.get('email')
    if not email:
        return jsonify({'authenticated': False}), 400
    db = get_db()
    row = db.execute('SELECT id, username, email FROM users WHERE email = ?', (email,)).fetchone()
    if not row:
        return jsonify({'authenticated': False}), 200
    return jsonify({'authenticated': True, 'email': row['email'], 'username': row['username']})


@app.route('/api/logout', methods=['POST'])
def api_logout():
    # For this simple demo, logout is client-side (localStorage). Accept the request and respond OK.
    return jsonify({'success': True})


@app.route('/api/update-profile', methods=['POST'])
def api_update_profile():
    data = request.get_json() or {}
    email = data.get('email')
    username = data.get('username')
    if not (email and username):
        return jsonify({'success': False, 'message': 'Email and username required'}), 400
    db = get_db()
    try:
        db.execute('UPDATE users SET username = ? WHERE email = ?', (username, email))
        db.commit()
    except Exception as e:
        return jsonify({'success': False, 'message': 'Update failed'}), 500
    return jsonify({'success': True, 'message': 'Profile updated', 'username': username})


@app.route('/api/save-skills', methods=['POST'])
def api_save_skills():
    # Handle FormData instead of JSON
    username = request.form.get('username')
    email = request.form.get('email')
    skills_json = request.form.get('skills')

    if not (email and skills_json):
        return jsonify({'success': False, 'message': 'Email and skills required'}), 400

    try:
        skills = json.loads(skills_json)
    except json.JSONDecodeError:
        return jsonify({'success': False, 'message': 'Invalid skills data'}), 400

    db = get_db()
    try:
        # Get user_id from email
        user_row = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if not user_row:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        user_id = user_row['id']

        # Clear existing skills first to prevent duplicates (since user is using the form as a whole)
        db.execute('DELETE FROM user_skills WHERE user_id = ?', (user_id,))

        # Insert new skills
        for skill_name, skill_data in skills.items():
            role = skill_data.get('role')
            teaching_details = skill_data.get('teaching_details', {})
            portfolio_link = teaching_details.get('link')
            github_link = teaching_details.get('github_link')
            upload_sample = teaching_details.get('upload_sample')

            db.execute('''
                INSERT INTO user_skills (user_id, skill_name, role, portfolio_link, github_link, upload_sample)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, skill_name, role, portfolio_link, github_link, upload_sample))

        db.commit()
        return jsonify({'success': True, 'message': 'Skills saved successfully'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': f'Save failed: {str(e)}'}), 500


@app.route('/api/get-skills', methods=['POST'])
def api_get_skills():
    data = request.get_json() or {}
    email = data.get('email')

    if not email:
        return jsonify({'success': False, 'message': 'Email required'}), 400

    db = get_db()
    try:
        # Get user_id from email
        user_row = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if not user_row:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        user_id = user_row['id']

        # Get skills where role is 'teach', limit to 5
        skills_rows = db.execute('SELECT skill_name, role, portfolio_link, github_link, upload_sample FROM user_skills WHERE user_id = ? AND role = ? LIMIT 5', (user_id, 'teach')).fetchall()

        skills = [dict(row) for row in skills_rows]

        return jsonify({'success': True, 'skills': skills})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to fetch skills: {str(e)}'}), 500


@app.route('/api/search', methods=['GET'])
def api_search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'success': False, 'message': 'Query parameter required'}), 400

    conn = sqlite3.connect('knowledge_switch.db')
    cursor = conn.cursor()

    # Search for skills
    cursor.execute('''
        SELECT DISTINCT skill_name FROM user_skills
        WHERE skill_name LIKE ? AND role = 'teach'
    ''', (f'%{query}%',))

    skills = [row[0] for row in cursor.fetchall()]

    # Search for users
    cursor.execute('''
        SELECT DISTINCT u.username, u.email
        FROM users u
        JOIN user_skills us ON u.id = us.user_id
        WHERE (u.username LIKE ? OR u.email LIKE ?) AND us.role = 'teach'
    ''', (f'%{query}%', f'%{query}%'))

    users = [{'username': row[0], 'email': row[1]} for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        'success': True,
        'skills': skills,
        'users': users
    })





@app.route('/video_call_api.html')
def video_call_api_page():
    return render_template('video_call_api.html')


if __name__ == '__main__':
    init_db()
    print('Database initialized (if needed):', DB_PATH)
    socketio.run(app, host='127.0.0.1', port=5000, debug=True)
