import sqlite3

def init_db():
    conn = sqlite3.connect('crosscountry.db')
    cursor = conn.cursor()

    # Create table for team members
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS team_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        email TEXT NOT NULL
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

    # Add mock data
    cursor.executemany('''
    INSERT INTO team_members (name, role, email)
    VALUES (?, ?, ?)
    ''', [
        ('John Doe', 'Runner', 'john@example.com'),
        ('Jane Smith', 'Coach', 'jane@example.com'),
        ('Alice Johnson', 'Runner', 'alice@example.com')
    ])

    cursor.executemany('''
    INSERT INTO training_skills (skill, description)
    VALUES (?, ?)
    ''', [
        ('Endurance', 'Increase stamina for long runs'),
        ('Speed', 'Improve sprinting ability'),
        ('Agility', 'Enhance quick movements and coordination')
    ])

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
