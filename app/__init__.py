from flask import Flask
from config import Config
from models.database import close_db, init_db

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(Config)
    
    # Register database teardown
    app.teardown_appcontext(close_db)
    
    # Register blueprints
    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.restaurant import bp as restaurant_bp
    from app.blueprints.customer import bp as customer_bp
    from app.blueprints.admin import bp as admin_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(restaurant_bp, url_prefix='/restaurant')
    app.register_blueprint(customer_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    return app