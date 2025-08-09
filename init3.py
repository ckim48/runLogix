# seed_scores_goals.py
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
    cur.execute("""CREATE TABLE IF NOT EXISTS best_scores(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      member_id INTEGER NOT NULL,
      distance REAL NOT NULL, time REAL NOT NULL, date TEXT NOT NULL)""")
    c.commit(); c.close()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="crosscountry.db")
    ap.add_argument("--weeks", type=int, default=12, help="how many past weeks to seed")
    ap.add_argument("--extra_monthly", type=int, default=2, help="extra current-month attempts/member")
    ap.add_argument("--distance", type=float, default=5.0, help="distance to seed (5.0 for 5k)")
    args = ap.parse_args()

    ensure_schema(args.db)
    c = conn(args.db)
    members = c.execute("SELECT id, name FROM team_members").fetchall()
    if not members:
        print("No team_members found. Seed members first."); return

    today = date.today()
    total_rows = 0

    # Give each runner an individualized baseline
    for idx, m in enumerate(members):
        base = 22.5 - (idx * 0.8)  # slightly faster for earlier members
        # Set/refresh target_time_5km ~ 90–95% of current baseline (smaller is faster)
        target = round(max(16.0, base * 0.92), 2)
        c.execute("UPDATE team_members SET target_time_5km=? WHERE id=?", (target, m["id"]))

        # Weekly history (so your 'week' granularity charts fill in)
        for w in range(args.weeks, -1, -1):
            d = today - timedelta(weeks=w)
            # Improvement trend + noise; lower time = better
            t = max(16.0, base - (args.weeks - w) * 0.08 + random.uniform(-0.45, 0.45))
            c.execute("""INSERT INTO best_scores(member_id,distance,time,date)
                         VALUES(?,?,?,?)""", (m["id"], args.distance, round(t, 2), d.isoformat()))
            total_rows += 1

        # Extra current-month results to feed monthly leaderboard
        for _ in range(args.extra_monthly):
            d = today - timedelta(days=random.randint(0, 20))
            t = round(base + random.uniform(-1.2, 2.2), 2)
            c.execute("""INSERT INTO best_scores(member_id,distance,time,date)
                         VALUES(?,?,?,?)""", (m["id"], args.distance, t, d.isoformat()))
            total_rows += 1

    c.commit(); c.close()
    print(f"Inserted {total_rows} best_scores rows and updated target_time_5km for {len(members)} member(s).")

if __name__ == "__main__":
    main()
