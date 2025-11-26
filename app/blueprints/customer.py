from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models.database import get_db
import secrets

bp = Blueprint('customer', __name__)

@bp.route('/marketplace')
def marketplace():
    if 'user_id' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('auth.login'))
    
    # Redirect needy users to free plates page
    if session.get('user_type') == 'needy':
        flash('As a needy user, you can access free donated plates only', 'info')
        return redirect(url_for('customer.free_plates'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Get available plates
    cursor.execute('''
        SELECT p.plate_id, p.title, p.description, p.price, p.quantity_available,
               p.start_time, p.end_time, u.name as restaurant_name
        FROM plates p
        JOIN users u ON u.user_id = p.restaurant_id
        WHERE p.is_active = 1 AND p.quantity_available > 0
          AND NOW() BETWEEN p.start_time AND p.end_time
        ORDER BY p.end_time ASC
    ''')
    plates = cursor.fetchall()
    cursor.close()
    
    return render_template('customer/marketplace.html', plates=plates)

@bp.route('/free-plates')
def free_plates():
    if 'user_id' not in session or session.get('user_type') != 'needy':
        flash('This page is for needy users only', 'error')
        return redirect(url_for('auth.login'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Check how many plates this needy user has already claimed
    cursor.execute('''
        SELECT COUNT(*) as count 
        FROM reservations 
        WHERE user_id = %s AND status IN ('CLAIMED', 'CONFIRMED')
          AND DATE(claimed_at) = CURDATE()
    ''', (session['user_id'],))
    claimed_count = cursor.fetchone()['count']
    
    # Get donated plates that haven't been claimed yet
    cursor.execute('''
        SELECT r.reservation_id, r.qty, p.plate_id, p.title, p.description, 
               p.price, p.start_time, p.end_time, u.name as restaurant_name
        FROM reservations r
        JOIN plates p ON p.plate_id = r.plate_id
        JOIN users u ON u.user_id = p.restaurant_id
        WHERE r.status = 'DONATED'
          AND NOW() BETWEEN p.start_time AND p.end_time
        ORDER BY r.created_at ASC
    ''')
    donated_plates = cursor.fetchall()
    cursor.close()
    
    return render_template('customer/free_plates.html', 
                          plates=donated_plates, 
                          claimed_count=claimed_count,
                          max_allowed=2)

@bp.route('/reserve', methods=['POST'])
def reserve():
    if 'user_id' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('auth.login'))
    
    plate_id = int(request.form.get('plate_id', 0))
    qty = max(1, int(request.form.get('qty', 1)))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    try:
        # Check if plate is available
        cursor.execute('''
            SELECT * FROM plates 
            WHERE plate_id = %s AND is_active = 1 
              AND quantity_available >= %s
              AND NOW() BETWEEN start_time AND end_time
        ''', (plate_id, qty))
        plate = cursor.fetchone()
        
        if not plate:
            flash('Plate not available', 'error')
            return redirect(url_for('customer.marketplace'))
        
        # Create reservation
        cursor.execute('''
            INSERT INTO reservations (user_id, plate_id, qty, status, created_at)
            VALUES (%s, %s, %s, 'HELD', NOW())
        ''', (session['user_id'], plate_id, qty))
        
        reservation_id = cursor.lastrowid
        db.commit()
        
        session['held_reservation_id'] = reservation_id
        flash('Reservation created! Please confirm your order.', 'success')
        return redirect(url_for('customer.checkout'))
        
    except Exception as e:
        db.rollback()
        flash(f'Error creating reservation: {e}', 'error')
        return redirect(url_for('customer.marketplace'))
    finally:
        cursor.close()

@bp.route('/claim-free/<int:reservation_id>', methods=['POST'])
def claim_free(reservation_id):
    if 'user_id' not in session or session.get('user_type') != 'needy':
        flash('This action is for needy users only', 'error')
        return redirect(url_for('auth.login'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    try:
        # Check how many plates user has claimed today
        cursor.execute('''
            SELECT COUNT(*) as count 
            FROM reservations 
            WHERE user_id = %s AND status IN ('CLAIMED', 'CONFIRMED')
              AND DATE(claimed_at) = CURDATE()
        ''', (session['user_id'],))
        claimed_count = cursor.fetchone()['count']
        
        if claimed_count >= 2:
            flash('You have already claimed your maximum of 2 free plates today. Please come back tomorrow!', 'error')
            return redirect(url_for('customer.free_plates'))
        
        # Get the donated reservation
        cursor.execute('''
            SELECT r.*, p.restaurant_id
            FROM reservations r
            JOIN plates p ON p.plate_id = r.plate_id
            WHERE r.reservation_id = %s AND r.status = 'DONATED'
        ''', (reservation_id,))
        reservation = cursor.fetchone()
        
        if not reservation:
            flash('This donated plate is no longer available', 'error')
            return redirect(url_for('customer.free_plates'))
        
        # Generate pickup code
        pickup_code = f"{secrets.randbelow(10**8):08d}"
        
        # Claim the reservation
        cursor.execute('''
            UPDATE reservations 
            SET user_id = %s, status = 'CLAIMED', pickup_code = %s, 
                claimed_at = NOW(), confirmed_at = NOW()
            WHERE reservation_id = %s
        ''', (session['user_id'], pickup_code, reservation_id))
        
        db.commit()
        
        flash(f'Free plate claimed! Your pickup code is: {pickup_code}', 'success')
        return redirect(url_for('customer.free_plates'))
        
    except Exception as e:
        db.rollback()
        flash(f'Error claiming plate: {e}', 'error')
        return redirect(url_for('customer.free_plates'))
    finally:
        cursor.close()

@bp.route('/checkout')
def checkout():
    if 'user_id' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('auth.login'))
    
    res_id = session.get('held_reservation_id')
    if not res_id:
        return redirect(url_for('customer.marketplace'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    cursor.execute('''
        SELECT r.reservation_id, r.qty, p.title, p.price, p.plate_id
        FROM reservations r 
        JOIN plates p ON p.plate_id = r.plate_id
        WHERE r.reservation_id = %s
    ''', (res_id,))
    reservation = cursor.fetchone()
    cursor.close()
    
    return render_template('customer/checkout.html', reservation=reservation)

@bp.route('/confirm', methods=['POST'])
def confirm():
    if 'user_id' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('auth.login'))
    
    res_id = int(request.form.get('reservation_id', 0))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    try:
        # Get reservation details
        cursor.execute('''
            SELECT r.*, p.price, p.quantity_available, p.restaurant_id
            FROM reservations r 
            JOIN plates p ON p.plate_id = r.plate_id
            WHERE r.reservation_id = %s AND r.user_id = %s AND r.status = 'HELD'
        ''', (res_id, session['user_id']))
        reservation = cursor.fetchone()
        
        if not reservation:
            flash('Reservation not found', 'error')
            return redirect(url_for('customer.marketplace'))
        
        # Check if enough quantity available
        if reservation['quantity_available'] < reservation['qty']:
            flash('Not enough plates available', 'error')
            return redirect(url_for('customer.marketplace'))
        
        # DONOR FLOW - Deduct inventory and create donated reservation
        if session['user_type'] == 'donner':
            # Update plate quantity (donors are paying for real plates)
            cursor.execute('''
                UPDATE plates 
                SET quantity_available = quantity_available - %s
                WHERE plate_id = %s
            ''', (reservation['qty'], reservation['plate_id']))
            
            # Record the transaction
            amount = float(reservation['price']) * int(reservation['qty'])
            cursor.execute('''
                INSERT INTO transactions (payer_user_id, payee_restaurant_id, amount, type)
                VALUES (%s, %s, %s, 'DONATION_PURCHASE')
            ''', (session['user_id'], reservation['restaurant_id'], amount))
            
            # Update this reservation to DONATED status (available for needy to claim)
            cursor.execute('''
                UPDATE reservations 
                SET status = 'DONATED', donor_id = %s, confirmed_at = NOW()
                WHERE reservation_id = %s
            ''', (session['user_id'], res_id))
            
            db.commit()
            session.pop('held_reservation_id', None)
            
            flash(f'Thank you for donating {reservation["qty"]} plate(s)! They are now available for those in need.', 'success')
            return redirect(url_for('customer.marketplace'))
        
        # CUSTOMER FLOW - Normal purchase
        else:
            # Update plate quantity
            cursor.execute('''
                UPDATE plates 
                SET quantity_available = quantity_available - %s
                WHERE plate_id = %s
            ''', (reservation['qty'], reservation['plate_id']))
            
            # Generate pickup code
            pickup_code = f"{secrets.randbelow(10**8):08d}"
            
            # Confirm reservation
            cursor.execute('''
                UPDATE reservations 
                SET status = 'CONFIRMED', confirmed_at = NOW(), pickup_code = %s
                WHERE reservation_id = %s
            ''', (pickup_code, res_id))
            
            # Record transaction
            amount = float(reservation['price']) * int(reservation['qty'])
            cursor.execute('''
                INSERT INTO transactions (payer_user_id, payee_restaurant_id, amount, type)
                VALUES (%s, %s, %s, 'CUSTOMER_PURCHASE')
            ''', (session['user_id'], reservation['restaurant_id'], amount))
            
            db.commit()
            session.pop('held_reservation_id', None)
            
            flash(f'Order confirmed! Your pickup code is: {pickup_code}', 'success')
            return redirect(url_for('customer.marketplace'))
        
    except Exception as e:
        db.rollback()
        flash(f'Error confirming order: {e}', 'error')
        return redirect(url_for('customer.checkout'))
    finally:
        cursor.close()