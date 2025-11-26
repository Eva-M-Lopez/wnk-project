from flask import Blueprint, render_template, session, request, redirect, url_for
from ..db import get_db

bp = Blueprint("needy", __name__)

@bp.route("/free")
def free():
    role = (session.get("user") or {}).get("role", "")
    rows = []

    if role == "NEEDY":
        con = get_db()
        try:
            with con.cursor() as cur:
                # Show all active plates with stock and in the pickup window
                cur.execute("""
                    SELECT
                      p.plate_id,
                      p.title,
                      p.price,
                      p.qty_available,
                      p.window_start,
                      p.window_end,
                      r.display_name
                    FROM plates p
                    JOIN restaurants r ON r.restaurant_id = p.restaurant_id
                    WHERE p.is_active = 1
                      AND p.qty_available > 0
                      AND NOW() BETWEEN p.window_start AND p.window_end
                    ORDER BY p.window_end ASC;
                """)
                for row in cur.fetchall():
                    q = int(row["qty_available"])
                    # free_left = how many units are actually available
                    row["free_left"] = q
                    # max you can claim at once: min(2, stock)
                    row["max_claim"] = max(1, min(2, q))
                    rows.append(row)
        finally:
            con.close()

    # layout.html will handle session['_flash'], so we don't pop it here
    return render_template(
        "free.html",
        title="Free Plates",
        rows=rows,
        role=role
    )


@bp.route("/actions/checkout_free", methods=["POST"])
def checkout_free():
    user = session.get("user") or {}
    if user.get("role") != "NEEDY":
        return ("Needy only", 403)

    plate_id = int(request.form.get("plate_id", 0) or 0)
    qty = max(1, int(request.form.get("qty", 1) or 1))

    con = get_db()
    try:
        with con.cursor() as cur:
            # 1) Enforce 2 free plates per day for this needy user
            cur.execute("""
                SELECT COALESCE(SUM(qty), 0) AS used_today
                FROM reservations
                WHERE user_id = %s
                  AND status IN ('CONFIRMED','PICKED_UP')
                  AND DATE(confirmed_at) = CURRENT_DATE()
            """, (user["user_id"],))
            used_today = int(cur.fetchone()["used_today"])
            if used_today + qty > 2:
                session["_flash"] = "❗ You have reached your free plate limit for today."
                con.rollback()
                return redirect(url_for("needy.free"))

            # 2) Lock the plate row
            cur.execute("SELECT * FROM plates WHERE plate_id = %s FOR UPDATE", (plate_id,))
            plate = cur.fetchone()
            if not plate:
                session["_flash"] = "❗ Plate not found."
                con.rollback()
                return redirect(url_for("needy.free"))

            cur.execute("SELECT NOW() AS n")
            now = cur.fetchone()["n"]
            if not (plate["window_start"] <= now <= plate["window_end"]):
                session["_flash"] = "❗ Outside pickup window."
                con.rollback()
                return redirect(url_for("needy.free"))

            if int(plate["qty_available"]) < qty:
                session["_flash"] = "❗ Not enough stock available."
                con.rollback()
                return redirect(url_for("needy.free"))

            # 3) Create CONFIRMED reservation with pickup code
            import secrets
            code = f"{secrets.randbelow(10**8):08d}"

            cur.execute("""
                INSERT INTO reservations (user_id, plate_id, qty, status, pickup_code, confirmed_at)
                VALUES (%s, %s, %s, 'CONFIRMED', %s, NOW())
            """, (user["user_id"], plate_id, qty, code))

            # 4) Decrement plate stock
            cur.execute("""
                UPDATE plates
                SET qty_available = qty_available - %s
                WHERE plate_id = %s
            """, (qty, plate_id))

            con.commit()
            session["_flash"] = f"✅ Free plate claimed! Your pickup code is {code}."
    except Exception as e:
        con.rollback()
        session["_flash"] = f"❗ Error claiming free plate: {e}"
    finally:
        con.close()

    return redirect(url_for("needy.free"))
