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
@app.route('/get_recommendation/<int:member_id>', methods=['GET'])
def get_recommendation(member_id):
    conn = get_db_connection()
    member = conn.execute('SELECT * FROM team_members WHERE id = ?', (member_id,)).fetchone()
    drills = conn.execute('SELECT * FROM training_drills WHERE member_id = ?', (member_id,)).fetchall()
    conn.close()

    if not member:
        return {"recommendation": "Member not found"}, 404

    # Prepare drill history for GPT
    if drills:
        drill_history = "\n".join([f"{drill['date']}: {drill['drill']} for {drill['duration']} minutes" for drill in drills])
        prompt = f"""
        The following is the drill history of a team member named {member['name']}:
        {drill_history}

        Based on this history, suggest a drill for the next session. Provide a concise explanation for your recommendation.
        """
    else:
        # No drill history available
        prompt = f"""
        There is no historical data for the team member named {member['name']}. 

        Suggest a beginner drill for their next session. Mention that more data is needed for better recommendations.
        """

    # Generate a recommendation using GPT
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a fitness coach."},
                {"role": "user", "content": prompt}
            ]
        )
        recommendation = response.choices[0].message.content.strip()
    except Exception as e:
        print(e)
        recommendation = "Unable to generate a recommendation. Please try again later."

    # Append a note if no historical data exists
    if not drills:
        recommendation += " Note: More data is needed to provide tailored recommendations in the future."

    return {"recommendation": recommendation}
@app.route('/')
def index():
    if 'user_id' not in session:
        flash('Please log in to access the dashboard.', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()

    try:
        # Check if the user is a team member
        user_role = session.get('role')
        if user_role == 'Member':
            # Get the corresponding member ID from the team_members table
            member = conn.execute(
                'SELECT id FROM team_members WHERE email = (SELECT email FROM users WHERE id = ?) LIMIT 1',
                (session['user_id'],)
            ).fetchone()

            if member:
                # Redirect the user to their `view_member` page
                return redirect(url_for('view_member', member_id=member['id']))
            else:
                flash('No associated team member account found.', 'danger')
                return redirect(url_for('login'))

        # For managers, proceed to the index page
        team_members = conn.execute(
            'SELECT * FROM team_members WHERE user_id = ?',
            (session['user_id'],)
        ).fetchall()
        return render_template('index.html', username=session['user_name'], team_members=team_members)

    finally:
        conn.close()


@app.route('/chart-data', methods=['GET'])
def chart_data():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 403

    user_id = session['user_id']
    conn = get_db_connection()

    # Data for Role Distribution (Filtered by user)
    roles = conn.execute('''
        SELECT role, COUNT(*) as count 
        FROM team_members 
        WHERE user_id = ? 
        GROUP BY role
    ''', (user_id,)).fetchall()
    role_data = [{'role': row['role'], 'count': row['count']} for row in roles]

    # Data for Drill Activity Over Time (Filtered by user's team members)
    drills = conn.execute('''
        SELECT date, COUNT(*) as count 
        FROM training_drills 
        WHERE member_id IN (
            SELECT id FROM team_members WHERE user_id = ?
        ) 
        GROUP BY date 
        ORDER BY date
    ''', (user_id,)).fetchall()
    drill_data = [{'date': row['date'], 'count': row['count']} for row in drills]

    # Data for Average Drill Duration by Member (Filtered by user's team members)
    durations = conn.execute('''
        SELECT tm.name, AVG(td.duration) as avg_duration 
        FROM training_drills td 
        JOIN team_members tm ON td.member_id = tm.id 
        WHERE tm.user_id = ? 
        GROUP BY tm.name
    ''', (user_id,)).fetchall()
    duration_data = [{'name': row['name'], 'avg_duration': row['avg_duration']} for row in durations]

    # Data for Best Scores Analysis (Filtered by user's team members)
    scores = conn.execute('''
        SELECT tm.name, bs.distance, bs.time 
        FROM best_scores bs 
        JOIN team_members tm ON bs.member_id = tm.id 
        WHERE tm.user_id = ?
    ''', (user_id,)).fetchall()
    score_data = [{'name': row['name'], 'distance': row['distance'], 'time': row['time']} for row in scores]

    conn.close()
    return jsonify({
        'role_data': role_data,
        'drill_data': drill_data,
        'duration_data': duration_data,
        'score_data': score_data
    })

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

    # Fetch scores sorted by distance and time
    best_scores = conn.execute('''
        SELECT * 
        FROM best_scores 
        WHERE member_id = ? 
        ORDER BY distance, time ASC
    ''', (member_id,)).fetchall()

    conn.close()
    if not member:
        return "Member not found", 404
    return render_template('view_member.html', member=member, drills=drills, best_scores=best_scores)

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
        distance = request.form['distance']
        time = request.form['time']
        date = request.form['date']
        conn.execute(
            'INSERT INTO best_scores (member_id, distance, time, date) VALUES (?, ?, ?, ?)',
            (member_id, distance, time, date)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('view_member', member_id=member_id))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        try:
            # Check the users table for a matching username and password
            user = conn.execute('SELECT * FROM users WHERE name = ? AND password = ?', (username, password)).fetchone()

            if user:
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['role'] = user['role']

                # Check if the user is a member
                if user['role'] == 'Member':
                    # Verify the member's email in the team_members table
                    member = conn.execute(
                        'SELECT * FROM team_members WHERE email = (SELECT email FROM users WHERE id = ?) LIMIT 1',
                        (user['id'],)
                    ).fetchone()

                    if member:
                        # Redirect to the corresponding view_member page
                        flash('Login successful!', 'success')
                        return redirect(url_for('view_member', member_id=member['id']))
                    else:
                        flash('You are not associated with a team member account.', 'danger')
                        return redirect(url_for('login'))

                # If the user is a manager, redirect to the index page
                flash('Login successful!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password', 'danger')
        finally:
            conn.close()

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = request.form['role']

        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('register'))

        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)',
                (name, email, password, role)
            )
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already registered.', 'warning')
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()  # Clear the session
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
