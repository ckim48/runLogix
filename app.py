from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from openai import OpenAI
import os


app = Flask(__name__)

@app.route('/get_recommendation/<int:member_id>', methods=['GET'])
def get_recommendation(member_id):
    conn = get_db_connection()
    member = conn.execute('SELECT * FROM team_members WHERE id = ?', (member_id,)).fetchone()
    drills = conn.execute('SELECT * FROM training_drills WHERE member_id = ?', (member_id,)).fetchall()
    conn.close()

    if not member:
        return {"recommendation": "Member not found"}, 404

    # Prepare drill history for GPT
    drill_history = "\n".join([f"{drill['date']}: {drill['drill']} for {drill['duration']} minutes" for drill in drills])
    prompt = f"""
    The following is the drill history of a team member named {member['name']}:
    {drill_history}

    Based on this history, suggest a drill for the next session. Provide a concise explanation for your recommendation.
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

    return {"recommendation": recommendation}

def get_db_connection():
    conn = sqlite3.connect('crosscountry.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    team_members = conn.execute('SELECT * FROM team_members').fetchall()
    conn.close()
    return render_template('index.html', team_members=team_members)
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
UPLOAD_FOLDER = 'static/images/profiles'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/manage_team', methods=['GET', 'POST'])
def manage_team():
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form['name']
        role = request.form['role']
        email = request.form['email']
        image = request.files['image']

        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            filename = None  # Default to None if no image is uploaded

        # Store the member's details and image filename in the database
        conn.execute('INSERT INTO team_members (name, role, email, image) VALUES (?, ?, ?, ?)',
                     (name, role, email, filename))
        conn.commit()

    team_members = conn.execute('SELECT * FROM team_members').fetchall()
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

if __name__ == '__main__':
    app.run(debug=True)
