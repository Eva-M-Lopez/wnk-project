import mysql.connector
from flask import current_app, g

def get_db():
    """Create database connection"""
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host=current_app.config['MYSQL_HOST'],
            user=current_app.config['MYSQL_USER'],
            password=current_app.config['MYSQL_PASSWORD'],
            database=current_app.config['MYSQL_DB'],
            port=current_app.config['MYSQL_PORT']
        )
    return g.db

def close_db(e=None):
    """Close database connection"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize database with schema"""
    db = get_db()
    cursor = db.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INT PRIMARY KEY AUTO_INCREMENT,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            user_type ENUM('admin', 'restaurant', 'customer', 'donner', 'needy') NOT NULL,
            name VARCHAR(255) NOT NULL,
            address TEXT NOT NULL,
            phone VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create payment_info table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_info (
            payment_id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            card_number VARCHAR(16),
            card_holder VARCHAR(255),
            expiry_date VARCHAR(7),
            cvv VARCHAR(4),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Create plates table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plates (
            plate_id INT PRIMARY KEY AUTO_INCREMENT,
            restaurant_id INT NOT NULL,
            description TEXT NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            quantity_available INT NOT NULL,
            quantity_original INT NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            status ENUM('active', 'sold_out', 'expired') DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (restaurant_id) REFERENCES users(user_id)
        )
    ''')
    
    db.commit()
    cursor.close()