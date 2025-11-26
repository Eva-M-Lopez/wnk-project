from flask import session, request, redirect
from .db import get_db

def ensure_dev_user():
    if "user" in session:
        return

def _dev_login(email, role, first, last):
    con = get_db()
    try:
        with con.cursor() as cur:
            cur.execute("SELECT user_id, first_name FROM users WHERE email=%s", (email,))
            row = cur.fetchone()
            if not row:
                cur.execute("""
                    INSERT INTO users (role, first_name, last_name, email, password_hash,
                                       addr_line1, city, state, zip)
                    VALUES (%s,%s,%s,%s,'x','1 Dev St','Orlando','FL','32816')
                """, (role, first, last, email))
                con.commit()
                uid = cur.lastrowid
            else:
                uid = row["user_id"]
            session["user"] = {"user_id": int(uid), "role": role, "first_name": first}
    finally:
        con.close()

def maybe_switch_user():
    as_role = request.args.get("as")
    if not as_role:
        return
    return redirect(request.path)