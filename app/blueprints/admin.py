from flask import Blueprint, render_template, session, flash, redirect, url_for
from models.database import get_db

bp = Blueprint('admin', __name__)

@bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('user_type') != 'admin':
        flash('Please login as admin', 'error')
        return redirect(url_for('auth.login'))
    
    return render_template('admin/dashboard.html')