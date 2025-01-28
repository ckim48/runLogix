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
    total_distance = conn.execute('''
        SELECT SUM(distance) AS total_distance
        FROM best_scores
        WHERE member_id = ?
    ''', (member_id,)).fetchone()['total_distance'] or 0
    conn.close()

    if not member:
        return {"recommendation": "Member not found"}, 404

    # Calculate goal progress percentage
    goal_target = member['goal_target'] or 0
    progress_percentage = (total_distance / goal_target) * 100 if goal_target > 0 else 0

    # Prepare drill history and progress for GPT
    drill_history = "\n".join([f"{drill['date']}: {drill['drill']} for {drill['duration']} minutes" for drill in drills]) or "No historical data available."
    goal_progress_info = f"Current progress: {total_distance} km out of {goal_target} km ({progress_percentage:.1f}%)."

    # Construct the GPT prompt
    prompt = f"""
    Here is the historical drill data and goal progress for a team member:
    Drill History:
    {drill_history}

    {goal_progress_info}

    Based on this, suggest a drill for the next session. Provide a concise explanation for your recommendation. Use two bullet points for two recommendation, each with a maximum of two sentences.
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

@app.route('/set_goal/<int:member_id>', methods=['POST'])
def set_goal(member_id):
    new_goal = request.form['goal']
    conn = get_db_connection()
    conn.execute('UPDATE team_members SET goal_target = ? WHERE id = ?', (new_goal, member_id))
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

    conn = get_db_connection()

    try:
        # Fetch the full name and role of the logged-in user
        user = conn.execute('SELECT fullname, role FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if not user:
            flash('User not found. Please log in again.', 'danger')
            return redirect(url_for('login'))

        fullname = user['fullname']
        role = user['role']

        # If the user is a team member, get their corresponding member ID
        member_id = None
        if role == 'Member':
            member = conn.execute('SELECT id FROM users WHERE name = ?', (session['user_name'],)).fetchone()
            member_id = member['id'] if member else None
            print(member_id)
        # Fetch all team members from the database
        team_members = conn.execute('SELECT * FROM team_members').fetchall()

        return render_template('index.html', fullname=fullname, role=role, member_id=member_id, team_members=team_members)

    finally:
        conn.close()
@app.route('/chart-data', methods=['GET'])
def chart_data():
    conn = get_db_connection()

    # Progress Over Time (Sum of weekly distances for all members)
    progress_data = conn.execute('''
        SELECT strftime('%Y-%W', date) as week, SUM(distance) as total_distance
        FROM best_scores
        GROUP BY week
        ORDER BY week
    ''').fetchall()

    progress_over_time = {
        'weeks': [row['week'] for row in progress_data],
        'distances': [row['total_distance'] for row in progress_data]
    }

    # Drill Distribution
    drill_data = conn.execute('''
        SELECT drill, COUNT(*) as count
        FROM training_drills
        GROUP BY drill
    ''').fetchall()

    drill_distribution = {
        'drills': [row['drill'] for row in drill_data],
        'counts': [row['count'] for row in drill_data]
    }

    # Top Performers
    top_performers = conn.execute('''
        SELECT tm.name, SUM(bs.distance) as total_distance
        FROM best_scores bs
        JOIN team_members tm ON bs.member_id = tm.id
        GROUP BY tm.name
        ORDER BY total_distance DESC
        LIMIT 5
    ''').fetchall()

    top_performers_data = {
        'names': [row['name'] for row in top_performers],
        'distances': [row['total_distance'] for row in top_performers]
    }

    # Goal Completion
    goal_completion = conn.execute('''
        SELECT tm.name, tm.goal_target, COALESCE(SUM(bs.distance), 0) as total_distance
        FROM team_members tm
        LEFT JOIN best_scores bs ON tm.id = bs.member_id
        GROUP BY tm.id
    ''').fetchall()

    goal_completion_data = {
        'names': [row['name'] for row in goal_completion],
        'percentages': [
            (row['total_distance'] / row['goal_target']) * 100 if row['goal_target'] > 0 else 0
            for row in goal_completion
        ]
    }

    conn.close()

    return jsonify({
        'progress_over_time': progress_over_time,
        'drill_distribution': drill_distribution,
        'top_performers': top_performers_data,
        'goal_completion': goal_completion_data
    })

@app.route('/leader-data', methods=['GET'])
def leader_data():
    conn = get_db_connection()

    # Total Distance Leaderboard
    top_performers = conn.execute('''
        SELECT tm.name, SUM(bs.distance) as total_distance
        FROM best_scores bs
        JOIN team_members tm ON bs.member_id = tm.id
        GROUP BY tm.name
        ORDER BY total_distance DESC
        LIMIT 5
    ''').fetchall()

    total_top_performers = {
        'names': [row['name'] for row in top_performers],
        'distances': [row['total_distance'] for row in top_performers]
    }

    # Monthly Distance Leaderboard
    current_month = conn.execute('SELECT strftime("%Y-%m", "now")').fetchone()[0]
    monthly_performers = conn.execute('''
        SELECT tm.name, SUM(bs.distance) as total_distance
        FROM best_scores bs
        JOIN team_members tm ON bs.member_id = tm.id
        WHERE strftime("%Y-%m", bs.date) = ?
        GROUP BY tm.name
        ORDER BY total_distance DESC
        LIMIT 5
    ''', (current_month,)).fetchall()

    monthly_top_performers = {
        'names': [row['name'] for row in monthly_performers],
        'distances': [row['total_distance'] for row in monthly_performers]
    }

    conn.close()

    return jsonify({
        'top_performers': total_top_performers,
        'monthly_top_performers': monthly_top_performers,
        # Include other data as necessary
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

    # Calculate progress data
    progress_dates = [row['date'] for row in drills] if drills else []
    progress_values = [row['duration'] for row in drills] if drills else []

    # Drill distribution data
    drill_types = ['Endurance', 'Speed Training', 'Hill Repeats', 'Interval Training']
    drill_counts = [
        sum(1 for drill in drills if drill['drill'] == dtype)
        for dtype in drill_types
    ]

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
        drill_counts=drill_counts
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

                # Redirect all users to the main page
                flash('Login successful!', 'success')
                return redirect(url_for('main'))
            else:
                flash('Invalid username or password', 'danger')
        finally:
            conn.close()

    return render_template('login.html')
import time

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
                'INSERT INTO users (name, email, password) VALUES (?, ?, ?)',
                (username, email, password)
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
    limit = int(request.args.get('limit', 7))  # Default to 7 rows
    offset = int(request.args.get('offset', 0))  # Default to the first page

    conn = get_db_connection()
    try:
        records = conn.execute('''
            SELECT distance, time, date
            FROM best_scores
            WHERE member_id = ?
            LIMIT ? OFFSET ?
        ''', (member_id, limit, offset)).fetchall()

        total_records = conn.execute('SELECT COUNT(*) FROM best_scores WHERE member_id = ?', (member_id,)).fetchone()[0]

        return jsonify({
            'records': [dict(record) for record in records],
            'has_more': offset + limit < total_records  # Check if there are more rows
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
    page = int(request.args.get('page', 1))  # Default to page 1
    limit = int(request.args.get('limit', 6))  # Default to 6 members per page
    offset = (page - 1) * limit

    conn = get_db_connection()
    members = conn.execute('''
        SELECT * FROM team_members
        LIMIT ? OFFSET ?
    ''', (limit, offset)).fetchall()

    total_members = conn.execute('SELECT COUNT(*) FROM team_members').fetchone()[0]
    conn.close()

    return jsonify({
        'members': [dict(member) for member in members],
        'has_more': offset + limit < total_members  # Check if there are more members to load
    })

if __name__ == '__main__':
    # init_db()
    app.run(debug=True)
