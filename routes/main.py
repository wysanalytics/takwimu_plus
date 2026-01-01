from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from models import db, Product, Sale, Expense, UserSettings, SaleItem
from datetime import datetime, timedelta
from sqlalchemy import func
from config import Config

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('landing.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    today = datetime.utcnow().date()

    today_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.user_id == current_user.id,
        func.date(Sale.created_at) == today
    ).scalar() or 0

    today_profit = db.session.query(func.sum(Sale.profit)).filter(
        Sale.user_id == current_user.id,
        func.date(Sale.created_at) == today
    ).scalar() or 0

    month_start = today.replace(day=1)
    monthly_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id,
        Expense.created_at >= month_start
    ).scalar() or 0

    monthly_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.user_id == current_user.id,
        Sale.created_at >= month_start
    ).scalar() or 0

    monthly_profit = db.session.query(func.sum(Sale.profit)).filter(
        Sale.user_id == current_user.id,
        Sale.created_at >= month_start
    ).scalar() or 0

    products_count = Product.query.filter_by(user_id=current_user.id).count()

    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    low_stock_threshold = settings.low_stock_threshold if settings else 5

    low_stock = Product.query.filter(
        Product.user_id == current_user.id,
        Product.stock <= low_stock_threshold
    ).all()

    vat_rate = settings.vat_rate if settings else 18.0
    estimated_vat = monthly_sales * (vat_rate / 100) if monthly_sales else 0

    return render_template('dashboard.html',
                           today_sales=today_sales,
                           today_profit=today_profit,
                           monthly_sales=monthly_sales,
                           monthly_profit=monthly_profit,
                           monthly_expenses=monthly_expenses,
                           products_count=products_count,
                           low_stock=low_stock,
                           estimated_vat=estimated_vat,
                           days_remaining=current_user.days_remaining(),
                           subscription_status=current_user.subscription_status
                           )


@main_bp.route('/pos')
@login_required
def pos():
    products = Product.query.filter_by(user_id=current_user.id).filter(Product.stock > 0).all()
    return render_template('pos.html', products=products)


@main_bp.route('/products')
@login_required
def products():
    products = Product.query.filter_by(user_id=current_user.id).order_by(Product.created_at.desc()).all()
    return render_template('products.html', products=products)


@main_bp.route('/expenses')
@login_required
def expenses():
    expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.created_at.desc()).all()
    categories = ['rent', 'transport', 'salaries', 'supplies', 'utilities', 'other']
    return render_template('expenses.html', expenses=expenses, categories=categories)


@main_bp.route('/reports')
@login_required
def reports():
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Weekly data
    weekly_sales = db.session.query(
        func.date(Sale.created_at).label('date'),
        func.sum(Sale.total_amount).label('sales'),
        func.sum(Sale.profit).label('profit'),
        func.count(Sale.id).label('count')
    ).filter(
        Sale.user_id == current_user.id,
        Sale.created_at >= week_ago
    ).group_by(func.date(Sale.created_at)).order_by(func.date(Sale.created_at)).all()

    weekly_data = [{'date': str(s.date), 'sales': float(s.sales or 0),
                    'profit': float(s.profit or 0), 'count': int(s.count or 0)}
                   for s in weekly_sales]

    # Monthly data
    monthly_sales = db.session.query(
        func.date(Sale.created_at).label('date'),
        func.sum(Sale.total_amount).label('sales'),
        func.sum(Sale.profit).label('profit'),
        func.count(Sale.id).label('count')
    ).filter(
        Sale.user_id == current_user.id,
        Sale.created_at >= month_ago
    ).group_by(func.date(Sale.created_at)).order_by(func.date(Sale.created_at)).all()

    monthly_data = [{'date': str(s.date), 'sales': float(s.sales or 0),
                     'profit': float(s.profit or 0), 'count': int(s.count or 0)}
                    for s in monthly_sales]

    # Expense breakdown by category
    expense_breakdown = db.session.query(
        Expense.category,
        func.sum(Expense.amount).label('amount')
    ).filter(
        Expense.user_id == current_user.id,
        Expense.created_at >= month_ago
    ).group_by(Expense.category).all()

    expense_data = [{'category': e.category.title() if e.category else 'Other',
                     'amount': float(e.amount or 0)}
                    for e in expense_breakdown]

    # Top selling products (using JSON items field since SaleItem might not exist yet)
    top_products = []
    try:
        top_products_query = db.session.query(
            Product.name,
            func.sum(SaleItem.quantity).label('quantity')
        ).join(SaleItem, SaleItem.product_id == Product.id
        ).join(Sale, Sale.id == SaleItem.sale_id
        ).filter(
            Sale.user_id == current_user.id,
            Sale.created_at >= month_ago
        ).group_by(Product.id).order_by(func.sum(SaleItem.quantity).desc()).limit(5).all()

        top_products = [{'name': p.name, 'quantity': int(p.quantity or 0)}
                        for p in top_products_query]
    except:
        pass

    return render_template('reports.html',
                           weekly_data=weekly_data,
                           monthly_data=monthly_data,
                           expense_data=expense_data,
                           top_products=top_products)


@main_bp.route('/tax')
@login_required
def tax():
    return render_template('tax.html')


@main_bp.route('/settings')
@login_required
def settings():
    return render_template('settings.html')


@main_bp.route('/billing')
@login_required
def billing():
    from models import Payment
    payments = Payment.query.filter_by(user_id=current_user.id).order_by(Payment.created_at.desc()).all()
    return render_template('billing.html',
                           payments=payments,
                           monthly_price=Config.MONTHLY_PRICE,
                           airtel_number=Config.AIRTEL_NUMBER,
                           days_remaining=current_user.days_remaining(),
                           subscription_status=current_user.subscription_status,
                           subscription_end=current_user.subscription_end
                           )