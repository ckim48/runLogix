# seed_training.py
import sqlite3, argparse, random
from datetime import date, timedelta

def conn(db):
    c = sqlite3.connect(db); c.row_factory = sqlite3.Row; return c

def ensure_schema(db):
    c = conn(db); cur = c.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS team_members(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL, name TEXT, role TEXT, email TEXT, image TEXT,
      target_time_5km REAL, goal_progress TEXT, goal_target TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS training_drills(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      member_id INTEGER NOT NULL,
      date TEXT NOT NULL, drill TEXT NOT NULL, duration INTEGER NOT NULL)""")
    c.commit(); c.close()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="crosscountry.db")
    ap.add_argument("--sessions", type=int, default=24, help="sessions per member")
    ap.add_argument("--days", type=int, default=84, help="look-back window in days")
    args = ap.parse_args()

    ensure_schema(args.db)
    c = conn(args.db)
    members = c.execute("SELECT id FROM team_members").fetchall()
    if not members:
        print("No team_members found. Seed members first."); return

    drills = ["Endurance","Speed Training","Hill Repeats","Interval Training"]
    today = date.today()

    inserted = 0
    for m in members:
        for _ in range(args.sessions):
            d = today - timedelta(days=random.randint(5, args.days))
            drill = random.choice(drills)
            duration = random.choice([30,35,40,45,50,60])
            c.execute("""INSERT INTO training_drills(member_id,date,drill,duration)
                         VALUES(?,?,?,?)""",
                      (m["id"], d.isoformat(), drill, duration))
            inserted += 1

    c.commit(); c.close()
    print(f"Inserted {inserted} training drill rows across {len(members)} member(s).")

if __name__ == "__main__":
    main()
