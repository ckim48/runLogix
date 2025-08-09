# seed_members.py
import sqlite3, argparse, os

def conn(db):
    c = sqlite3.connect(db); c.row_factory = sqlite3.Row; return c

def ensure_schema(db):
    c = conn(db); cur = c.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT UNIQUE, email TEXT UNIQUE, password TEXT,
      fullname TEXT, role TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS team_members(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      name TEXT NOT NULL, role TEXT NOT NULL,
      email TEXT NOT NULL, image TEXT,
      target_time_5km REAL, goal_progress TEXT, goal_target TEXT,
      FOREIGN KEY(user_id) REFERENCES users(id))""")
    c.commit(); c.close()

def get_user_id(db, username):
    c = conn(db)
    u = c.execute("SELECT id FROM users WHERE name=?", (username,)).fetchone()
    if not u:
        c.execute("""INSERT INTO users(name,email,password,fullname,role)
                     VALUES(?,?,?,?,?)""",
                  (username, f"{username.lower()}@example.com", "pass",
                   username.replace("_"," "), "Manager"))
        c.commit()
        u = c.execute("SELECT id FROM users WHERE name=?", (username,)).fetchone()
    c.close()
    return u["id"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="crosscountry.db")
    ap.add_argument("--user", default="Manager1", help="attach members to this username")
    ap.add_argument("--count", type=int, default=5, help="how many members to add")
    args = ap.parse_args()

    ensure_schema(args.db)
    uid = get_user_id(args.db, args.user)

    names = [
        "Alex Kim","Jordan Lee","Sam Park","Morgan Choi","Taylor Yu",
        "Riley Han","Jamie Seo","Casey Min","Avery Shin","Drew Park"
    ]
    roles = ["Runner","Runner","Runner","Runner","Runner","Runner","Runner","Runner","Runner","Runner"]

    c = conn(args.db)
    existing_emails = {r["email"] for r in c.execute(
        "SELECT email FROM team_members WHERE user_id=?", (uid,)).fetchall()}

    added = 0
    for i, nm in enumerate(names):
        if added >= args.count: break
        email = nm.lower().replace(" ",".") + "@example.com"
        if email in existing_emails: continue
        c.execute("""INSERT INTO team_members(user_id,name,role,email,image,target_time_5km)
                     VALUES(?,?,?,?,?,?)""",
                  (uid, nm, roles[i], email, None, None))
        added += 1
    c.commit(); c.close()
    print(f"Added {added} member(s) to user {args.user}.")

if __name__ == "__main__":
    main()
