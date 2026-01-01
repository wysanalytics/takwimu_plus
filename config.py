import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or '2001'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'mysql+pymysql://root:password@localhost/takwimu_plus'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Admin credentials
    ADMIN_USERNAME = 'ADMIN'
    ADMIN_SECRET_KEY = '2001'
    ADMIN_PASSWORD = 'ADMIN2001'

    # Subscription settings
    TRIAL_DAYS = 30
    MONTHLY_PRICE = 15000  # TZS
    AIRTEL_NUMBER = '+255785614335'