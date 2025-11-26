import os
from flask import Flask
from .db import get_db
from .blueprints.market import bp as market_bp
from .blueprints.actions import bp as actions_bp
from .blueprints.needy import bp as needy_bp

def create_app():
    base_dir = os.path.dirname(os.path.abspath(__file__))   # ...\user-flow\app
    templates_dir = os.path.join(base_dir, '..', 'templates')  # ...\user-flow\templates

    app = Flask(__name__, template_folder=templates_dir)
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", "dev-change-me")

    app.register_blueprint(market_bp)
    app.register_blueprint(actions_bp, url_prefix="/actions")
    app.register_blueprint(needy_bp)

    return app
