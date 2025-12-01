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
    
    # Check how many plates this needy user has already claimed today
    cursor.execute('''
        SELECT COALESCE(SUM(qty), 0) as total_claimed
        FROM reservations 
        WHERE user_id = %s AND status IN ('CLAIMED', 'PICKED_UP')
          AND DATE(claimed_at) = CURDATE()
    ''', (session['user_id'],))
    total_claimed = cursor.fetchone()['total_claimed']
    
    remaining_plates = max(0, 2 - total_claimed)
    
    # Get donated plates that haven't been claimed yet
    cursor.execute('''
        SELECT r.reservation_id, r.qty as available_qty, p.plate_id, p.title, p.description, 
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
    
    # Initialize needy cart if it doesn't exist
    if 'needy_cart' not in session:
        session['needy_cart'] = []
    
    return render_template('customer/free_plates.html', 
                          plates=donated_plates, 
                          total_claimed=total_claimed,
                          remaining_plates=remaining_plates,
                          max_allowed=2,
                          needy_cart=session.get('needy_cart', []))

@bp.route('/add-to-cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('auth.login'))
    
    plate_id = int(request.form.get('plate_id', 0))
    qty = max(1, int(request.form.get('qty', 1)))
    
    # Initialize cart in session if it doesn't exist
    if 'cart' not in session:
        session['cart'] = []
    
    # Check if plate already in cart
    cart = session['cart']
    found = False
    for item in cart:
        if item['plate_id'] == plate_id:
            item['qty'] += qty
            found = True
            break
    
    if not found:
        cart.append({'plate_id': plate_id, 'qty': qty})
    
    session['cart'] = cart
    session['cart_count'] = len(cart)
    session.modified = True
    
    flash(f'Added {qty} item(s) to cart!', 'success')
    return redirect(url_for('customer.marketplace'))

@bp.route('/cart')
def cart():
    if 'user_id' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('auth.login'))
    
    cart_items = session.get('cart', [])
    
    if not cart_items:
        return render_template('customer/cart.html', cart_items=[], total=0)
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Get details for all items in cart
    plate_ids = [item['plate_id'] for item in cart_items]
    placeholders = ','.join(['%s'] * len(plate_ids))
    
    cursor.execute(f'''
        SELECT p.plate_id, p.title, p.description, p.price, p.quantity_available,
               p.start_time, p.end_time, u.name as restaurant_name, p.is_active
        FROM plates p
        JOIN users u ON u.user_id = p.restaurant_id
        WHERE p.plate_id IN ({placeholders})
    ''', plate_ids)
    
    plates = cursor.fetchall()
    cursor.close()
    
    # Merge cart quantities with plate details
    cart_details = []
    total = 0
    
    for item in cart_items:
        for plate in plates:
            if plate['plate_id'] == item['plate_id']:
                cart_detail = {**plate, 'cart_qty': item['qty']}
                cart_detail['subtotal'] = plate['price'] * item['qty']
                total += cart_detail['subtotal']
                cart_details.append(cart_detail)
                break
    
    return render_template('customer/cart.html', cart_items=cart_details, total=total)

@bp.route('/update-cart', methods=['POST'])
def update_cart():
    if 'user_id' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('auth.login'))
    
    plate_id = int(request.form.get('plate_id', 0))
    qty = int(request.form.get('qty', 0))
    
    cart = session.get('cart', [])
    
    if qty <= 0:
        # Remove item from cart
        cart = [item for item in cart if item['plate_id'] != plate_id]
        flash('Item removed from cart', 'info')
    else:
        # Update quantity
        for item in cart:
            if item['plate_id'] == plate_id:
                item['qty'] = qty
                break
        flash('Cart updated', 'success')
    
    session['cart'] = cart
    session['cart_count'] = len(cart)
    session.modified = True
    
    return redirect(url_for('customer.cart'))

@bp.route('/remove-from-cart/<int:plate_id>', methods=['POST'])
def remove_from_cart(plate_id):
    if 'user_id' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('auth.login'))
    
    cart = session.get('cart', [])
    cart = [item for item in cart if item['plate_id'] != plate_id]
    
    session['cart'] = cart
    session['cart_count'] = len(cart)
    session.modified = True
    
    flash('Item removed from cart', 'info')
    return redirect(url_for('customer.cart'))

@bp.route('/add-to-needy-cart', methods=['POST'])
def add_to_needy_cart():
    if 'user_id' not in session or session.get('user_type') != 'needy':
        flash('This action is for needy users only', 'error')
        return redirect(url_for('auth.login'))
    
    reservation_id = int(request.form.get('reservation_id', 0))
    qty = int(request.form.get('qty', 1))
    
    if qty < 1:
        flash('Quantity must be at least 1', 'error')
        return redirect(url_for('customer.free_plates'))
    
    # Initialize needy cart
    if 'needy_cart' not in session:
        session['needy_cart'] = []
    
    # Calculate current cart total
    cart = session['needy_cart']
    current_total = sum(item['qty'] for item in cart)
    
    # Check if adding would exceed limit
    if current_total + qty > 2:
        flash(f'Cannot add {qty} plate(s). You can only claim 2 plates total. You currently have {current_total} in your selection.', 'error')
        return redirect(url_for('customer.free_plates'))
    
    # Check if item already in cart
    found = False
    for item in cart:
        if item['reservation_id'] == reservation_id:
            item['qty'] += qty
            found = True
            break
    
    if not found:
        cart.append({'reservation_id': reservation_id, 'qty': qty})
    
    session['needy_cart'] = cart
    session.modified = True
    
    flash(f'Added {qty} plate(s) to your selection!', 'success')
    return redirect(url_for('customer.free_plates'))

@bp.route('/remove-from-needy-cart/<int:reservation_id>', methods=['POST'])
def remove_from_needy_cart(reservation_id):
    if 'user_id' not in session or session.get('user_type') != 'needy':
        flash('This action is for needy users only', 'error')
        return redirect(url_for('auth.login'))
    
    cart = session.get('needy_cart', [])
    cart = [item for item in cart if item['reservation_id'] != reservation_id]
    
    session['needy_cart'] = cart
    session.modified = True
    
    flash('Item removed from selection', 'info')
    return redirect(url_for('customer.free_plates'))

@bp.route('/claim-free/<int:reservation_id>', methods=['POST'])
def claim_free(reservation_id):
    if 'user_id' not in session or session.get('user_type') != 'needy':
        flash('This action is for needy users only', 'error')
        return redirect(url_for('auth.login'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    try:
        # Check how many plates user has claimed today (by quantity)
        cursor.execute('''
            SELECT COALESCE(SUM(qty), 0) as total_claimed
            FROM reservations 
            WHERE user_id = %s AND status IN ('CLAIMED', 'PICKED_UP')
              AND DATE(claimed_at) = CURDATE()
        ''', (session['user_id'],))
        total_claimed = cursor.fetchone()['total_claimed']
        
        if total_claimed >= 2:
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

@bp.route('/claim-selected-plates', methods=['POST'])
def claim_selected_plates():
    if 'user_id' not in session or session.get('user_type') != 'needy':
        flash('This action is for needy users only', 'error')
        return redirect(url_for('auth.login'))
    
    cart = session.get('needy_cart', [])
    
    if not cart:
        flash('No plates selected', 'error')
        return redirect(url_for('customer.free_plates'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    try:
        # Check how many plates user has already claimed today
        cursor.execute('''
            SELECT COALESCE(SUM(qty), 0) as total_claimed
            FROM reservations 
            WHERE user_id = %s AND status IN ('CLAIMED', 'PICKED_UP')
              AND DATE(claimed_at) = CURDATE()
        ''', (session['user_id'],))
        total_claimed = cursor.fetchone()['total_claimed']
        
        # Calculate cart total
        cart_total = sum(item['qty'] for item in cart)
        
        if total_claimed + cart_total > 2:
            flash(f'Cannot claim {cart_total} plates. You have already claimed {total_claimed} today. Maximum is 2 plates total.', 'error')
            return redirect(url_for('customer.free_plates'))
        
        claimed_items = []
        
        for cart_item in cart:
            reservation_id = cart_item['reservation_id']
            requested_qty = cart_item['qty']
            
            # Get the donated reservation with lock
            cursor.execute('''
                SELECT r.*, p.restaurant_id, p.title
                FROM reservations r
                JOIN plates p ON p.plate_id = r.plate_id
                WHERE r.reservation_id = %s AND r.status = 'DONATED'
                FOR UPDATE
            ''', (reservation_id,))
            
            reservation = cursor.fetchone()
            
            if not reservation:
                db.rollback()
                flash('One or more plates are no longer available', 'error')
                return redirect(url_for('customer.free_plates'))
            
            # Check if enough quantity available
            if reservation['qty'] < requested_qty:
                db.rollback()
                flash(f'Not enough "{reservation["title"]}" available. Only {reservation["qty"]} left.', 'error')
                return redirect(url_for('customer.free_plates'))
            
            # If requesting less than total available, split the reservation
            if reservation['qty'] > requested_qty:
                # Update existing reservation to reduce quantity
                cursor.execute('''
                    UPDATE reservations 
                    SET qty = qty - %s
                    WHERE reservation_id = %s
                ''', (requested_qty, reservation_id))
                
                # Create new reservation for claimed portion
                pickup_code = f"{secrets.randbelow(10**8):08d}"
                cursor.execute('''
                    INSERT INTO reservations (user_id, donor_id, plate_id, qty, status, pickup_code, claimed_at, confirmed_at)
                    VALUES (%s, %s, %s, %s, 'CLAIMED', %s, NOW(), NOW())
                ''', (session['user_id'], reservation['donor_id'], reservation['plate_id'], requested_qty, pickup_code))
                
                claimed_items.append({
                    'title': reservation['title'],
                    'qty': requested_qty,
                    'pickup_code': pickup_code
                })
            else:
                # Claim entire reservation
                pickup_code = f"{secrets.randbelow(10**8):08d}"
                cursor.execute('''
                    UPDATE reservations 
                    SET user_id = %s, status = 'CLAIMED', pickup_code = %s, 
                        claimed_at = NOW(), confirmed_at = NOW()
                    WHERE reservation_id = %s
                ''', (session['user_id'], pickup_code, reservation_id))
                
                claimed_items.append({
                    'title': reservation['title'],
                    'qty': requested_qty,
                    'pickup_code': pickup_code
                })
        
        db.commit()
        
        # Clear needy cart
        session['needy_cart'] = []
        session.modified = True
        
        # Build success message
        message = f'Successfully claimed {cart_total} plate(s)! '
        for item in claimed_items:
            message += f"{item['title']} ({item['qty']}): {item['pickup_code']} | "
        
        flash(message.rstrip(' | '), 'success')
        return redirect(url_for('customer.order_history'))
        
    except Exception as e:
        db.rollback()
        flash(f'Error claiming plates: {e}', 'error')
        return redirect(url_for('customer.free_plates'))
    finally:
        cursor.close()

@bp.route('/checkout')
def checkout():
    if 'user_id' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('auth.login'))
    
    cart_items = session.get('cart', [])
    
    if not cart_items:
        flash('Your cart is empty', 'info')
        return redirect(url_for('customer.marketplace'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Get details for all items in cart
    plate_ids = [item['plate_id'] for item in cart_items]
    placeholders = ','.join(['%s'] * len(plate_ids))
    
    cursor.execute(f'''
        SELECT p.plate_id, p.title, p.description, p.price, p.quantity_available,
               p.start_time, p.end_time, p.restaurant_id, u.name as restaurant_name, p.is_active
        FROM plates p
        JOIN users u ON u.user_id = p.restaurant_id
        WHERE p.plate_id IN ({placeholders})
          AND p.is_active = 1
          AND NOW() BETWEEN p.start_time AND p.end_time
    ''', plate_ids)
    
    plates = cursor.fetchall()
    cursor.close()
    
    # Merge cart quantities with plate details and check availability
    cart_details = []
    total = 0
    has_unavailable = False
    
    for item in cart_items:
        for plate in plates:
            if plate['plate_id'] == item['plate_id']:
                if plate['quantity_available'] < item['qty']:
                    has_unavailable = True
                cart_detail = {**plate, 'cart_qty': item['qty']}
                cart_detail['subtotal'] = plate['price'] * item['qty']
                cart_detail['available'] = plate['quantity_available'] >= item['qty']
                total += cart_detail['subtotal']
                cart_details.append(cart_detail)
                break
    
    if has_unavailable:
        flash('Some items in your cart are no longer available in the requested quantity. Please update your cart.', 'warning')
    
    return render_template('customer/checkout.html', cart_items=cart_details, total=total)

@bp.route('/confirm-order', methods=['POST'])
def confirm_order():
    if 'user_id' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('auth.login'))
    
    cart_items = session.get('cart', [])
    
    if not cart_items:
        flash('Your cart is empty', 'error')
        return redirect(url_for('customer.marketplace'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    try:
        total_amount = 0
        confirmed_items = []
        
        for cart_item in cart_items:
            plate_id = cart_item['plate_id']
            qty = cart_item['qty']
            
            # Get plate details and lock row for update
            cursor.execute('''
                SELECT p.*, u.user_id as restaurant_id
                FROM plates p
                JOIN users u ON p.restaurant_id = u.user_id
                WHERE p.plate_id = %s AND p.is_active = 1
                  AND p.quantity_available >= %s
                  AND NOW() BETWEEN p.start_time AND p.end_time
                FOR UPDATE
            ''', (plate_id, qty))
            
            plate = cursor.fetchone()
            
            if not plate:
                db.rollback()
                flash(f'Item "{plate_id}" is no longer available in requested quantity', 'error')
                return redirect(url_for('customer.cart'))
            
            # Update plate quantity
            cursor.execute('''
                UPDATE plates 
                SET quantity_available = quantity_available - %s
                WHERE plate_id = %s
            ''', (qty, plate_id))
            
            # DONOR FLOW - Create donated reservation
            if session['user_type'] == 'donner':
                cursor.execute('''
                    INSERT INTO reservations (donor_id, plate_id, qty, status, confirmed_at)
                    VALUES (%s, %s, %s, 'DONATED', NOW())
                ''', (session['user_id'], plate_id, qty))
                
                # Record transaction
                amount = float(plate['price']) * int(qty)
                cursor.execute('''
                    INSERT INTO transactions (payer_user_id, payee_restaurant_id, amount, type)
                    VALUES (%s, %s, %s, 'DONATION_PURCHASE')
                ''', (session['user_id'], plate['restaurant_id'], amount))
                
                total_amount += amount
            
            # CUSTOMER FLOW - Normal purchase
            else:
                # Generate pickup code
                pickup_code = f"{secrets.randbelow(10**8):08d}"
                
                # Create confirmed reservation
                cursor.execute('''
                    INSERT INTO reservations (user_id, plate_id, qty, status, pickup_code, confirmed_at)
                    VALUES (%s, %s, %s, 'CONFIRMED', %s, NOW())
                ''', (session['user_id'], plate_id, qty, pickup_code))
                
                # Record transaction
                amount = float(plate['price']) * int(qty)
                cursor.execute('''
                    INSERT INTO transactions (payer_user_id, payee_restaurant_id, amount, type)
                    VALUES (%s, %s, %s, 'CUSTOMER_PURCHASE')
                ''', (session['user_id'], plate['restaurant_id'], amount))
                
                total_amount += amount
                confirmed_items.append({
                    'title': plate['title'],
                    'qty': qty,
                    'pickup_code': pickup_code
                })
        
        db.commit()
        
        # Clear cart
        session['cart'] = []
        session['cart_count'] = 0
        session.modified = True
        
        if session['user_type'] == 'donner':
            flash(f'Thank you for donating {len(cart_items)} item(s) totaling ${total_amount:.2f}! They are now available for those in need.', 'success')
        else:
            flash(f'Order confirmed! {len(confirmed_items)} item(s) ordered. Check your order history for pickup codes.', 'success')
        
        return redirect(url_for('customer.order_history') if session['user_type'] == 'customer' else url_for('customer.marketplace'))
        
    except Exception as e:
        db.rollback()
        flash(f'Error confirming order: {e}', 'error')
        return redirect(url_for('customer.cart'))
    finally:
        cursor.close()

@bp.route('/order-history')
def order_history():
    if 'user_id' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('auth.login'))
    
    user_type = session.get('user_type')
    
    # Only customers and needy users have order history
    if user_type not in ['customer', 'needy']:
        flash('Order history is not available for your account type', 'info')
        return redirect(url_for('customer.marketplace'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    orders = []
    
    try:
        if user_type == 'customer':
            # Get customer's purchase history
            cursor.execute('''
                SELECT r.reservation_id, r.qty, r.status, r.pickup_code, 
                       r.confirmed_at, r.created_at,
                       p.title, p.description, p.price, p.start_time, p.end_time,
                       u.name as restaurant_name,
                       (r.qty * p.price) as total_price
                FROM reservations r
                JOIN plates p ON p.plate_id = r.plate_id
                JOIN users u ON p.restaurant_id = u.user_id
                WHERE r.user_id = %s AND r.status IN ('CONFIRMED', 'PICKED_UP')
                ORDER BY r.confirmed_at DESC
            ''', (session['user_id'],))
            orders = cursor.fetchall()
            
        elif user_type == 'needy':
            # Get needy user's claimed plates history
            cursor.execute('''
                SELECT r.reservation_id, r.qty, r.status, r.pickup_code,
                       r.claimed_at, r.created_at,
                       p.title, p.description, p.price, p.start_time, p.end_time,
                       u.name as restaurant_name,
                       donor.name as donated_by
                FROM reservations r
                JOIN plates p ON p.plate_id = r.plate_id
                JOIN users u ON p.restaurant_id = u.user_id
                LEFT JOIN users donor ON r.donor_id = donor.user_id
                WHERE r.user_id = %s AND r.status IN ('CLAIMED', 'PICKED_UP')
                ORDER BY r.claimed_at DESC
            ''', (session['user_id'],))
            orders = cursor.fetchall()
        
        cursor.close()
        
        return render_template('customer/order_history.html', 
                             orders=orders, 
                             user_type=user_type)
    
    except Exception as e:
        flash(f'Error loading order history: {e}', 'error')
        return redirect(url_for('customer.marketplace'))