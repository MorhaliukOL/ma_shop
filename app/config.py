from pathlib import Path
from environs import Env

basedir = Path(Path(__file__).parent).resolve()
env = Env()
env.read_env()


class Config(object):

    SQLALCHEMY_DATABASE_URI = env.str("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = env.str("SECRET_KEY")
    SITE_URL = "localhost:5000"
    SECURITY_PASSWORD_SALT = env.str("SECURITY_PASSWORD_SALT")
    UPLOAD_FOLDER = 'static/img'
    THUMBNAIL_SIZE = (120, 70)
    PRODUCT_NAME_MAX_LENGTH = 1000
    SMTP_SERVER = "localhost"
    ADMIN_EMAIL = "admin@ma_shop.org"
    LOG_TO_STDOUT = env.str('LOG_TO_STDOUT')


"""App config variables"""
STATUS_ORDER = [('New order', 'New order'), ('Completed', 'Completed'), ('Canceled', 'Canceled')]

NAME_MAX_LENGTH = 50
PASSWORD_MAX_LENGTH = 50
CATEGORY_MAX_LENGTH = 50

PRODUCT_MAX_LENGTH = 50

ITEMS_PER_PAGE = 10
