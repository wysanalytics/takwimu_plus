from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from models import db, User, Payment, Sale, Message, ActivityLog
from datetime import datetime, timedelta
from sqlalchemy import func
from utils.sms import notify_user_sms

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def log_activity(action, details=None):
    log = ActivityLog(action=action, details=details, admin_action=True)
    db.session.add(log)
    db.session.commit()


@admin_bp.route('/logout')
def logout():
    session.pop('is_admin', None)
    session.pop('admin_email', None)
    return redirect(url_for('auth.login'))


@admin_bp.route('/')
def dashboard():
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

    today = datetime.utcnow().date()

    total_users = User.query.count()
    active_subscriptions = User.query.filter_by(subscription_status='active').count()
    trial_users = User.query.filter_by(subscription_status='trial').count()
    expired_users = total_users - active_subscriptions - trial_users
    pending_payments = Payment.query.filter_by(status='pending').count()

    today_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        func.date(Sale.created_at) == today
    ).scalar() or 0

    today_profit = db.session.query(func.sum(Sale.profit)).filter(
        func.date(Sale.created_at) == today
    ).scalar() or 0

    total_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.status == 'verified'
    ).scalar() or 0

    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    unread_messages = Message.query.filter_by(sender='user', is_read=False).count()

    return render_template('admin/dashboard.html',
                           total_users=total_users,
                           active_subscriptions=active_subscriptions,
                           trial_users=trial_users,
                           expired_users=expired_users,
                           pending_payments=pending_payments,
                           today_sales=today_sales,
                           today_profit=today_profit,
                           total_revenue=total_revenue,
                           recent_users=recent_users,
                           unread_messages=unread_messages,
                           now=datetime.utcnow())


@admin_bp.route('/api/users')
def api_users():
    if not session.get('is_admin'):
        return jsonify([])
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([{
        'id': u.id,
        'email': u.email,
        'business_name': u.business_name,
        'phone': u.phone,
        'subscription_status': u.subscription_status,
        'days_remaining': u.days_remaining(),
        'created_at': u.created_at.isoformat() if u.created_at else None
    } for u in users])


@admin_bp.route('/api/users/<int:id>/activate', methods=['POST'])
def activate_user(id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    user = User.query.get_or_404(id)
    user.subscription_status = 'active'
    user.subscription_end = datetime.utcnow() + timedelta(days=30)
    db.session.commit()
    log_activity('User Activated', f'Activated {user.email}')
    return jsonify({'success': True})


@admin_bp.route('/api/users/<int:id>/suspend', methods=['POST'])
def suspend_user(id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    user = User.query.get_or_404(id)
    user.subscription_status = 'suspended'
    db.session.commit()
    log_activity('User Suspended', f'Suspended {user.email}')
    return jsonify({'success': True})


@admin_bp.route('/api/payments')
def api_payments():
    if not session.get('is_admin'):
        return jsonify([])
    payments = Payment.query.order_by(Payment.created_at.desc()).all()
    return jsonify([{
        'id': p.id,
        'user_email': p.user.email if p.user else 'Unknown',
        'user_business': p.user.business_name if p.user else 'Unknown',
        'transaction_ref': p.transaction_ref,
        'payer_phone': p.payer_phone,
        'amount': p.amount,
        'status': p.status,
        'created_at': p.created_at.isoformat() if p.created_at else None
    } for p in payments])


@admin_bp.route('/api/payments/<int:id>/verify', methods=['POST'])
def verify_payment(id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    payment = Payment.query.get_or_404(id)
    payment.status = 'verified'
    payment.verified_at = datetime.utcnow()
    payment.user.subscription_status = 'active'
    payment.user.subscription_end = datetime.utcnow() + timedelta(days=30)
    db.session.commit()
    log_activity('Payment Verified', f'Verified {payment.transaction_ref}')

    # Send SMS notification
    if payment.user and payment.user.phone:
        notify_user_sms(payment.user, "Payment Confirmed",
                        "Your payment has been verified. Subscription active for 30 days.")

    return jsonify({'success': True})


@admin_bp.route('/api/payments/<int:id>/reject', methods=['POST'])
def reject_payment(id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    payment = Payment.query.get_or_404(id)
    payment.status = 'rejected'
    db.session.commit()
    log_activity('Payment Rejected', f'Rejected {payment.transaction_ref}')
    return jsonify({'success': True})


@admin_bp.route('/api/messages')
def api_messages():
    if not session.get('is_admin'):
        return jsonify([])
    messages = Message.query.filter_by(sender='user').order_by(Message.created_at.desc()).all()
    return jsonify([{
        'id': m.id,
        'user_id': m.user_id,
        'user_email': m.user.email if m.user else 'Unknown',
        'user_business': m.user.business_name if m.user else 'Unknown',
        'user_phone': m.user.phone if m.user else None,
        'subject': m.subject,
        'content': m.content,
        'is_read': m.is_read,
        'created_at': m.created_at.isoformat() if m.created_at else None
    } for m in messages])


@admin_bp.route('/api/messages/<int:id>/read', methods=['POST'])
def mark_read(id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    msg = Message.query.get_or_404(id)
    msg.is_read = True
    db.session.commit()
    return jsonify({'success': True})


@admin_bp.route('/api/messages/send', methods=['POST'])
def send_message():
    """Send message to specific user with SMS notification"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    user = User.query.get(data['user_id'])

    if not user:
        return jsonify({'error': 'User not found'}), 404

    msg = Message(
        user_id=data['user_id'],
        sender='admin',
        subject=data.get('subject', 'Message from Admin'),
        content=data['content']
    )
    db.session.add(msg)
    db.session.commit()

    # Send SMS notification
    if user.phone:
        notify_user_sms(user, data.get('subject', 'New Message'), data['content'])

    log_activity('Message Sent', f'To: {user.email}')
    return jsonify({'success': True})


@admin_bp.route('/api/messages/reply', methods=['POST'])
def reply_message():
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    user = User.query.get(data['user_id'])

    msg = Message(
        user_id=data['user_id'],
        sender='admin',
        subject=data.get('subject', 'Reply from Admin'),
        content=data['content']
    )
    db.session.add(msg)
    db.session.commit()

    # Send SMS notification
    if user and user.phone:
        notify_user_sms(user, data.get('subject', 'Reply from Support'), data['content'])

    return jsonify({'success': True})


@admin_bp.route('/api/announcements', methods=['GET', 'POST'])
def announcements():
    if not session.get('is_admin'):
        return jsonify([])

    if request.method == 'POST':
        data = request.json
        msg = Message(
            sender='admin',
            subject=data['subject'],
            content=data['content'],
            is_announcement=True
        )
        db.session.add(msg)
        db.session.commit()
        log_activity('Announcement Sent', data['subject'])

        # Send SMS to all users with phones
        if data.get('send_sms'):
            users = User.query.filter(User.phone.isnot(None)).all()
            for user in users:
                notify_user_sms(user, data['subject'], data['content'])

        return jsonify({'success': True})

    msgs = Message.query.filter_by(is_announcement=True).order_by(Message.created_at.desc()).all()
    return jsonify([{
        'id': m.id,
        'subject': m.subject,
        'content': m.content,
        'created_at': m.created_at.isoformat() if m.created_at else None
    } for m in msgs])


@admin_bp.route('/api/activity')
def api_activity():
    if not session.get('is_admin'):
        return jsonify([])
    logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(50).all()
    return jsonify([{
        'id': l.id,
        'action': l.action,
        'details': l.details,
        'created_at': l.created_at.isoformat() if l.created_at else None
    } for l in logs])


@admin_bp.route('/api/export/users')
def export_users():
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    users = User.query.all()
    csv = "Business,Email,Phone,Status,Days Remaining,Joined\n"
    for u in users:
        csv += f"{u.business_name or 'N/A'},{u.email},{u.phone or 'N/A'},{u.subscription_status},{u.days_remaining()},{u.created_at.strftime('%Y-%m-%d') if u.created_at else 'N/A'}\n"
    return csv, 200, {'Content-Type': 'text/csv', 'Content-Disposition': 'attachment; filename=users.csv'}


@admin_bp.route('/api/export/payments')
def export_payments():
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    payments = Payment.query.all()
    csv = "Date,Business,Email,Reference,Phone,Amount,Status\n"
    for p in payments:
        csv += f"{p.created_at.strftime('%Y-%m-%d') if p.created_at else 'N/A'},{p.user.business_name if p.user else 'N/A'},{p.user.email if p.user else 'N/A'},{p.transaction_ref},{p.payer_phone or 'N/A'},{p.amount},{p.status}\n"
    return csv, 200, {'Content-Type': 'text/csv', 'Content-Disposition': 'attachment; filename=payments.csv'}