from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models.database import get_db
import mysql.connector

bp = Blueprint('restaurant', __name__)

@bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('user_type') != 'restaurant':
        flash('Please login as a restaurant', 'error')
        return redirect(url_for('auth.login'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    cursor.execute('''
        SELECT * FROM plates 
        WHERE restaurant_id = %s 
        ORDER BY created_at DESC
    ''', (session['user_id'],))
    plates = cursor.fetchall()
    cursor.close()
    
    return render_template('restaurant/dashboard.html', plates=plates)

@bp.route('/create-listing', methods=['GET', 'POST'])
def create_listing():
    if 'user_id' not in session or session.get('user_type') != 'restaurant':
        flash('Please login as a restaurant', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        title = request.form.get('title')
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
                (restaurant_id, title, description, price, quantity_available, quantity_original, start_time, end_time, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)
            ''', (session['user_id'], title, description, price, quantity, quantity, start_time, end_time))
            
            db.commit()
            cursor.close()
            
            flash('Listing created successfully!', 'success')
            return redirect(url_for('restaurant.dashboard'))
            
        except mysql.connector.Error as err:
            flash(f'Error creating listing: {err}', 'error')
            return redirect(url_for('restaurant.create_listing'))
    
    return render_template('restaurant/create_listing.html')