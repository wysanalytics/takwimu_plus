from flask import Flask, send_from_directory, render_template, request, jsonify, session, redirect, url_for
from flask_login import LoginManager, login_required, current_user
from config import Config
from models import db, User, UserSettings
from utils.translations import t
import os

login_manager = LoginManager()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Language support - inject into all templates
    @app.context_processor
    def inject_translations():
        lang = session.get('lang', 'en')
        return {
            't': lambda key: t(key, lang),
            'lang': lang
        }

    @app.route('/set-language/<lang>')
    def set_language(lang):
        if lang in ['en', 'sw']:
            session['lang'] = lang
        return redirect(request.referrer or url_for('main.dashboard'))

    # Serve PWA files
    @app.route('/manifest.json')
    def manifest():
        return send_from_directory('static', 'manifest.json')

    @app.route('/sw.js')
    def service_worker():
        return send_from_directory('static', 'sw.js')

    @app.route('/settings')
    @login_required
    def settings_page():
        return render_template('settings.html')

    @app.route('/api/settings', methods=['GET', 'POST'])
    @login_required
    def api_settings():
        if request.method == 'GET':
            settings = UserSettings.query.filter_by(user_id=current_user.id).first()
            if not settings:
                settings = UserSettings(user_id=current_user.id)
                db.session.add(settings)
                db.session.commit()

            return jsonify({
                'vatRate': settings.vat_rate,
                'presumptiveTaxRate': settings.presumptive_tax_rate,
                'lowStockAlertEnabled': settings.low_stock_alert_enabled,
                'lowStockThreshold': settings.low_stock_threshold,
                'smsRemindersEnabled': settings.sms_reminders_enabled,
                'smsPhoneNumber': settings.sms_phone_number
            })

        data = request.get_json()
        settings = UserSettings.query.filter_by(user_id=current_user.id).first()

        if not settings:
            settings = UserSettings(user_id=current_user.id)
            db.session.add(settings)

        settings.vat_rate = data.get('vatRate', 18.0)
        settings.presumptive_tax_rate = data.get('presumptiveTaxRate', 3.0)
        settings.low_stock_alert_enabled = data.get('lowStockAlertEnabled', True)
        settings.low_stock_threshold = data.get('lowStockThreshold', 10)
        settings.sms_reminders_enabled = data.get('smsRemindersEnabled', False)
        settings.sms_phone_number = data.get('smsPhoneNumber')

        db.session.commit()
        return jsonify({'success': True})

    # Register blueprints
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.api import api_bp
    from routes.admin import admin_bp
    from routes.messages import messages_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(messages_bp)

    with app.app_context():
        db.create_all()

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)