import sqlite3
from random import randint, uniform
from faker import Faker
from datetime import datetime, timedelta

def add_mock_data():
    conn = sqlite3.connect('crosscountry.db')
    cursor = conn.cursor()

    fake = Faker()

    # Add mock users
    for _ in range(3):
        name = fake.first_name()
        email = fake.email()
        password = "password123"
        cursor.execute('''
            INSERT OR IGNORE INTO users (name, email, password) VALUES (?, ?, ?)
        ''', (name, email, password))

    # Get all user IDs
    user_ids = [row[0] for row in cursor.execute('SELECT id FROM users').fetchall()]

    # Add mock team members
    for user_id in user_ids:
        member_name = fake.name()
        role = "Runner" if randint(0, 1) else "Coach"
        email = fake.email()
        cursor.execute('''
            INSERT OR IGNORE INTO team_members (user_id, name, role, email) VALUES (?, ?, ?, ?)
        ''', (user_id, member_name, role, email))

    # Get all member IDs
    member_ids = [row[0] for row in cursor.execute('SELECT id FROM team_members').fetchall()]

    # Add mock training drills
    for member_id in member_ids:
        for _ in range(15):  # Each member has 15 drills
            date = (datetime.now() - timedelta(days=randint(1, 100))).strftime('%Y-%m-%d')
            drill = fake.random_element(elements=("Endurance Run", "Interval Training", "Hill Repeats", "Speed Training"))
            duration = randint(20, 90)  # Duration between 20 and 90 minutes
            cursor.execute('''
                INSERT INTO training_drills (member_id, date, drill, duration) VALUES (?, ?, ?, ?)
            ''', (member_id, date, drill, duration))

    # Add mock best scores
    for member_id in member_ids:
        for _ in range(10):  # Each member has 10 records
            distance = round(uniform(5.0, 15.0), 2)  # Distance between 5 and 15 km
            time = round(uniform(15.0, 90.0), 2)  # Time between 15 and 90 minutes
            date = (datetime.now() - timedelta(days=randint(1, 100))).strftime('%Y-%m-%d')
            cursor.execute('''
                INSERT INTO best_scores (member_id, distance, time, date) VALUES (?, ?, ?, ?)
            ''', (member_id, distance, time, date))

    conn.commit()
    conn.close()
    print("Mock data added successfully!")


add_mock_data()
