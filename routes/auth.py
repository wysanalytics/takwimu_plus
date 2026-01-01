from flask import Blueprint, render_template, redirect, url_for, session, request, flash
from flask_login import login_user, logout_user, current_user
from models import db, User
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint('auth', __name__)

# Admin credentials
ADMIN_SECRET_KEY = "2001"
ADMIN_EMAIL = "wysanalytics@gmail.com"
ADMIN_PASSWORD = "ADMIN2001"


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Already logged in?
    if session.get('is_admin'):
        return redirect(url_for('admin.dashboard'))
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        secret_key = request.form.get('secret_key', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        # Check if admin login (secret key provided)
        if secret_key == ADMIN_SECRET_KEY:
            if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
                session['is_admin'] = True
                session['admin_email'] = email
                flash('Welcome, Admin!', 'success')
                return redirect(url_for('admin.dashboard'))
            else:
                flash('Invalid admin credentials', 'error')
                return render_template('login.html')

        # Regular user login (no secret key)
        if email and password:
            user = User.query.filter_by(email=email).first()
            if user and check_password_hash(user.password_hash, password):
                login_user(user)
                flash('Welcome back!', 'success')
                return redirect(url_for('main.dashboard'))
            else:
                flash('Invalid email or password', 'error')
        else:
            flash('Please enter email and password', 'error')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        business_name = request.form.get('business_name', '').strip()
        phone = request.form.get('phone', '').strip()

        if not email or not password:
            flash('Email and password are required', 'error')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('register.html')

        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            first_name=first_name,
            last_name=last_name,
            business_name=business_name,
            phone=phone,
            subscription_status='trial',
            subscription_end=datetime.utcnow() + timedelta(days=30),
            created_at=datetime.utcnow()
        )

        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash('Account created! You have 30 days free trial.', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('register.html')


@auth_bp.route('/logout')
def logout():
    logout_user()
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('auth.login'))