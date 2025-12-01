from flask import Blueprint, render_template, session, flash, redirect, url_for, request
from models.database import get_db
from datetime import datetime, timedelta

bp = Blueprint('admin', __name__)


@bp.route('/dashboard')
def dashboard():
    # 1. Security Check
    if 'user_id' not in session or session.get('user_type') != 'admin':
        flash('Please login as admin', 'error')
        return redirect(url_for('auth.login'))

    # 2. Get Filter Parameters
    report_type = request.args.get('report_type')
    year = request.args.get('year', datetime.now().year)
    start_date = request.args.get('start_date')
    search_query = request.args.get('search_query', '')

    data = []
    summary = {}
    chart_data = {}

    db = get_db()
    cursor = db.cursor(dictionary=True)


    try:
        cursor.execute("SET SESSION sql_mode = 'IGNORE_SPACE,NO_ENGINE_SUBSTITUTION'")
        cursor.fetchall()  # Consume result if any
    except:
        pass


    # DASHBOARD CHARTS

    if not report_type:

        cursor.execute("SELECT user_type, COUNT(*) as count FROM users GROUP BY user_type")
        user_rows = cursor.fetchall()

        chart_data['user_labels'] = [r['user_type'].capitalize() for r in user_rows]
        chart_data['user_counts'] = [r['count'] for r in user_rows]



        cursor.execute(
            "SELECT DATE(created_at) as date, type, SUM(amount) as total FROM transactions WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) GROUP BY DATE(created_at), type ORDER BY DATE(created_at) ASC")
        fin_rows = cursor.fetchall()

        unique_dates = sorted(list(set(row['date'].strftime('%Y-%m-%d') for row in fin_rows)))

        val_map = {}
        for row in fin_rows:
            d = row['date'].strftime('%Y-%m-%d')
            t = row['type']
            if d not in val_map: val_map[d] = {}
            val_map[d][t] = float(row['total'])

        customer_data = []
        donor_data = []

        for d in unique_dates:
            customer_data.append(val_map.get(d, {}).get('CUSTOMER_PURCHASE', 0))
            donor_data.append(val_map.get(d, {}).get('DONATION_PURCHASE', 0))

        chart_data['dates'] = unique_dates
        chart_data['customer_trend'] = customer_data
        chart_data['donor_trend'] = donor_data


    # Member Lookup

    elif report_type == 'member_lookup':
        if search_query:
            query = "SELECT user_id, name, email, user_type, phone, address, created_at FROM users WHERE name LIKE %s OR email LIKE %s"
            search_param = f"%{search_query}%"
            cursor.execute(query, (search_param, search_param))
            data = cursor.fetchall()


    # Restaurant Activity

    elif report_type == 'restaurant_activity':
        query = "SELECT u.name, COUNT(p.plate_id) as listings_count, COALESCE(SUM(p.quantity_original),0) as total_plates, COALESCE(SUM(p.quantity_original-p.quantity_available),0) as sold_plates FROM users u LEFT JOIN plates p ON u.user_id = p.restaurant_id WHERE u.user_type = 'restaurant'"

        if start_date:
            query += " AND p.created_at >= %s"
            params = (start_date,)
        else:
            params = ()
        query += " GROUP BY u.user_id"
        cursor.execute(query, params)
        data = cursor.fetchall()


    # Customer Purchases

    elif report_type == 'customer_purchases':
        query = "SELECT r.created_at as date, u.name as user_name, p.title as plate_title, rest.name as restaurant_name, r.qty, (r.qty * p.price) as total_price FROM reservations r JOIN users u ON r.user_id = u.user_id JOIN plates p ON r.plate_id = p.plate_id JOIN users rest ON p.restaurant_id = rest.user_id WHERE r.status = 'CONFIRMED'"

        params = []
        if start_date:
            query += " AND r.created_at >= %s"
            params.append(start_date)
        query += " ORDER BY r.created_at DESC"
        cursor.execute(query, tuple(params))
        data = cursor.fetchall()


    # Donor History

    elif report_type == 'donor_purchases':
        query = "SELECT r.created_at as date, u.name as donor_name, p.title as plate_title, rest.name as restaurant_name, r.qty, (r.qty * p.price) as total_donation FROM reservations r JOIN users u ON r.donor_id = u.user_id JOIN plates p ON r.plate_id = p.plate_id JOIN users rest ON p.restaurant_id = rest.user_id WHERE r.status IN ('DONATED', 'CLAIMED')"

        params = []
        if start_date:
            query += " AND r.created_at >= %s"
            params.append(start_date)
        query += " ORDER BY r.created_at DESC"
        cursor.execute(query, tuple(params))
        data = cursor.fetchall()


    # Annual Free Plate Report

    elif report_type == 'free_plates':
        cursor.execute(
            "SELECT u.name, COUNT(r.reservation_id) as plates_received, MAX(r.claimed_at) as last_pickup FROM reservations r JOIN users u ON r.user_id = u.user_id WHERE r.status = 'CLAIMED' AND YEAR(r.claimed_at) = %s GROUP BY u.user_id",
            (year,))
        data = cursor.fetchall()

        cursor.execute(
            "SELECT COUNT(r.reservation_id) as total_count, SUM(p.price*r.qty) as total_value FROM reservations r JOIN plates p ON r.plate_id = p.plate_id WHERE r.status = 'CLAIMED' AND YEAR(r.claimed_at) = %s",
            (year,))
        summary = cursor.fetchone()


    # Tax Donation Report

    elif report_type == 'tax_report':
        cursor.execute(
            "SELECT u.name, u.email, u.address, SUM(t.amount) as total_donated, COUNT(t.transaction_id) as transaction_count FROM transactions t JOIN users u ON t.payer_user_id = u.user_id WHERE t.type = 'DONATION_PURCHASE' AND YEAR(t.created_at) = %s GROUP BY u.user_id",
            (year,))
        data = cursor.fetchall()

    cursor.close()

    return render_template('admin/dashboard.html',
                           data=data,
                           report_type=report_type,
                           chart_data=chart_data,
                           year=year,
                           start_date=start_date,
                           search_query=search_query,
                           summary=summary,
                           current_date=datetime.now().strftime('%Y-%m-%d'))