import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from openai import OpenAI
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'
UPLOAD_FOLDER = 'static/images/profiles'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    conn = sqlite3.connect('crosscountry.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = sqlite3.connect('crosscountry.db')
    cursor = conn.cursor()

    # Create table for users
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL
    )
    ''')

    # Create table for team members (linked to users)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS team_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        email TEXT NOT NULL,
        image TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # Create table for training skills
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS training_skills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        skill TEXT NOT NULL,
        description TEXT NOT NULL
    )
    ''')

    # Create table for training drills
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS training_drills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        drill TEXT NOT NULL,
        duration INTEGER NOT NULL,
        FOREIGN KEY (member_id) REFERENCES team_members (id)
    )
    ''')

    # Create table for best scores
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS best_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        distance REAL NOT NULL,
        time REAL NOT NULL,
        date TEXT NOT NULL,
        FOREIGN KEY (member_id) REFERENCES team_members (id)
    )
    ''')

    # Add mock data for users
    cursor.executemany('''
    INSERT OR IGNORE INTO users (name, email, password)
    VALUES (?, ?, ?)
    ''', [
        ('JohnDoe', 'john@example.com', 'password123'),
        ('JaneSmith', 'jane@example.com', 'password456'),
        ('TestUser', 'testtest@example.com', 'testpassword')
    ])

    # Add mock data for team members linked to users
    cursor.executemany('''
    INSERT OR IGNORE INTO team_members (user_id, name, role, email)
    VALUES (?, ?, ?, ?)
    ''', [
        (1, 'Runner One', 'Runner', 'runner1@example.com'),
        (1, 'Runner Two', 'Runner', 'runner2@example.com'),
        (2, 'Coach One', 'Coach', 'coach1@example.com'),
        (3, 'Test Runner', 'Runner', 'testrunner@example.com'),  # Linked to TestUser
        (3, 'Test Coach', 'Coach', 'testcoach@example.com')     # Linked to TestUser
    ])

    # Add mock data for training drills
    cursor.executemany('''
    INSERT OR IGNORE INTO training_drills (member_id, date, drill, duration)
    VALUES (?, ?, ?, ?)
    ''', [
        (4, '2025-01-01', 'Interval Training', 30),
        (5, '2025-01-02', 'Endurance Run', 45)
    ])

    # Add mock data for best scores
    cursor.executemany('''
    INSERT OR IGNORE INTO best_scores (member_id, distance, time, date)
    VALUES (?, ?, ?, ?)
    ''', [
        (4, 5.0, 20.5, '2025-01-03'),
        (5, 10.0, 45.2, '2025-01-04')
    ])

    conn.commit()
    conn.close()
@app.route('/delete_member/<int:member_id>', methods=['POST'])
def delete_member(member_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    conn = get_db_connection()
    conn.execute('DELETE FROM team_members WHERE id = ?', (member_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/update_member/<int:member_id>', methods=['POST'])
def update_member(member_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    name = request.form['name']
    role = request.form['role']
    email = request.form['email']
    image = request.files.get('image', None)

    conn = get_db_connection()
    filename = None
    if image and allowed_file(image.filename):
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        conn.execute('''
            UPDATE team_members SET name = ?, role = ?, email = ?, image = ? WHERE id = ?
        ''', (name, role, email, filename, member_id))
    else:
        conn.execute('''
            UPDATE team_members SET name = ?, role = ?, email = ? WHERE id = ?
        ''', (name, role, email, member_id))

    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/get_recommendation/<int:member_id>', methods=['GET'])
def get_recommendation(member_id):
    conn = get_db_connection()
    member = conn.execute('SELECT * FROM team_members WHERE id = ?', (member_id,)).fetchone()
    drills = conn.execute('SELECT * FROM training_drills WHERE member_id = ?', (member_id,)).fetchall()
    total_distance = conn.execute('''
        SELECT SUM(distance) AS total_distance
        FROM best_scores
        WHERE member_id = ?
    ''', (member_id,)).fetchone()['total_distance'] or 0
    conn.close()

    if not member:
        return jsonify({"error": "Member not found"}), 404

    target_time = member['target_time_5km']
    drill_history = "\n".join([
        f"{drill['date']}: {drill['drill']} for {drill['duration']} minutes"
        for drill in drills
    ]) or "No historical data available."

    goal_progress_info = f"Target 5km Time: {target_time} minutes."

    prompt = f"""
    You are a performance analyst. Based on the training history and goal progress of the following athlete, estimate their best time for a 5km run.

    Training History:
    {drill_history}

    Total distance run so far: {total_distance} km
    Goal progress: {goal_progress_info}

    Please guess a reasonable 5km time in minutes and explain your reasoning in 1-2 sentences.
    Format:
    - Predicted 5km Time: X minutes
    - Reason: ...
    """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a fitness coach."},
                {"role": "user", "content": prompt}
            ]
        )
        recommendation_raw = response.choices[0].message.content.strip()
    except Exception as e:
        print(e)
        return jsonify({
            "prediction": None,
            "reason": None,
            "full_text": "Unable to generate a recommendation. Please try again later."
        }), 500

    # Extract structured parts
    prediction = ""
    reason = ""
    for line in recommendation_raw.splitlines():
        if line.startswith("- Predicted 5km Time:"):
            prediction = line.replace("- Predicted 5km Time:", "").strip()
        elif line.startswith("- Reason:"):
            reason = line.replace("- Reason:", "").strip()

    # Fallback if extraction fails
    if not prediction or not reason:
        # Try basic sentence extraction
        sentences = recommendation_raw.split(". ")
        prediction = sentences[0].strip() + '.' if len(sentences) > 0 else ""
        reason = sentences[1].strip() + '.' if len(sentences) > 1 else ""

    if not drills:
        reason += " Note: More data is needed to provide tailored recommendations in the future."

    return jsonify({
        "prediction": prediction,
        "reason": reason,
        "full_text": recommendation_raw
    })


@app.route('/set_goal/<int:member_id>', methods=['POST'])
def set_goal(member_id):
    new_target_time = request.form['target_time']

    conn = get_db_connection()
    conn.execute('UPDATE team_members SET target_time_5km = ? WHERE id = ?', (new_target_time, member_id))
    conn.commit()
    conn.close()
    flash('Goal updated successfully!', 'success')
    return redirect(url_for('view_member', member_id=member_id))

@app.route('/')
def index():
    return render_template('landing.html')
@app.route('/main')
def main():
    if 'user_id' not in session:
        flash('Please log in to access the dashboard.', 'warning')
        return redirect(url_for('login'))

    ensure_coach_notes_schema()  # make sure table/column exists

    conn = get_db_connection()
    try:
        user = conn.execute('SELECT fullname, role FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if not user:
            flash('User not found. Please log in again.', 'danger')
            return redirect(url_for('login'))

        fullname = user['fullname']
        role = user['role']

        # Manager sees their latest note; others see latest note from any Manager
        if role == 'Manager':
            coach_data = conn.execute(
                'SELECT * FROM coach_notes WHERE user_id = ? ORDER BY updated_at DESC, id DESC LIMIT 1',
                (session['user_id'],)
            ).fetchone()
        else:
            coach_data = conn.execute('''
                SELECT cn.*
                FROM coach_notes cn
                JOIN users u ON u.id = cn.user_id
                WHERE u.role = 'Manager'
                ORDER BY cn.updated_at DESC, cn.id DESC
                LIMIT 1
            ''').fetchone()

        # Member quick link (if you actually want the team_members id, grab from that table)
        member_id = None
        tm = conn.execute(
            'SELECT tm.id FROM team_members tm WHERE tm.user_id = ? LIMIT 1',
            (session['user_id'],)
        ).fetchone()
        member_id = tm['id'] if tm else None

        team_members = conn.execute('SELECT * FROM team_members').fetchall()

        return render_template(
            'index.html',
            fullname=fullname,
            role=role,
            member_id=member_id,
            team_members=team_members,
            coach_data=coach_data
        )
    finally:
        conn.close()
def ensure_coach_notes_schema():
    conn = get_db_connection()
    try:
        # Create table if missing
        conn.execute('''
        CREATE TABLE IF NOT EXISTS coach_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            reminder TEXT,
            race_date TEXT,
            race_time TEXT,
            location TEXT,
            weather TEXT,
            requirements TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        # If table existed without updated_at, add it
        cols = [r['name'] for r in conn.execute("PRAGMA table_info(coach_notes)").fetchall()]
        if 'updated_at' not in cols:
            conn.execute("ALTER TABLE coach_notes ADD COLUMN updated_at DATETIME")
        conn.commit()
    finally:
        conn.close()





@app.route('/add_drill/<int:member_id>', methods=['GET', 'POST'])
def add_drill(member_id):
    conn = get_db_connection()
    if request.method == 'POST':
        date = request.form['date']
        drill = request.form['drill']
        duration = request.form['duration']
        conn.execute('INSERT INTO training_drills (member_id, date, drill, duration) VALUES (?, ?, ?, ?)',
                     (member_id, date, drill, duration))
        conn.commit()
        conn.close()
        return redirect(url_for('view_member', member_id=member_id))
    conn.close()
    return render_template('add_drill.html', member_id=member_id)
@app.route('/view_member/<int:member_id>')
def view_member(member_id):
    conn = get_db_connection()
    member = conn.execute('SELECT * FROM team_members WHERE id = ?', (member_id,)).fetchone()
    drills = conn.execute('SELECT * FROM training_drills WHERE member_id = ?', (member_id,)).fetchall()

    # All scores (kept as-is)
    best_scores = conn.execute('''
        SELECT * 
        FROM best_scores 
        WHERE member_id = ? 
        ORDER BY distance, time ASC
    ''', (member_id,)).fetchall()

    fivek_records = conn.execute('''
        SELECT date, time
        FROM best_scores
        WHERE member_id = ? AND ABS(distance - 5.0) < 0.01
        ORDER BY date
    ''', (member_id,)).fetchall()

    progress_dates = [row['date'] for row in fivek_records]
    progress_values = [row['time'] for row in fivek_records]

    best_time_row = conn.execute('''
        SELECT MIN(time) AS best_time
        FROM best_scores
        WHERE member_id = ? AND ABS(distance - 5.0) < 0.01
    ''', (member_id,)).fetchone()
    best_time = best_time_row['best_time'] if best_time_row and best_time_row['best_time'] is not None else None

    # Drill distribution (unchanged)
    drill_types = ['Endurance', 'Speed Training', 'Hill Repeats', 'Interval Training']
    drill_counts = [sum(1 for d in drills if d['drill'] == dtype) for dtype in drill_types]

    conn.close()
    if not member:
        return "Member not found", 404

    return render_template(
        'view_member.html',
        member=member,
        drills=drills,
        best_scores=best_scores,
        total_distance=sum(row['distance'] for row in best_scores),
        progress_dates=progress_dates,
        progress_values=progress_values,
        drill_types=drill_types,
        drill_counts=drill_counts,
        best_time=best_time   # 👉 pass this to template
    )


@app.route('/update_progress/<int:member_id>', methods=['POST'])
def update_progress(member_id):
    new_progress = request.form['goal_progress']
    new_target = request.form['goal_target']

    conn = get_db_connection()
    conn.execute(
        'UPDATE team_members SET goal_progress = ?, goal_target = ? WHERE id = ?',
        (new_progress, new_target, member_id)
    )
    conn.commit()
    conn.close()

    flash('Progress updated successfully!', 'success')
    return redirect(url_for('view_member', member_id=member_id))

@app.route('/manage_team', methods=['GET', 'POST'])
def manage_team():
    if 'user_id' not in session:
        flash('Please log in to manage your team.', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form['name']
        role = request.form['role']
        email = request.form['email']
        image = request.files['image']

        filename = None
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn.execute(
            'INSERT INTO team_members (user_id, name, role, email, image) VALUES (?, ?, ?, ?, ?)',
            (session['user_id'], name, role, email, filename)
        )
        conn.commit()

        # Fetch updated team members
        team_members = conn.execute(
            'SELECT * FROM team_members WHERE user_id = ?',
            (session['user_id'],)
        ).fetchall()
        conn.close()

        # Return updated members dynamically
        return jsonify({'status': 'success', 'team_members': [dict(member) for member in team_members]})

    team_members = conn.execute(
        'SELECT * FROM team_members WHERE user_id = ?',
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return render_template('manage_team.html', team_members=team_members)

@app.route('/manage_skills', methods=['GET', 'POST'])
def manage_skills():
    conn = get_db_connection()
    if request.method == 'POST':
        skill = request.form['skill']
        description = request.form['description']
        conn.execute('INSERT INTO training_skills (skill, description) VALUES (?, ?)', (skill, description))
        conn.commit()
    training_skills = conn.execute('SELECT * FROM training_skills').fetchall()
    conn.close()
    return render_template('manage_skills.html', training_skills=training_skills)
@app.route('/add_score/<int:member_id>', methods=['POST'])
def add_score(member_id):
    conn = get_db_connection()
    if request.method == 'POST':
        try:
            # no distance from form anymore
            distance = 5.0
            time_val = float(request.form['time'])
        except (ValueError, KeyError):
            flash('Time must be a number (e.g., 21.5).', 'danger')
            conn.close()
            return redirect(url_for('view_member', member_id=member_id))

        date = request.form['date']
        conn.execute(
            'INSERT INTO best_scores (member_id, distance, time, date) VALUES (?, ?, ?, ?)',
            (member_id, distance, time_val, date)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('view_member', member_id=member_id))
from datetime import datetime, timedelta

def compute_duration_minutes(date_str, bed_str, wake_str):
    bed = datetime.fromisoformat(f"{date_str}T{bed_str}:00")
    wake = datetime.fromisoformat(f"{date_str}T{wake_str}:00")
    if wake <= bed:
        wake += timedelta(days=1)
    return int((wake - bed).total_seconds() // 60)
@app.route('/add_sleep/<int:member_id>', methods=['POST'])
def add_sleep(member_id):
    date = request.form['sleep_date']
    bedtime = request.form['bedtime']
    waketime = request.form['waketime']
    quality = request.form.get('quality') or None
    notes = request.form.get('notes', '')

    dur_min = compute_duration_minutes(date, bedtime, waketime)

    conn = get_db_connection()
    conn.execute("""
      INSERT INTO sleep_logs (member_id, date, bedtime, waketime, duration_minutes, quality, notes)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (member_id, date, bedtime, waketime, dur_min, int(quality) if quality else None, notes))
    conn.commit()
    conn.close()
    return redirect(url_for('view_member', member_id=member_id))
@app.route('/sleep_logs/<int:member_id>', methods=['GET'])
def sleep_logs(member_id):
    # Optional paging
    limit = int(request.args.get('limit', 14))
    offset = int(request.args.get('offset', 0))
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT id, date, bedtime, waketime, duration_minutes, quality, notes
        FROM sleep_logs
        WHERE member_id = ?
        ORDER BY date DESC
        LIMIT ? OFFSET ?
    """, (member_id, limit, offset)).fetchall()
    total = conn.execute("""
        SELECT COUNT(*) FROM sleep_logs WHERE member_id = ?
    """, (member_id,)).fetchone()[0]
    conn.close()

    return jsonify({
        "logs": [dict(r) for r in rows],
        "has_more": offset + limit < total
    })
@app.route('/gallery')
def gallery():
    return render_template('gallery.html')

@app.route('/sleep_series/<int:member_id>', methods=['GET'])
def sleep_series(member_id):
    # for chart (last 30 days)
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT date, duration_minutes, quality
        FROM sleep_logs
        WHERE member_id = ?
        ORDER BY date
        LIMIT 60
    """, (member_id,)).fetchall()
    conn.close()

    series = [{
        "date": r["date"],
        "hours": round(r["duration_minutes"] / 60.0, 2),
        "quality": r["quality"]
    } for r in rows]

    return jsonify(series)

@app.route('/training_drills_events/<int:member_id>', methods=['GET'])
def training_drills_events(member_id):
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT id, date, drill, duration
        FROM training_drills
        WHERE member_id = ?
        ORDER BY date
    ''', (member_id,)).fetchall()
    conn.close()

    # FullCalendar expects: [{ title, start, ... }]
    events = [{
        "id": row["id"],
        "title": f'{row["drill"]} ({row["duration"]} min)',
        "start": row["date"],  # YYYY-MM-DD
        "allDay": True
    } for row in rows]

    return jsonify(events)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        try:
            user = conn.execute(
                'SELECT * FROM users WHERE name = ? AND password = ?',
                (username, password)
            ).fetchone()

            if user:
                # sqlite3.Row -> use [] or wrap as dict
                # If the column doesn't exist yet (pre-migration), default to approved.
                is_approved = dict(user).get('is_approved', 1)

                if is_approved == 0:
                    flash('Your account is pending approval. Please try again later.', 'warning')
                    return redirect(url_for('login'))

                session['user_id'] = user['id']
                session['user_name'] = user['name']
                flash('Login successful!', 'success')
                return redirect(url_for('main'))
            else:
                flash('Invalid username or password', 'danger')
        finally:
            conn.close()

    return render_template('login.html')

import time
@app.route('/pending-users', methods=['GET'])
def pending_users():
    if 'user_id' not in session:
        return jsonify({'users': []}), 200
    # (Optional) verify the session user is a Manager, if you store roles on users
    conn = get_db_connection()
    rows = conn.execute('SELECT id, name, email FROM users WHERE IFNULL(is_approved,0) = 0').fetchall()
    conn.close()
    return jsonify({'users': [dict(r) for r in rows]})

@app.route('/approve-user/<int:user_id>', methods=['POST'])
def approve_user(user_id):
    if 'user_id' not in session:
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 403

    conn = get_db_connection()

    # Approve the user
    conn.execute(
        'UPDATE users SET is_approved = 1 WHERE id = ?',
        (user_id,)
    )

    # Get the user's name (or other details for the team_members table)
    user = conn.execute(
        'SELECT name FROM users WHERE id = ?',
        (user_id,)
    ).fetchone()

    if user:
        # Check if they are already in team_members to avoid duplicates
        existing = conn.execute(
            'SELECT id FROM team_members WHERE user_id = ?',
            (user_id,)
        ).fetchone()

        if not existing:
            conn.execute(
                'INSERT INTO team_members (user_id, name) VALUES (?, ?)',
                (user_id, user['name'])
            )

    conn.commit()
    conn.close()

    return jsonify({'ok': True})


@app.route('/reject-user/<int:user_id>', methods=['POST'])
def reject_user(user_id):
    if 'user_id' not in session:
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 403
    conn = get_db_connection()
    # Simple reject = delete user; or you could add a status column instead
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['name']
        fullname = request.form['fullname']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        profile_image = request.files['profile_image']

        # Check if passwords match
        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('register'))

        # Handle the uploaded profile image
        filename = None
        if profile_image and allowed_file(profile_image.filename):
            # Generate a unique file name
            extension = profile_image.filename.rsplit('.', 1)[1].lower()
            filename = f"profile_{username}_{int(time.time())}.{extension}"
            profile_image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db_connection()
        try:
            # Insert the new user into the users table
            conn.execute(
                'INSERT INTO users (name, email, password, is_approved) VALUES (?, ?, ?, ?)',
                (username, email, password, 0)
            )
            # Get the user ID of the newly inserted user
            user_id = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()['id']

            # Insert the new member into the team_members table
            conn.execute(
                'INSERT INTO team_members (user_id, name, role, email, image) VALUES (?, ?, ?, ?, ?)',
                (user_id, fullname, 'Member', email, filename)
            )
            conn.commit()

            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already registered.', 'warning')
        finally:
            conn.close()

    return render_template('register.html')



@app.route('/training_drills/<int:member_id>', methods=['GET'])
def training_drills(member_id):
    limit = int(request.args.get('limit', 7))  # Default to 7 rows
    offset = int(request.args.get('offset', 0))  # Default to the first page

    conn = get_db_connection()
    drills = conn.execute('''
        SELECT * FROM training_drills
        WHERE member_id = ?
        LIMIT ? OFFSET ?
    ''', (member_id, limit, offset)).fetchall()

    total_drills = conn.execute('SELECT COUNT(*) FROM training_drills WHERE member_id = ?', (member_id,)).fetchone()[0]
    conn.close()

    return jsonify({
        'drills': [dict(drill) for drill in drills],
        'has_more': offset + limit < total_drills  # Check if there are more rows to load
    })
@app.route('/record_history/<int:member_id>', methods=['GET'])
def record_history(member_id):
    limit = int(request.args.get('limit', 7))
    offset = int(request.args.get('offset', 0))

    conn = get_db_connection()
    try:
        records = conn.execute('''
            SELECT time, date
            FROM best_scores
            WHERE member_id = ?
              AND CAST(distance AS REAL) BETWEEN 4.95 AND 5.05
            ORDER BY date
            LIMIT ? OFFSET ?
        ''', (member_id, limit, offset)).fetchall()

        total_records = conn.execute('''
            SELECT COUNT(*)
            FROM best_scores
            WHERE member_id = ?
              AND CAST(distance AS REAL) BETWEEN 4.95 AND 5.05
        ''', (member_id,)).fetchone()[0]

        return jsonify({
            'records': [dict(record) for record in records],
            'has_more': offset + limit < total_records
        })
    except Exception as e:
        print(f"Error in /record_history: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()




@app.route('/logout')
def logout():
    session.clear()  # Clear the session
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))
@app.route('/team_members', methods=['GET'])
def team_members():
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 6))
    offset = (page - 1) * limit

    # read sort params from query
    sort = (request.args.get('sort') or 'name').lower()
    direction = (request.args.get('dir') or 'asc').lower()
    direction = 'DESC' if direction == 'desc' else 'ASC'

    # only allow known columns to prevent SQL injection
    sort_map = {
        'name': 'tm.name',
        'role': 'tm.role',
        'created': 'tm.id',          # use id as "recently added" if you don't have created_at
        'best_time': 'bt.best_time'  # from subquery below
    }
    order_col = sort_map.get(sort, 'tm.name')

    conn = get_db_connection()

    # LEFT JOIN a subquery to get each member’s best 5k time
    # only include members whose owning user is approved
    # handle NULLS for best_time so they sort to the end on ASC
    if order_col == 'bt.best_time' and direction == 'ASC':
        order_clause = 'CASE WHEN bt.best_time IS NULL THEN 1 ELSE 0 END, bt.best_time ASC'
    elif order_col == 'bt.best_time' and direction == 'DESC':
        order_clause = 'CASE WHEN bt.best_time IS NULL THEN 1 ELSE 0 END, bt.best_time DESC'
    else:
        order_clause = f'{order_col} {direction}'

    members = conn.execute(f'''
        SELECT tm.*, bt.best_time
        FROM team_members tm
        JOIN users u ON u.id = tm.user_id
        LEFT JOIN (
            SELECT member_id, MIN(time) AS best_time
            FROM best_scores
            WHERE ABS(distance - 5.0) < 0.01
            GROUP BY member_id
        ) bt ON bt.member_id = tm.id
        WHERE COALESCE(u.is_approved, 0) = 1
        ORDER BY {order_clause}
        LIMIT ? OFFSET ?
    ''', (limit, offset)).fetchall()

    total_members = conn.execute('''
        SELECT COUNT(*)
        FROM team_members tm
        JOIN users u ON u.id = tm.user_id
        WHERE COALESCE(u.is_approved, 0) = 1
    ''').fetchone()[0]

    conn.close()

    return jsonify({
        'members': [dict(m) for m in members],
        'has_more': offset + limit < total_members
    })

@app.route('/save_coach_notes', methods=['POST'])
def save_coach_notes():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 403

    conn = get_db_connection()
    try:
        # enforce role check
        role = conn.execute('SELECT role FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if not role or role['role'] != 'Manager':
            return jsonify({'success': False, 'error': 'Only managers can save coach notes'}), 403

        data = request.get_json()
        existing = conn.execute(
            'SELECT id FROM coach_notes WHERE user_id = ?',
            (session['user_id'],)
        ).fetchone()

        if existing:
            conn.execute('''
                UPDATE coach_notes
                SET reminder = ?, race_date = ?, race_time = ?, location = ?, weather = ?, requirements = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (data['reminder'], data['race_date'], data['race_time'],
                  data['location'], data['weather'], data['requirements'], session['user_id']))
        else:
            conn.execute('''
                INSERT INTO coach_notes (user_id, reminder, race_date, race_time, location, weather, requirements, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (session['user_id'], data['reminder'], data['race_date'], data['race_time'],
                  data['location'], data['weather'], data['requirements']))
        conn.commit()
        return jsonify({'success': True})
    finally:
        conn.close()

@app.route('/chart-data', methods=['GET'])
def chart_data():
    gran = (request.args.get('gran') or 'week').lower()
    if gran not in ('day', 'week', 'month'):
        gran = 'week'

    if gran == 'day':
        group_fmt = "%Y-%m-%d"
        date_from_sql = "date('now','-29 days')"  # last 30 days
    elif gran == 'week':
        group_fmt = "%Y-%W"
        date_from_sql = "date('now','-84 days')"  # ~12 weeks
    else:
        group_fmt = "%Y-%m"
        date_from_sql = "date('now','start of month','-11 months')"  # last 12 months incl. current

    conn = get_db_connection()

    # Progress Over Time (approved users only)
    progress_data = conn.execute(f'''
        SELECT strftime('{group_fmt}', bs.date) AS grp, AVG(bs.time) AS avg_time
        FROM best_scores bs
        JOIN team_members tm ON bs.member_id = tm.id
        JOIN users u ON u.id = tm.user_id
        WHERE ABS(bs.distance - 5.0) < 0.01
          AND bs.date >= {date_from_sql}
          AND COALESCE(u.is_approved, 0) = 1
        GROUP BY grp
        ORDER BY grp
    ''').fetchall()
    progress_over_time = {
        'labels': [row['grp'] for row in progress_data],
        'times':  [row['avg_time'] for row in progress_data]
    }

    # Drill Distribution (approved users only)
    drill_data = conn.execute(f'''
        SELECT td.drill, COUNT(*) AS count
        FROM training_drills td
        JOIN team_members tm ON td.member_id = tm.id
        JOIN users u ON u.id = tm.user_id
        WHERE td.date >= {date_from_sql}
          AND COALESCE(u.is_approved, 0) = 1
        GROUP BY td.drill
        ORDER BY count DESC
    ''').fetchall()
    drill_distribution = {
        'drills': [row['drill'] for row in drill_data],
        'counts': [row['count'] for row in drill_data]
    }

    # Top Performers (approved users only)
    top_performers = conn.execute(f'''
        SELECT tm.name, MIN(bs.time) AS best_time
        FROM best_scores bs
        JOIN team_members tm ON bs.member_id = tm.id
        JOIN users u ON u.id = tm.user_id
        WHERE ABS(bs.distance - 5.0) < 0.01
          AND bs.date >= {date_from_sql}
          AND COALESCE(u.is_approved, 0) = 1
        GROUP BY tm.name
        HAVING best_time IS NOT NULL
        ORDER BY best_time ASC
        LIMIT 5
    ''').fetchall()
    top_performers_data = {
        'names': [r['name'] for r in top_performers],
        'times': [r['best_time'] for r in top_performers]
    }

    # Goal Completion (approved users only, overall)
    goal_rows = conn.execute('''
        SELECT tm.name,
               tm.target_time_5km AS target_time,
               MIN(bs.time) AS best_time
        FROM team_members tm
        JOIN users u ON u.id = tm.user_id
        LEFT JOIN best_scores bs
          ON tm.id = bs.member_id AND ABS(bs.distance - 5.0) < 0.01
        WHERE COALESCE(u.is_approved, 0) = 1
        GROUP BY tm.id
    ''').fetchall()

    def pct(target, best):
        if target is None or best is None or target <= 0:
            return 0
        return min(100.0, max(0.0, (target / best) * 100.0))

    goal_completion_data = {
        'names': [r['name'] for r in goal_rows],
        'percentages': [pct(r['target_time'], r['best_time']) for r in goal_rows]
    }

    conn.close()
    return jsonify({
        'gran': gran,
        'progress_over_time': progress_over_time,
        'drill_distribution': drill_distribution,
        'top_performers': top_performers_data,
        'goal_completion': goal_completion_data
    })


@app.route('/leader-data', methods=['GET'])
def leader_data():
    conn = get_db_connection()

    # Overall fastest 5k (approved users only)
    overall = conn.execute('''
        SELECT tm.name, MIN(bs.time) AS best_time
        FROM best_scores bs
        JOIN team_members tm ON bs.member_id = tm.id
        JOIN users u ON u.id = tm.user_id
        WHERE ABS(bs.distance - 5.0) < 0.01
          AND COALESCE(u.is_approved, 0) = 1
        GROUP BY tm.name
        ORDER BY best_time ASC
        LIMIT 5
    ''').fetchall()
    total_top = {
        'names': [r['name'] for r in overall],
        'times': [r['best_time'] for r in overall]
    }

    # This month's fastest 5k (approved users only)
    current_month = conn.execute('SELECT strftime("%Y-%m", "now")').fetchone()[0]
    monthly = conn.execute('''
        SELECT tm.name, MIN(bs.time) AS best_time
        FROM best_scores bs
        JOIN team_members tm ON bs.member_id = tm.id
        JOIN users u ON u.id = tm.user_id
        WHERE ABS(bs.distance - 5.0) < 0.01
          AND strftime("%Y-%m", bs.date) = ?
          AND COALESCE(u.is_approved, 0) = 1
        GROUP BY tm.name
        ORDER BY best_time ASC
        LIMIT 5
    ''', (current_month,)).fetchall()
    monthly_top = {
        'names': [r['name'] for r in monthly],
        'times': [r['best_time'] for r in monthly]
    }

    conn.close()
    return jsonify({
        'top_performers': total_top,
        'monthly_top_performers': monthly_top
    })


if __name__ == '__main__':
    # init_db()
    app.run(debug=True)
