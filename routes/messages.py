from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, Message
from datetime import datetime

messages_bp = Blueprint('messages', __name__)


@messages_bp.route('/notifications')
@login_required
def notifications():
    """User sees admin messages and announcements"""
    # Get direct messages to this user
    user_messages = Message.query.filter_by(
        user_id=current_user.id,
        sender='admin'
    ).order_by(Message.created_at.desc()).all()

    # Get announcements (for all users)
    announcements = Message.query.filter_by(
        is_announcement=True
    ).order_by(Message.created_at.desc()).all()

    return render_template('notifications.html',
                           messages=user_messages,
                           announcements=announcements)


@messages_bp.route('/notifications/<int:id>/read', methods=['POST'])
@login_required
def mark_read(id):
    msg = Message.query.get_or_404(id)
    if msg.user_id == current_user.id:
        msg.is_read = True
        db.session.commit()
    return jsonify({'success': True})


@messages_bp.route('/support', methods=['GET', 'POST'])
@login_required
def support():
    """User submits support request or complaint"""
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        content = request.form.get('content', '').strip()
        category = request.form.get('category', 'general')

        if not subject or not content:
            flash('Please fill in all fields', 'error')
            return render_template('support.html')

        msg = Message(
            user_id=current_user.id,
            sender='user',
            subject=f"[{category.upper()}] {subject}",
            content=content,
            is_read=False
        )
        db.session.add(msg)
        db.session.commit()

        flash('Your message has been sent to support!', 'success')
        return redirect(url_for('messages.support'))

    # Show user's sent messages
    sent_messages = Message.query.filter_by(
        user_id=current_user.id,
        sender='user'
    ).order_by(Message.created_at.desc()).all()

    return render_template('support.html', sent_messages=sent_messages)


@messages_bp.route('/api/unread-count')
@login_required
def unread_count():
    """Get unread notification count for navbar badge"""
    count = Message.query.filter_by(
        user_id=current_user.id,
        sender='admin',
        is_read=False
    ).count()

    # Also count unread announcements
    announcements = Message.query.filter_by(is_announcement=True).count()

    return jsonify({'count': count, 'announcements': announcements})