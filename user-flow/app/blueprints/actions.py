from flask import Blueprint, request, redirect, url_for, session
from ..db import get_db

bp = Blueprint("actions", __name__)

@bp.route("/reserve", methods=["POST"])
def reserve():
    user = session.get("user")
    if not user or user.get("role") not in ("CUSTOMER","DONOR"):
        return ("Login required", 403)
    plate_id = int(request.form.get("plate_id", 0))
    qty = max(1, int(request.form.get("qty", 1)))

    con = get_db()
    try:
        with con.cursor() as cur:
            cur.execute("SELECT plate_id, price, qty_available, window_start, window_end FROM plates WHERE plate_id=%s FOR UPDATE", (plate_id,))
            plate = cur.fetchone()
            if not plate: con.rollback(); return ("Could not reserve: plate not found", 400)
            cur.execute("SELECT NOW() n"); now = cur.fetchone()["n"]
            if not (plate["window_start"] <= now <= plate["window_end"]):
                con.rollback(); return ("Could not reserve: not within pickup window", 400)
            if user["role"]=="CUSTOMER" and qty > int(plate["qty_available"]):
                con.rollback(); return ("Could not reserve: not enough stock", 400)

            cur.execute("INSERT INTO reservations (user_id, plate_id, qty, status, created_at) VALUES (%s,%s,%s,'HELD',NOW())",
                        (user["user_id"], plate_id, qty))
            con.commit()
            session["held_reservation_id"] = cur.lastrowid
    except Exception as e:
        con.rollback(); return (f"Could not reserve: {e}", 400)
    finally:
        con.close()
    return redirect(url_for("actions.checkout"))

@bp.route("/confirm", methods=["POST"])
def confirm():
    user = session.get("user")
    if not user: return ("Login required", 403)
    res_id = int(request.form.get("reservation_id", 0))

    con = get_db()
    try:
        with con.cursor() as cur:
            cur.execute("""
                SELECT r.*, p.price, p.qty_available, p.window_start, p.window_end, p.restaurant_id
                FROM reservations r JOIN plates p ON p.plate_id=r.plate_id
                WHERE r.reservation_id=%s FOR UPDATE
            """,(res_id,))
            row = cur.fetchone()
            if not row: con.rollback(); return ("Could not confirm: reservation not found", 400)
            if int(row["user_id"]) != int(user["user_id"]): con.rollback(); return ("Not your reservation", 400)
            if row["status"] != "HELD": con.rollback(); return ("Already processed", 400)
            cur.execute("SELECT NOW() n"); now = cur.fetchone()["n"]
            if not (row["window_start"] <= now <= row["window_end"]):
                con.rollback(); return ("Outside pickup window", 400)

            if user["role"]=="CUSTOMER":
                if int(row["qty_available"]) < int(row["qty"]):
                    con.rollback(); return ("Sold out", 400)
                cur.execute("UPDATE plates SET qty_available=qty_available-%s WHERE plate_id=%s",
                            (row["qty"], row["plate_id"]))
                import secrets
                code = f"{secrets.randbelow(10**8):08d}"
                cur.execute("UPDATE reservations SET status='CONFIRMED', confirmed_at=NOW(), pickup_code=%s WHERE reservation_id=%s",
                            (code, res_id))
                amount = float(row["price"]) * int(row["qty"])
                cur.execute("INSERT INTO transactions (payer_user_id, payee_restaurant_id, amount, type) VALUES (%s,%s,%s,'CUSTOMER_PURCHASE')",
                            (user["user_id"], row["restaurant_id"], amount))
                con.commit()
                session.pop("held_reservation_id", None)
                session["_flash"] = f"Order confirmed. Your pickup code is {code}."
                return redirect(url_for("market.marketplace"))
            else:  # DONOR
                amount = float(row["price"]) * int(row["qty"])
                cur.execute("INSERT INTO transactions (payer_user_id, payee_restaurant_id, amount, type) VALUES (%s,%s,%s,'DONATION_PURCHASE')",
                            (user["user_id"], row["restaurant_id"], amount))
                cur.execute("UPDATE reservations SET status='CANCELLED' WHERE reservation_id=%s", (res_id,))
                con.commit()
                session.pop("held_reservation_id", None)
                session["_flash"] = "Thank you! Your donation has been recorded."
                return redirect(url_for("market.marketplace"))
    except Exception:
        con.rollback()
        return ("An unexpected error occurred. Please try again.", 400)
    finally:
        con.close()
    return redirect(url_for("actions.checkout"))


# small page to render checkout (keep with market for simplicity if you want)
@bp.route("/checkout")
def checkout():
    from flask import render_template
    res_id = session.get("held_reservation_id")
    if not res_id: return redirect(url_for("market.marketplace"))
    con = get_db(); row=None
    try:
        with con.cursor() as cur:
            cur.execute("""
                SELECT r.reservation_id, r.qty, p.title, p.price, p.plate_id
                FROM reservations r JOIN plates p ON p.plate_id=r.plate_id
                WHERE r.reservation_id=%s
            """,(res_id,))
            row = cur.fetchone()
    finally: con.close()
    role = (session.get("user") or {}).get("role","CUSTOMER")
    return render_template("checkout.html", title="Checkout", row=row, role=role)