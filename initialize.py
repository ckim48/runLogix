import sqlite3
def init_db():
    conn = sqlite3.connect('crosscountry.db')
    cursor = conn.cursor()

    # Check if `manager_id` column exists in `team_members`
    cursor.execute('PRAGMA table_info(team_members)')
    columns = [col[1] for col in cursor.fetchall()]
    if 'manager_id' not in columns:
        cursor.execute('ALTER TABLE team_members ADD COLUMN manager_id INTEGER REFERENCES users(id)')

    # Update mock data to include `manager_id` where `users.role = 'Manager'`
    cursor.execute('UPDATE team_members SET manager_id = (SELECT id FROM users WHERE name = "JohnDoe" AND role = "Manager") WHERE user_id = 1')
    cursor.execute('UPDATE team_members SET manager_id = (SELECT id FROM users WHERE name = "JaneSmith" AND role = "Manager") WHERE user_id = 2')
    cursor.execute('UPDATE team_members SET manager_id = (SELECT id FROM users WHERE name = "TestUser" AND role = "Manager") WHERE user_id = 3')

    conn.commit()
    conn.close()

init_db()