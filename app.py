import os
import sys

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask import Flask, render_template, session
from config import Config
from database import init_db, seed_demo_data

def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, 'templates'),
        static_folder=os.path.join(BASE_DIR, 'static')
    )
    app.config.from_object(config_class)

    # Initialize Database & Seed demo data safely
    with app.app_context():
        try:
            init_db()
            seed_demo_data()
        except Exception as e:
            print(f"Notice during DB init/seed: {e}")

    # Register Blueprints
    from routes.auth import auth_bp
    from routes.user import user_bp
    from routes.medicine import medicine_bp
    from routes.pharmacy import pharmacy_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(medicine_bp)
    app.register_blueprint(pharmacy_bp)
    app.register_blueprint(admin_bp)

    # Context Processors for global template variables
    @app.context_processor
    def inject_global_vars():
        return {
            'app_name': 'Medicine Availability Finder',
            'medical_disclaimer': 'Medical Disclaimer: This website provides medicine availability and pharmacy information for informational purposes only. It does not provide medical advice, diagnosis, or treatment recommendations. Please consult a qualified healthcare professional before using any medicine.',
            'current_user_role': session.get('role'),
            'current_user_name': session.get('user_name'),
            'current_user_id': session.get('user_id'),
            'current_user_city': session.get('user_city'),
            'current_user_area': session.get('user_area'),
            'current_user_lat': session.get('user_lat'),
            'current_user_lng': session.get('user_lng')
        }

    # Custom Jinja Filters
    @app.template_filter('currency')
    def currency_filter(val):
        try:
            return f"₹{float(val):,.2f}"
        except Exception:
            return f"₹{val}"

    @app.template_filter('stock_badge')
    def stock_badge_filter(qty):
        try:
            q = int(qty)
            if q > 10:
                return '<span class="badge bg-success"><i class="bi bi-check-circle-fill me-1"></i>Available</span>'
            elif q >= 1:
                return '<span class="badge bg-warning text-dark"><i class="bi bi-exclamation-triangle-fill me-1"></i>Low Stock</span>'
            else:
                return '<span class="badge bg-danger"><i class="bi bi-x-circle-fill me-1"></i>Out of Stock</span>'
        except Exception:
            return '<span class="badge bg-secondary">Unknown</span>'

    # Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('base.html', error_title='404 - Page Not Found', error_message='The requested page could not be found.'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('base.html', error_title='500 - Server Error', error_message='An unexpected error occurred. Please try again later.'), 500

    return app

app = create_app()

if __name__ == '__main__':
    print("Starting Medicine Availability Finder on http://127.0.0.1:5000 ...")
    app.run(host='127.0.0.1', port=5000, debug=True)
