from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models.database import get_db, close_db, init_db
import mysql.connector

app = Flask(__name__)
app.config.from_object(Config)

# Register database teardown
app.teardown_appcontext(close_db)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get form data
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        user_type = request.form.get('user_type')
        name = request.form.get('name')
        address = request.form.get('address')
        phone = request.form.get('phone')
        
        # Validate passwords match
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('register'))
        
        # Hash password
        password_hash = generate_password_hash(password)
        
        try:
            db = get_db()
            cursor = db.cursor()
            
            # Insert user
            cursor.execute('''
                INSERT INTO users (email, password_hash, user_type, name, address, phone)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (email, password_hash, user_type, name, address, phone))
            
            user_id = cursor.lastrowid
            
            # If customer or donner, get payment info
            if user_type in ['customer', 'donner']:
                card_number = request.form.get('card_number')
                card_holder = request.form.get('card_holder')
                expiry_date = request.form.get('expiry_date')
                cvv = request.form.get('cvv')
                
                cursor.execute('''
                    INSERT INTO payment_info (user_id, card_number, card_holder, expiry_date, cvv)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (user_id, card_number, card_holder, expiry_date, cvv))
            
            db.commit()
            cursor.close()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except mysql.connector.Error as err:
            flash(f'Registration failed: {err}', 'error')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()
        cursor.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['user_type'] = user['user_type']
            session['name'] = user['name']
            
            flash('Login successful!', 'success')
            
            # Redirect based on user type
            if user['user_type'] == 'restaurant':
                return redirect(url_for('restaurant_dashboard'))
            elif user['user_type'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('customer_dashboard'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('login'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    if request.method == 'POST':
        # Update user information
        name = request.form.get('name')
        address = request.form.get('address')
        phone = request.form.get('phone')
        
        cursor.execute('''
            UPDATE users 
            SET name = %s, address = %s, phone = %s
            WHERE user_id = %s
        ''', (name, address, phone, session['user_id']))
        
        # Update payment info if customer or donner
        if session['user_type'] in ['customer', 'donner']:
            card_holder = request.form.get('card_holder')
            card_number = request.form.get('card_number')
            expiry_date = request.form.get('expiry_date')
            cvv = request.form.get('cvv')
            
            cursor.execute('''
                UPDATE payment_info 
                SET card_holder = %s, card_number = %s, expiry_date = %s, cvv = %s
                WHERE user_id = %s
            ''', (card_holder, card_number, expiry_date, cvv, session['user_id']))
        
        db.commit()
        session['name'] = name
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    # Get user data
    cursor.execute('SELECT * FROM users WHERE user_id = %s', (session['user_id'],))
    user = cursor.fetchone()
    
    # Get payment info if customer or donner
    payment_info = None
    if session['user_type'] in ['customer', 'donner']:
        cursor.execute('SELECT * FROM payment_info WHERE user_id = %s', (session['user_id'],))
        payment_info = cursor.fetchone()
    
    cursor.close()
    
    return render_template('profile.html', user=user, payment_info=payment_info)

@app.route('/restaurant/dashboard')
def restaurant_dashboard():
    if 'user_id' not in session or session.get('user_type') != 'restaurant':
        flash('Please login as a restaurant', 'error')
        return redirect(url_for('login'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Get restaurant's plates
    cursor.execute('''
        SELECT * FROM plates 
        WHERE restaurant_id = %s 
        ORDER BY created_at DESC
    ''', (session['user_id'],))
    plates = cursor.fetchall()
    cursor.close()
    
    return render_template('restaurant/dashboard.html', plates=plates)

@app.route('/restaurant/create-listing', methods=['GET', 'POST'])
def create_listing():
    if 'user_id' not in session or session.get('user_type') != 'restaurant':
        flash('Please login as a restaurant', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        description = request.form.get('description')
        price = request.form.get('price')
        quantity = request.form.get('quantity')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        
        try:
            db = get_db()
            cursor = db.cursor()
            
            cursor.execute('''
                INSERT INTO plates 
                (restaurant_id, description, price, quantity_available, quantity_original, start_time, end_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (session['user_id'], description, price, quantity, quantity, start_time, end_time))
            
            db.commit()
            cursor.close()
            
            flash('Listing created successfully!', 'success')
            return redirect(url_for('restaurant_dashboard'))
            
        except mysql.connector.Error as err:
            flash(f'Error creating listing: {err}', 'error')
            return redirect(url_for('create_listing'))
    
    return render_template('restaurant/create_listing.html')

# Placeholder routes for other user types (your teammates will implement these)
@app.route('/customer/dashboard')
def customer_dashboard():
    if 'user_id' not in session or session.get('user_type') not in ['customer', 'donner', 'needy']:
        flash('Please login first', 'error')
        return redirect(url_for('login'))
    return render_template('customer/dashboard.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('user_type') != 'admin':
        flash('Please login as admin', 'error')
        return redirect(url_for('login'))
    return render_template('admin/dashboard.html')

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)