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
        user_type = request.form.get('user_type')
        name = request.form.get('name')
        address = request.form.get('address')
        phone = request.form.get('phone')
        
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

@app.route('/restaurant/dashboard')
def restaurant_dashboard():
    if 'user_id' not in session or session.get('user_type') != 'restaurant':
        flash('Please login as a restaurant', 'error')
        return redirect(url_for('login'))
    
    return render_template('restaurant/dashboard.html')

# Placeholder routes for other dashboards
@app.route('/customer/dashboard')
def customer_dashboard():
    return "Customer Dashboard (handled by teammate)"

@app.route('/admin/dashboard')
def admin_dashboard():
    return "Admin Dashboard (handled by teammate)"

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)