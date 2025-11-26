from flask import Blueprint, render_template, session
from ..db import get_db
from ..auth import ensure_dev_user, maybe_switch_user

bp = Blueprint("market", __name__)

@bp.before_app_request
def _dev_login_middleware():
    rv = maybe_switch_user()
    if rv: return rv
    ensure_dev_user()

@bp.route("/")
def home():
    return marketplace()

@bp.route("/marketplace")
def marketplace():
    role = (session.get("user") or {}).get("role", "CUSTOMER")
    con = get_db(); plates = []
    try:
        with con.cursor() as cur:
            cur.execute("""
                SELECT p.plate_id, p.title, p.description, p.price, p.qty_available,
                       p.window_start, p.window_end, r.display_name
                FROM plates p
                JOIN restaurants r ON r.restaurant_id = p.restaurant_id
                WHERE p.is_active=1 AND p.qty_available>0
                  AND NOW() BETWEEN p.window_start AND p.window_end
                ORDER BY p.window_end ASC
            """)
            plates = cur.fetchall()
    finally:
        con.close()
    return render_template("marketplace.html", title="Marketplace", role=role, plates=plates)