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
            title VARCHAR(255),
            description TEXT NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            quantity_available INT NOT NULL,
            quantity_original INT NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            status ENUM('active', 'sold_out', 'expired') DEFAULT 'active',
            is_active TINYINT DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (restaurant_id) REFERENCES users(user_id)
        )
    ''')
    
    # Create reservations table with updated status
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            reservation_id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NULL,
            donor_id INT NULL,
            plate_id INT NOT NULL,
            qty INT NOT NULL,
            status ENUM('HELD', 'CONFIRMED', 'CANCELLED', 'PICKED_UP', 'DONATED', 'CLAIMED') DEFAULT 'HELD',
            pickup_code VARCHAR(8),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confirmed_at TIMESTAMP NULL,
            claimed_at TIMESTAMP NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (donor_id) REFERENCES users(user_id),
            FOREIGN KEY (plate_id) REFERENCES plates(plate_id)
        )
    ''')
    
    # Create transactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INT PRIMARY KEY AUTO_INCREMENT,
            payer_user_id INT NOT NULL,
            payee_restaurant_id INT NOT NULL,
            amount DECIMAL(10, 2) NOT NULL,
            type ENUM('CUSTOMER_PURCHASE', 'DONATION_PURCHASE') NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (payer_user_id) REFERENCES users(user_id),
            FOREIGN KEY (payee_restaurant_id) REFERENCES users(user_id)
        )
    ''')
    
    db.commit()
    cursor.close()
    print("Database initialized successfully!")