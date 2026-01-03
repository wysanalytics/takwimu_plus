from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, Product, Sale, Expense, Payment, UserSettings
from datetime import datetime, timedelta
from sqlalchemy import func
import requests
import re
from time import time

api_bp = Blueprint('api', __name__)

# Rate limiting storage for barcode lookups
barcode_rate_limits = {}


# Products API
@api_bp.route('/products', methods=['GET'])
@login_required
def get_products():
    products = Product.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'model_number': p.model_number,
        'barcode': p.barcode,
        'buying_price': p.buying_price,
        'selling_price': p.selling_price,
        'stock': p.stock,
        'category': p.category
    } for p in products])


@api_bp.route('/products', methods=['POST'])
@login_required
def add_product():
    data = request.json
    product = Product(
        user_id=current_user.id,
        name=data['name'],
        model_number=data.get('model_number', ''),
        barcode=data.get('barcode', ''),
        buying_price=float(data['buying_price']),
        selling_price=float(data['selling_price']),
        stock=int(data.get('stock', 0)),
        category=data.get('category', '')
    )
    db.session.add(product)
    db.session.commit()
    return jsonify({'success': True, 'id': product.id})


@api_bp.route('/products/<int:id>', methods=['PUT'])
@login_required
def update_product(id):
    product = Product.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    data = request.json
    product.name = data.get('name', product.name)
    product.model_number = data.get('model_number', product.model_number)
    product.barcode = data.get('barcode', product.barcode)
    product.buying_price = float(data.get('buying_price', product.buying_price))
    product.selling_price = float(data.get('selling_price', product.selling_price))
    product.stock = int(data.get('stock', product.stock))
    product.category = data.get('category', product.category)
    db.session.commit()
    return jsonify({'success': True})


@api_bp.route('/products/<int:id>', methods=['DELETE'])
@login_required
def delete_product(id):
    product = Product.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(product)
    db.session.commit()
    return jsonify({'success': True})


# Barcode Lookup API
@api_bp.route('/barcode/lookup/<barcode>')
@login_required
def barcode_lookup(barcode):
    # Rate limiting: max 30 requests per minute per user
    user_id = str(current_user.id)
    now = time()

    if user_id in barcode_rate_limits:
        rate_data = barcode_rate_limits[user_id]
        if now > rate_data['reset_time']:
            rate_data = {'count': 0, 'reset_time': now + 60}
        rate_data['count'] += 1
        barcode_rate_limits[user_id] = rate_data
    else:
        barcode_rate_limits[user_id] = {'count': 1, 'reset_time': now + 60}

    if barcode_rate_limits[user_id]['count'] > 30:
        return jsonify({'error': 'Too many requests. Please wait a minute.'}), 429

    # Validate barcode format (digits only, 8-14 characters)
    if not re.match(r'^\d{8,14}$', barcode):
        return jsonify({'error': 'Invalid barcode format'}), 400

    try:
        # Try Open Food Facts first (free, no API key needed)
        off_response = requests.get(
            f'https://world.openfoodfacts.org/api/v0/product/{barcode}.json',
            timeout=10
        )
        off_data = off_response.json()

        if off_data.get('status') == 1 and off_data.get('product'):
            product = off_data['product']
            categories = product.get('categories_tags', [])
            category = categories[0].replace('en:', '') if categories else 'general'
            return jsonify({
                'name': product.get('product_name') or product.get('product_name_en') or 'Unknown Product',
                'category': category,
                'brand': product.get('brands'),
                'imageUrl': product.get('image_url')
            })

        # Try UPC Database as fallback
        upc_response = requests.get(
            f'https://api.upcitemdb.com/prod/trial/lookup?upc={barcode}',
            timeout=10
        )
        upc_data = upc_response.json()

        if upc_data.get('items') and len(upc_data['items']) > 0:
            item = upc_data['items'][0]
            images = item.get('images', [])
            return jsonify({
                'name': item.get('title') or 'Unknown Product',
                'category': item.get('category') or 'general',
                'brand': item.get('brand'),
                'imageUrl': images[0] if images else None
            })

        # Product not found
        return jsonify({
            'error': 'Product not found',
            'barcode': barcode,
            'message': 'Product not in database. Enter details manually.'
        }), 404

    except requests.Timeout:
        return jsonify({'error': 'Request timeout. Try again.'}), 504
    except Exception as e:
        print(f"Barcode lookup error: {e}")
        return jsonify({'error': 'Failed to lookup barcode'}), 500


# Sales API
@api_bp.route('/sales', methods=['POST'])
@login_required
def create_sale():
    data = request.json
    items = data['items']

    total_amount = sum(float(item['selling_price']) * int(item['quantity']) for item in items)
    total_cost = sum(float(item['buying_price']) * int(item['quantity']) for item in items)
    profit = total_amount - total_cost

    sale = Sale(
        user_id=current_user.id,
        total_amount=total_amount,
        total_cost=total_cost,
        profit=profit,
        payment_method=data.get('payment_method', 'cash'),
        items=items
    )
    db.session.add(sale)

    for item in items:
        product = Product.query.get(item['product_id'])
        if product and product.user_id == current_user.id:
            product.stock -= int(item['quantity'])

    db.session.commit()
    return jsonify({'success': True, 'id': sale.id, 'total': total_amount, 'profit': profit})


@api_bp.route('/sales', methods=['GET'])
@login_required
def get_sales():
    sales = Sale.query.filter_by(user_id=current_user.id).order_by(Sale.created_at.desc()).limit(50).all()
    return jsonify([{
        'id': s.id,
        'total_amount': s.total_amount,
        'profit': s.profit,
        'payment_method': s.payment_method,
        'items': s.items,
        'created_at': s.created_at.isoformat()
    } for s in sales])


# Expenses API
@api_bp.route('/expenses', methods=['GET'])
@login_required
def get_expenses():
    expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.created_at.desc()).all()
    return jsonify([{
        'id': e.id,
        'description': e.description,
        'amount': e.amount,
        'category': e.category,
        'created_at': e.created_at.isoformat()
    } for e in expenses])


@api_bp.route('/expenses', methods=['POST'])
@login_required
def add_expense():
    data = request.json
    expense = Expense(
        user_id=current_user.id,
        description=data['description'],
        amount=float(data['amount']),
        category=data['category']
    )
    db.session.add(expense)
    db.session.commit()
    return jsonify({'success': True, 'id': expense.id})


@api_bp.route('/expenses/<int:id>', methods=['DELETE'])
@login_required
def delete_expense(id):
    expense = Expense.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(expense)
    db.session.commit()
    return jsonify({'success': True})


# Settings API
@api_bp.route('/settings', methods=['GET'])
@login_required
def get_settings():
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        return jsonify({
            'vatRate': 18.0,
            'presumptiveTaxRate': 3.0,
            'lowStockAlertEnabled': True,
            'lowStockThreshold': 10,
            'smsRemindersEnabled': False,
            'smsPhoneNumber': ''
        })
    return jsonify({
        'vatRate': settings.vat_rate,
        'presumptiveTaxRate': settings.presumptive_tax_rate,
        'lowStockAlertEnabled': settings.low_stock_alert_enabled,
        'lowStockThreshold': settings.low_stock_threshold,
        'smsRemindersEnabled': settings.sms_reminders_enabled,
        'smsPhoneNumber': settings.sms_phone_number or ''
    })


@api_bp.route('/settings', methods=['POST'])
@login_required
def save_settings():
    data = request.json
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)

    settings.vat_rate = float(data.get('vatRate', 18.0))
    settings.presumptive_tax_rate = float(data.get('presumptiveTaxRate', 3.0))
    settings.low_stock_alert_enabled = data.get('lowStockAlertEnabled', True)
    settings.low_stock_threshold = int(data.get('lowStockThreshold', 10))
    settings.sms_reminders_enabled = data.get('smsRemindersEnabled', False)
    settings.sms_phone_number = data.get('smsPhoneNumber', '')

    db.session.commit()
    return jsonify({'success': True})


# Dashboard summary
@api_bp.route('/dashboard/summary')
@login_required
def dashboard_summary():
    today = datetime.utcnow().date()
    month_start = today.replace(day=1)

    today_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.user_id == current_user.id,
        func.date(Sale.created_at) == today
    ).scalar() or 0

    today_profit = db.session.query(func.sum(Sale.profit)).filter(
        Sale.user_id == current_user.id,
        func.date(Sale.created_at) == today
    ).scalar() or 0

    month_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.user_id == current_user.id,
        Sale.created_at >= month_start
    ).scalar() or 0

    month_profit = db.session.query(func.sum(Sale.profit)).filter(
        Sale.user_id == current_user.id,
        Sale.created_at >= month_start
    ).scalar() or 0

    monthly_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id,
        Expense.created_at >= month_start
    ).scalar() or 0

    return jsonify({
        'todaySales': float(today_sales),
        'todayProfit': float(today_profit),
        'monthSales': float(month_sales),
        'monthProfit': float(month_profit),
        'monthlyExpenses': float(monthly_expenses)
    })


# Payment submission
@api_bp.route('/payments', methods=['POST'])
@login_required
def submit_payment():
    data = request.json
    payment = Payment(
        user_id=current_user.id,
        amount=15000,
        transaction_ref=data['transaction_ref'],
        payer_phone=data.get('payer_phone')
    )
    db.session.add(payment)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Payment submitted for verification'})


# Reports API
@api_bp.route('/reports/weekly')
@login_required
def weekly_report():
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)

    daily_data = db.session.query(
        func.date(Sale.created_at).label('date'),
        func.sum(Sale.total_amount).label('sales'),
        func.sum(Sale.profit).label('profit')
    ).filter(
        Sale.user_id == current_user.id,
        Sale.created_at >= week_ago
    ).group_by(func.date(Sale.created_at)).all()

    return jsonify([{
        'date': str(d.date),
        'sales': float(d.sales or 0),
        'profit': float(d.profit or 0)
    } for d in daily_data])