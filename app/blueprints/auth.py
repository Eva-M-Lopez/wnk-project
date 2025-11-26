from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from models.database import get_db
import mysql.connector

bp = Blueprint('auth', __name__)

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        user_type = request.form.get('user_type')
        name = request.form.get('name')
        address = request.form.get('address')
        phone = request.form.get('phone')
        
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('auth.register'))
        
        password_hash = generate_password_hash(password)
        
        try:
            db = get_db()
            cursor = db.cursor()
            
            cursor.execute('''
                INSERT INTO users (email, password_hash, user_type, name, address, phone)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (email, password_hash, user_type, name, address, phone))
            
            user_id = cursor.lastrowid
            
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
            return redirect(url_for('auth.login'))
            
        except mysql.connector.Error as err:
            flash(f'Registration failed: {err}', 'error')
            return redirect(url_for('auth.register'))
    
    return render_template('register.html')

@bp.route('/login', methods=['GET', 'POST'])
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
            
            if user['user_type'] == 'restaurant':
                return redirect(url_for('restaurant.dashboard'))
            elif user['user_type'] == 'admin':
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('customer.marketplace'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.index'))

@bp.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('auth.login'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        phone = request.form.get('phone')
        
        cursor.execute('''
            UPDATE users 
            SET name = %s, address = %s, phone = %s
            WHERE user_id = %s
        ''', (name, address, phone, session['user_id']))
        
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
        return redirect(url_for('auth.profile'))
    
    cursor.execute('SELECT * FROM users WHERE user_id = %s', (session['user_id'],))
    user = cursor.fetchone()
    
    payment_info = None
    if session['user_type'] in ['customer', 'donner']:
        cursor.execute('SELECT * FROM payment_info WHERE user_id = %s', (session['user_id'],))
        payment_info = cursor.fetchone()
    
    cursor.close()
    
    return render_template('profile.html', user=user, payment_info=payment_info)