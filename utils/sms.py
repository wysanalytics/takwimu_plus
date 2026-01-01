import requests

# Africa's Talking or similar SMS API
SMS_API_KEY = None  # Set in config
SMS_SENDER_ID = "TAKWIMU"


def send_sms(phone, message):
    """Send SMS notification to user's phone"""
    if not SMS_API_KEY:
        print(f"[SMS Mock] To: {phone}, Message: {message}")
        return True

    # Using Africa's Talking API (popular in Tanzania)
    try:
        response = requests.post(
            'https://api.africastalking.com/version1/messaging',
            headers={
                'apiKey': SMS_API_KEY,
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            data={
                'username': 'sandbox',  # Change for production
                'to': phone,
                'message': message,
                'from': SMS_SENDER_ID
            }
        )
        return response.status_code == 201
    except Exception as e:
        print(f"SMS Error: {e}")
        return False


def notify_user_sms(user, subject, content):
    """Send notification SMS to user"""
    if user.phone:
        message = f"TAKWIMU+: {subject}\n{content[:100]}"
        return send_sms(user.phone, message)
    return False