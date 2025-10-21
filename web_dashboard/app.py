"""
Flask application for WhaleBots web dashboard.
"""

import os
from flask import Flask, render_template
from datetime import timedelta

from shared.data_manager import DataManager
from discord_bot.services.bot_service import BotService
from discord_bot.services.subscription_service import SubscriptionService


def create_app(whalebots_path: str = None) -> Flask:
    """
    Create and configure Flask application.
    
    Args:
        whalebots_path: Path to WhaleBots installation
        
    Returns:
        Configured Flask application
    """
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JSON_SORT_KEYS'] = False
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    
    # Initialize services
    if whalebots_path is None:
        whalebots_path = os.getenv("WHALEBOTS_PATH", os.getcwd())
    
    app.data_manager = DataManager()
    app.bot_service = BotService(whalebots_path, app.data_manager)
    app.subscription_service = SubscriptionService(app.data_manager)
    
    # Register blueprints
    from web_dashboard.routes.overview import overview_bp
    from web_dashboard.routes.users import users_bp
    from web_dashboard.routes.instances import instances_bp
    from web_dashboard.routes.config import config_bp
    from web_dashboard.routes.logs import logs_bp
    from web_dashboard.routes.emulator_health import emulator_health_bp

    app.register_blueprint(overview_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(instances_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(emulator_health_bp)
    
    # Main routes
    @app.route('/')
    def index():
        """Main dashboard page."""
        return render_template('overview.html')
    
    @app.route('/users')
    def users_page():
        """Users management page."""
        return render_template('users.html')
    
    @app.route('/instances')
    def instances_page():
        """Running instances page."""
        return render_template('instances.html')
    
    @app.route('/config')
    def config_page():
        """Configuration page."""
        return render_template('config.html')
    
    @app.route('/logs')
    def logs_page():
        """Audit logs page."""
        return render_template('logs.html')

    @app.route('/emulator-health')
    def emulator_health_page():
        """Emulator health monitoring page."""
        return render_template('emulator_health.html')

    return app

